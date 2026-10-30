"""Thin client for the National Treasury eTenders OCDS API.

Docs / interactive schema: https://ocds-api.etenders.gov.za/swagger/index.html

The API is public and needs no API key. Behaviour to know about, confirmed
by running against the live feed:
  - dateFrom and dateTo are both required query parameters (ISO date, e.g. 2026-08-01).
  - Responses can be slow (tens of seconds) and the API is frequently flaky
    mid-pagination -- a 500 Internal Server Error on page 2+ while page 1
    succeeds is common, observed on the majority of real runs, not a rare
    edge case. We page by incrementing PageNumber ourselves rather than
    trusting the response's own `links.next` (also observed unreliable),
    and a single page failing does not stop the whole fetch -- we skip it
    and keep trying subsequent page numbers, since the pages are independent
    windows into the same date range rather than a true single-file stream.
    A page we gave up on after retries means whatever fell on it is missed
    for this run; the next scheduled run's overlapping lookback window is
    what's relied on to eventually pick it up.

If National Treasury tweaks field names, only this file and parser.py should
need updating -- everything downstream works off the plain dict a release
gets parsed into by parser.py.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Iterator

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 90
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
PAGE_SIZE = 50
MAX_CONSECUTIVE_PAGE_FAILURES = 6
MAX_PAGES = 500


class OCDSClientError(RuntimeError):
    pass


def _get_with_retries(url: str, params: dict | None = None) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            logger.warning(
                "OCDS API request failed (attempt %d/%d): %s", attempt, MAX_RETRIES, exc
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise OCDSClientError(f"Giving up on {url} after {MAX_RETRIES} attempts") from last_error


def fetch_releases(api_base: str, lookback_days: int) -> Iterator[dict]:
    """Yield every OCDS release published in the last `lookback_days` days.

    Pages through PageNumber=1, 2, 3, ... until a page comes back with zero
    releases (true end of data) or too many consecutive pages fail outright.
    A single failed page is skipped, not fatal -- unlike a plain byte stream,
    each page is its own independent query, so page 3 can succeed even if
    page 2 just failed.
    """
    date_to = date.today()
    date_from = date_to - timedelta(days=lookback_days)

    page_number = 0
    total_yielded = 0
    consecutive_failures = 0

    while page_number < MAX_PAGES:
        page_number += 1
        logger.info("Fetching OCDS releases page %d ...", page_number)
        params = {
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "PageNumber": page_number,
            "PageSize": PAGE_SIZE,
        }

        try:
            payload = _get_with_retries(api_base, params)
        except OCDSClientError:
            consecutive_failures += 1
            logger.error(
                "Giving up on page %d after retries (%d consecutive page "
                "failure(s)); trying the next page instead of stopping.",
                page_number,
                consecutive_failures,
            )
            if consecutive_failures >= MAX_CONSECUTIVE_PAGE_FAILURES:
                logger.error(
                    "Stopping after %d consecutive page failures; keeping "
                    "the %d release(s) already fetched. The next scheduled "
                    "run's overlapping lookback window will pick up "
                    "anything missed here.",
                    consecutive_failures,
                    total_yielded,
                )
                return
            continue

        consecutive_failures = 0
        releases = payload.get("releases", [])
        logger.info("Page %d returned %d release(s)", page_number, len(releases))
        total_yielded += len(releases)
        yield from releases

        if not releases:
            return

    logger.warning(
        "Hit the %d-page safety cap; stopping with %d release(s) fetched. "
        "If this keeps happening, LOOKBACK_DAYS is probably too wide.",
        MAX_PAGES,
        total_yielded,
    )
