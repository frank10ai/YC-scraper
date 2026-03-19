#!/usr/bin/env python3
"""
Apollo.io Enrichment Script for YC European Companies
Enriches the scraped CSV with founder emails and LinkedIn URLs
using the Apollo.io API (works with the Free plan).

Usage:
    export APOLLO_API_KEY="your-api-key-here"
    python enrich_with_apollo.py

Find your API key at: https://app.apollo.io/#/settings/integrations/api
"""

import csv
import json
import os
import sys
import time

import requests

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
INPUT_CSV = "yc_european_companies.csv"
OUTPUT_CSV = "yc_european_companies_enriched.csv"
CACHE_FILE = "apollo_cache.json"

# Apollo API endpoints
APOLLO_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/search"

# Rate limiting: Apollo Free allows ~50 req/min
REQUEST_DELAY = 1.5  # seconds between requests


def load_cache() -> dict:
    """Load cached results to avoid re-querying companies we already looked up."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    """Save cache to disk."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def search_founders(company_name: str, domain: str = "") -> list[dict]:
    """
    Search Apollo for founders/CEOs of a company.
    Returns list of dicts with name, email, linkedin, title.
    """
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }

    # Search for founders, CEOs, and co-founders
    payload = {
        "api_key": APOLLO_API_KEY,
        "q_organization_name": company_name,
        "person_titles": ["founder", "co-founder", "ceo", "cto"],
        "page": 1,
        "per_page": 5,
    }

    # If we have a domain, use it for more precise matching
    if domain:
        payload["q_organization_domains"] = domain

    try:
        resp = requests.post(
            APOLLO_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code == 429:
            print("    Rate limited, waiting 60s...")
            time.sleep(60)
            resp = requests.post(
                APOLLO_SEARCH_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )

        if resp.status_code != 200:
            print(f"    Apollo API error {resp.status_code}: {resp.text[:200]}")
            return []

        data = resp.json()
        people = data.get("people", [])

        results = []
        for person in people:
            results.append({
                "name": person.get("name", ""),
                "email": person.get("email", ""),
                "linkedin": person.get("linkedin_url", ""),
                "title": person.get("title", ""),
            })

        return results

    except requests.RequestException as e:
        print(f"    Request error: {e}")
        return []


def extract_domain(website: str) -> str:
    """Extract domain from a website URL."""
    if not website:
        return ""
    website = website.strip().lower()
    website = website.replace("https://", "").replace("http://", "")
    website = website.split("/")[0]
    website = website.replace("www.", "")
    return website


def main():
    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY environment variable not set.")
        print()
        print("Steps:")
        print("  1. Go to https://app.apollo.io/#/settings/integrations/api")
        print("  2. Copy your API key")
        print("  3. Run: export APOLLO_API_KEY='your-key-here'")
        print("  4. Then run this script again")
        sys.exit(1)

    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} not found. Run scrape_yc_europe.py first.")
        sys.exit(1)

    # Read input CSV
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        companies = list(reader)

    print(f"Loaded {len(companies)} companies from {INPUT_CSV}")

    # Load cache
    cache = load_cache()
    print(f"Cache has {len(cache)} entries")

    # Enrich each company
    enriched = 0
    skipped = 0

    for i, company in enumerate(companies):
        name = company["Company Name"]
        website = company.get("Website", "")
        domain = extract_domain(website)
        cache_key = f"{name}|{domain}"

        # Already has founder data from YC scraping?
        has_founders = bool(company.get("Founder Names", "").strip())

        # Check cache
        if cache_key in cache:
            founders = cache[cache_key]
            skipped += 1
        else:
            print(f"  [{i+1}/{len(companies)}] {name}...", end=" ")

            founders = search_founders(name, domain)

            if founders:
                print(f"Found {len(founders)} person(s)")
                enriched += 1
            else:
                print("No results")

            # Save to cache regardless of result
            cache[cache_key] = founders
            save_cache(cache)

            time.sleep(REQUEST_DELAY)

        # Update company data
        if founders:
            founder_names = "; ".join(f["name"] for f in founders if f["name"])
            founder_emails = "; ".join(f["email"] for f in founders if f["email"])
            founder_linkedins = "; ".join(f["linkedin"] for f in founders if f["linkedin"])
            founder_titles = "; ".join(f["title"] for f in founders if f["title"])

            # Only overwrite if we didn't already have data
            if not has_founders:
                company["Founder Names"] = founder_names
            if not company.get("Founder LinkedIn Profiles", "").strip():
                company["Founder LinkedIn Profiles"] = founder_linkedins

            # Always add new fields
            company["Founder Emails"] = founder_emails
            company["Founder Titles"] = founder_titles

    print(f"\nEnrichment complete:")
    print(f"  New lookups: {enriched}")
    print(f"  From cache: {skipped}")

    # Write enriched CSV
    fieldnames = [
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
        "Founder Titles",
        "Founder Emails",
        "Founder LinkedIn Profiles",
        "YC Profile URL",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(companies)

    print(f"\nEnriched CSV saved to: {OUTPUT_CSV}")
    print(f"Total companies: {len(companies)}")

    # Stats
    with_email = sum(1 for c in companies if c.get("Founder Emails", "").strip())
    with_linkedin = sum(1 for c in companies if c.get("Founder LinkedIn Profiles", "").strip())
    print(f"  With emails: {with_email}")
    print(f"  With LinkedIn: {with_linkedin}")


if __name__ == "__main__":
    main()
