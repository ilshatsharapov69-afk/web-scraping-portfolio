# Web Scraping Portfolio

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-1.40-green?logo=playwright&logoColor=white)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-4.12-orange)
![Requests](https://img.shields.io/badge/Requests-2.31-lightgrey)
![SQLite](https://img.shields.io/badge/SQLite-3-blue?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

Python developer specializing in **web scraping**, **data extraction**, and **automation**. This repository showcases three production-quality scraping tools demonstrating different techniques — from API integration to browser automation to database-backed lead generation.

---

## Projects

### 1. [Google Maps Business Scraper](01-google-maps-scraper/)

Extract business data from Google Maps with dual API support, automatic pagination, and review extraction.

| Feature | Details |
|---------|---------|
| **Data source** | Google Maps (via SerpAPI or Places API) |
| **Tech** | Python, Requests, Dataclasses |
| **Output** | CSV, JSON (10 fields per business) |
| **Key features** | Pagination, retry with exponential backoff, review extraction, single place lookup |

```bash
python scraper.py --query "restaurants in Miami" --output results.csv
```

---

### 2. [E-Commerce Price Tracker](02-ecommerce-price-tracker/)

Monitor product prices on JavaScript-heavy e-commerce sites using browser automation with anti-bot detection and adaptive rate limiting.

| Feature | Details |
|---------|---------|
| **Data source** | E-commerce product pages (JS-rendered) |
| **Tech** | Python, Playwright, BeautifulSoup |
| **Output** | CSV, JSON (11 fields per product) |
| **Key features** | Adaptive rate limiting, CAPTCHA detection, multi-selector fallback, MD5 deduplication |

```bash
python scraper.py --url "https://example.com/s?k=laptops" --output laptops.csv
```

---

### 3. [Business Lead Generation Tool](03-lead-generation-tool/)

Scrape business directories to build qualified lead lists with quality scoring, SQLite storage, and data enrichment.

| Feature | Details |
|---------|---------|
| **Data source** | Business directories (Yellow Pages style) |
| **Tech** | Python, Requests, BeautifulSoup, SQLite |
| **Output** | CSV, JSON, SQLite database |
| **Key features** | Lead scoring algorithm, UPSERT dedup, website enrichment, filtered export |

```bash
python scraper.py --query "plumbers" --location "London" --output leads.csv
```

---

## Tech Stack

| Technology | Used In | Purpose |
|-----------|---------|---------|
| **Python 3.10+** | All projects | Core language |
| **Playwright** | Price Tracker | Browser automation for JS-rendered pages |
| **BeautifulSoup** | Price Tracker, Lead Gen | HTML parsing |
| **Requests** | Maps Scraper, Lead Gen | HTTP client |
| **SQLite** | Lead Gen | Persistent data storage |
| **Dataclasses** | All projects | Typed data models |
| **Argparse** | All projects | CLI interfaces |

## Common Patterns

All projects share battle-tested scraping patterns:

- **Retry with exponential backoff** — automatic retries on 429/5xx errors
- **Rate limiting** — configurable delays between requests
- **Human-like behavior** — randomized pauses to avoid detection
- **Data deduplication** — hash-based dedup prevents duplicates
- **Clean data models** — structured dataclasses with typed fields
- **Flexible output** — CSV and JSON export
- **Error handling** — graceful degradation on missing fields

## Contact

Available for custom web scraping and data extraction projects.

- **Freelancer.com:** [Your Profile](https://www.freelancer.com/u/ilshatsharapov69-afk)
- **Email:** ilshat.sharapov69@gmail.com
- **GitHub:** [Your GitHub](https://github.com/ilshatsharapov69-afk)
