#!/usr/bin/env python3
"""Write the tidy coefficient table as Parquet: one row per coefficient and published column.

uv run python scripts/02_export_parquet.py   # data/parquet/coefficients.parquet and tables.json
"""

import json

import igrf
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = igrf.ROOT
SCHEMA = pa.schema([
    ("kind", pa.string()), ("n", pa.int8()), ("m", pa.int8()), ("epoch_label", pa.string()),
    ("epoch_year", pa.float64()), ("series", pa.string()), ("value", pa.float64()), ("unit", pa.string()),
])  # fmt: skip


def main() -> int:
    rows = igrf.tidy(igrf.load_published())
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    out = ROOT / "data" / "parquet"
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out / "coefficients.parquet", compression="zstd")
    info = {"tables": {"coefficients": {"rows": table.num_rows, "columns": SCHEMA.names}}}
    (out / "tables.json").write_text(json.dumps(info, indent=1) + "\n")
    print(f"coefficients.parquet: {table.num_rows:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
