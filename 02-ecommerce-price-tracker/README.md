# E-Commerce Price Tracker

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-1.40-green?logo=playwright&logoColor=white)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-4.12-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

Monitor and track product prices on e-commerce websites using browser automation. Handles JavaScript-rendered pages, anti-bot detection, and deduplicates results automatically.

## Features

- **Browser automation with Playwright** — renders JavaScript-heavy product pages
- **Adaptive rate limiting** — dynamically adjusts delays based on server responses (relaxes on success, tightens on blocks)
- **Anti-bot detection** — detects CAPTCHAs and access blocks, backs off automatically
- **Human-like behavior** — randomized delays between requests to avoid detection
- **Multi-selector fallback** — tries multiple CSS selectors per field for resilience against DOM changes
- **Content deduplication** — MD5 hash-based dedup prevents duplicate entries across pages
- **Automatic pagination** — follows "Next" links across search result pages
- **Price tracking** — captures current price, original price, and discount percentage
- **Flexible output** — CSV or JSON export

## Quick Start

```bash
git clone https://github.com/ilshatsharapov69-afk/web-scraping-portfolio.git
cd web-scraping-portfolio/02-ecommerce-price-tracker
pip install -r requirements.txt
playwright install chromium
```

**Configuration:** Open `scraper.py` and set `BASE_URL` to your target e-commerce site:
```python
BASE_URL = "https://www.amazon.com"  # Replace with target site
```

**Run the scraper:**
```bash
# Scrape a category page (with pagination)
python scraper.py --url "https://www.amazon.com/s?k=headphones" --output headphones.csv

# Limit to 5 pages
python scraper.py --url "https://www.amazon.com/s?k=laptops" --max-pages 5

# Scrape individual product URLs
python scraper.py --urls-file product_urls.txt --format json

# Add category label
python scraper.py --url "https://www.amazon.com/s?k=monitors" --category "Monitors"
```

## Demo Run

```
$ python scraper.py --url "https://www.amazon.com/s?k=headphones" --max-pages 3
14:05:12 [INFO] Scraping category: https://www.amazon.com/s?k=headphones (max 3 pages)
14:05:12 [INFO] --- Page 1/3 ---
14:05:15 [INFO] Found 24 products using selector: [data-component-type='s-search-result']
14:05:15 [INFO] Extracted 24 products (total: 24)
14:05:18 [INFO] --- Page 2/3 ---
14:05:21 [INFO] Found 24 products using selector: [data-component-type='s-search-result']
14:05:21 [INFO] Extracted 24 products (total: 48)
14:05:24 [INFO] --- Page 3/3 ---
14:05:27 [INFO] Found 22 products using selector: [data-component-type='s-search-result']
14:05:27 [INFO] Removed 3 duplicate(s).
14:05:27 [INFO] Saved 67 products to headphones.csv
14:05:27 [INFO] Done. Collected 67 unique products.
```

## Sample Output

| Product | Price | Original | Discount | Rating | Reviews | Seller |
|---------|-------|----------|----------|--------|---------|--------|
| Sony WH-1000XM5 Headphones | $298.00 | $399.99 | 25.5% | 4.7 | 18,432 | Sony Official |
| Apple MacBook Air M2 | $1,049.00 | $1,199.00 | 12.5% | 4.8 | 9,876 | Apple Store |
| Samsung Odyssey G9 49" | $899.99 | $1,299.99 | 30.8% | 4.5 | 3,421 | Samsung Direct |
| Bose QuietComfort Earbuds II | $199.00 | $279.00 | 28.7% | 4.6 | 11,234 | Bose Direct |
| SanDisk Extreme Pro 1TB SSD | $79.99 | $129.99 | 38.5% | 4.7 | 23,456 | Western Digital |
| LG C3 65" OLED TV | $1,496.99 | $1,799.99 | 16.8% | 4.8 | 7,654 | LG Electronics |
| Logitech MX Master 3S | $89.99 | $99.99 | 10.0% | 4.6 | 12,543 | Logitech |
| Keychron K2 Keyboard | $89.00 | $99.00 | 10.1% | 4.5 | 6,789 | Keychron |
| Kindle Paperwhite Signature | $149.99 | $189.99 | 21.1% | 4.7 | 28,901 | Amazon |
| Dell XPS 15 Laptop | $1,299.99 | $1,549.99 | 16.1% | 4.4 | 5,432 | Dell |

Full sample data (20 records): [`sample_data/products_amazon.csv`](sample_data/products_amazon.csv)

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  Launch       │────>│  Extract      │────>│  Deduplicate  │────>│  Export   │
│  Browser      │     │  Products     │     │  (MD5 hash)   │     │  CSV/JSON │
│  + Navigate   │     │  (fallback    │     │               │     │          │
│  + Anti-bot   │     │   selectors)  │     │               │     │          │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────┘
        │                    │
        ▼                    ▼
  Adaptive Rate        Multi-selector
  Limiter adjusts      fallback tries
  delays per response  4+ CSS patterns
```

### Adaptive Rate Limiting

The scraper dynamically adjusts request delays based on server behavior:

| Event | Multiplier Change | Effect |
|-------|-------------------|--------|
| 10 consecutive successes | x0.95 (min 0.7x) | Gradually speeds up |
| Block/CAPTCHA detected | x2.0 (max 5.0x) | Doubles delay |
| Rate limit (429) | x1.5 (max 5.0x) | Increases delay by 50% |

Default delay range: **2–5 seconds** between requests, adjusted by the multiplier.

## Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Product title |
| `price` | float | Current price |
| `original_price` | float | Original/list price |
| `discount_pct` | float | Discount percentage |
| `currency` | string | Currency code (default: USD) |
| `rating` | float | Star rating |
| `reviews_count` | int | Number of customer reviews |
| `seller` | string | Seller name |
| `category` | string | Product category |
| `url` | string | Product page URL |
| `scraped_at` | string | Timestamp of extraction (ISO 8601) |

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--url` / `-u` | — | Category or search URL to scrape |
| `--urls-file` | — | File with product URLs (one per line) |
| `--output` / `-o` | `products.csv` | Output file path |
| `--max-pages` | `10` | Maximum pages to follow |
| `--category` / `-c` | `""` | Category label |
| `--format` / `-f` | `csv` | Output format: `csv` or `json` |

## Tech Stack

- **Python 3.10+** — core language
- **Playwright** — browser automation for JS-rendered pages
- **BeautifulSoup** — HTML parsing
- **Hashlib** — MD5-based content deduplication

---

Built by [Ilshat Sharapov](https://www.freelancer.com/u/ilshatsharapov69-afk) — available for custom web scraping projects.
