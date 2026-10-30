"""One-off / reusable diagnostic: search the raw OCDS feed for specific text
(a municipality name, a bid number, anything) regardless of the production
KEYWORDS filter, and print exactly what the feed contains for it --
including the raw milestones/amendments structure, so we can tell apart
"the feed doesn't have this" from "our keyword filter excluded it" from
"our parser is reading the wrong field names".

Usage (env vars, both optional):
  SEARCH_TERMS="Metsimaholo,Sekhukhune,Richmond"   (comma-separated, case-insensitive)
  DEBUG_LOOKBACK_DAYS="60"

Run: python debug_search.py
"""
from __future__ import annotations

import json
import os

from config import load_settings
from filters import matches_keywords
from ocds_client import fetch_releases
from parser import parse_release


def main() -> None:
    settings = load_settings()
    search_terms = [
        t.strip().lower()
        for t in os.environ.get("SEARCH_TERMS", "Metsimaholo,Sekhukhune,Richmond").split(",")
        if t.strip()
    ]
    lookback_days = int(os.environ.get("DEBUG_LOOKBACK_DAYS", "60"))

    print(f"Searching for: {search_terms}")
    print(f"Lookback window: {lookback_days} days")
    print(f"Current KEYWORDS filter: {settings.keywords}")
    print("=" * 70)

    total_releases = 0
    found_count = 0

    for release in fetch_releases(settings.ocds_api_base, lookback_days):
        total_releases += 1
        tender = parse_release(release)
        if tender is None:
            continue

        haystack = f"{tender.buyer_name} {tender.title} {tender.description}".lower()
        hit_terms = [t for t in search_terms if t in haystack]
        if not hit_terms:
            continue

        found_count += 1
        would_match_keywords = matches_keywords(tender, settings.keywords)

        print(f"\nMATCH ({', '.join(hit_terms)}): ocid={tender.ocid}")
        print(f"  Title: {tender.title}")
        print(f"  Buyer: {tender.buyer_name}")
        print(f"  Status: {tender.status}")
        print(f"  Closing date: {tender.closing_date}")
        print(f"  Would pass current KEYWORDS filter: {bool(would_match_keywords)} {would_match_keywords}")
        print(f"  Parsed has_briefing: {tender.has_briefing}  briefing_date: {tender.briefing_date}")
        print(f"  Parsed amendments count: {len(tender.amendments)}")
        print("  --- raw tender.milestones ---")
        print(json.dumps(release.get("tender", {}).get("milestones"), indent=2)[:2000])
        print("  --- raw tender.amendments ---")
        print(json.dumps(release.get("tender", {}).get("amendments"), indent=2)[:2000])
        print("  --- raw top-level release keys ---")
        print(list(release.keys()))
        print("  --- raw tender keys ---")
        print(list(release.get("tender", {}).keys()))

    print("\n" + "=" * 70)
    print(f"Scanned {total_releases} release(s) total. Found {found_count} matching search term(s).")


if __name__ == "__main__":
    main()
