#!/usr/bin/env python3
"""Check the Parquet against the raw file with a second reader (DuckDB), and the field against ppigrf.

    uv run python scripts/03_verify.py   # writes docs/verify_local.json

Route 1: the raw text is read by DuckDB as all-varchar whitespace-separated text, melted to one row per
coefficient and column, and compared cell by cell with the Parquet.
Route 2: the main field at fixed places and epochs is computed from the Parquet with our own synthesis and
with ppigrf (which reads its own IGRF14.shc); the largest difference is recorded.
"""

import datetime
import json
import sys

import duckdb
import igrf
import numpy as np
import ppigrf

ROOT = igrf.ROOT


def main() -> int:
    raw = sorted((ROOT / "data" / "raw").glob(f"*/{igrf.FILE_NAME}"))[-1]
    pq = ROOT / "data" / "parquet" / "coefficients.parquet"
    con = duckdb.connect()
    # DuckDB reads the file as text and splits it itself; none of our parser is used on this route
    con.execute(
        "create table lines as select row_number() over () ln, line from ("
        "select unnest(string_split(content, chr(10))) line from read_text(?))", [str(raw)]
    )  # fmt: skip
    con.execute("create table kept as select ln, trim(line) line from lines "
                "where trim(line) <> '' and not starts_with(line, '#')")  # fmt: skip
    con.execute("create table split as select ln, regexp_split_to_array(line, '\\s+') a from kept")
    head = con.execute("select a from split order by ln limit 2").fetchall()
    series, labels = head[0][0][3:], head[1][0][3:]
    con.execute(
        "create table src as select * from split where ln > (select min(ln) + 1 from split)"
    )
    n_rows = con.execute("select count(*) from src").fetchone()[0]
    expected = n_rows * len(labels)
    con.execute("create table lab as select * from (select unnest(range(1, ?)) i, unnest(?) l, unnest(?) s)",
                [len(labels) + 1, labels, series])  # fmt: skip
    con.execute("create table melt as select a[1] kind, cast(a[2] as int) n, cast(a[3] as int) m, l.i, "
                "a[3 + l.i] v, l.l, l.s from src cross join lab l")  # fmt: skip
    con.execute(f"create table mine as select * from read_parquet('{pq}')")
    n_mine = con.execute("select count(*) from mine").fetchone()[0]
    diff = con.execute(
        "select count(*) from melt x full join mine y on y.kind = x.kind and y.n = x.n and y.m = x.m "
        "and y.epoch_label = x.l where x.kind is null or y.kind is null "
        "or abs(cast(x.v as double) - y.value) > 0 or y.series <> x.s"
    ).fetchone()[0]  # fmt: skip
    sv_bad = con.execute("select count(*) from mine where (series='SV') <> (unit='nT/yr') "
                         "or (series='SV') <> (epoch_year is null)").fetchone()[0]  # fmt: skip
    rows = igrf.tidy(igrf.load_published())
    lon = np.array([139.69, -73.97, 0.0, 151.2, -60.0, 10.0])
    lat = np.array([35.69, 40.71, 51.48, -33.87, -80.0, 0.0])
    worst = {}
    for year in (1900.0, 1950.0, 1975.0, 2000.0, 2010.0, 2020.0, 2025.0):
        be, bn, bu = ppigrf.igrf(lon, lat, 0.0, datetime.datetime(int(year), 1, 1))
        theirs = np.array([be.ravel(), bn.ravel(), bu.ravel()])
        mine = igrf.field_enu(rows, year, lon, lat, 0.0)
        worst[str(year)] = float(np.abs(mine - theirs).max())
    res = {
        "raw_rows": n_rows, "melted_cells": expected, "parquet_rows": n_mine,
        "cell_differences": diff, "sv_flag_problems": sv_bad,
        "max_field_difference_nT_vs_ppigrf": worst,
        "ppigrf_version": __import__("importlib.metadata").metadata.version("ppigrf"),
        "ok": diff == 0 and sv_bad == 0 and n_mine == expected and max(worst.values()) < 0.5,
    }  # fmt: skip
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "verify_local.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
