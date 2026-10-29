"""Tests for the IGRF-14 coefficient parser and for the field computed from the tidy table.

The field test compares our own spherical harmonic synthesis, fed from the tidy table, with ppigrf,
an independent package that reads its own bundled IGRF14.shc file.
"""

import igrf
import numpy as np
import pytest

SAMPLE = """\
# comment line one
# comment line two
c/s deg ord IGRF IGRF DGRF IGRF   SV
g/h n m 1900.0 1905.0 1910.0 2025.0 2025-30
g  1  0 -31543 -31464 -31354.5 -29350.0 12.6
h  1  1   5922   5909 5898 4545.5 -21.5
g  2  0   -677   -728 -769 -2556.3 -5.3
"""


def test_parse_header_and_rows():
    t = igrf.parse(SAMPLE)
    assert t.epoch_labels == ["1900.0", "1905.0", "1910.0", "2025.0", "2025-30"]
    assert t.series == ["IGRF", "IGRF", "DGRF", "IGRF", "SV"]
    assert [(r.kind, r.n, r.m) for r in t.rows] == [("g", 1, 0), ("h", 1, 1), ("g", 2, 0)]
    assert t.rows[0].values == [-31543.0, -31464.0, -31354.5, -29350.0, 12.6]


def test_tidy_has_one_row_per_coefficient_and_column():
    t = igrf.parse(SAMPLE)
    rows = igrf.tidy(t)
    assert len(rows) == 3 * 5
    sv = [r for r in rows if r["epoch_label"] == "2025-30"]
    assert len(sv) == 3 and all(r["unit"] == "nT/yr" and r["epoch_year"] is None for r in sv)
    first = rows[0]
    assert first == {"kind": "g", "n": 1, "m": 0, "epoch_label": "1900.0", "epoch_year": 1900.0,
                     "series": "IGRF", "value": -31543.0, "unit": "nT"}  # fmt: skip


def test_parse_rejects_a_ragged_row():
    bad = SAMPLE.replace("g  2  0   -677   -728 -769 -2556.3 -5.3", "g  2  0   -677")
    with pytest.raises(ValueError):
        igrf.parse(bad)


def test_synthesis_matches_ppigrf_for_the_real_file():
    ppigrf = pytest.importorskip("ppigrf")
    import datetime

    from_file = igrf.load_published()
    tidy = igrf.tidy(from_file)
    lon = np.array([139.69, -73.97, 0.0, 151.2, -60.0])
    lat = np.array([35.69, 40.71, 51.48, -33.87, -80.0])
    for year in (2000.0, 2015.0, 2020.0, 2025.0):
        be, bn, bu = ppigrf.igrf(lon, lat, 0.0, datetime.datetime(int(year), 1, 1))
        mine = igrf.field_enu(tidy, year, lon, lat, 0.0)
        theirs = np.array([be.ravel(), bn.ravel(), bu.ravel()])
        assert np.abs(mine - theirs).max() < 0.01, (year, np.abs(mine - theirs).max())
