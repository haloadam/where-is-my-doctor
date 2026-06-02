#!/usr/bin/env python
"""Compare v1 (haversine x 1.4) vs v2 (OSRM road) nearest-GP distances for every desert,
and report how much the displayed data changes. Run after the pipeline + 08_road_cache.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from lib.config import AVG_SPEED_KMH, INTERIM, ROAD_CACHE, ROAD_FACTOR
from lib.haversine import haversine_km, latlon_to_xyz
from lib.io import read_parquet
from lib.seats import filled_seat_codes, seat_points


def pct(a, b):  # change from a (v1) to b (v2)
    return (b - a) / a * 100.0


def main():
    gdf = gpd.read_parquet(INTERIM / "settlement_geom.parquet")
    practices = read_parquet("practices")
    vac_set = set(read_parquet("vacancies")["hsz_kod"])
    scored = gpd.read_parquet(INTERIM / "settlements_scored.parquet")

    filled = filled_seat_codes(practices, gdf, vac_set)
    seats, _ = seat_points(practices, gdf)
    fs = seats[seats["seat_ksh"].isin(filled)].reset_index(drop=True)
    tree = cKDTree(latlon_to_xyz(fs["seat_lat"].to_numpy(float), fs["seat_lon"].to_numpy(float)))

    cache = pd.read_csv(ROAD_CACHE, dtype={"from_ksh": str, "to_ksh": str})
    cache = cache[cache["to_ksh"].isin(filled)]
    best = cache.loc[cache.groupby("from_ksh")["road_km"].idxmin()].set_index("from_ksh")

    rows = []
    d = scored[(scored["is_desert"] == 1) & scored["centroid_lat"].notna()]
    for _, s in d.iterrows():
        if s["ksh_code"] not in best.index:
            continue
        # v1: nearest filled seat by straight line, x1.4
        _, j = tree.query(latlon_to_xyz([float(s.centroid_lat)], [float(s.centroid_lon)]), k=1)
        j = int(np.atleast_1d(j)[0])
        v1_km = round(float(haversine_km(s.centroid_lat, s.centroid_lon,
                                         fs.seat_lat[j], fs.seat_lon[j])) * ROAD_FACTOR, 1)
        r = best.loc[s["ksh_code"]]
        v2_km = float(r["road_km"])
        rows.append({"name": s["name"], "v1_km": v1_km, "v2_km": v2_km,
                     "v1_min": round(v1_km / AVG_SPEED_KMH * 60), "v2_min": float(r["drive_minutes"]),
                     "same_target": fs.seat_name[j] == r["to_name"]})
    df = pd.DataFrame(rows)
    n = len(df)
    df["pct_km"] = pct(df["v1_km"], df["v2_km"])
    df["abs_pct"] = df["pct_km"].abs()

    print(f"\n=== v1 (légvonal × 1.4)  vs  v2 (OSRM közúti)  —  {n} sivatag / deserts ===\n")
    print(f"  Átlagos távolság / mean distance :  v1 {df.v1_km.mean():5.1f} km  →  v2 {df.v2_km.mean():5.1f} km")
    print(f"  Medián távolság   / median        :  v1 {df.v1_km.median():5.1f} km  →  v2 {df.v2_km.median():5.1f} km")
    print(f"  Összes táv / total km             :  v1 {df.v1_km.sum():.0f}  →  v2 {df.v2_km.sum():.0f}  "
          f"({pct(df.v1_km.sum(), df.v2_km.sum()):+.1f}%)")
    print(f"  Átlagos idő / mean drive time     :  v1 {df.v1_min.mean():4.0f} perc  →  "
          f"v2 {df.v2_min.mean():4.0f} perc\n")

    print(f"  Átlagos eltérés (előjeles) / mean % change   : {df.pct_km.mean():+.1f}%")
    print(f"  Medián eltérés / median % change             : {df.pct_km.median():+.1f}%")
    print(f"  Átlagos abszolút eltérés / mean abs % change : {df.abs_pct.mean():.1f}%\n")

    longer = (df.v2_km > df.v1_km).mean() * 100
    print(f"  v2 nagyobb (hosszabb) mint v1 / v2 longer    : {longer:.0f}% of deserts")
    for t in (10, 25, 50, 100):
        print(f"    |változás| > {t:3d}% / |change| > {t:3d}% : {(df.abs_pct > t).mean()*100:5.1f}%  "
              f"({int((df.abs_pct > t).sum())} település)")
    print(f"  Más legközelebbi orvos lett / nearest GP changed town : "
          f"{(~df.same_target).mean()*100:.0f}% ({int((~df.same_target).sum())} település)\n")

    big = df.reindex(df.abs_pct.sort_values(ascending=False).index).head(8)
    print("  Legnagyobb eltérések / biggest changes:")
    for _, r in big.iterrows():
        print(f"    {r['name']:<22} v1 {r.v1_km:5.1f} km  →  v2 {r.v2_km:5.1f} km   ({r.pct_km:+.0f}%)")


if __name__ == "__main__":
    main()
