"""Constants and helpers shared by the scripts of igrf-14-coefficients-2024-11."""

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[1]
COEFF_URL = "https://www.ngdc.noaa.gov/IAGA/vmod/coeffs/igrf14coeffs.txt"
PAGE_URL = "https://www.ncei.noaa.gov/products/international-geomagnetic-reference-field"
UA = "Mozilla/5.0 (research; yuiseki)"
FILE_NAME = "igrf14coeffs.txt"
REFERENCE_RADIUS_KM = 6371.2  # the IGRF reference sphere
WGS84_A_KM = 6378.137
WGS84_B_KM = 6356.7523142


@dataclass
class Row:
    kind: str
    n: int
    m: int
    values: list[float]


@dataclass
class Table:
    epoch_labels: list[str]
    series: list[str]
    rows: list[Row]


def parse(text: str) -> Table:
    """Parse the published whitespace table: two '#' lines, a series line, an epoch line, then rows."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    series_line, epoch_line, *body = lines
    series = series_line.split()[3:]
    epochs = epoch_line.split()[3:]
    if len(series) != len(epochs):
        raise ValueError(f"{len(series)} series labels for {len(epochs)} epochs")
    rows = []
    for ln in body:
        f = ln.split()
        if len(f) != 3 + len(epochs):
            raise ValueError(f"row has {len(f)} fields, expected {3 + len(epochs)}: {ln[:40]}")
        rows.append(Row(f[0], int(f[1]), int(f[2]), [float(v) for v in f[3:]]))
    return Table(epochs, series, rows)


def load_published(path: Path | None = None) -> Table:
    path = path or sorted((ROOT / "data" / "raw").glob(f"*/{FILE_NAME}"))[-1]
    return parse(path.read_text(encoding="utf-8"))


def tidy(t: Table) -> list[dict]:
    """One record per coefficient and published column, in the order of the file."""
    out = []
    for r in t.rows:
        for label, ser, v in zip(t.epoch_labels, t.series, r.values, strict=True):
            is_sv = ser == "SV"
            out.append({
                "kind": r.kind, "n": r.n, "m": r.m, "epoch_label": label,
                "epoch_year": None if is_sv else float(label), "series": ser,
                "value": v, "unit": "nT/yr" if is_sv else "nT",
            })  # fmt: skip
    return out


def _coeffs_at(rows: list[dict], year: float) -> dict[tuple[str, int, int], float]:
    """Linear interpolation between epochs; past the last epoch the secular variation is added."""
    by = {}
    for r in rows:
        by.setdefault((r["kind"], r["n"], r["m"]), []).append(r)
    out = {}
    for key, rs in by.items():
        ep = sorted((r["epoch_year"], r["value"]) for r in rs if r["epoch_year"] is not None)
        years = [e for e, _ in ep]
        if year > years[-1]:
            sv = next(r["value"] for r in rs if r["series"] == "SV")
            out[key] = ep[-1][1] + sv * (year - years[-1])
        else:
            out[key] = float(np.interp(year, years, [v for _, v in ep]))
    return out


def _schmidt_factors(nmax: int) -> dict[tuple[int, int], float]:
    s = {}
    for n in range(1, nmax + 1):
        dfac = 1.0
        for k in range(1, 2 * n, 2):
            dfac *= k
        for m in range(n + 1):
            eps = 1.0 if m == 0 else 2.0
            s[(n, m)] = (dfac / math.factorial(n - m)) * math.sqrt(
                eps * math.factorial(n - m) / math.factorial(n + m)
            )
    return s


def field_enu(rows: list[dict], year: float, lon_deg, lat_deg, height_km: float = 0.0):
    """Main field (east, north, up) in nT at geodetic positions, from the tidy table.

    A plain spherical harmonic synthesis, written here to check the table against another
    implementation; it is not part of the published data.
    """
    coeffs = _coeffs_at(rows, year)
    nmax = max(n for _, n, _ in coeffs)
    lon = np.radians(np.atleast_1d(np.asarray(lon_deg, dtype=float)))
    lat = np.radians(np.atleast_1d(np.asarray(lat_deg, dtype=float)))
    a, b = WGS84_A_KM, WGS84_B_KM
    e2 = 1 - (b / a) ** 2
    sl, cl = np.sin(lat), np.cos(lat)
    big_n = a / np.sqrt(1 - e2 * sl**2)
    rho = (big_n + height_km) * cl
    z = (big_n * (1 - e2) + height_km) * sl
    r = np.hypot(rho, z)
    lat_gc = np.arctan2(z, rho)
    theta = np.pi / 2 - lat_gc
    ct, st = np.cos(theta), np.sin(theta)
    sfac = _schmidt_factors(nmax)
    p = {(0, 0): np.ones_like(ct)}
    dp = {(0, 0): np.zeros_like(ct)}
    for n in range(1, nmax + 1):
        for m in range(n + 1):
            if m == n:
                p[(n, n)] = st * p[(n - 1, n - 1)]
                dp[(n, n)] = st * dp[(n - 1, n - 1)] + ct * p[(n - 1, n - 1)]
            else:
                k = 0.0 if n == 1 else ((n - 1) ** 2 - m**2) / ((2 * n - 1) * (2 * n - 3))
                p2 = p.get((n - 2, m), 0.0)
                dp2 = dp.get((n - 2, m), 0.0)
                p[(n, m)] = ct * p[(n - 1, m)] - k * p2
                dp[(n, m)] = ct * dp[(n - 1, m)] - st * p[(n - 1, m)] - k * dp2
    br = np.zeros_like(ct)
    bt = np.zeros_like(ct)
    bp = np.zeros_like(ct)
    ratio = REFERENCE_RADIUS_KM / r
    for n in range(1, nmax + 1):
        rn = ratio ** (n + 2)
        for m in range(n + 1):
            g = coeffs.get(("g", n, m), 0.0)
            h = coeffs.get(("h", n, m), 0.0)
            s = sfac[(n, m)]
            cm, sm = np.cos(m * lon), np.sin(m * lon)
            gh = g * cm + h * sm
            br += (n + 1) * rn * gh * s * p[(n, m)]
            bt += -rn * gh * s * dp[(n, m)]
            bp += rn * m * (g * sm - h * cm) * s * p[(n, m)] / st
    x_gc, y, z_gc = -bt, bp, -br
    psi = lat - lat_gc
    x = x_gc * np.cos(psi) + z_gc * np.sin(psi)
    zz = z_gc * np.cos(psi) - x_gc * np.sin(psi)
    return np.array([y, x, -zz])
