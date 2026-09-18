# tender-alert-bot

Emails you when a new (or changed) tender/RFQ/bid matching your keywords
appears on South Africa's National Treasury eTenders portal.

Keywords out of the box: `newspaper`, `advertising`, `media buying`, `radio`, `billboard`.

## How it works

Rather than scraping the public website's HTML (fragile — breaks every time
the site is redesigned), this uses National Treasury's own **public OCDS
API** (Open Contracting Data Standard), which publishes every tender as
structured JSON:

- API: `https://ocds-api.etenders.gov.za/api/OCDSReleases`
- Docs / interactive schema: `https://ocds-api.etenders.gov.za/swagger/index.html`
- No API key needed.

Each run:

1. **Fetch** every release published in the last `LOOKBACK_DAYS` days (default 30 —
   wide enough to catch amendments to tenders that were published earlier).
2. **Filter** to releases whose tender title or description contains one of
   your keywords.
3. **Diff** each match against a small SQLite database (`data/seen_tenders.db`)
   of everything we've already alerted on. A tender is flagged as:
   - **NEW** — first time we've seen this OCID.
   - **CLOSING DATE CHANGED** — same OCID, closing date differs from last run.
   - **ERRATUM / AMENDMENT** — same OCID, an amendment was added.
   - **UPDATED** — same OCID, something else in the tracked fields changed.
4. **Email** one alert per new/changed tender via Gmail SMTP, containing:
   description, organ of state (buyer), date published, closing date,
   whether there's a compulsory briefing (and its date, or an explicit "no
   briefing" statement), document links, and any amendment history.

> **Important — verify the schema on your first real run.** The sandbox this
> project was built in could not reach `etenders.gov.za` (network egress was
> blocked), so `parser.py` was written defensively against the published
> OCDS standard, with fallback field names where the standard allows
> variation — but it hasn't been run against a live response. Before you
> trust it, run:
> ```
> python inspect_api.py
> ```
> This fetches one real page and prints both the raw JSON and what the
> parser extracted from it. If a field looks wrong or empty, fix the
> corresponding line in `parser.py` (each extraction is a small, isolated
> `.get(...)` chain — safe to tweak).

## Setup

### 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create a Gmail App Password

Alerts send FROM a Gmail account you control, using an **App Password**
(not your normal Gmail password — Google blocks plain-password SMTP login).

1. Turn on 2-Step Verification: https://myaccount.google.com/signinoptions/two-step-verification
2. Create an app password: https://myaccount.google.com/apppasswords
3. Copy the 16-character password it gives you.

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:
- `GMAIL_ADDRESS` — the Gmail account you just made an app password for.
- `GMAIL_APP_PASSWORD` — that 16-character app password.
- `ALERT_RECIPIENTS` — comma-separated addresses to send TO (can be the same Gmail address, or any inbox).
- `KEYWORDS` — comma-separated, edit freely.
- `LOOKBACK_DAYS` — how far back to re-scan each run.

### 4. Verify the API schema, then do a first run

```bash
python inspect_api.py   # confirm field names look right (see note above)
python main.py           # real run — will email you for every current match
```

The first run will likely email you every currently-open tender that
matches your keywords (everything is "new" the first time). That's
expected — after that, you'll only get alerts for genuinely new or changed
tenders.

## Running it on a schedule (free, no server) — GitHub Actions

1. Push this project to your own new GitHub repository.
2. In the repo's **Settings → Secrets and variables → Actions**, add:
   - **Secrets**: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `ALERT_RECIPIENTS`
   - **Variables** (optional, has defaults): `KEYWORDS`, `LOOKBACK_DAYS`
3. That's it — `.github/workflows/scrape.yml` runs every 3 hours
   (`workflow_dispatch` also lets you trigger it manually from the Actions
   tab), and commits the updated `data/seen_tenders.db` back to the repo
   after each run so state persists between runs.

To change the schedule, edit the `cron:` line in `.github/workflows/scrape.yml`
(it's in UTC — South Africa is UTC+2).

## Running it on a schedule — your own machine/server instead

If you'd rather not use GitHub Actions:

- **Linux/macOS**: add a cron entry, e.g. `0 */3 * * * cd /path/to/tender-alert-bot && .venv/bin/python main.py`
- **Windows**: use Task Scheduler to run `python main.py` on an interval.
- **Any always-on box**: a simple `while true; do python main.py; sleep 10800; done` works too, just keep it running (e.g. in `tmux`/`screen`, or as a systemd service).

## Project layout

```
config.py        settings loaded from .env / environment
ocds_client.py   talks to the OCDS API (pagination, retries)
parser.py        raw OCDS release -> flat TenderRecord
filters.py       keyword matching
storage.py       SQLite "have we alerted on this before?" memory
notifier.py      builds + sends the email
main.py          wires it all together — this is what you run/schedule
inspect_api.py   one-off helper to sanity-check the live API schema
tests/           unit tests using a synthetic OCDS fixture (no network needed)
```

## Extending it later

- **More organs of state / provinces**: the OCDS feed already covers all
  national + provincial tenders; just broaden `KEYWORDS`.
- **HTML email formatting**: `notifier.py`'s `build_body` returns plain
  text on purpose (simplest possible starting point) — swap in an HTML
  `MIMEText` part if you want richer formatting/links.
- **Slack/SMS instead of (or alongside) email**: `main.py` only calls
  `send_email` in one place — easy to add another notifier function next
  to it (e.g. Twilio for SMS, a Slack webhook).
- **Multiple keyword profiles per recipient**: currently one keyword list
  for everyone in `ALERT_RECIPIENTS`; if you need per-person keyword sets,
  that's a small change to `config.py` + a loop in `main.py`.
