#!/usr/bin/env python3
"""Read the repository back from the Hub at the recorded revision and compare it with the local copy:
file checksums, row count, schema, value counts, NULL counts and the cells themselves.

    uv run python scripts/05_verify_hub.py   # needs docs/revision.json from src/publish.py --push
"""

import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).parents[1]


def main() -> int:
    rev = json.loads((ROOT / "docs" / "revision.json").read_text())
    repo, sha = rev["repo"], rev["revision"]
    out, bad = {"repo": repo, "revision": sha}, []
    cache = ROOT / "data" / "hub_readback"
    for name, want in rev["sha256"].items():
        p = Path(hf_hub_download(repo, name, repo_type="dataset", revision=sha, local_dir=cache))
        if hashlib.sha256(p.read_bytes()).hexdigest() != want:
            bad.append(f"checksum {name}")
    out["files_checked"] = len(rev["sha256"])
    hub = pq.read_table(cache / "parquet" / "coefficients.parquet")
    mine = pq.read_table(ROOT / "data" / "parquet" / "coefficients.parquet")
    info = json.loads((ROOT / "data" / "parquet" / "tables.json").read_text())
    out["rows"] = hub.num_rows
    out["schema"] = [f"{f.name}:{f.type}" for f in hub.schema]
    if hub.schema != mine.schema:
        bad.append("schema")
    if hub.num_rows != info["tables"]["coefficients"]["rows"]:
        bad.append("rows vs the local table")
    if not hub.equals(mine):
        bad.append("cells differ from the local copy")
    df = hub.to_pandas()
    out["value_counts"] = {c: {str(k): int(v) for k, v in df[c].value_counts().sort_index().items()}
                           for c in ("kind", "series", "unit")}  # fmt: skip
    out["nulls"] = {c: int(df[c].isna().sum()) for c in df.columns}
    if out["nulls"]["epoch_year"] != int((df["series"] == "SV").sum()) or any(
        v for k, v in out["nulls"].items() if k != "epoch_year"
    ):
        bad.append("unexpected nulls")
    out["problems"] = bad
    (ROOT / "docs" / "verify_hub.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "schema"}, indent=1))
    print(
        "OK: the repository at", sha, "equals the local copy" if not bad else f"has problems: {bad}"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
