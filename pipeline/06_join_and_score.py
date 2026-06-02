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
from lib.config import AVG_SPEED_KMH, EXPECT, INTERIM, ROAD_CACHE, ROAD_FACTOR
from lib.haversine import chord_to_km, latlon_to_xyz
from lib.io import read_parquet
from lib.scoring import classify
from lib.seats import filled_seat_codes, seat_points

RUN_DATE = date.today()


def nearest_gp(a, gdf, vac_set):
    """nearest_gp_km/minutes/settlement for each desert (the nearest FILLED körzet seat).

    Prefers real OSRM road distances from processed/road_cache.csv (v2); falls back to
    haversine x ROAD_FACTOR (v1) per-desert when no cached filled seat is available.
    `nearest_gp_method` records which was used. Served settlements get 0 (functioning access)."""
    practices = read_parquet("practices")
    seats, cov = seat_points(practices, gdf)
    a.check("A-SEAT-JOIN", cov >= EXPECT["SEAT_JOIN_MIN"], f"{cov*100:.1f}% of seats resolved to a centroid")
    filled = filled_seat_codes(practices, gdf, vac_set)

    # v1 baseline: nearest FILLED seat by straight line x 1.4, for every desert.
    fseats = seats[seats["seat_ksh"].isin(filled)].reset_index(drop=True)
    tree = cKDTree(latlon_to_xyz(fseats["seat_lat"].to_numpy(float), fseats["seat_lon"].to_numpy(float)))
    fnames = fseats["seat_name"].to_numpy()

    gdf["nearest_gp_km"] = 0.0
    gdf["nearest_gp_minutes"] = 0.0
    gdf["nearest_gp_settlement"] = pd.Series([None] * len(gdf), dtype=object, index=gdf.index)
    gdf["nearest_gp_method"] = pd.Series([None] * len(gdf), dtype=object, index=gdf.index)
    dmask = (gdf["is_desert"] == 1) & gdf["centroid_lat"].notna()
    if dmask.any():
        q = latlon_to_xyz(gdf.loc[dmask, "centroid_lat"].astype(float).values,
                          gdf.loc[dmask, "centroid_lon"].astype(float).values)
        dist, idx = tree.query(q, k=1)
        km = (chord_to_km(dist) * ROAD_FACTOR).round(1)
        gdf.loc[dmask, "nearest_gp_km"] = km
        gdf.loc[dmask, "nearest_gp_minutes"] = (km / AVG_SPEED_KMH * 60).round(0)
        gdf.loc[dmask, "nearest_gp_settlement"] = fnames[idx]
        gdf.loc[dmask, "nearest_gp_method"] = "straight"

    # v2 override: real road distance to the nearest FILLED cached seat, where available.
    if ROAD_CACHE.exists():
        cache = pd.read_csv(ROAD_CACHE, dtype={"from_ksh": str, "to_ksh": str})
        cache = cache[cache["to_ksh"].isin(filled)]
        best = cache.loc[cache.groupby("from_ksh")["road_km"].idxmin()].set_index("from_ksh")
        used = 0
        for i in gdf.index[dmask]:
            code = gdf.at[i, "ksh_code"]
            if code in best.index:
                r = best.loc[code]
                gdf.at[i, "nearest_gp_km"] = float(r["road_km"])
                gdf.at[i, "nearest_gp_minutes"] = float(r["drive_minutes"])
                gdf.at[i, "nearest_gp_settlement"] = r["to_name"]
                gdf.at[i, "nearest_gp_method"] = "road"
                used += 1
        frac = used / max(1, int(dmask.sum()))
        a.warn("A-ROAD-USED", frac >= EXPECT["ROAD_USED_MIN"], f"{frac*100:.1f}% of deserts via road")
        a.stat("nearest_gp_road_share", round(frac, 4))
    if dmask.any():
        a.stat("max_desert_km", float(gdf.loc[dmask, "nearest_gp_km"].max()))


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
