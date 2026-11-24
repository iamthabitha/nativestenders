"""Best-effort extraction of compulsory briefing / site meeting mentions
from a tender's PDF document(s).

This feed never carries structured briefing data (confirmed: no
"milestones" field exists at all in any release we've checked), but the
tender PDF itself often states the briefing date and venue in plain text
-- confirmed against a real tender (Dr JS Moroka Local Municipality,
JSM-COMMS-AD01/26-29): "A Compulsory briefing session meeting will be
held on 23 November 2026 at ... Ga-Phahla Community Hall, commencing at
10H30 to 11H00."

Deliberately does NOT search for "compulsory" alone -- that word appears
constantly in unrelated boilerplate ("COMPULSORY BID DOCUMENTS",
"compulsory returnable documents", etc.), confirmed by testing against a
real tender PDF where it produced a dozen false matches. "briefing" and
similar meeting-specific terms are much more precise anchors.

Downloading and parsing PDFs is slow and sometimes unreliable (another
government domain, www.etenders.gov.za, with its own flakiness), so this
is only ever called for tenders we're about to email about (a handful per
run), never across the full fetched set. Every failure mode (download
error, non-PDF content, a scanned image with no text layer, wrong
encoding) is swallowed -- this is a nice-to-have enrichment, never
something that should block sending the underlying alert.
"""
from __future__ import annotations

import io
import logging
import re

import requests

logger = logging.getLogger(__name__)

BRIEFING_ANCHORS = [
    "briefing",
    "site meeting",
    "site visit",
    "pre-bid meeting",
    "clarification meeting",
]

REQUEST_TIMEOUT_SECONDS = 30
MAX_DOCUMENT_BYTES = 20_000_000
MAX_DOCUMENTS_TO_SCAN = 3
SNIPPET_CHARS_BEFORE = 150
SNIPPET_CHARS_AFTER = 300


def _extract_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _find_snippets(text: str) -> list[str]:
    lower_text = text.lower()
    snippets: list[str] = []
    seen = set()
    for anchor in BRIEFING_ANCHORS:
        for match in re.finditer(re.escape(anchor), lower_text):
            start = max(0, match.start() - SNIPPET_CHARS_BEFORE)
            end = min(len(text), match.end() + SNIPPET_CHARS_AFTER)
            snippet = " ".join(text[start:end].split())
            if snippet and snippet not in seen:
                seen.add(snippet)
                snippets.append(snippet)
    return snippets


def find_briefing_mentions(document_urls: list[str]) -> list[str]:
    """Best-effort: download up to MAX_DOCUMENTS_TO_SCAN PDFs and return any
    text snippets mentioning a briefing/site meeting. Returns [] on any
    failure or if nothing is found -- never raises."""
    snippets: list[str] = []
    for url in document_urls[:MAX_DOCUMENTS_TO_SCAN]:
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            if len(response.content) > MAX_DOCUMENT_BYTES:
                logger.info("Skipping PDF scan for %s: too large", url)
                continue
            text = _extract_text(response.content)
        except Exception:
            logger.info("Could not extract text from %s for briefing scan", url, exc_info=True)
            continue

        found = _find_snippets(text)
        if found:
            snippets.extend(found)
            break  # good enough -- avoid downloading every document once we have an answer

    return snippets
