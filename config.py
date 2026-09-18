"""Loads settings from environment variables (and .env locally)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    gmail_address: str
    gmail_app_password: str
    alert_recipients: list[str]
    keywords: list[str]
    lookback_days: int
    ocds_api_base: str
    db_path: str = "data/seen_tenders.db"


def load_settings() -> Settings:
    missing = [
        name
        for name in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "ALERT_RECIPIENTS")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill it in."
        )

    return Settings(
        gmail_address=os.environ["GMAIL_ADDRESS"],
        gmail_app_password=os.environ["GMAIL_APP_PASSWORD"],
        alert_recipients=_split_csv(os.environ["ALERT_RECIPIENTS"]),
        keywords=_split_csv(
            os.environ.get("KEYWORDS")
            or "newspaper,advertising,media buying,radio,billboard"
        ),
        lookback_days=int(os.environ.get("LOOKBACK_DAYS") or "30"),
        ocds_api_base=os.environ.get("OCDS_API_BASE")
        or "https://ocds-api.etenders.gov.za/api/OCDSReleases",
    )
