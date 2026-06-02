"""Shared GP-seat → settlement bridge, used by both 06 (monthly lookup) and 08 (road cache).

A 'seat' is the settlement that hosts a körzet's surgery (active XLSX col H). We resolve each
practice's seat to a canonical KSH code + centroid by normalized name, so 06 and 08 cannot drift
on this load-bearing join."""
from __future__ import annotations

import pandas as pd

from lib.names import normalize


def canonical_lut(gdf) -> "pd.DataFrame":
    """name_norm -> {ksh_code, centroid_lat, centroid_lon} for settlements that have a centroid."""
    base = gdf.dropna(subset=["centroid_lat"]).copy()
    base["centroid_lat"] = base["centroid_lat"].astype(float)
    base["centroid_lon"] = base["centroid_lon"].astype(float)
    return base.drop_duplicates("name_norm").set_index("name_norm")


def resolve_seats(practices, gdf) -> "tuple[pd.DataFrame, float]":
    """Attach seat_ksh / seat_lat / seat_lon to each practice row (by normalized seat name).
    Returns (practices_with_seat, coverage_fraction)."""
    lut = canonical_lut(gdf)
    p = practices.copy()
    p["nn"] = p["seat_name"].map(normalize)
    # Budapest is aggregated to one unit (name_norm "budapest"); collapse kerület seat names too.
    p.loc[p["nn"].str.startswith("budapest", na=False), "nn"] = "budapest"
    p["seat_ksh"] = p["nn"].map(lut["ksh_code"])
    p["seat_lat"] = p["nn"].map(lut["centroid_lat"])
    p["seat_lon"] = p["nn"].map(lut["centroid_lon"])
    coverage = float(p["nn"].isin(lut.index).mean())
    return p, coverage


def seat_points(practices, gdf) -> "tuple[pd.DataFrame, float]":
    """Distinct seat settlements with a centroid: DataFrame[seat_ksh, seat_name, lat, lon]."""
    p, cov = resolve_seats(practices, gdf)
    s = (p.dropna(subset=["seat_ksh", "seat_lat", "seat_lon"])
           .drop_duplicates("seat_ksh")[["seat_ksh", "seat_name", "seat_lat", "seat_lon"]]
           .reset_index(drop=True))
    return s, cov


def filled_seat_codes(practices, gdf, vac_set) -> "set[str]":
    """Set of seat KSH codes that host >=1 FILLED (non-vacant) körzet this month."""
    p, _ = resolve_seats(practices, gdf)
    filled = p[~p["hsz_kod"].isin(vac_set)]
    return set(filled["seat_ksh"].dropna())
