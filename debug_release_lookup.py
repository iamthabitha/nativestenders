"""One-off diagnostic: look up specific ocids directly via the newly-found
per-release endpoint (/api/OCDSReleases/release/{ocid}), discovered via the
API's Swagger spec in debug_awards.py. Much faster than a date-range scan
since it's one request per ocid, not pages of everything.

Checks whether an already-closed tender's compiled record ever gets
updated with award/contract/status data after its closing date -- i.e.
whether outcome tracking is feasible at all with this feed.

Usage: OCIDS="ocds-9t57fa-170867,ocds-9t57fa-171550" python debug_release_lookup.py
Defaults to a few known already-closed tenders from the live database.
"""
from __future__ import annotations

import json
import os

import requests

DEFAULT_OCIDS = [
    "ocds-9t57fa-170867",  # TDR28/2026/2027, closed 2026-10-23
    "ocds-9t57fa-171324",  # CSIR EOI 8131/07/10/2026, closed 2026-10-07
    "ocds-9t57fa-171387",  # GSH5/2026, closed 2026-10-22
    "ocds-9t57fa-171550",  # SO/241/09/2026, closed 2026-09-29 (oldest closed)
]

BASE = "https://ocds-api.etenders.gov.za/api/OCDSReleases/release"


def main() -> None:
    ocids = [o.strip() for o in os.environ.get("OCIDS", "").split(",") if o.strip()] or DEFAULT_OCIDS

    for ocid in ocids:
        url = f"{BASE}/{ocid}"
        print("=" * 70)
        print(f"GET {url}")
        try:
            response = requests.get(url, timeout=60)
            print(f"HTTP {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(json.dumps(data, indent=2)[:6000])
            else:
                print(response.text[:1000])
        except requests.RequestException as exc:
            print(f"Request failed: {exc}")
        print()


if __name__ == "__main__":
    main()
