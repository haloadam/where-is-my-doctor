#!/usr/bin/env python
"""Step 8 (occasional, NOT in the monthly 01–07 chain) — precompute a stable road-distance cache.

For every settlement, query a local OSRM for the driving distance + time to its K nearest *seat*
settlements (haversine-prefiltered). Roads are stable, so this is run occasionally and committed;
the monthly pipeline (06) only reads processed/road_cache.csv and takes the min over the seats that
are FILLED that month. Requires `bash scripts/osrm_build.sh` running (osrm-routed on OSRM_URL)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree

from lib.assertions import Assertions
from lib.config import EXPECT, INTERIM, OSRM_URL, ROAD_CACHE, ROAD_CACHE_META, ROAD_K
from lib.haversine import haversine_km, latlon_to_xyz
from lib.io import read_parquet, write_json
from lib.seats import seat_points


def osrm_table(src_lat, src_lon, dst_latlon):
    """One source -> many destinations. Returns (dist_km[], dur_min[]) with None for unreachable."""
    coords = f"{src_lon},{src_lat};" + ";".join(f"{lo},{la}" for la, lo in dst_latlon)
    url = (f"{OSRM_URL}/table/v1/driving/{coords}"
           f"?sources=0&annotations=duration,distance")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d.get("code") != "Ok":
        return [None] * len(dst_latlon), [None] * len(dst_latlon)
    dist = d["distances"][0][1:]          # drop self (index 0)
    dur = d["durations"][0][1:]
    km = [None if x is None else round(x / 1000.0, 1) for x in dist]
    mn = [None if x is None else round(x / 60.0) for x in dur]
    return km, mn


def main():
    a = Assertions("08_road_cache")
    gdf = gpd.read_parquet(INTERIM / "settlement_geom.parquet")
    practices = read_parquet("practices")
    seats, seat_cov = seat_points(practices, gdf)
    a.check("A-SEAT-JOIN", seat_cov >= EXPECT["SEAT_JOIN_MIN"], f"{seat_cov*100:.1f}% seats resolved")

    seat_lat = seats["seat_lat"].to_numpy(float)
    seat_lon = seats["seat_lon"].to_numpy(float)
    seat_ksh = seats["seat_ksh"].to_numpy()
    seat_name = seats["seat_name"].to_numpy()
    tree = cKDTree(latlon_to_xyz(seat_lat, seat_lon))

    pts = gdf.dropna(subset=["centroid_lat"]).copy()
    pts["centroid_lat"] = pts["centroid_lat"].astype(float)
    pts["centroid_lon"] = pts["centroid_lon"].astype(float)
    k = min(ROAD_K + 1, len(seats))       # +1 so we can drop self if a settlement is its own seat

    rows, covered, total = [], 0, len(pts)
    for i, (_, s) in enumerate(pts.iterrows()):
        _, idx = tree.query(latlon_to_xyz([s.centroid_lat], [s.centroid_lon]), k=k)
        cand = [j for j in np.atleast_1d(idx[0]) if seat_ksh[j] != s.ksh_code][:ROAD_K]
        dst = [(seat_lat[j], seat_lon[j]) for j in cand]
        km, mn = osrm_table(s.centroid_lat, s.centroid_lon, dst)
        got = False
        for j, dk, dm in zip(cand, km, mn):
            if dk is None:
                continue
            got = True
            rows.append({"from_ksh": s.ksh_code, "to_ksh": seat_ksh[j], "to_name": seat_name[j],
                         "road_km": dk, "drive_minutes": dm,
                         "haversine_km": round(float(haversine_km(s.centroid_lat, s.centroid_lon,
                                                                   seat_lat[j], seat_lon[j])), 1)})
        covered += int(got)
        if (i + 1) % 500 == 0:
            print(f"  routed {i+1}/{total} settlements...", flush=True)

    cache = pd.DataFrame(rows)
    coverage = covered / total
    a.check("A-ROAD-COVERAGE", coverage >= EXPECT["ROAD_COVERAGE_MIN"],
            f"{coverage*100:.2f}% of settlements have >=1 routable seat")
    sane = (cache["road_km"] >= cache["haversine_km"] - 0.2).mean()  # road >= straight-line (tolerance)
    a.warn("A-ROAD-SANE", sane > 0.98, f"{sane*100:.1f}% of pairs have road_km >= haversine_km")
    ratio = (cache["road_km"] / cache["haversine_km"].replace(0, np.nan))
    a.stat("road_pairs", len(cache))
    a.stat("road_ratio_median", round(float(ratio.median()), 3))
    a.stat("road_pairs_ratio_gt3", int((ratio > 3).sum()))

    cache.to_csv(ROAD_CACHE, index=False)
    write_json(ROAD_CACHE_META, {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "osrm_url": OSRM_URL, "profile": "car", "K": ROAD_K,
        "settlements": total, "pairs": len(cache), "coverage": round(coverage, 4),
    })
    a.save()
    print(f"\nwrote {ROAD_CACHE} ({len(cache)} pairs, {coverage*100:.2f}% coverage, "
          f"median road/straight ratio {ratio.median():.2f})")


if __name__ == "__main__":
    main()
