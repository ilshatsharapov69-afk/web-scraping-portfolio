"""Business Lead Generation Tool

Scrape business directories to build lead lists with contact details,
quality scoring, and SQLite storage. Features deduplication, pagination,
data enrichment, and export with filtering.

Usage:
    python scraper.py --query "plumbers" --location "London" --output leads.csv
    python scraper.py --query "restaurants" --location "Manchester" --max-pages 10
    python scraper.py --export --min-score 0.7 --output qualified_leads.csv
    python scraper.py --query "electricians" --location "Birmingham" --format json

Dependencies:
    pip install requests beautifulsoup4
"""

import argparse
import csv
import hashlib
import json
import logging
import random
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]
DEFAULT_DB = Path("leads.db")

# Target directory base URL — replace with the actual business directory you want to scrape
BASE_URL = "https://www.yellowpages.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Business:
    """Represents a business lead with contact details and quality score."""
    name: str = ""
    address: str = ""
    city: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    category: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    description: str = ""
    lead_score: float = 0.0
    content_hash: str = ""
    source_url: str = ""
    scraped_at: str = ""


# ---------------------------------------------------------------------------
# Database layer (SQLite)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    category TEXT,
    rating REAL DEFAULT 0.0,
    reviews_count INTEGER DEFAULT 0,
    description TEXT,
    lead_score REAL DEFAULT 0.0,
    content_hash TEXT UNIQUE,
    source_url TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    scraped_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category);
CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(lead_score);
CREATE INDEX IF NOT EXISTS idx_leads_hash ON leads(content_hash);
"""


@contextmanager
def get_connection(db_path: Path = DEFAULT_DB):
    """Yield a SQLite connection with WAL mode enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DEFAULT_DB):
    """Create database tables and indexes."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info(f"Database initialized: {db_path}")


def upsert_lead(conn: sqlite3.Connection, biz: Business):
    """Insert or update a lead using content hash for deduplication.

    On conflict, updates last_seen_at and merges new data with existing
    using COALESCE to preserve non-null values.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO leads (
            name, address, city, phone, email, website, category,
            rating, reviews_count, description, lead_score,
            content_hash, source_url, first_seen_at, last_seen_at, scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(content_hash) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            scraped_at = excluded.scraped_at,
            phone = COALESCE(NULLIF(excluded.phone, ''), leads.phone),
            email = COALESCE(NULLIF(excluded.email, ''), leads.email),
            website = COALESCE(NULLIF(excluded.website, ''), leads.website),
            rating = CASE WHEN excluded.rating > 0 THEN excluded.rating ELSE leads.rating END,
            reviews_count = CASE WHEN excluded.reviews_count > 0 THEN excluded.reviews_count ELSE leads.reviews_count END,
            lead_score = excluded.lead_score
    """, (
        biz.name, biz.address, biz.city, biz.phone, biz.email,
        biz.website, biz.category, biz.rating, biz.reviews_count,
        biz.description, biz.lead_score, biz.content_hash,
        biz.source_url, now, now, now,
    ))


def fetch_leads(conn: sqlite3.Connection, min_score: float = 0.0,
                category: str = "", city: str = "") -> list[dict]:
    """Query leads from database with optional filters."""
    query = "SELECT * FROM leads WHERE lead_score >= ?"
    params: list = [min_score]

    if category:
        query += " AND category = ?"
        params.append(category)
    if city:
        query += " AND city = ?"
        params.append(city)

    query += " ORDER BY lead_score DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_stats(conn: sqlite3.Connection) -> dict:
    """Get summary statistics from the leads database."""
    row = conn.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT city) as cities,
            COUNT(DISTINCT category) as categories,
            AVG(lead_score) as avg_score,
            SUM(CASE WHEN email != '' THEN 1 ELSE 0 END) as with_email,
            SUM(CASE WHEN phone != '' THEN 1 ELSE 0 END) as with_phone,
            SUM(CASE WHEN website != '' THEN 1 ELSE 0 END) as with_website
        FROM leads
    """).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_page(url: str, session: requests.Session) -> Optional[str]:
    """Fetch a page with retry and exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 429:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(f"Rate limited. Retrying in {delay}s...")
                time.sleep(delay)
                continue
            logger.error(f"HTTP {resp.status_code} for {url}")
            if resp.status_code >= 500:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                continue
            return None
        except requests.RequestException as e:
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            logger.error(f"Request error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
    return None


def human_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Sleep for a random human-like duration."""
    time.sleep(random.uniform(min_sec, max_sec))


# ---------------------------------------------------------------------------
# Content deduplication
# ---------------------------------------------------------------------------

def compute_hash(biz: Business) -> str:
    """Generate content hash for deduplication."""
    raw = f"{biz.name.lower().strip()}|{biz.city.lower().strip()}|{biz.phone}"
    return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Lead scoring
# ---------------------------------------------------------------------------

SCORE_WEIGHTS = {
    "has_phone": 0.20,
    "has_email": 0.20,
    "has_website": 0.15,
    "has_rating": 0.15,
    "has_description": 0.10,
    "has_address": 0.10,
    "review_volume": 0.10,
}


def score_lead(biz: Business) -> float:
    """Calculate a quality score (0.0–1.0) based on data completeness.

    Each field contributes a weighted score. Businesses with more complete
    contact information score higher, making them better leads.
    """
    score = 0.0
    if biz.phone:
        score += SCORE_WEIGHTS["has_phone"]
    if biz.email:
        score += SCORE_WEIGHTS["has_email"]
    if biz.website:
        score += SCORE_WEIGHTS["has_website"]
    if biz.rating > 0:
        score += SCORE_WEIGHTS["has_rating"]
    if biz.description:
        score += SCORE_WEIGHTS["has_description"]
    if biz.address:
        score += SCORE_WEIGHTS["has_address"]

    # Review volume bonus (normalized: 50+ reviews = full score)
    if biz.reviews_count > 0:
        review_factor = min(biz.reviews_count / 50, 1.0)
        score += SCORE_WEIGHTS["review_volume"] * review_factor

    return round(score, 2)


# ---------------------------------------------------------------------------
# Data enrichment
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}"
)


def extract_emails(text: str) -> list[str]:
    """Extract email addresses from text."""
    return EMAIL_PATTERN.findall(text)


def extract_phones(text: str) -> list[str]:
    """Extract phone numbers from text."""
    return PHONE_PATTERN.findall(text)


def enrich_from_website(biz: Business, session: requests.Session) -> Business:
    """Visit business website to extract additional contact details."""
    if not biz.website:
        return biz

    try:
        html = fetch_page(biz.website, session)
        if not html:
            return biz

        # Extract emails from page
        if not biz.email:
            emails = extract_emails(html)
            # Filter out common non-business emails
            filtered = [
                e for e in emails
                if not any(x in e.lower() for x in [
                    "example.com", "sentry.io", "wixpress", "placeholder",
                ])
            ]
            if filtered:
                biz.email = filtered[0]

        # Extract phone from page if not already set
        if not biz.phone:
            phones = extract_phones(html)
            if phones:
                biz.phone = phones[0].strip()

    except Exception as e:
        logger.debug(f"Enrichment failed for {biz.website}: {e}")

    return biz


# ---------------------------------------------------------------------------
# Directory scraping
# ---------------------------------------------------------------------------

def build_search_url(query: str, location: str, page: int = 1) -> str:
    """Build search URL for business directory (Yellow Pages style)."""
    params = f"?q={query}&location={location}&page={page}"
    return BASE_URL + "/search" + params


def parse_listing_page(html: str, category: str = "",
                       city: str = "") -> list[Business]:
    """Parse a directory listing page and extract business data."""
    soup = BeautifulSoup(html, "html.parser")
    businesses = []

    # Try multiple selectors for resilience
    card_selectors = [
        ".business-card",
        ".listing-item",
        ".result-card",
        ".organic .srp-listing",
    ]

    cards = []
    for sel in card_selectors:
        cards = soup.select(sel)
        if cards:
            break

    if not cards:
        logger.warning("No business cards found on page.")
        return businesses

    for card in cards:
        try:
            # Extract name
            name_el = card.select_one("h2 a, .business-name a, .listing-title a")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            # Extract link
            source_url = ""
            if name_el and name_el.get("href"):
                source_url = name_el["href"]

            # Extract address
            addr_el = card.select_one(".address, .street-address, .adr")
            address = addr_el.get_text(strip=True) if addr_el else ""

            # Extract phone
            phone_el = card.select_one(".phone, .business-phone, [data-phone]")
            phone = ""
            if phone_el:
                phone = phone_el.get("data-phone", "") or phone_el.get_text(strip=True)

            # Extract rating
            rating_el = card.select_one(".rating, .star-rating, [class*='rating']")
            rating = 0.0
            if rating_el:
                rating_text = rating_el.get("aria-label", "") or rating_el.get_text()
                match = re.search(r"(\d+\.?\d*)", rating_text)
                if match:
                    rating = float(match.group(1))

            # Extract review count
            reviews_el = card.select_one(".review-count, .ratings-count")
            reviews_count = 0
            if reviews_el:
                text = reviews_el.get_text()
                nums = re.findall(r"\d+", text.replace(",", ""))
                if nums:
                    reviews_count = int(nums[0])

            # Extract website
            website_el = card.select_one("a.website, a[href*='website'], .track-visit-website")
            website = ""
            if website_el:
                website = website_el.get("href", "")

            # Extract description/snippet
            desc_el = card.select_one(".snippet, .description, .body")
            description = desc_el.get_text(strip=True)[:200] if desc_el else ""

            biz = Business(
                name=name,
                address=address,
                city=city,
                phone=phone,
                website=website,
                category=category,
                rating=rating,
                reviews_count=reviews_count,
                description=description,
                source_url=source_url,
            )
            biz.content_hash = compute_hash(biz)
            biz.lead_score = score_lead(biz)
            biz.scraped_at = datetime.now(timezone.utc).isoformat()

            businesses.append(biz)

        except Exception as e:
            logger.debug(f"Error parsing card: {e}")
            continue

    return businesses


def has_next_page(soup: BeautifulSoup) -> bool:
    """Check if there's a next page in pagination."""
    next_link = soup.select_one(
        "a.next, .pagination .next a, a[aria-label='Next']"
    )
    return next_link is not None


# ---------------------------------------------------------------------------
# Main scraping flow
# ---------------------------------------------------------------------------

def scrape_directory(query: str, location: str, max_pages: int = 10,
                     enrich: bool = False,
                     db_path: Path = DEFAULT_DB) -> list[Business]:
    """Scrape business directory with pagination, scoring, and storage.

    Args:
        query: Business type to search (e.g., "plumbers")
        location: City or area (e.g., "London")
        max_pages: Maximum pages to scrape
        enrich: Whether to visit business websites for extra contact data
        db_path: SQLite database path for persistent storage

    Returns:
        List of scraped Business objects
    """
    init_db(db_path)
    all_businesses: list[Business] = []
    seen_hashes: set[str] = set()

    session = requests.Session()
    session.headers.update(HEADERS)

    for page_num in range(1, max_pages + 1):
        url = build_search_url(query, location, page_num)
        logger.info(f"--- Page {page_num}/{max_pages} ---")

        html = fetch_page(url, session)
        if not html:
            logger.error(f"Failed to fetch page {page_num}. Stopping.")
            break

        businesses = parse_listing_page(html, category=query, city=location)
        if not businesses:
            logger.info("No listings found. Reached end of results.")
            break

        # Deduplicate within this run
        new_businesses = []
        for biz in businesses:
            if biz.content_hash not in seen_hashes:
                seen_hashes.add(biz.content_hash)
                new_businesses.append(biz)

        # Optionally enrich with website data
        if enrich:
            for i, biz in enumerate(new_businesses):
                if biz.website:
                    logger.info(f"  Enriching {i + 1}/{len(new_businesses)}: {biz.name}")
                    biz = enrich_from_website(biz, session)
                    biz.lead_score = score_lead(biz)  # Re-score after enrichment
                    human_delay(1.0, 3.0)

        # Store in database
        with get_connection(db_path) as conn:
            for biz in new_businesses:
                upsert_lead(conn, biz)

        all_businesses.extend(new_businesses)
        logger.info(f"Extracted {len(new_businesses)} leads (total: {len(all_businesses)})")

        # Check pagination
        soup = BeautifulSoup(html, "html.parser")
        if not has_next_page(soup):
            logger.info("No more pages. Pagination complete.")
            break

        human_delay(2.0, 5.0)

    return all_businesses


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "name", "address", "city", "phone", "email", "website",
    "category", "rating", "reviews_count", "lead_score",
]


def save_csv(leads: list[dict], path: Path) -> None:
    """Export leads to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for lead in leads:
            writer.writerow({k: lead.get(k, "") for k in CSV_FIELDS})
    logger.info(f"Saved {len(leads)} leads to {path}")


def save_json(leads: list[dict], path: Path) -> None:
    """Export leads to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(leads)} leads to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Business Lead Generation Tool — scrape directories, score, and export leads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --query "plumbers" --location "London" --output leads.csv
  %(prog)s --query "restaurants" --location "Manchester" --max-pages 10 --enrich
  %(prog)s --export --min-score 0.7 --output qualified_leads.csv
  %(prog)s --stats
        """,
    )
    # Scraping mode
    parser.add_argument("--query", "-q", help="Business type to search")
    parser.add_argument("--location", "-l", help="City or area to search in")
    parser.add_argument("--max-pages", type=int, default=10,
                        help="Maximum pages to scrape (default: 10)")
    parser.add_argument("--enrich", action="store_true",
                        help="Visit business websites for extra contact data")

    # Export mode
    parser.add_argument("--export", action="store_true",
                        help="Export leads from database (no scraping)")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="Minimum lead score for export (0.0–1.0)")
    parser.add_argument("--filter-category", default="",
                        help="Filter by category")
    parser.add_argument("--filter-city", default="",
                        help="Filter by city")

    # Stats mode
    parser.add_argument("--stats", action="store_true",
                        help="Show database statistics")

    # Common options
    parser.add_argument("--output", "-o", default="leads.csv",
                        help="Output file path (default: leads.csv)")
    parser.add_argument("--format", "-f", choices=["csv", "json"], default="csv",
                        help="Output format (default: csv)")
    parser.add_argument("--db", default="leads.db",
                        help="Database file path (default: leads.db)")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db)

    if args.stats:
        init_db(db_path)
        with get_connection(db_path) as conn:
            stats = get_stats(conn)
        print(f"\n{'='*40}")
        print("  Lead Database Statistics")
        print(f"{'='*40}")
        print(f"  Total leads:      {stats['total']:,}")
        print(f"  Cities:           {stats['cities']}")
        print(f"  Categories:       {stats['categories']}")
        print(f"  Avg lead score:   {stats['avg_score']:.2f}")
        print(f"  With phone:       {stats['with_phone']:,}")
        print(f"  With email:       {stats['with_email']:,}")
        print(f"  With website:     {stats['with_website']:,}")
        print(f"{'='*40}\n")
        return

    if args.export:
        init_db(db_path)
        with get_connection(db_path) as conn:
            leads = fetch_leads(
                conn,
                min_score=args.min_score,
                category=args.filter_category,
                city=args.filter_city,
            )
        if not leads:
            logger.warning("No leads match the given filters.")
            return
        output_path = Path(args.output)
        if args.format == "json" or output_path.suffix == ".json":
            save_json(leads, output_path)
        else:
            save_csv(leads, output_path)
        return

    # Scraping mode
    if not args.query or not args.location:
        logger.error("Both --query and --location are required for scraping.")
        return

    logger.info(f"Scraping: '{args.query}' in '{args.location}' (max {args.max_pages} pages)")
    businesses = scrape_directory(
        query=args.query,
        location=args.location,
        max_pages=args.max_pages,
        enrich=args.enrich,
        db_path=db_path,
    )

    if not businesses:
        logger.warning("No leads collected.")
        return

    # Also export to file
    leads = [asdict(b) for b in businesses]
    output_path = Path(args.output)
    if args.format == "json" or output_path.suffix == ".json":
        save_json(leads, output_path)
    else:
        save_csv(leads, output_path)

    logger.info(f"Done. {len(businesses)} leads collected and stored.")


if __name__ == "__main__":
    main()
