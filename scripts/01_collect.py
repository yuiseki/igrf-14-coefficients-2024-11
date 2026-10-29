#!/usr/bin/env python3
"""Fetch the IGRF-14 coefficient file and the NCEI product page, check them, and write the MANIFEST.

    uv run python scripts/01_collect.py

The file is IAGA's, as served by NOAA NCEI. The run directory is named after the file's Last-Modified date.
"""

import email.utils
import hashlib
import json
import urllib.request
from datetime import UTC, datetime

import igrf

ROOT = igrf.ROOT


def fetch(url: str) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": igrf.UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(), {k.lower(): v for k, v in r.headers.items()}


def main() -> int:
    body, head = fetch(igrf.COEFF_URL)
    text = body.decode("utf-8")
    if "14th Generation International Geomagnetic Reference Field" not in text:
        raise SystemExit("the file does not say it is the 14th generation")
    t = igrf.parse(text)  # raises on a ragged row
    modified = email.utils.parsedate_to_datetime(head["last-modified"]).astimezone(UTC)
    run = ROOT / "data" / "raw" / modified.strftime("%Y%m%d")
    run.mkdir(parents=True, exist_ok=True)
    (run / igrf.FILE_NAME).write_bytes(body)
    page, page_head = fetch(igrf.PAGE_URL)
    ev = ROOT / "data" / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "ncei_igrf_product_page.html").write_bytes(page)
    page_text = page.decode("utf-8", "replace")
    for phrase in ("may be used freely by the public", "14th generation"):
        if phrase not in page_text:
            raise SystemExit(f"the NCEI product page no longer says: {phrase}")
    manifest = {
        "acquired_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": {
            igrf.FILE_NAME: {"url": igrf.COEFF_URL, "size": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                             "last_modified": head["last-modified"], "http_status": 200},
            "../../evidence/ncei_igrf_product_page.html": {
                "url": igrf.PAGE_URL, "size": len(page), "sha256": hashlib.sha256(page).hexdigest(),
                "role": "the licence and citation statement"},
        },
        "coefficient_rows": len(t.rows), "epochs": t.epoch_labels,
    }  # fmt: skip
    (run / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"{run}: {len(body):,} bytes, {len(t.rows)} coefficients, {len(t.epoch_labels)} columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
