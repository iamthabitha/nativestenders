"""Entry point: fetch recent OCDS releases, filter by keyword, diff against
what we've already alerted on, and email anything new or changed.

Run manually:      python main.py
Run on a schedule:  see .github/workflows/scrape.yml
"""
from __future__ import annotations

import logging
import sys

from config import load_settings
from filters import matches_keywords
from notifier import TenderEvent, build_body, build_subject, send_email
from ocds_client import fetch_releases
from parser import parse_release
from pdf_scan import find_briefing_mentions
from storage import TenderStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def run() -> int:
    settings = load_settings()
    store = TenderStore(settings.db_path)

    releases = list(fetch_releases(settings.ocds_api_base, settings.lookback_days))
    logger.info("Fetched %d release(s) in the lookback window", len(releases))

    events: list[TenderEvent] = []
    for release in releases:
        tender = parse_release(release)
        if tender is None:
            continue

        matched = matches_keywords(tender, settings.keywords)
        if not matched:
            continue

        diff = store.check_and_record(tender)
        if diff.is_new or diff.is_changed:
            events.append(TenderEvent(tender=tender, matched_keywords=matched, diff=diff))

    logger.info("%d matching tender event(s) to alert on", len(events))

    for event in events:
        try:
            event.briefing_snippets = find_briefing_mentions(
                [doc.url for doc in event.tender.documents]
            )
        except Exception:
            logger.exception(
                "Briefing PDF scan failed for OCID %s -- sending alert without it",
                event.tender.ocid,
            )

        try:
            send_email(
                gmail_address=settings.gmail_address,
                gmail_app_password=settings.gmail_app_password,
                recipients=settings.alert_recipients,
                subject=build_subject(event),
                body=build_body(event),
            )
        except Exception:
            logger.exception("Failed to send alert for OCID %s", event.tender.ocid)

    return 0


if __name__ == "__main__":
    sys.exit(run())
