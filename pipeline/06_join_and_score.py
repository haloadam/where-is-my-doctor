#!/usr/bin/env python
"""Step 6 — join memberships + vacancies + population + geometry, compute access.

Honest desert model: every settlement is assigned to >=1 körzet on paper, so paper
coverage is never zero. What matters is FUNCTIONING coverage:
  active_gp_count            = distinct NON-vacant körzets serving the settlement
  vacant_count               = distinct vacant körzets serving it
  persistently_vacant_count  = distinct OKFŐ-persistent vacant körzets serving it
  is_desert                  = active_gp_count == 0  (served only by empty posts)
  gps_per_1000               = active_gp_count / population * 1000
Budapest kerület codes are folded into the parent (13578) via code_remap.
Nearest-GP (haversine x1.4) is added in step 06b/phase 3; columns reserved here."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from lib.assertions import Assertions
from lib.config import (ACCESS_TIERS, AVG_SPEED_KMH, DESERT_BAND, EXPECT, INTERIM, ROAD_FACTOR)
from lib.haversine import chord_to_km, latlon_to_xyz
from lib.io import read_parquet
from lib.names import normalize

RUN_DATE = date.today()


def nearest_gp(a, gdf, vac_set):
    """For each desert, straight-line km x ROAD_FACTOR to the nearest seat of a FILLED körzet.
    Served settlements get nearest_gp_km = 0 (functioning access). Seats are mapped to a
    centroid by normalized name (A-SEAT-JOIN guards coverage)."""
    practices = read_parquet("practices")
    filled = practices[~practices["hsz_kod"].isin(vac_set)].copy()
    filled["nn"] = filled["seat_name"].map(normalize)
    base = gdf.dropna(subset=["centroid_lat"]).drop_duplicates("name_norm")
    lut = base.set_index("name_norm")
    seats = filled[filled["nn"] != ""].drop_duplicates("nn")
    matched = seats["nn"].isin(lut.index)
    a.check("A-SEAT-JOIN", matched.mean() >= EXPECT["SEAT_JOIN_MIN"],
            f"{matched.mean()*100:.1f}% of {len(seats)} filled-körzet seats resolved to a centroid")

    seat_lut = lut.loc[seats.loc[matched, "nn"].tolist()]
    tree = cKDTree(latlon_to_xyz(seat_lut["centroid_lat"].astype(float).values,
                                 seat_lut["centroid_lon"].astype(float).values))
    seat_names = seat_lut["name"].values

    gdf["nearest_gp_km"] = 0.0
    gdf["nearest_gp_minutes"] = 0.0
    gdf["nearest_gp_settlement"] = pd.Series([None] * len(gdf), dtype=object, index=gdf.index)
    dmask = (gdf["is_desert"] == 1) & gdf["centroid_lat"].notna()
    if dmask.any():
        q = latlon_to_xyz(gdf.loc[dmask, "centroid_lat"].astype(float).values,
                          gdf.loc[dmask, "centroid_lon"].astype(float).values)
        dist, idx = tree.query(q, k=1)
        km = (chord_to_km(dist) * ROAD_FACTOR).round(1)
        gdf.loc[dmask, "nearest_gp_km"] = km
        gdf.loc[dmask, "nearest_gp_minutes"] = (km / AVG_SPEED_KMH * 60).round(0)
        gdf.loc[dmask, "nearest_gp_settlement"] = seat_names[idx]
        a.stat("max_desert_km", float(km.max()))


def classify(active_count, per_1000):
    if active_count == 0:
        return "desert", DESERT_BAND
    if per_1000 is None or pd.isna(per_1000):
        return "ok", ACCESS_TIERS[-1][2]
    for hi, name, band in ACCESS_TIERS:
        if per_1000 < hi:
            return name, band
    return ACCESS_TIERS[-1][1], ACCESS_TIERS[-1][2]


def main():
    a = Assertions("06_join_and_score")
    gdf = gpd.read_parquet(INTERIM / "settlement_geom.parquet")
    mem = read_parquet("practice_membership").copy()
    remap_df = read_parquet("code_remap")
    remap = dict(zip(remap_df["raw_code"], remap_df["canonical_code"]))
    mem["canonical_code"] = mem["ksh_code"].map(lambda c: remap.get(c, c))
    mem = mem.drop_duplicates(subset=["hsz_kod", "canonical_code"])

    # Vacancy lookup (optional — present from phase 2 onward).
    try:
        vac = read_parquet("vacancies")
        vstart = {h: s for h, s in zip(vac["hsz_kod"], vac["vacancy_start"]) if s}
        vac_set = set(vac["hsz_kod"])
        pers_set = set(vac.loc[vac["is_persistent"], "hsz_kod"])
    except FileNotFoundError:
        vstart, vac_set, pers_set = {}, set(), set()

    mem["is_vacant"] = mem["hsz_kod"].isin(vac_set)
    mem["is_persistent"] = mem["hsz_kod"].isin(pers_set)

    g = mem.groupby("canonical_code")
    active = g.apply(lambda d: int((~d["is_vacant"]).sum()), include_groups=False)
    vacant = g["is_vacant"].sum()
    persistent = g["is_persistent"].sum()

    def longest_days(d):
        starts = [vstart.get(h) for h in d.loc[d["is_vacant"], "hsz_kod"] if vstart.get(h)]
        if not starts:
            return pd.NA
        oldest = min(date.fromisoformat(s) for s in starts)
        return (RUN_DATE - oldest).days
    longest = g.apply(longest_days, include_groups=False)

    gdf["active_gp_count"] = gdf["ksh_code"].map(active).fillna(0).astype(int)
    gdf["vacant_count"] = gdf["ksh_code"].map(vacant).fillna(0).astype(int)
    gdf["persistently_vacant_count"] = gdf["ksh_code"].map(persistent).fillna(0).astype(int)
    gdf["longest_vacancy_days"] = gdf["ksh_code"].map(longest).astype("Int64")

    pop = pd.to_numeric(gdf["population"], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        per = gdf["active_gp_count"] / pop * 1000.0
    gdf["gps_per_1000"] = per.where(pop.notna() & (pop > 0)).round(2)

    cls = [classify(c, p) for c, p in zip(gdf["active_gp_count"], gdf["gps_per_1000"])]
    gdf["access_class"] = [c for c, _ in cls]
    gdf["access_band"] = [b for _, b in cls]
    gdf["is_desert"] = (gdf["active_gp_count"] == 0).astype(int)

    # Nearest functioning GP: distance from each desert to the nearest seat of a FILLED körzet.
    nearest_gp(a, gdf, vac_set)

    desert_frac = gdf["is_desert"].mean()
    pop_null = pop.isna().mean()
    subset_ok = bool((gdf["persistently_vacant_count"] <= gdf["vacant_count"]).all())
    a.check("A-PERSIST-SUBSET", subset_ok, "persistently_vacant_count <= vacant_count")
    a.warn("A-DESERT-SANITY", desert_frac < EXPECT["DESERT_SANITY_MAX"], f"{desert_frac*100:.1f}% deserts")
    a.warn("A-POP-NULL", pop_null < EXPECT["POP_NULL_MAX"], f"{pop_null*100:.2f}% null population")
    a.stat("desert_count", int(gdf["is_desert"].sum()))
    a.stat("served_count", int((gdf["active_gp_count"] > 0).sum()))
    a.stat("settlements_with_vacancy", int((gdf["vacant_count"] > 0).sum()))

    gdf.to_parquet(INTERIM / "settlements_scored.parquet")
    a.save()
    print(f"\nscored {len(gdf)}: {int(gdf['is_desert'].sum())} deserts, "
          f"{int((gdf['vacant_count']>0).sum())} with >=1 vacant körzet")
    print("  access_class:", gdf["access_class"].value_counts().to_dict())


if __name__ == "__main__":
    main()
