#!/usr/bin/env python3
"""Write data/README.md (the dataset card), data/LICENSE and data/provenance.yaml.

uv run python scripts/04_card.py
"""

import json

import igrf

ROOT = igrf.ROOT
DATA = ROOT / "data"

STATEMENT = (
    "The software code is in the public domain and not licensed or under copyright. The information and "
    "software may be used freely by the public. As required by 17 U.S.C. 403, third parties producing "
    "copyrighted works consisting predominantly of the material produced by U.S. government agencies must "
    "provide notice with such work(s) identifying the U.S. Government material incorporated and stating "
    "that such material is not subject to copyright protection."
)
CITATION = (
    "International Geomagnetic Reference Field: the 13th generation, Alken, P., Thébault, E., Beggan, C.D. "
    "et al. International Geomagnetic Reference Field: the thirteenth generation. Earth Planets Space 73, "
    "49 (2021). doi: 10.1186/s40623-020-01288-x"
)

CARD = """---
license: other
license_name: ncei-free-use-us-government-notice
license_link: LICENSE
language:
- en
tags:
- geomagnetism
- igrf
- geophysics
- spherical-harmonics
size_categories:
- 1K<n<10K
configs:
- config_name: coefficients
  data_files: parquet/coefficients.parquet
---

# IGRF-14 coefficients (IAGA, via NOAA NCEI), file of {modified}

国際標準地球磁場 IGRF の第 14 世代の球面調和係数(1900〜2025 年の 26 時点と、2025〜2030 年の永年変化)の凍結コピーです。
配布元のファイルと、1 係数 1 時点 1 行に直した Parquet を置きます。

The IGRF-14 Schmidt semi-normalised spherical harmonic coefficients (degree 1 to 13; 26 epochs from 1900.0 to
2025.0 and the secular variation for 2025-30), exactly as published, plus a tidy Parquet table. Nothing is
computed or changed. The coefficients were finalised by an IAGA task force in November 2024.

## Source

- Files: {coeff_url} ({size:,} bytes, Last-Modified {last_modified}, sha256 `{sha}`).
- Product page and terms: {page_url} (saved as `evidence/ncei_igrf_product_page.html`).
- Acquired {acquired}. This repository holds the current file of IGRF-14.
- Producer: IAGA Working Group V-MOD. Distributed by NOAA NCEI.

## Terms of use and attribution

No licence text exists for the coefficient file itself. The NCEI product page of the model states, under
"License and Copyright Information":

> {statement}

The same page asks for this citation:

> {citation}

The page names the 13th generation paper although the file is the 14th generation; check IAGA for the
reference of the 14th generation. Please also review the Model Health Warning on the NCEI page before you
use the model.

The maintainer treats the provider's condition (acknowledgement of the source, and the notice that this
material is U.S. Government material not subject to copyright protection) as equivalent to CC BY attribution,
because no licence text exists for the coefficient file itself. That is the maintainer's reading, not a
statement of NCEI or IAGA. The NCEI statement is a page-level statement about the product, not a statement
inside the file.

This copy is a mirror of U.S. Government material (NOAA NCEI) and IAGA data; it is not subject to copyright
protection in the United States as far as the page says. NOAA and IAGA did not review this copy.

## Files

| file | content |
| --- | --- |
| `raw/{run}/igrf14coeffs.txt` | the published file, byte for byte |
| `raw/{run}/MANIFEST.json` | URL, size, sha256 and Last-Modified of the file and of the saved page |
| `parquet/coefficients.parquet` | the tidy table, {rows:,} rows |
| `parquet/tables.json` | row count and column names |
| `evidence/ncei_igrf_product_page.html` | the NCEI page with the terms and the citation |
| `provenance.yaml`, `LICENSE` | provenance record and the quoted terms |

## Columns of `coefficients`

| column | original | note |
| --- | --- | --- |
| `kind` | `c/s` (g or h) | Gauss coefficient g or h |
| `n` | `deg` | degree, 1 to 13 |
| `m` | `ord` | order, 0 to n |
| `epoch_label` | the epoch header | verbatim text, e.g. `1900.0`, `2025.0`, `2025-30` |
| `epoch_year` | the epoch header | the epoch as a number, null for the secular variation column |
| `series` | the series header | `IGRF`, `DGRF` or `SV`, as in the file |
| `value` | the cell | nT, or nT/yr for `SV` |
| `unit` | (file comment) | `nT` or `nT/yr` |

Zeros are kept as published. The non-zero coefficients reach degree 10 for the epochs 1900.0 to 1995.0 and
degree 13 from 2000.0; the secular variation is 0 above degree 8 (115 coefficients).

## Transformation

`scripts/01_collect.py` downloads the file and the page and writes the MANIFEST. `scripts/02_export_parquet.py`
melts the table with `scripts/igrf.py`. `scripts/03_verify.py` reads the raw text again with DuckDB, melts it
independently and compares every cell (0 differences), and compares the main field computed from the table
with ppigrf {ppigrf} (its own IGRF14.shc) at six places and seven epochs (largest difference
{worst:.5f} nT). The synthesis used for that check is test code and is not part of the data.

## Limits

- This is the model's coefficients, not a field value; compute the field with a package of your choice.
- By the series labels of the file, 1900.0 to 1940.0 are IGRF, 1945.0 to 2020.0 are DGRF (definitive), and
  2025.0 is IGRF; the 2025-30 secular variation goes with it. The IGRF-labelled columns are the ones that
  later generations replace.
- When IAGA publishes a correction or the next generation, this repository follows the latest file.
"""


def main() -> int:
    run = sorted((DATA / "raw").glob("*/MANIFEST.json"))[-1].parent
    m = json.loads((run / "MANIFEST.json").read_text())
    f = m["files"][igrf.FILE_NAME]
    info = json.loads((DATA / "parquet" / "tables.json").read_text())
    ver = json.loads((ROOT / "docs" / "verify_local.json").read_text())
    if not ver["ok"]:
        raise SystemExit("verify_local.json is not ok")
    card = CARD.format(
        modified=f["last_modified"][5:16], run=run.name, coeff_url=igrf.COEFF_URL, size=f["size"],
        last_modified=f["last_modified"], sha=f["sha256"], page_url=igrf.PAGE_URL,
        acquired=m["acquired_utc"][:10], statement=STATEMENT, citation=CITATION,
        rows=info["tables"]["coefficients"]["rows"], ppigrf=ver["ppigrf_version"],
        worst=max(ver["max_field_difference_nT_vs_ppigrf"].values()),
    )  # fmt: skip
    (DATA / "README.md").write_text(card, encoding="utf-8")
    (DATA / "LICENSE").write_text(
        "Terms as stated by NOAA NCEI on the IGRF product page "
        f"({igrf.PAGE_URL}), under License and Copyright Information:\n\n{STATEMENT}\n\n"
        f"Requested citation:\n\n{CITATION}\n\n"
        "No licence text exists for the coefficient file itself; see the card for the maintainer's reading.\n",
        encoding="utf-8",
    )
    (DATA / "provenance.yaml").write_text(
        "source: International Geomagnetic Reference Field, 14th generation (IAGA), via NOAA NCEI\n"
        f"url: {igrf.COEFF_URL}\n"
        f"terms_page: {igrf.PAGE_URL}\n"
        "license: NCEI page statement (free use, US Government notice); no licence text for the file\n"
        f"retrieved: {m['acquired_utc'][:10]}\n"
        f"last_modified: {f['last_modified']}\n"
        f"sha256: {f['sha256']}\n"
        f"rows: {info['tables']['coefficients']['rows']}\n",
        encoding="utf-8",
    )
    print(f"card: {len(card):,} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
