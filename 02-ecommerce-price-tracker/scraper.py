"""E-Commerce Price Tracker

Monitor product prices on e-commerce websites using Playwright for
JavaScript-rendered pages. Features adaptive rate limiting, anti-bot
detection, content deduplication, and CSV export with price history.

Usage:
    python scraper.py --url "https://www.amazon.com/s?k=laptops" --output prices.csv
    python scraper.py --url "https://www.amazon.com/s?k=headphones" --max-pages 5
    python scraper.py --urls-file product_urls.txt --output tracked_prices.csv

Dependencies:
    pip install playwright beautifulsoup4
    playwright install chromium
"""

import argparse
import csv
import hashlib
import json
import logging
import random
import re
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser

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
BLOCK_BACKOFF = (30.0, 60.0)  # seconds to wait when blocked

# Target website base URL — replace with the actual e-commerce site you want to scrape
BASE_URL = "https://www.amazon.com"

SELECTORS = {
    "product_card": [
        "[data-component-type='s-search-result']",
        ".s-result-item",
        ".product-card",
        ".sg-col-inner",
    ],
    "title": [
        "h2 a span",
        ".a-text-normal",
        "[data-cy='title-recipe'] a",
        ".product-title",
    ],
    "price": [
        ".a-price .a-offscreen",
        ".a-price-whole",
        "[data-cy='price-recipe']",
        ".price-current",
    ],
    "original_price": [
        ".a-text-price .a-offscreen",
        ".a-price[data-a-strike] .a-offscreen",
        ".list-price",
    ],
    "rating": [
        ".a-icon-alt",
        "[data-cy='reviews-ratings-count']",
        ".star-rating",
    ],
    "reviews_count": [
        ".a-size-base.s-underline-text",
        "[data-cy='reviews-block'] span",
        ".ratings-count",
    ],
    "seller": [
        ".a-size-small .a-link-normal",
        ".seller-name",
        ".sold-by",
    ],
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Product:
    """Represents a single product listing."""
    name: str = ""
    price: float = 0.0
    original_price: float = 0.0
    discount_pct: float = 0.0
    currency: str = "USD"
    rating: float = 0.0
    reviews_count: int = 0
    seller: str = ""
    category: str = ""
    url: str = ""
    content_hash: str = ""
    scraped_at: str = ""


# ---------------------------------------------------------------------------
# Adaptive Rate Limiter
# ---------------------------------------------------------------------------

class AdaptiveRateLimiter:
    """Dynamically adjusts request delays based on server responses.

    Relaxes delays after consecutive successes, tightens after blocks
    or rate limits. Prevents aggressive scraping while maximizing throughput.
    """

    def __init__(self, base_min: float = 2.0, base_max: float = 5.0):
        self.base_min = base_min
        self.base_max = base_max
        self.multiplier = 1.0
        self.consecutive_successes = 0

    def on_success(self):
        """Record a successful page load."""
        self.consecutive_successes += 1
        if self.consecutive_successes >= 10 and self.multiplier > 0.7:
            self.multiplier = max(0.7, self.multiplier * 0.95)
            logger.debug(f"Rate limiter relaxed to {self.multiplier:.2f}x")

    def on_block(self):
        """Record a block or CAPTCHA detection — doubles the delay."""
        self.consecutive_successes = 0
        self.multiplier = min(5.0, self.multiplier * 2.0)
        logger.warning(f"Rate limiter tightened to {self.multiplier:.2f}x (block detected)")

    def on_rate_limit(self):
        """Record a rate limit response — increases delay by 50%."""
        self.consecutive_successes = 0
        self.multiplier = min(5.0, self.multiplier * 1.5)
        logger.warning(f"Rate limiter tightened to {self.multiplier:.2f}x (rate limited)")

    def wait(self):
        """Sleep for the adaptive delay duration."""
        delay = random.uniform(
            self.base_min * self.multiplier,
            self.base_max * self.multiplier,
        )
        logger.debug(f"Waiting {delay:.1f}s (multiplier={self.multiplier:.2f})")
        time.sleep(delay)

    @property
    def current_range(self) -> tuple[float, float]:
        return (self.base_min * self.multiplier, self.base_max * self.multiplier)


# ---------------------------------------------------------------------------
# Anti-bot detection
# ---------------------------------------------------------------------------

def is_blocked(page: Page) -> bool:
    """Detect common bot protection pages (CAPTCHA, access denied, etc.)."""
    try:
        title = page.title().lower()
        indicators = [
            "captcha", "robot", "blocked", "access denied",
            "just a moment", "verify you are human", "unusual traffic",
        ]
        return any(kw in title for kw in indicators)
    except Exception:
        return False


def human_delay(min_sec: float = 1.0, max_sec: float = 3.0):
    """Sleep for a random human-like duration."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Content deduplication
# ---------------------------------------------------------------------------

def compute_hash(product: Product) -> str:
    """Generate MD5 hash for deduplication based on name + seller + price."""
    raw = f"{product.name}|{product.seller}|{product.price}"
    return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def try_selectors(page: Page, selectors: list[str], context_el=None) -> str:
    """Try multiple CSS selectors, return text of first match or empty string."""
    target = context_el if context_el else page
    for sel in selectors:
        try:
            el = target.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def parse_price(text: str) -> float:
    """Extract numeric price from text like '$29.99' or '1,299.00'."""
    if not text:
        return 0.0
    cleaned = re.sub(r"[^\d.,]", "", text)
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_rating(text: str) -> float:
    """Extract rating from text like '4.5 out of 5 stars'."""
    if not text:
        return 0.0
    match = re.search(r"(\d+\.?\d*)", text)
    return float(match.group(1)) if match else 0.0


def parse_review_count(text: str) -> int:
    """Extract review count from text like '1,234 ratings'."""
    if not text:
        return 0
    cleaned = re.sub(r"[^\d]", "", text)
    try:
        return int(cleaned)
    except ValueError:
        return 0


def calculate_discount(price: float, original: float) -> float:
    """Calculate discount percentage."""
    if original > 0 and price > 0 and original > price:
        return round((1 - price / original) * 100, 1)
    return 0.0


# ---------------------------------------------------------------------------
# Page scraping
# ---------------------------------------------------------------------------

def extract_products(page: Page, category: str = "") -> list[Product]:
    """Extract all product listings from the current page."""
    products = []
    now = datetime.now(timezone.utc).isoformat()

    # Try each product card selector
    cards = []
    for sel in SELECTORS["product_card"]:
        cards = page.query_selector_all(sel)
        if cards:
            logger.info(f"Found {len(cards)} products using selector: {sel}")
            break

    if not cards:
        logger.warning("No product cards found on page.")
        return products

    for card in cards:
        try:
            name = try_selectors(page, SELECTORS["title"], card)
            if not name:
                continue

            price_text = try_selectors(page, SELECTORS["price"], card)
            orig_text = try_selectors(page, SELECTORS["original_price"], card)
            rating_text = try_selectors(page, SELECTORS["rating"], card)
            reviews_text = try_selectors(page, SELECTORS["reviews_count"], card)
            seller_text = try_selectors(page, SELECTORS["seller"], card)

            price = parse_price(price_text)
            original_price = parse_price(orig_text)

            # Try to get product URL
            link = card.query_selector("h2 a, .product-title a, a[href*='/dp/']")
            url = ""
            if link:
                href = link.get_attribute("href") or ""
                if href.startswith("/"):
                    url = f"{BASE_URL}{href}"
                elif href.startswith("http"):
                    url = href

            product = Product(
                name=name,
                price=price,
                original_price=original_price,
                discount_pct=calculate_discount(price, original_price),
                rating=parse_rating(rating_text),
                reviews_count=parse_review_count(reviews_text),
                seller=seller_text,
                category=category,
                url=url,
                scraped_at=now,
            )
            product.content_hash = compute_hash(product)
            products.append(product)

        except Exception as e:
            logger.debug(f"Error extracting product card: {e}")
            continue

    return products


def navigate_with_retry(page: Page, url: str, rate_limiter: AdaptiveRateLimiter) -> bool:
    """Navigate to URL with retry, block detection, and adaptive rate limiting."""
    for attempt in range(MAX_RETRIES):
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            human_delay(1.5, 3.0)

            if not is_blocked(page):
                rate_limiter.on_success()
                return True

            logger.warning(f"Bot detection triggered (attempt {attempt + 1}/{MAX_RETRIES})")
            rate_limiter.on_block()

            if attempt < MAX_RETRIES - 1:
                backoff = random.uniform(*BLOCK_BACKOFF)
                logger.info(f"Backing off for {backoff:.0f}s...")
                time.sleep(backoff)

        except Exception as e:
            logger.error(f"Navigation error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                rate_limiter.on_rate_limit()
                rate_limiter.wait()

    return False


def has_next_page(page: Page) -> Optional[str]:
    """Check for a 'next page' link and return its URL, or None."""
    next_selectors = [
        "a.s-pagination-next",
        ".a-pagination .a-last a",
        "a[aria-label='Next']",
        ".pagination .next a",
    ]
    for sel in next_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                href = el.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        return f"{BASE_URL}{href}"
                    return href
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(products: list[Product]) -> list[Product]:
    """Remove duplicate products based on content hash."""
    seen: set[str] = set()
    unique = []
    for p in products:
        if p.content_hash not in seen:
            seen.add(p.content_hash)
            unique.append(p)
    duplicates = len(products) - len(unique)
    if duplicates:
        logger.info(f"Removed {duplicates} duplicate(s).")
    return unique


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "name", "price", "original_price", "discount_pct", "currency",
    "rating", "reviews_count", "seller", "category", "url", "scraped_at",
]


def save_csv(products: list[Product], path: Path) -> None:
    """Export products to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for p in products:
            row = asdict(p)
            writer.writerow({k: row[k] for k in CSV_FIELDS})
    logger.info(f"Saved {len(products)} products to {path}")


def save_json(products: list[Product], path: Path) -> None:
    """Export products to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in products], f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(products)} products to {path}")


# ---------------------------------------------------------------------------
# Main scraping flow
# ---------------------------------------------------------------------------

def scrape_category(url: str, max_pages: int = 10,
                    category: str = "") -> list[Product]:
    """Scrape product listings from a category or search results page.

    Handles pagination, adaptive rate limiting, anti-bot detection,
    and deduplication across pages.
    """
    all_products: list[Product] = []
    rate_limiter = AdaptiveRateLimiter(base_min=2.0, base_max=5.0)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        current_url = url
        for page_num in range(1, max_pages + 1):
            logger.info(f"--- Page {page_num}/{max_pages} ---")

            if not navigate_with_retry(page, current_url, rate_limiter):
                logger.error(f"Failed to load page {page_num}. Stopping.")
                break

            products = extract_products(page, category)
            if not products:
                logger.info("No products found. Reached end of results.")
                break

            all_products.extend(products)
            logger.info(f"Extracted {len(products)} products (total: {len(all_products)})")

            # Check for next page
            next_url = has_next_page(page)
            if not next_url:
                logger.info("No next page link found. Pagination complete.")
                break

            current_url = next_url
            rate_limiter.wait()

        browser.close()

    # Deduplicate across all pages
    all_products = deduplicate(all_products)
    return all_products


def scrape_urls(urls: list[str]) -> list[Product]:
    """Scrape individual product pages from a list of URLs."""
    products: list[Product] = []
    rate_limiter = AdaptiveRateLimiter(base_min=2.0, base_max=4.0)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for i, url in enumerate(urls, 1):
            logger.info(f"[{i}/{len(urls)}] Scraping: {url}")
            if not navigate_with_retry(page, url, rate_limiter):
                continue

            page_products = extract_products(page)
            if page_products:
                products.extend(page_products)
            rate_limiter.wait()

        browser.close()

    return deduplicate(products)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="E-Commerce Price Tracker — monitor product prices with Playwright",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --url "https://www.amazon.com/s?k=laptops" --output laptops.csv
  %(prog)s --url "https://www.amazon.com/s?k=electronics" --max-pages 5
  %(prog)s --urls-file product_urls.txt --format json
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", "-u", help="Category or search results URL to scrape")
    group.add_argument("--urls-file", help="File with product URLs (one per line)")

    parser.add_argument("--output", "-o", default="products.csv",
                        help="Output file path (default: products.csv)")
    parser.add_argument("--max-pages", type=int, default=10,
                        help="Maximum pages to scrape (default: 10)")
    parser.add_argument("--category", "-c", default="",
                        help="Category label for the products")
    parser.add_argument("--format", "-f", choices=["csv", "json"], default="csv",
                        help="Output format (default: csv)")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.url:
        logger.info(f"Scraping category: {args.url} (max {args.max_pages} pages)")
        products = scrape_category(args.url, args.max_pages, args.category)
    else:
        urls_path = Path(args.urls_file)
        if not urls_path.exists():
            logger.error(f"URLs file not found: {urls_path}")
            return
        urls = [line.strip() for line in urls_path.read_text().splitlines() if line.strip()]
        logger.info(f"Scraping {len(urls)} individual product URLs")
        products = scrape_urls(urls)

    if not products:
        logger.warning("No products collected.")
        return

    output_path = Path(args.output)
    if args.format == "json" or output_path.suffix == ".json":
        save_json(products, output_path)
    else:
        save_csv(products, output_path)

    logger.info(f"Done. Collected {len(products)} unique products.")


if __name__ == "__main__":
    main()
