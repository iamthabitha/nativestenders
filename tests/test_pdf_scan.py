import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdf_scan import _find_snippets

# Real text (reflowed) from a live tender PDF (Dr JS Moroka Local
# Municipality, JSM-COMMS-AD01/26-29) that this feature was built to catch.
REAL_TENDER_TEXT = """
8. Non-attendance of mandatory/compulsory:
9. The Bid has not been properly signed by a party having the authority to do so

A Compulsory briefing session meeting will be held on 23 November 2026 at Dr JS Moroka
Local Municipality (Siyabuswa) Ga-Phahla Community Hall, commencing at 10H30 to 11H00
(According to Municipality's time).

COMPULSORY BID DOCUMENTS
FORM A
NB: It is compulsory for all bidders to sign this form
"""


def test_finds_the_actual_briefing_sentence():
    snippets = _find_snippets(REAL_TENDER_TEXT)
    assert any("23 November 2026" in s and "Ga-Phahla Community Hall" in s for s in snippets)


def test_does_not_treat_bare_compulsory_as_a_match():
    # "compulsory" alone appears 4 times in boilerplate unrelated to any
    # meeting -- searching on it directly would flood the email with noise.
    # Only the specific "briefing"/"site meeting" anchors should fire.
    text_without_briefing_word = REAL_TENDER_TEXT.replace("briefing session meeting", "meeting")
    snippets = _find_snippets(text_without_briefing_word)
    assert snippets == []


def test_no_match_returns_empty_list():
    assert _find_snippets("Nothing relevant in this document at all.") == []
