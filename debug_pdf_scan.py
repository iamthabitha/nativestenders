"""One-off diagnostic: download a tender document PDF and check whether it
has an extractable text layer, and whether scanning it for briefing-related
keywords actually surfaces the compulsory briefing info a user can see by
eye but our system currently can't -- i.e. is PDF text extraction worth
building into the real pipeline.

Usage: PDF_URL="https://www.etenders.gov.za/home/Download?..." python debug_pdf_scan.py
Defaults to the JS Moroka JSM-COMMS-AD01/26-29 tender doc that prompted this check.
"""
from __future__ import annotations

import os
import re

import requests

DEFAULT_URL = (
    "https://www.etenders.gov.za/home/Download?"
    "blobName=195ec0ba-7c88-4447-b3c1-2ea5cd7e2041.pdf"
    "&downloadedFileName=Advertising%20tender%20doc%20JSM%20COMMS%20ADS01%202629%20final.pdf"
)

KEYWORDS = ["briefing", "compulsory", "site meeting", "site visit", "pre-bid"]


def main() -> None:
    url = os.environ.get("PDF_URL", DEFAULT_URL)
    print(f"Downloading: {url}")
    response = requests.get(url, timeout=60)
    print(f"HTTP {response.status_code}, {len(response.content)} bytes, "
          f"content-type={response.headers.get('content-type')}")

    path = "/tmp/debug_tender.pdf"
    with open(path, "wb") as f:
        f.write(response.content)

    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf not installed -- installing for this run only")
        os.system("pip install -q pypdf")
        from pypdf import PdfReader

    reader = PdfReader(path)
    print(f"Pages: {len(reader.pages)}")

    full_text = ""
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        full_text += text + "\n"
        print(f"--- Page {i + 1}: {len(text)} chars extracted ---")

    print(f"\nTotal extracted text: {len(full_text)} chars")
    if len(full_text.strip()) < 50:
        print("Essentially no extractable text -- likely a scanned image PDF, not real text.")
        return

    print("\n" + "=" * 70)
    print("Searching extracted text for briefing-related keywords ...")
    lower_text = full_text.lower()
    for kw in KEYWORDS:
        for match in re.finditer(re.escape(kw), lower_text):
            start = max(0, match.start() - 200)
            end = min(len(full_text), match.end() + 200)
            print(f"\n[{kw}] ...{full_text[start:end].strip()}...")


if __name__ == "__main__":
    main()
