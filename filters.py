"""Keyword matching against a tender's title + description."""
from __future__ import annotations

from parser import TenderRecord


def matches_keywords(tender: TenderRecord, keywords: list[str]) -> list[str]:
    """Returns the subset of `keywords` found in the tender's text (case-insensitive)."""
    text = tender.searchable_text
    return [kw for kw in keywords if kw.lower() in text]
