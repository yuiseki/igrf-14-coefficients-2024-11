#!/usr/bin/env python3
"""Push the card, licence, provenance, the raw file, the Parquet and the evidence to the Hub in one commit.

uv run python src/publish.py             # dry run: list the files and their sizes
uv run python src/publish.py --push      # prints the commit sha and writes docs/revision.json
"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPO = "yuiseki/igrf-14-coefficients-2024-11"


def collect() -> dict[str, Path]:
    card = (DATA / "README.md").read_text(encoding="utf-8")
    if (
        "license: other" not in card
        or "No licence text exists for the coefficient file itself" not in card
    ):
        raise SystemExit("the card does not carry the licence statement")
    run = sorted((DATA / "raw").glob("*/MANIFEST.json"))[-1].parent
    info = json.loads((DATA / "parquet" / "tables.json").read_text())
    rows = info["tables"]["coefficients"]["rows"]
    ver = json.loads((ROOT / "docs" / "verify_local.json").read_text())
    if f"{rows:,}" not in card or not ver["ok"] or ver["parquet_rows"] != rows:
        raise SystemExit("the card or the local verification does not match the table")
    m = json.loads((run / "MANIFEST.json").read_text())
    f = run / "igrf14coeffs.txt"
    if hashlib.sha256(f.read_bytes()).hexdigest() != m["files"][f.name]["sha256"]:
        raise SystemExit("the raw file is not the file in its manifest")
    files = {
        "README.md": DATA / "README.md", "LICENSE": DATA / "LICENSE",
        "provenance.yaml": DATA / "provenance.yaml",
        f"raw/{run.name}/igrf14coeffs.txt": f, f"raw/{run.name}/MANIFEST.json": run / "MANIFEST.json",
        "parquet/coefficients.parquet": DATA / "parquet" / "coefficients.parquet",
        "parquet/tables.json": DATA / "parquet" / "tables.json",
        "evidence/ncei_igrf_product_page.html": DATA / "evidence" / "ncei_igrf_product_page.html",
        "docs/verify_local.json": ROOT / "docs" / "verify_local.json",
    }  # fmt: skip
    missing = [k for k, v in files.items() if not v.is_file()]
    if missing:
        raise SystemExit(f"missing: {missing}")
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    files = collect()
    total = sum(p.stat().st_size for p in files.values())
    print(f"{a.repo}\n  {len(files)} files, {total:,} bytes")
    for k, p in files.items():
        print(f"  {k}  {p.stat().st_size:,}")
    if not a.push:
        print("\ndry run. pass --push to upload")
        return 0
    from huggingface_hub import CommitOperationAdd, HfApi

    api = HfApi()
    api.create_repo(a.repo, repo_type="dataset", exist_ok=True, private=False)
    ops = [CommitOperationAdd(path_in_repo=k, path_or_fileobj=str(p)) for k, p in files.items()]
    info = api.create_commit(a.repo, ops, repo_type="dataset",
                             commit_message="IGRF-14 coefficients as published (file of 2024-11-18)")  # fmt: skip
    sums = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in files.items()}
    (ROOT / "docs" / "revision.json").write_text(
        json.dumps({"repo": a.repo, "revision": info.oid, "sha256": sums}, indent=1) + "\n"
    )
    print("pushed", a.repo, "revision", info.oid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
