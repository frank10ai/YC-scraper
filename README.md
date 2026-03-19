# YC European Companies Scraper

Scrapes Y Combinator-backed European companies (2020–2025 batches) and exports them to CSV and JSON.

## Data Collected

| Column | Source |
|--------|--------|
| Company Name | YC Directory (via yc-oss API) |
| Batch | YC Directory |
| Location | YC Directory |
| Description | YC Directory |
| Industry | YC Directory |
| Tags | YC Directory |
| Website | YC Directory |
| Team Size | YC Directory |
| Founder Names | YC Company Profile Pages |
| Founder LinkedIn | YC Company Profile Pages |

## Usage

```bash
# Install dependencies
pip install requests beautifulsoup4

# Run with founder data (requires access to ycombinator.com)
python scrape_yc_europe.py

# Run without founder data (uses only GitHub API)
python scrape_yc_europe.py --no-founders
```

Set `GITHUB_TOKEN` env var to increase GitHub API rate limits (60 → 5000 req/hr).

## Output

- `yc_european_companies.csv` — Spreadsheet-ready format
- `yc_european_companies.json` — Structured JSON with full details

## Data Source

Company data is fetched from the [yc-oss/api](https://github.com/yc-oss/api) GitHub repository, which mirrors YC's Algolia search index daily. Founder data is scraped from individual YC company profile pages.