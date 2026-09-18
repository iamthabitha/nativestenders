"""Turns one raw OCDS release dict into a flat, easy-to-use TenderRecord.

Written defensively: National Treasury's feed mostly follows the OCDS
standard field names, but this pulls from a couple of plausible alternate
spots for each field so a minor schema difference doesn't crash the whole
run. Run `python inspect_api.py` against the live API to see the real
shape and adjust the `.get(...)` chains below if something comes back empty.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Document:
    title: str
    url: str


@dataclass
class Amendment:
    date: str | None
    description: str


@dataclass
class TenderRecord:
    ocid: str
    release_id: str
    release_date: str | None
    title: str
    description: str
    buyer_name: str
    status: str
    date_published: str | None
    closing_date: str | None
    briefing_date: str | None
    briefing_is_compulsory: bool
    has_briefing: bool
    documents: list[Document] = field(default_factory=list)
    amendments: list[Amendment] = field(default_factory=list)

    @property
    def searchable_text(self) -> str:
        return f"{self.title}\n{self.description}".lower()

    @property
    def fingerprint(self) -> str:
        """Cheap signature used to detect 'something changed' between runs."""
        return "|".join(
            [
                str(self.closing_date),
                str(self.status),
                str(len(self.amendments)),
                str(self.briefing_date),
            ]
        )


def _first_nonempty(*values):
    for value in values:
        if value:
            return value
    return None


def _extract_briefing(milestones: list[dict]) -> tuple[str | None, bool, bool]:
    """Returns (briefing_date, is_compulsory, has_briefing)."""
    for milestone in milestones or []:
        title = str(milestone.get("title") or "").lower()
        description = str(milestone.get("description") or "").lower()
        blob = f"{title} {description}"
        if "briefing" in blob or "site meeting" in blob or "site visit" in blob:
            due_date = _first_nonempty(milestone.get("dueDate"), milestone.get("date"))
            is_compulsory = "compulsory" in blob or "mandatory" in blob
            return due_date, is_compulsory, True
    return None, False, False


def _extract_documents(documents: list[dict]) -> list[Document]:
    result = []
    for doc in documents or []:
        title = _first_nonempty(doc.get("title"), doc.get("description"), "Tender document")
        url = _first_nonempty(doc.get("url"), doc.get("documentUrl"), doc.get("link"))
        if url:
            result.append(Document(title=title, url=url))
    return result


def _extract_amendments(amendments: list[dict]) -> list[Amendment]:
    result = []
    for amendment in amendments or []:
        description = _first_nonempty(
            amendment.get("description"),
            amendment.get("rationale"),
            "Amendment / erratum notice",
        )
        result.append(Amendment(date=amendment.get("date"), description=description))
    return result


def parse_release(release: dict) -> TenderRecord | None:
    tender = release.get("tender")
    if not tender:
        return None

    buyer = _first_nonempty(
        release.get("buyer"),
        tender.get("procuringEntity"),
    ) or {}
    if isinstance(buyer, dict):
        buyer_name = _first_nonempty(buyer.get("name"), "Unknown organ of state")
    else:
        buyer_name = str(buyer)

    tender_period = tender.get("tenderPeriod") or {}
    briefing_date, briefing_is_compulsory, has_briefing = _extract_briefing(
        tender.get("milestones", [])
    )

    return TenderRecord(
        ocid=release.get("ocid", ""),
        release_id=str(release.get("id", "")),
        release_date=release.get("date"),
        title=_first_nonempty(tender.get("title"), "(no title given)"),
        description=_first_nonempty(tender.get("description"), "(no description given)"),
        buyer_name=buyer_name,
        status=_first_nonempty(tender.get("status"), "unknown"),
        date_published=_first_nonempty(tender_period.get("startDate"), release.get("date")),
        closing_date=tender_period.get("endDate"),
        briefing_date=briefing_date,
        briefing_is_compulsory=briefing_is_compulsory,
        has_briefing=has_briefing,
        documents=_extract_documents(tender.get("documents", [])),
        amendments=_extract_amendments(tender.get("amendments", [])),
    )
