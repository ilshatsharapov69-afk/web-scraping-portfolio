# Web Scraping Portfolio

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-1.49-green?logo=playwright&logoColor=white)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-4.12-orange)
![Requests](https://img.shields.io/badge/Requests-2.32-lightgrey)
![SQLite](https://img.shields.io/badge/SQLite-3-blue?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)
![CI](https://github.com/ilshatsharapov69-afk/web-scraping-portfolio/actions/workflows/lint.yml/badge.svg)

Python developer specializing in **web scraping**, **data extraction**, and **automation**. Three production-quality tools demonstrating different techniques — API integration, browser automation, and database-backed lead generation.

---

## Projects at a Glance

| # | Project | Tech Stack | What It Does |
|---|---------|------------|-------------|
| 1 | [Google Maps Scraper](01-google-maps-scraper/) | Requests, SerpAPI | Extract businesses from Google Maps |
| 2 | [E-Commerce Price Tracker](02-ecommerce-price-tracker/) | Playwright, BeautifulSoup | Track product prices on JS-heavy sites |
| 3 | [Lead Generation Tool](03-lead-generation-tool/) | BeautifulSoup, SQLite | Build scored lead lists from directories |

## Performance

| Project | Speed | Capacity | Success Rate |
|---------|-------|----------|-------------|
| Google Maps Scraper | ~100 businesses/min | Up to 10,000 per run | 99%+ (API-backed) |
| E-Commerce Tracker | ~20 products/min | 100+ pages with pagination | 95%+ with anti-bot |
| Lead Generation | ~50 leads/min | SQLite stores 100K+ leads | 98%+ |

---

## 1. [Google Maps Business Scraper](01-google-maps-scraper/)

Extract business data from Google Maps with dual API support, automatic pagination, and review extraction.

**Key features:** Dual API (SerpAPI + Places), pagination, retry with exponential backoff, review extraction

```
$ python scraper.py --query "restaurants in NYC" --max-results 20
10:23:45 [INFO] Method: serpapi | Max results: 20 | Reviews: False
10:23:46 [INFO] SerpAPI: fetching results (offset 0, collected 0)...
10:23:48 [INFO] SerpAPI: fetching results (offset 20, collected 20)...
10:23:48 [INFO] SerpAPI: collected 20 businesses.
10:23:48 [INFO] Saved 20 records to results.csv
10:23:48 [INFO] Done.
```

| Name | Address | Rating | Reviews | Phone |
|------|---------|--------|---------|-------|
| Joe's Pizza | 7 Carmine St, New York | 4.5 | 8,743 | (212) 366-1182 |
| Le Bernardin | 155 W 51st St, New York | 4.7 | 4,521 | (212) 554-1515 |
| Katz's Delicatessen | 205 E Houston St, New York | 4.6 | 15,234 | (212) 254-2246 |

---

## 2. [E-Commerce Price Tracker](02-ecommerce-price-tracker/)

Track product prices on JavaScript-heavy e-commerce sites using Playwright browser automation.

**Key features:** Adaptive rate limiting, CAPTCHA detection, multi-selector fallback, MD5 deduplication

```
$ python scraper.py --url "https://www.amazon.com/s?k=headphones" --max-pages 3
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

| Product | Price | Original | Discount | Rating | Reviews |
|---------|-------|----------|----------|--------|---------|
| Sony WH-1000XM5 Wireless Headphones | $298.00 | $399.99 | 25.5% | 4.7 | 18,432 |
| Apple MacBook Air M2 13-inch | $1,049.00 | $1,199.00 | 12.5% | 4.8 | 9,876 |
| Samsung 49-inch Odyssey G9 Monitor | $899.99 | $1,299.99 | 30.8% | 4.5 | 3,421 |

---

## 3. [Business Lead Generation Tool](03-lead-generation-tool/)

Scrape business directories to build qualified lead lists with quality scoring, SQLite storage, and data enrichment.

**Key features:** Lead scoring (0.0–1.0), UPSERT deduplication, website enrichment, filtered export

```
$ python scraper.py --query "plumbers" --location "London" --enrich
09:41:03 [INFO] Database initialized: leads.db
09:41:03 [INFO] Scraping: 'plumbers' in 'London' (max 10 pages)
09:41:03 [INFO] --- Page 1/10 ---
09:41:05 [INFO]   Enriching 1/18: Thames Plumbing Services
09:41:08 [INFO]   Enriching 2/18: CityFlow Drainage
09:41:11 [INFO] Extracted 18 leads (total: 18)
09:41:11 [INFO] --- Page 2/10 ---
09:41:14 [INFO] Extracted 15 leads (total: 33)
09:41:14 [INFO] No more pages. Pagination complete.
09:41:14 [INFO] Saved 33 leads to leads.csv
09:41:14 [INFO] Done. 33 leads collected and stored.
```

| Business | City | Phone | Email | Score |
|----------|------|-------|-------|-------|
| Thames Plumbing Services | London | +44 20 7946 0958 | info@thamesplumbing.co.uk | 0.95 |
| Mayfair Pipes & Heating | London | +44 20 7890 1234 | mayfair@pipesheating.com | 0.95 |
| Southbank Plumbing Co | London | +44 20 7678 9012 | — | 0.75 |

---

## Tech Stack

| Technology | Used In | Purpose |
|-----------|---------|---------|
| **Python 3.10+** | All projects | Core language |
| **Playwright** | Price Tracker | Browser automation for JS-rendered pages |
| **BeautifulSoup** | Price Tracker, Lead Gen | HTML parsing |
| **Requests** | Maps Scraper, Lead Gen | HTTP client |
| **SQLite** | Lead Gen | Persistent data storage with WAL mode |
| **Dataclasses** | All projects | Typed data models |

## What Sets This Apart

All three projects use **production-grade patterns** — not just basic `requests.get()`:

- **Retry with exponential backoff** — automatic retries on 429/5xx errors with configurable delays
- **Adaptive rate limiting** — dynamically adjusts request frequency based on server responses
- **Anti-bot detection** — identifies CAPTCHAs, access blocks, and backs off automatically
- **Content deduplication** — MD5 hash-based dedup prevents duplicate records across runs
- **Human-like behavior** — randomized delays between requests to avoid fingerprinting
- **Structured data models** — typed dataclasses, not raw dicts
- **Flexible CLI** — argparse with multiple modes, filters, and output formats

## Contact

Available for custom web scraping and data extraction projects.

- **Freelancer.com:** [Ilshat Sharapov](https://www.freelancer.com/u/ilshatsharapov69-afk)
- **Email:** ilshat.sharapov69@gmail.com
- **GitHub:** [ilshatsharapov69-afk](https://github.com/ilshatsharapov69-afk)
