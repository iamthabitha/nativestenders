"""One-off: run the real production pipeline (fetch -> parse -> scan PDF ->
build email) for one specific ocid, end to end, without touching storage or
actually sending an email. Confirms pdf_scan.py works against the real
network path (a real PDF download from www.etenders.gov.za via a real
OCDS API lookup), not just a local mock.

Usage: OCIDS="ocds-9t57fa-178943" python debug_validate_briefing.py
"""
from __future__ import annotations

import os

import requests

from notifier import TenderEvent, build_body, build_subject
from parser import parse_release
from pdf_scan import find_briefing_mentions
from storage import DiffResult

BASE = "https://ocds-api.etenders.gov.za/api/OCDSReleases/release"
DEFAULT_OCID = "ocds-9t57fa-178943"  # Dr JS Moroka, JSM-COMMS-AD01/26-29


def main() -> None:
    ocid = os.environ.get("OCIDS", DEFAULT_OCID).split(",")[0].strip()
    url = f"{BASE}/{ocid}"
    print(f"GET {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    release = response.json()

    tender = parse_release(release)
    if tender is None:
        print("parse_release returned None -- no tender block in this release")
        return

    print(f"Parsed tender: {tender.title} / {tender.buyer_name}")
    print(f"Documents: {[d.url for d in tender.documents]}")

    print("\nRunning pdf_scan.find_briefing_mentions on the real document(s) ...")
    snippets = find_briefing_mentions([d.url for d in tender.documents])
    print(f"Found {len(snippets)} snippet(s).")

    event = TenderEvent(
        tender=tender,
        matched_keywords=["advertising"],
        diff=DiffResult(is_new=True, is_changed=False),
        briefing_snippets=snippets,
    )

    print("\n" + "=" * 70)
    print("SUBJECT:", build_subject(event))
    print()
    print(build_body(event))


if __name__ == "__main__":
    main()
