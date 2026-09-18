"""SQLite-backed memory of which tenders we've already alerted on.

Keeps things simple on purpose (stdlib sqlite3, one table, no ORM) since
this is a small single-user tool. `check_and_record` is the one function
main.py needs: give it a parsed TenderRecord, get back what (if anything)
changed since last time.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from parser import TenderRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_tenders (
    ocid TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    closing_date TEXT,
    amendment_count INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass
class DiffResult:
    is_new: bool
    is_changed: bool
    previous_closing_date: str | None = None
    previous_amendment_count: int = 0


class TenderStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        with self._connect() as conn:
            conn.execute(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def check_and_record(self, tender: TenderRecord) -> DiffResult:
        """Compares `tender` against what's stored, then upserts the new state.

        Must be called at most once per tender per run, in the order you
        want "new" vs "changed" evaluated -- it mutates storage immediately.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT fingerprint, closing_date, amendment_count FROM seen_tenders WHERE ocid = ?",
                (tender.ocid,),
            ).fetchone()

            if row is None:
                conn.execute(
                    "INSERT INTO seen_tenders (ocid, title, fingerprint, closing_date, amendment_count) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        tender.ocid,
                        tender.title,
                        tender.fingerprint,
                        tender.closing_date,
                        len(tender.amendments),
                    ),
                )
                return DiffResult(is_new=True, is_changed=False)

            old_fingerprint, old_closing_date, old_amendment_count = row
            changed = old_fingerprint != tender.fingerprint
            if changed:
                conn.execute(
                    "UPDATE seen_tenders SET fingerprint = ?, closing_date = ?, "
                    "amendment_count = ?, last_updated_at = datetime('now') WHERE ocid = ?",
                    (
                        tender.fingerprint,
                        tender.closing_date,
                        len(tender.amendments),
                        tender.ocid,
                    ),
                )
            return DiffResult(
                is_new=False,
                is_changed=changed,
                previous_closing_date=old_closing_date,
                previous_amendment_count=old_amendment_count,
            )
