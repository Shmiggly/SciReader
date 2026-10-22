# /// script
# requires-python = ">=3.12"
# dependencies = ["certifi>=2026.10.19"]
# ///
"""Download the sample papers listed in samples/manifest.json (stdlib + certifi).

Usage:  uv run scripts/fetch_samples.py
Respects arXiv etiquette (one request every 3 s, descriptive User-Agent).
TLS trusts certifi's bundle, not Python's default context: on Windows that loads the system roots into
OpenSSL, which never sees Microsoft's blocklist, and accepted the leaked eMudhra intermediates (Oct 2026).
"""

from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
USER_AGENT = "SciReader/0.1 (open-source paper reader; hackathon dev; https://github.com/Shmiggly/SciReader)"
TLS = ssl.create_default_context(cafile=certifi.where())


def main() -> int:
    manifest = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    failures = 0
    last_request = 0.0
    for paper in manifest["papers"]:
        dest = SAMPLES / paper["file"]
        if dest.exists() and dest.stat().st_size > 10_000:
            print(f"ok      {paper['file']} ({dest.stat().st_size / 1e6:.1f} MB, already present)")
            continue
        if paper.get("manual"):
            print(f"MANUAL  {paper['file']}: {paper.get('manual_note', 'download by hand')}")
            continue
        wait = 3.0 - (time.monotonic() - last_request)
        if wait > 0:
            time.sleep(wait)
        last_request = time.monotonic()
        req = urllib.request.Request(paper["url"], headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=120, context=TLS) as resp:
                data = resp.read()
            if not data.startswith(b"%PDF"):
                raise ValueError("response is not a PDF")
            dest.write_bytes(data)
            print(f"fetched {paper['file']} ({len(data) / 1e6:.1f} MB)")
        except Exception as exc:  # noqa: BLE001 - report and continue with the rest
            failures += 1
            print(f"FAILED  {paper['file']}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
