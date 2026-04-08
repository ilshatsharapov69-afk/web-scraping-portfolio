# Business Lead Generation Tool

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-4.12-orange)
![SQLite](https://img.shields.io/badge/SQLite-3-blue?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

Scrape business directories to build qualified lead lists with contact details, quality scoring, and persistent SQLite storage. Supports data enrichment, deduplication, and filtered export.

## Features

- **Lead quality scoring** — weighted algorithm (0.0–1.0) based on data completeness (phone, email, website, rating, reviews)
- **SQLite persistent storage** — leads survive across runs with UPSERT logic (insert or update)
- **Content deduplication** — MD5 hash prevents duplicate entries across scraping sessions
- **Data enrichment** — optionally visits business websites to extract emails and phone numbers
- **Multi-page pagination** — automatically follows result pages
- **Filtered export** — query stored leads by score, category, or city
- **Retry with backoff** — handles network errors and rate limits gracefully
- **Human-like delays** — randomized pauses between requests (2–5s)
- **Three modes** — scrape, export, or view statistics

## Quick Start

```bash
git clone https://github.com/ilshatsharapov69-afk/web-scraping-portfolio.git
cd web-scraping-portfolio/03-lead-generation-tool
pip install -r requirements.txt
```

**Scrape leads:**
```bash
# Basic scraping
python scraper.py --query "plumbers" --location "London" --output leads.csv

# With data enrichment (visits websites for emails)
python scraper.py --query "restaurants" --location "Manchester" --max-pages 10 --enrich

# Export only high-quality leads
python scraper.py --export --min-score 0.7 --output qualified_leads.csv

# View database stats
python scraper.py --stats
```

## Sample Output

| Business | City | Phone | Email | Website | Rating | Reviews | Score |
|----------|------|-------|-------|---------|--------|---------|-------|
| Thames Plumbing Services | London | +44 20 7946 0958 | info@thamesplumbing.co.uk | thamesplumbing.co.uk | 4.8 | 127 | 0.95 |
| Mayfair Pipes & Heating | London | +44 20 7890 1234 | mayfair@pipesheating.com | pipesheating.com | 4.9 | 92 | 0.95 |
| Westminster Water Works | London | +44 20 8123 4567 | contact@westwaterworks.com | westwaterworks.com | 4.7 | 198 | 0.95 |
| QuickFix Plumbers | London | +44 20 7234 5678 | jobs@quickfixplumbers.com | quickfixplumbers.com | 4.5 | 203 | 0.95 |
| Shoreditch Pipe Works | London | +44 20 8890 1234 | work@shoreditchpipes.com | shoreditchpipes.com | 4.8 | 165 | 0.95 |
| Greenway Heating Ltd | London | +44 20 7345 6789 | hello@greenway-heating.co.uk | greenway-heating.co.uk | 4.7 | 156 | 0.95 |
| Notting Hill Plumbing | London | +44 20 8567 8901 | hello@nhplumbing.co.uk | nhplumbing.co.uk | 4.6 | 134 | 0.95 |
| Hackney Home Services | London | +44 20 8012 3456 | info@hackneyhome.co.uk | hackneyhome.co.uk | 4.5 | 112 | 0.95 |
| Southbank Plumbing Co | London | +44 20 7678 9012 | — | southbankplumbing.co.uk | 4.6 | 178 | 0.75 |
| Canary Wharf Maintenance | London | +44 20 8345 6789 | — | cwmaintenance.co.uk | 4.0 | 15 | 0.70 |

Full sample data (20 records): [`sample_data/businesses_london.csv`](sample_data/businesses_london.csv)

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  Scrape       │────>│  Enrich       │────>│  Score &      │────>│  Store    │
│  Directory    │     │  (optional)   │     │  Deduplicate  │     │  SQLite   │
│  Pages        │     │  Visit sites  │     │  MD5 hash     │     │  + Export │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────┘
```

### Lead Scoring Algorithm

Each field contributes a weighted score based on its value for lead qualification:

| Field | Weight | Why It Matters |
|-------|--------|----------------|
| Has phone | 20% | Direct contact channel |
| Has email | 20% | Digital outreach |
| Has website | 15% | Business legitimacy |
| Has rating | 15% | Active on platforms |
| Has description | 10% | Engagement signal |
| Has address | 10% | Physical presence |
| Review volume | 10% | Popularity (50+ = full score) |

**Score examples:**
- 0.95 — phone + email + website + rating + reviews + address
- 0.75 — phone + website + rating (no email)
- 0.45 — phone + address only

### Database Schema

```sql
CREATE TABLE leads (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT, city TEXT,
    phone TEXT, email TEXT, website TEXT,
    category TEXT,
    rating REAL, reviews_count INTEGER,
    lead_score REAL,
    content_hash TEXT UNIQUE,     -- deduplication key
    first_seen_at TEXT,           -- preserved across updates
    last_seen_at TEXT             -- updated on re-scrape
);
```

**UPSERT logic:** On duplicate hash, updates `last_seen_at` and merges new data with `COALESCE` — preserves existing values while adding newly discovered fields.

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--query` / `-q` | — | Business type (e.g., "plumbers") |
| `--location` / `-l` | — | City or area (e.g., "London") |
| `--max-pages` | `10` | Max directory pages to scrape |
| `--enrich` | `false` | Visit websites for extra contact data |
| `--export` | — | Export from DB without scraping |
| `--min-score` | `0.0` | Min lead score for export |
| `--filter-category` | — | Filter by business category |
| `--filter-city` | — | Filter by city |
| `--output` / `-o` | `leads.csv` | Output file path |
| `--format` / `-f` | `csv` | Output: `csv` or `json` |
| `--db` | `leads.db` | SQLite database file |
| `--stats` | — | Print database statistics |

## Tech Stack

- **Python 3.10+** — core language
- **Requests** — HTTP client with retry support
- **BeautifulSoup** — HTML parsing with multi-selector fallback
- **SQLite** — persistent lead storage with WAL mode
- **Hashlib** — MD5 content deduplication

---

Built by [Ilshat Sharapov](https://www.freelancer.com/u/ilshatsharapov69-afk) — available for custom web scraping projects.
