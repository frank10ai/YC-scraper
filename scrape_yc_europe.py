#!/usr/bin/env python3
"""
YC European Companies Scraper
Scrapes Y Combinator companies from Europe (2020-2025 batches)
and exports to CSV with founder + LinkedIn data.

Data sources:
- Company data: yc-oss GitHub API (https://github.com/yc-oss/api)
- Founder data: YC company profile pages (ycombinator.com)
"""

import csv
import json
import time
import base64
import re
import sys
import os
import requests
from urllib.parse import quote

# Batches to scrape (matching the user's URL filters)
BATCHES = [
    "fall-2025", "summer-2025", "spring-2025", "winter-2025",
    "fall-2024", "summer-2024", "winter-2024",
    "summer-2023", "winter-2023",
    "summer-2022", "winter-2022",
    "summer-2021", "winter-2021",
    "summer-2020",
]

GITHUB_API_BASE = "https://api.github.com/repos/yc-oss/api/contents"
OUTPUT_CSV = "yc_european_companies.csv"
OUTPUT_JSON = "yc_european_companies.json"

# Rate limiting for GitHub API (unauthenticated: 60 req/hr)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def github_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def fetch_batch_companies(batch_name: str) -> list[dict]:
    """Fetch all companies from a specific YC batch via GitHub API."""
    url = f"{GITHUB_API_BASE}/batches/{batch_name}.json"
    resp = requests.get(url, headers=github_headers(), timeout=30)
    if resp.status_code == 404:
        print(f"  Batch {batch_name} not found, skipping.")
        return []
    resp.raise_for_status()
    data = resp.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content)


def filter_european(companies: list[dict]) -> list[dict]:
    """Filter companies that have 'Europe' in their regions."""
    return [c for c in companies if any("Europe" in r for r in c.get("regions", []))]


def fetch_founders_from_yc(slug: str) -> list[dict]:
    """
    Fetch founder info from the YC company profile page.
    Returns list of dicts with 'name' and 'linkedin' keys.

    This requires direct access to ycombinator.com which may not work
    in all environments. Falls back gracefully.
    """
    url = f"https://www.ycombinator.com/companies/{slug}"
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })
        if resp.status_code != 200:
            return []

        html = resp.text

        # YC embeds company data as JSON in a Next.js script tag
        # Look for founder data in the page
        founders = []

        # Method 1: Parse Next.js __NEXT_DATA__ JSON
        next_data_match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html, re.DOTALL
        )
        if next_data_match:
            try:
                next_data = json.loads(next_data_match.group(1))
                props = next_data.get("props", {}).get("pageProps", {})
                company_data = props.get("company", {})
                for founder in company_data.get("founders", []):
                    name = founder.get("full_name", "")
                    linkedin = founder.get("linkedin_url", "")
                    if name:
                        founders.append({"name": name, "linkedin": linkedin or ""})
                return founders
            except (json.JSONDecodeError, KeyError):
                pass

        # Method 2: Parse from HTML using regex patterns
        # Look for founder sections with LinkedIn links
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # YC profile pages have founder cards with name + LinkedIn
        founder_sections = soup.find_all("div", class_=re.compile(r"founder", re.I))
        for section in founder_sections:
            name_el = section.find(["h3", "h4", "a", "span"])
            linkedin_el = section.find("a", href=re.compile(r"linkedin\.com"))
            if name_el:
                founders.append({
                    "name": name_el.get_text(strip=True),
                    "linkedin": linkedin_el["href"] if linkedin_el else ""
                })

        return founders

    except requests.RequestException:
        return []


def main():
    print("=" * 60)
    print("YC European Companies Scraper")
    print("=" * 60)

    all_companies = []
    skip_founders = "--no-founders" in sys.argv

    # Step 1: Fetch company data from all batches
    print(f"\nFetching companies from {len(BATCHES)} batches...")
    for batch in BATCHES:
        print(f"\n  Batch: {batch}")
        try:
            companies = fetch_batch_companies(batch)
            european = filter_european(companies)
            print(f"    Total: {len(companies)}, European: {len(european)}")
            all_companies.extend(european)
        except Exception as e:
            print(f"    Error: {e}")
        time.sleep(1)  # Rate limit for GitHub API

    print(f"\nTotal European companies found: {len(all_companies)}")

    # Deduplicate by company ID
    seen_ids = set()
    unique_companies = []
    for c in all_companies:
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            unique_companies.append(c)
    all_companies = unique_companies
    print(f"After deduplication: {len(all_companies)}")

    # Step 2: Fetch founder data from YC profile pages
    if not skip_founders:
        print(f"\nFetching founder data from YC profiles...")
        for i, company in enumerate(all_companies):
            slug = company["slug"]
            print(f"  [{i+1}/{len(all_companies)}] {company['name']}...", end=" ")
            founders = fetch_founders_from_yc(slug)
            company["founders"] = founders
            if founders:
                print(f"Found {len(founders)} founder(s)")
            else:
                print("No founder data")
            time.sleep(0.5)  # Be polite
    else:
        print("\nSkipping founder data (--no-founders flag)")
        for company in all_companies:
            company["founders"] = []

    # Step 3: Export to CSV
    print(f"\nExporting to {OUTPUT_CSV}...")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Company Name",
            "Batch",
            "Location",
            "Description",
            "Industry",
            "Tags",
            "Website",
            "Team Size",
            "Status",
            "Stage",
            "Founder Names",
            "Founder LinkedIn Profiles",
            "YC Profile URL",
        ])
        for c in all_companies:
            founder_names = "; ".join(f["name"] for f in c.get("founders", []))
            founder_linkedins = "; ".join(
                f["linkedin"] for f in c.get("founders", []) if f.get("linkedin")
            )
            writer.writerow([
                c["name"],
                c.get("batch", ""),
                c.get("all_locations", ""),
                c.get("one_liner", ""),
                " | ".join(c.get("industries", [])),
                ", ".join(c.get("tags", [])),
                c.get("website", ""),
                c.get("team_size", ""),
                c.get("status", ""),
                c.get("stage", ""),
                founder_names,
                founder_linkedins,
                c.get("url", ""),
            ])

    # Step 4: Export to JSON (for programmatic use)
    print(f"Exporting to {OUTPUT_JSON}...")
    export_data = []
    for c in all_companies:
        export_data.append({
            "name": c["name"],
            "batch": c.get("batch", ""),
            "location": c.get("all_locations", ""),
            "description": c.get("one_liner", ""),
            "long_description": c.get("long_description", ""),
            "industry": c.get("industries", []),
            "tags": c.get("tags", []),
            "website": c.get("website", ""),
            "team_size": c.get("team_size", ""),
            "status": c.get("status", ""),
            "stage": c.get("stage", ""),
            "founders": c.get("founders", []),
            "yc_url": c.get("url", ""),
        })
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"\nDone! {len(all_companies)} companies exported.")
    print(f"  CSV: {OUTPUT_CSV}")
    print(f"  JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
