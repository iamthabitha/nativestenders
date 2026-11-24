"""Builds and sends the email alert for one tender event."""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from parser import TenderRecord
from storage import DiffResult

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


@dataclass
class TenderEvent:
    tender: TenderRecord
    matched_keywords: list[str]
    diff: DiffResult
    # Populated by main.py after construction (a best-effort PDF scan) --
    # never required at construction time, since it's an enrichment step
    # that must not block the underlying alert if it fails.
    briefing_snippets: list[str] = field(default_factory=list)


def _event_label(event: TenderEvent) -> str:
    if event.diff.is_new:
        return "NEW TENDER"
    if event.tender.amendments and event.diff.previous_amendment_count < len(
        event.tender.amendments
    ):
        return "ERRATUM / AMENDMENT"
    if event.diff.previous_closing_date and event.diff.previous_closing_date != event.tender.closing_date:
        return "CLOSING DATE CHANGED"
    if event.diff.new_documents:
        return "NEW DOCUMENT ADDED"
    return "UPDATED"


def _briefing_section(event: TenderEvent) -> list[str]:
    tender = event.tender
    if tender.has_briefing:
        # This feed has never been observed to populate "milestones" in
        # practice, but keep this path in case that ever changes.
        compulsory = "Compulsory" if tender.briefing_is_compulsory else "Optional"
        date_text = tender.briefing_date or "date not specified"
        return [f"{compulsory} briefing session: {date_text}"]

    if event.briefing_snippets:
        lines = [
            "Briefing session info (extracted from the tender document -- verify against "
            "the actual document before relying on it):",
        ]
        for snippet in event.briefing_snippets:
            lines.append(f"  \"{snippet}\"")
        return lines

    # No structured data (confirmed: "milestones" is never present in this feed)
    # and scanning the tender document(s) didn't turn up a mention either. Say
    # exactly that rather than claiming there is no briefing -- there may well
    # be one described somewhere we didn't check (a non-PDF document, a scanned
    # image with no text layer, or phrasing our scan doesn't recognise).
    return [
        "Briefing session info is not available in this data feed, and scanning "
        "the tender document(s) didn't find a clear mention either -- check the "
        "tender documents below yourself, or search the tender number on "
        "https://www.etenders.gov.za/ for compulsory briefing/site meeting details."
    ]


def build_subject(event: TenderEvent) -> str:
    return f"[{_event_label(event)}] {event.tender.title[:100]}"


def build_body(event: TenderEvent) -> str:
    tender = event.tender
    lines = [
        f"{_event_label(event)}",
        "=" * 60,
        f"Title: {tender.title}",
        f"Organ of state: {tender.buyer_name}",
        f"Status: {tender.status}",
        f"Matched keywords: {', '.join(event.matched_keywords)}",
        "",
        "Description:",
        tender.description,
        "",
        f"Date published: {tender.date_published or 'not specified'}",
        f"Closing date: {tender.closing_date or 'not specified'}",
    ]

    if event.diff.is_changed and event.diff.previous_closing_date and (
        event.diff.previous_closing_date != tender.closing_date
    ):
        lines.append(f"  (previous closing date was: {event.diff.previous_closing_date})")

    lines += ["", *_briefing_section(event), ""]

    if event.diff.new_documents:
        lines += [
            "NEW DOCUMENT(S) SINCE OUR LAST ALERT ON THIS TENDER:",
            "This feed doesn't carry structured award/cancellation/status data, so a new",
            "document is our only signal something happened -- it could be an award",
            "notice, a cancellation, an addendum, or just a clarification. Check it:",
        ]
        for doc in event.diff.new_documents:
            lines.append(f"  - {doc.title}: {doc.url}")
        lines.append("")

    if tender.documents:
        lines.append("Tender documents:")
        for doc in tender.documents:
            lines.append(f"  - {doc.title}: {doc.url}")
    else:
        lines.append("No document links were provided in the feed for this tender.")
        lines.append(
            "Search the tender number on https://www.etenders.gov.za/ to download documents."
        )

    if tender.amendments:
        lines += ["", "Amendments / erratum notices on record:"]
        for amendment in tender.amendments:
            lines.append(f"  - {amendment.date or 'undated'}: {amendment.description}")

    lines += [
        "",
        f"OCID: {tender.ocid}",
        "-- Automated alert from tender-alert-bot --",
    ]
    return "\n".join(lines)


def send_email(
    *,
    gmail_address: str,
    gmail_app_password: str,
    recipients: list[str],
    subject: str,
    body: str,
) -> None:
    message = MIMEMultipart()
    message["From"] = gmail_address
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, recipients, message.as_string())

    logger.info("Sent alert email: %s", subject)
