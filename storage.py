"""SQLite-backed memory of which tenders we've already alerted on.

Keeps things simple on purpose (stdlib sqlite3, one table, no ORM) since
this is a small single-user tool. `check_and_record` is the one function
main.py needs: give it a parsed TenderRecord, get back what (if anything)
changed since last time.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from parser import Document, TenderRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_tenders (
    ocid TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    buyer_name TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL,
    closing_date TEXT,
    amendment_count INTEGER NOT NULL DEFAULT 0,
    document_urls TEXT NOT NULL DEFAULT '[]',
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
    new_documents: list[Document] = field(default_factory=list)


class TenderStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        with self._connect() as conn:
            conn.execute(SCHEMA)
            for migration in (
                "ALTER TABLE seen_tenders ADD COLUMN buyer_name TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE seen_tenders ADD COLUMN document_urls TEXT NOT NULL DEFAULT '[]'",
            ):
                try:
                    conn.execute(migration)
                except sqlite3.OperationalError:
                    pass  # already has the column -- fine for a DB created before this field existed

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
        current_doc_urls = tender.document_urls

        with self._connect() as conn:
            row = conn.execute(
                "SELECT fingerprint, closing_date, amendment_count, document_urls "
                "FROM seen_tenders WHERE ocid = ?",
                (tender.ocid,),
            ).fetchone()

            if row is None:
                conn.execute(
                    "INSERT INTO seen_tenders (ocid, title, buyer_name, fingerprint, closing_date, "
                    "amendment_count, document_urls) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        tender.ocid,
                        tender.title,
                        tender.buyer_name,
                        tender.fingerprint,
                        tender.closing_date,
                        len(tender.amendments),
                        json.dumps(current_doc_urls),
                    ),
                )
                return DiffResult(is_new=True, is_changed=False)

            old_fingerprint, old_closing_date, old_amendment_count, old_doc_urls_json = row
            old_doc_urls = set(json.loads(old_doc_urls_json or "[]"))
            new_documents = [doc for doc in tender.documents if doc.url not in old_doc_urls]

            changed = old_fingerprint != tender.fingerprint or bool(new_documents)
            if changed:
                conn.execute(
                    "UPDATE seen_tenders SET fingerprint = ?, closing_date = ?, "
                    "amendment_count = ?, document_urls = ?, last_updated_at = datetime('now') "
                    "WHERE ocid = ?",
                    (
                        tender.fingerprint,
                        tender.closing_date,
                        len(tender.amendments),
                        json.dumps(current_doc_urls),
                        tender.ocid,
                    ),
                )
            return DiffResult(
                is_new=False,
                is_changed=changed,
                previous_closing_date=old_closing_date,
                previous_amendment_count=old_amendment_count,
                new_documents=new_documents,
            )
