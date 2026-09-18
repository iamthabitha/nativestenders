import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filters import matches_keywords
from parser import parse_release
from storage import TenderStore

SAMPLE_RELEASE = {
    "ocid": "ocds-9t57fa-EXAMPLE001",
    "id": "EXAMPLE001-1",
    "date": "2026-09-01T09:00:00Z",
    "buyer": {"name": "Department of Communications"},
    "tender": {
        "title": "Supply and delivery of newspaper advertising space",
        "description": "Appointment of a service provider for radio and billboard media buying.",
        "status": "active",
        "tenderPeriod": {"startDate": "2026-09-01", "endDate": "2026-10-01"},
        "milestones": [
            {
                "title": "Compulsory briefing session",
                "dueDate": "2026-09-10T10:00:00Z",
            }
        ],
        "documents": [
            {"title": "RFQ document", "url": "https://example.org/rfq.pdf"}
        ],
        "amendments": [],
    },
}


def test_parse_release_extracts_expected_fields():
    tender = parse_release(SAMPLE_RELEASE)
    assert tender is not None
    assert tender.ocid == "ocds-9t57fa-EXAMPLE001"
    assert tender.buyer_name == "Department of Communications"
    assert tender.closing_date == "2026-10-01"
    assert tender.has_briefing is True
    assert tender.briefing_is_compulsory is True
    assert tender.documents[0].url == "https://example.org/rfq.pdf"


def test_parse_release_returns_none_without_tender_block():
    assert parse_release({"ocid": "x"}) is None


def test_keyword_matching_is_case_insensitive():
    tender = parse_release(SAMPLE_RELEASE)
    matched = matches_keywords(tender, ["newspaper", "billboard", "irrelevant-word"])
    assert set(matched) == {"newspaper", "billboard"}


def test_store_detects_new_then_unchanged_then_changed(tmp_path):
    db_path = str(tmp_path / "test.db")
    store = TenderStore(db_path)
    tender = parse_release(SAMPLE_RELEASE)

    first = store.check_and_record(tender)
    assert first.is_new is True

    second = store.check_and_record(tender)
    assert second.is_new is False
    assert second.is_changed is False

    changed_release = json_copy_with_new_closing_date(SAMPLE_RELEASE, "2026-10-15")
    changed_tender = parse_release(changed_release)
    third = store.check_and_record(changed_tender)
    assert third.is_new is False
    assert third.is_changed is True
    assert third.previous_closing_date == "2026-10-01"


def json_copy_with_new_closing_date(release: dict, new_date: str) -> dict:
    import copy

    updated = copy.deepcopy(release)
    updated["tender"]["tenderPeriod"]["endDate"] = new_date
    return updated
