"""One-off diagnostic: does this OCDS feed ever carry award/outcome data
(who won, award value, award date) or cancellation status, and is there a
dedicated API endpoint for looking up a single ocid's current state rather
than re-scanning date-range pages?

Checks, in order:
  1. Tries a few common Swagger/OpenAPI spec paths to list every endpoint
     the API actually exposes (we've only ever used /api/OCDSReleases).
  2. Scans a window of recent releases and tallies every distinct
     tender.status value seen, and how many releases have a non-empty
     "awards" or "contracts" array.
  3. Prints the full raw JSON of the first release found (if any) that has
     award or contract data, so we can see the real field names.

Run: python debug_awards.py
"""
from __future__ import annotations

import json
import os
from collections import Counter

import requests

from config import load_settings
from ocds_client import fetch_releases
from parser import parse_release

SWAGGER_CANDIDATES = [
    "https://ocds-api.etenders.gov.za/swagger/v1/swagger.json",
    "https://ocds-api.etenders.gov.za/swagger/index.html",
]


def check_swagger() -> None:
    print("=" * 70)
    print("Checking for a Swagger/OpenAPI spec (to find other endpoints) ...")
    for url in SWAGGER_CANDIDATES:
        try:
            response = requests.get(url, timeout=30)
            print(f"\n{url} -> HTTP {response.status_code}")
            if response.status_code == 200 and "json" in response.headers.get("content-type", ""):
                spec = response.json()
                paths = list((spec.get("paths") or {}).keys())
                print(f"  Found {len(paths)} path(s):")
                for path in paths:
                    print(f"    {path}")
            else:
                print(f"  (not usable JSON spec, {len(response.text)} bytes)")
        except requests.RequestException as exc:
            print(f"\n{url} -> request failed: {exc}")


def check_award_data() -> None:
    settings = load_settings()
    lookback_days = int(os.environ.get("DEBUG_LOOKBACK_DAYS", "14"))

    print("\n" + "=" * 70)
    print(f"Scanning releases from the last {lookback_days} days for award/status data ...")

    status_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    total = 0
    with_awards = 0
    with_contracts = 0
    first_award_example = None
    first_contract_example = None

    for release in fetch_releases(settings.ocds_api_base, lookback_days):
        total += 1
        tender = parse_release(release)
        status = tender.status if tender else "(no tender block)"
        status_counts[status] += 1
        for tag in release.get("tag", []) or []:
            tag_counts[tag] += 1

        awards = release.get("awards")
        if awards:
            with_awards += 1
            if first_award_example is None:
                first_award_example = release

        contracts = release.get("contracts")
        if contracts:
            with_contracts += 1
            if first_contract_example is None:
                first_contract_example = release

    print(f"\nScanned {total} release(s) total.")
    print(f"Releases with a non-empty 'awards' array: {with_awards}")
    print(f"Releases with a non-empty 'contracts' array: {with_contracts}")
    print(f"\nDistinct tender.status values seen: {dict(status_counts)}")
    print(f"Distinct release 'tag' values seen: {dict(tag_counts)}")

    if first_award_example:
        print("\n--- First release found with award data (full JSON, truncated) ---")
        print(json.dumps(first_award_example, indent=2)[:4000])
    else:
        print("\nNo release in this window had any award data.")

    if first_contract_example and first_contract_example is not first_award_example:
        print("\n--- First release found with contract data (full JSON, truncated) ---")
        print(json.dumps(first_contract_example, indent=2)[:4000])


if __name__ == "__main__":
    check_swagger()
    check_award_data()
