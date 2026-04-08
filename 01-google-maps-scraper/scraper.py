"""Google Maps Business Data Scraper

Extract business data from Google Maps using SerpAPI or Google Places API.
Supports pagination, review extraction, retry with exponential backoff,
and export to CSV or JSON.

Usage:
    python scraper.py --query "restaurants in Miami" --output results.csv
    python scraper.py --query "plumbers in London" --include-reviews
    python scraper.py --place-id ChIJN1t_tDeuEmsRUsoyG83frY4
    python scraper.py --query "dentists in Dallas" --method places --api-key YOUR_KEY

Methods:
    serpapi  (default) - Uses SerpAPI Google Maps API (free tier: 100/month)
    places             - Uses Google Places API (requires billing)

Dependencies:
    pip install requests
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import requests

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

SERPAPI_BASE = "https://serpapi.com/search.json"
PLACES_BASE = "https://maps.googleapis.com/maps/api/place"

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]  # exponential backoff (seconds)
RATE_LIMIT_DELAY = 1.0    # seconds between API calls


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Business:
    """Represents a single business extracted from Google Maps."""
    name: str = ""
    address: str = ""
    phone: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    review_texts: str = ""
    website: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    place_id: str = ""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api_request(url: str, params: dict) -> Optional[dict]:
    """Make an API request with retry and exponential backoff.

    Handles 429 (rate limit) and 5xx errors with automatic retries.
    Returns parsed JSON on success, None if all attempts fail.
    """
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(f"Rate limited (429). Retrying in {delay}s...")
                time.sleep(delay)
                continue
            logger.error(f"API error {resp.status_code}: {resp.text[:200]}")
            if resp.status_code >= 500:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                time.sleep(delay)
                continue
            return None
        except requests.RequestException as e:
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            logger.error(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
    logger.error("All retry attempts exhausted.")
    return None


# ---------------------------------------------------------------------------
# SerpAPI method
# ---------------------------------------------------------------------------

def serpapi_search(query: str, api_key: str, max_results: int,
                   include_reviews: bool) -> list[Business]:
    """Search Google Maps via SerpAPI with automatic pagination."""
    businesses: list[Business] = []
    start = 0

    while len(businesses) < max_results:
        logger.info(f"SerpAPI: fetching results (offset {start}, collected {len(businesses)})...")
        params = {
            "engine": "google_maps",
            "q": query,
            "api_key": api_key,
            "start": start,
            "type": "search",
        }
        data = api_request(SERPAPI_BASE, params)
        if not data:
            break

        results = data.get("local_results", [])
        if not results:
            logger.info("No more results from SerpAPI.")
            break

        for item in results:
            if len(businesses) >= max_results:
                break

            biz = Business(
                name=item.get("title", ""),
                address=item.get("address", ""),
                phone=item.get("phone", ""),
                rating=float(item.get("rating", 0)),
                reviews_count=int(item.get("reviews", 0)),
                website=item.get("website", ""),
                latitude=float(item.get("gps_coordinates", {}).get("latitude", 0)),
                longitude=float(item.get("gps_coordinates", {}).get("longitude", 0)),
                place_id=item.get("place_id", ""),
            )

            if include_reviews and biz.place_id:
                biz.review_texts = _serpapi_get_reviews(biz.place_id, api_key)

            businesses.append(biz)

        # Check for next page
        pagination = data.get("serpapi_pagination", {})
        if "next" not in pagination:
            break
        start += len(results)
        time.sleep(RATE_LIMIT_DELAY)

    logger.info(f"SerpAPI: collected {len(businesses)} businesses.")
    return businesses


def _serpapi_get_reviews(place_id: str, api_key: str, max_reviews: int = 5) -> str:
    """Fetch top reviews for a place via SerpAPI."""
    params = {
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "api_key": api_key,
    }
    time.sleep(RATE_LIMIT_DELAY)
    data = api_request(SERPAPI_BASE, params)
    if not data:
        return ""

    reviews = data.get("reviews", [])[:max_reviews]
    texts = [r.get("snippet", "").replace("\n", " ").strip() for r in reviews]
    return "; ".join(t for t in texts if t)


# ---------------------------------------------------------------------------
# Google Places API method
# ---------------------------------------------------------------------------

def places_search(query: str, api_key: str, max_results: int,
                  include_reviews: bool) -> list[Business]:
    """Search Google Maps via Google Places API with token-based pagination."""
    businesses: list[Business] = []
    next_page_token: Optional[str] = None

    while len(businesses) < max_results:
        logger.info(f"Places API: fetching results (collected {len(businesses)})...")
        params: dict = {
            "query": query,
            "key": api_key,
        }
        if next_page_token:
            params["pagetoken"] = next_page_token

        data = api_request(f"{PLACES_BASE}/textsearch/json", params)
        if not data or data.get("status") != "OK":
            status = data.get("status", "UNKNOWN") if data else "NO_RESPONSE"
            logger.error(f"Places API error: {status}")
            break

        for item in data.get("results", []):
            if len(businesses) >= max_results:
                break

            location = item.get("geometry", {}).get("location", {})
            biz = Business(
                name=item.get("name", ""),
                address=item.get("formatted_address", ""),
                rating=float(item.get("rating", 0)),
                reviews_count=int(item.get("user_ratings_total", 0)),
                latitude=float(location.get("lat", 0)),
                longitude=float(location.get("lng", 0)),
                place_id=item.get("place_id", ""),
            )

            # Enrich with phone, website, and reviews from Place Details
            if biz.place_id:
                details = _places_get_details(biz.place_id, api_key, include_reviews)
                biz.phone = details.get("phone", "")
                biz.website = details.get("website", "")
                if include_reviews:
                    biz.review_texts = details.get("review_texts", "")

            businesses.append(biz)

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break
        # Google requires a short delay before using next_page_token
        time.sleep(2)

    logger.info(f"Places API: collected {len(businesses)} businesses.")
    return businesses


def _places_get_details(place_id: str, api_key: str,
                        include_reviews: bool) -> dict:
    """Fetch place details (phone, website, reviews) from Places API."""
    fields = "formatted_phone_number,website"
    if include_reviews:
        fields += ",reviews"

    params = {
        "place_id": place_id,
        "fields": fields,
        "key": api_key,
    }
    time.sleep(RATE_LIMIT_DELAY)
    data = api_request(f"{PLACES_BASE}/details/json", params)
    if not data or data.get("status") != "OK":
        return {}

    result = data.get("result", {})
    details: dict = {
        "phone": result.get("formatted_phone_number", ""),
        "website": result.get("website", ""),
    }

    if include_reviews:
        reviews = result.get("reviews", [])[:5]
        texts = [r.get("text", "").replace("\n", " ").strip() for r in reviews]
        details["review_texts"] = "; ".join(t for t in texts if t)

    return details


# ---------------------------------------------------------------------------
# Single place lookup
# ---------------------------------------------------------------------------

def lookup_place(place_id: str, api_key: str, method: str,
                 include_reviews: bool) -> list[Business]:
    """Look up a single place by its Google Place ID."""
    if method == "places":
        fields = "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,geometry"
        if include_reviews:
            fields += ",reviews"

        params = {
            "place_id": place_id,
            "fields": fields,
            "key": api_key,
        }
        data = api_request(f"{PLACES_BASE}/details/json", params)
        if not data or data.get("status") != "OK":
            logger.error("Failed to fetch place details.")
            return []

        r = data.get("result", {})
        location = r.get("geometry", {}).get("location", {})
        review_texts = ""
        if include_reviews:
            reviews = r.get("reviews", [])[:5]
            texts = [rv.get("text", "").replace("\n", " ").strip() for rv in reviews]
            review_texts = "; ".join(t for t in texts if t)

        biz = Business(
            name=r.get("name", ""),
            address=r.get("formatted_address", ""),
            phone=r.get("formatted_phone_number", ""),
            rating=float(r.get("rating", 0)),
            reviews_count=int(r.get("user_ratings_total", 0)),
            review_texts=review_texts,
            website=r.get("website", ""),
            latitude=float(location.get("lat", 0)),
            longitude=float(location.get("lng", 0)),
            place_id=place_id,
        )
        return [biz]

    else:
        # SerpAPI method
        params = {
            "engine": "google_maps_reviews",
            "place_id": place_id,
            "api_key": api_key,
        }
        data = api_request(SERPAPI_BASE, params)
        if not data:
            logger.error("Failed to fetch place via SerpAPI.")
            return []

        info = data.get("place_info", {})
        review_texts = ""
        if include_reviews:
            reviews = data.get("reviews", [])[:5]
            texts = [rv.get("snippet", "").replace("\n", " ").strip() for rv in reviews]
            review_texts = "; ".join(t for t in texts if t)

        biz = Business(
            name=info.get("title", ""),
            address=info.get("address", ""),
            phone=info.get("phone", ""),
            rating=float(info.get("rating", 0)),
            reviews_count=int(info.get("reviews", 0)),
            review_texts=review_texts,
            website=info.get("website", ""),
            latitude=float(info.get("gps_coordinates", {}).get("latitude", 0)),
            longitude=float(info.get("gps_coordinates", {}).get("longitude", 0)),
            place_id=place_id,
        )
        return [biz]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "name", "address", "phone", "rating", "reviews_count",
    "review_texts", "website", "latitude", "longitude", "place_id",
]


def save_csv(businesses: list[Business], path: Path) -> None:
    """Export businesses to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for biz in businesses:
            writer.writerow(asdict(biz))
    logger.info(f"Saved {len(businesses)} records to {path}")


def save_json(businesses: list[Business], path: Path) -> None:
    """Export businesses to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(biz) for biz in businesses], f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(businesses)} records to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google Maps Business Data Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --query "restaurants in Miami" --output results.csv
  %(prog)s --query "plumbers in London" --include-reviews
  %(prog)s --place-id ChIJN1t_tDeuEmsRUsoyG83frY4
  %(prog)s --query "dentists" --method places --api-key YOUR_KEY
  %(prog)s --query "cafes in Berlin" --max-results 50 --format json
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", "-q", help="Search query (e.g., 'restaurants in Miami')")
    group.add_argument("--place-id", help="Google Place ID for single business lookup")

    parser.add_argument("--output", "-o", default="results.csv",
                        help="Output file path (default: results.csv)")
    parser.add_argument("--method", "-m", choices=["serpapi", "places"], default="serpapi",
                        help="API method: serpapi (default) or places")
    parser.add_argument("--api-key", "-k",
                        help="API key (or set SERPAPI_API_KEY / GOOGLE_PLACES_API_KEY env var)")
    parser.add_argument("--max-results", type=int, default=100,
                        help="Maximum businesses to collect (default: 100)")
    parser.add_argument("--include-reviews", action="store_true",
                        help="Include top review texts (slower, extra API calls)")
    parser.add_argument("--format", "-f", choices=["csv", "json"], default="csv",
                        help="Output format (default: csv)")

    return parser.parse_args()


def resolve_api_key(args: argparse.Namespace) -> str:
    """Resolve API key from CLI args or environment variables."""
    if args.api_key:
        return args.api_key

    env_var = "SERPAPI_API_KEY" if args.method == "serpapi" else "GOOGLE_PLACES_API_KEY"
    key = os.environ.get(env_var, "")
    if not key:
        logger.error(f"No API key provided. Set {env_var} or use --api-key.")
        sys.exit(1)
    return key


def main() -> None:
    args = parse_args()
    api_key = resolve_api_key(args)

    logger.info(f"Method: {args.method} | Max results: {args.max_results} | "
                f"Reviews: {args.include_reviews}")

    if args.place_id:
        businesses = lookup_place(
            args.place_id, api_key, args.method, args.include_reviews
        )
    elif args.method == "serpapi":
        businesses = serpapi_search(
            args.query, api_key, args.max_results, args.include_reviews
        )
    else:
        businesses = places_search(
            args.query, api_key, args.max_results, args.include_reviews
        )

    if not businesses:
        logger.warning("No businesses found.")
        sys.exit(0)

    output_path = Path(args.output)
    if args.format == "json" or output_path.suffix == ".json":
        save_json(businesses, output_path)
    else:
        save_csv(businesses, output_path)

    logger.info("Done.")


if __name__ == "__main__":
    main()
