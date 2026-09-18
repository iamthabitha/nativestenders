"""Run this FIRST, from your own machine, before relying on main.py.

It fetches one page of real releases from the OCDS API and prints the raw
JSON structure of the first release plus what parser.py extracted from it.
The sandbox this project was built in could not reach etenders.gov.za to
verify field names, so parser.py was written defensively (multiple
fallback field names per value). Use this script's output to confirm
everything lined up -- if a field prints as None/empty here but you can
see the real value in the raw JSON dump, that's the line in parser.py to
adjust.

Usage: python inspect_api.py
"""
from __future__ import annotations

import json

from config import load_settings
from ocds_client import fetch_releases
from parser import parse_release


def main() -> None:
    settings = load_settings()
    releases = fetch_releases(settings.ocds_api_base, lookback_days=settings.lookback_days)

    first = next(releases, None)
    if first is None:
        print("No releases returned for this lookback window. Try raising LOOKBACK_DAYS.")
        return

    print("=" * 70)
    print("RAW release JSON (first result):")
    print("=" * 70)
    print(json.dumps(first, indent=2)[:4000])

    print()
    print("=" * 70)
    print("What parser.py extracted from it:")
    print("=" * 70)
    parsed = parse_release(first)
    print(parsed)


if __name__ == "__main__":
    main()
