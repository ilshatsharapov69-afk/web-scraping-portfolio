# Google Maps Business Scraper

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-2.31-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

Extract business data from Google Maps at scale. Supports two API backends (SerpAPI and Google Places API), automatic pagination, review extraction, and export to CSV or JSON.

## Features

- **Dual API support** — SerpAPI (free tier: 100 searches/month) or Google Places API
- **Automatic pagination** — collects hundreds of results across multiple pages
- **Review extraction** — grab top 5 customer reviews per business
- **Retry with exponential backoff** — handles rate limits (429) and server errors gracefully
- **Single place lookup** — look up any business by its Google Place ID
- **Flexible output** — export to CSV or JSON
- **Clean data model** — structured `Business` dataclass with 10 fields

## Quick Start

```bash
git clone https://github.com/ilshatsharapov69-afk/web-scraping-portfolio.git
cd web-scraping-portfolio/01-google-maps-scraper
pip install -r requirements.txt
```

**Run a search:**
```bash
# Using SerpAPI (default)
export SERPAPI_API_KEY=your_key_here
python scraper.py --query "restaurants in New York" --output results.csv

# Using Google Places API
python scraper.py --query "plumbers in London" --method places --api-key YOUR_KEY

# Include reviews + JSON output
python scraper.py --query "dentists in Dallas" --include-reviews --format json

# Look up a single business
python scraper.py --place-id ChIJN1t_tDeuEmsRUsoyG83frY4
```

## Sample Output

| Name | Address | Rating | Reviews | Phone | Website |
|------|---------|--------|---------|-------|---------|
| Joe's Pizza | 7 Carmine St, New York | 4.5 | 8,743 | (212) 366-1182 | joespizzanyc.com |
| Le Bernardin | 155 W 51st St, New York | 4.7 | 4,521 | (212) 554-1515 | le-bernardin.com |
| Peter Luger Steak House | 178 Broadway, Brooklyn | 4.4 | 12,890 | (718) 387-7400 | peterluger.com |
| Katz's Delicatessen | 205 E Houston St, New York | 4.6 | 15,234 | (212) 254-2246 | katzsdelicatessen.com |
| Levain Bakery | 167 W 74th St, New York | 4.5 | 6,312 | (917) 464-3769 | levainbakery.com |
| Di Fara Pizza | 1424 Avenue J, Brooklyn | 4.3 | 3,876 | (718) 258-1367 | difaranyc.com |
| Shake Shack | Madison Ave, New York | 4.2 | 9,451 | (212) 889-6600 | shakeshack.com |
| Los Tacos No.1 | 75 9th Ave, New York | 4.7 | 5,634 | (212) 256-0343 | lostacos1.com |
| Momofuku Noodle Bar | 171 1st Ave, New York | 4.3 | 4,102 | (212) 777-7773 | momofukunoodlebar.com |
| The Halal Guys | 53rd St & 6th Ave, New York | 4.5 | 18,432 | (347) 527-1505 | thehalalguys.com |

Full sample data (20 records): [`sample_data/restaurants_nyc.csv`](sample_data/restaurants_nyc.csv)

## How It Works

1. **Search** — sends paginated queries to the selected API
2. **Parse** — extracts business fields (name, address, phone, rating, coordinates, etc.)
3. **Enrich** — optionally fetches detailed reviews per business
4. **Export** — saves structured data to CSV or JSON

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────┐
│  API Query   │────>│  Parse Data  │────>│  Enrich w/   │────>│  Export   │
│  + Paginate  │     │  (10 fields) │     │  Reviews     │     │  CSV/JSON │
└─────────────┘     └─────────────┘     └─────────────┘     └──────────┘
```

## Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Business name |
| `address` | string | Full formatted address |
| `phone` | string | Phone number |
| `rating` | float | Star rating (1.0–5.0) |
| `reviews_count` | int | Total number of reviews |
| `review_texts` | string | Top review snippets (semicolon-separated) |
| `website` | string | Business website URL |
| `latitude` | float | GPS latitude |
| `longitude` | float | GPS longitude |
| `place_id` | string | Google Place ID |

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--query` / `-q` | — | Search query (e.g., "restaurants in Miami") |
| `--place-id` | — | Google Place ID for single lookup |
| `--output` / `-o` | `results.csv` | Output file path |
| `--method` / `-m` | `serpapi` | API backend: `serpapi` or `places` |
| `--api-key` / `-k` | env var | API key (or set via environment) |
| `--max-results` | `100` | Maximum businesses to collect |
| `--include-reviews` | `false` | Fetch top review texts |
| `--format` / `-f` | `csv` | Output format: `csv` or `json` |

## Tech Stack

- **Python 3.10+** — core language
- **Requests** — HTTP client with timeout and retry support
- **Dataclasses** — clean, typed data models
- **Argparse** — flexible CLI interface

---

Built by [Ilshat Sharapov](https://www.freelancer.com/u/ilshatsharapov69-afk) — available for custom web scraping projects.
