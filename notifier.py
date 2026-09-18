"""Builds and sends the email alert for one tender event."""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
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


def _event_label(event: TenderEvent) -> str:
    if event.diff.is_new:
        return "NEW TENDER"
    if event.tender.amendments and event.diff.previous_amendment_count < len(
        event.tender.amendments
    ):
        return "ERRATUM / AMENDMENT"
    if event.diff.previous_closing_date and event.diff.previous_closing_date != event.tender.closing_date:
        return "CLOSING DATE CHANGED"
    return "UPDATED"


def _briefing_line(tender: TenderRecord) -> str:
    if not tender.has_briefing:
        return "No compulsory briefing session is listed for this tender."
    compulsory = "Compulsory" if tender.briefing_is_compulsory else "Optional"
    date_text = tender.briefing_date or "date not specified"
    return f"{compulsory} briefing session: {date_text}"


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

    lines += ["", _briefing_line(tender), ""]

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
