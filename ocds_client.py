"""Thin client for the National Treasury eTenders OCDS API.

Docs / interactive schema: https://ocds-api.etenders.gov.za/swagger/index.html

The API is public and needs no API key. Two quirks to know about, based on
the OCDS API's own published behaviour:
  - dateFrom and dateTo are both required query parameters (ISO date, e.g. 2026-08-01).
  - Responses can be slow (tens of seconds) and results are paginated through
    a `links.next` URL in the response body, not a page-number you increment.

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

    Follows the API's own pagination (`links.next`) until exhausted.
    """
    date_to = date.today()
    date_from = date_to - timedelta(days=lookback_days)

    url = api_base
    params: dict | None = {
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "PageNumber": 1,
        "PageSize": 100,
    }

    page = 0
    total_yielded = 0
    while url:
        page += 1
        logger.info("Fetching OCDS releases page %d ...", page)
        try:
            payload = _get_with_retries(url, params)
        except OCDSClientError:
            logger.error(
                "Giving up on page %d after retries; keeping the %d release(s) "
                "already fetched from earlier pages. The next scheduled run's "
                "overlapping lookback window will pick up anything missed here.",
                page,
                total_yielded,
            )
            return
        params = None  # subsequent requests use the full `next` URL as-is

        releases = payload.get("releases", [])
        logger.info("Page %d returned %d release(s)", page, len(releases))
        total_yielded += len(releases)
        yield from releases

        url = (payload.get("links") or {}).get("next")
