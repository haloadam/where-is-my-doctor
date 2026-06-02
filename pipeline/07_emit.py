#!/usr/bin/env python
"""Step 7 — emit the tiler inputs + table + meta, then run the full assertion suite.

Outputs (processed/):
  settlements.geojson      polygons + all display props (tiler input; gitignored)
  vacant_points.geojson    centroids of settlements with vacancies (overlay layer)
  worst_100.{json,csv}     the worst-access settlements table
  meta.json                freshness + observed counts
  build_report.json        every assertion result (written incrementally by all steps)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from lib.assertions import Assertions
from lib.config import INTERIM, PROCESSED, RAW
from lib.io import read_json, write_json

PROP_COLS = [
    "ksh_code", "name", "county", "population", "active_gp_count", "gps_per_1000",
    "access_class", "access_band", "is_desert", "nearest_gp_km", "nearest_gp_minutes",
    "nearest_gp_settlement", "vacant_count", "persistently_vacant_count",
    "longest_vacancy_days", "centroid_lat", "centroid_lon",
]


def _clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return None
    if isinstance(v, float):
        return v
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return v
    return v


def _props(row):
    return {c: _clean(row[c]) for c in PROP_COLS}


def round_coords(geom, nd=5):
    gj = mapping(geom)

    def r(x):
        if isinstance(x, (list, tuple)):
            return [r(i) for i in x]
        return round(x, nd)

    gj["coordinates"] = r(gj["coordinates"])
    return gj


def main():
    a = Assertions("07_emit")
    gdf = gpd.read_parquet(INTERIM / "settlements_scored.parquet")
    gdf["centroid_lat"] = pd.to_numeric(gdf["centroid_lat"], errors="coerce").round(5)
    gdf["centroid_lon"] = pd.to_numeric(gdf["centroid_lon"], errors="coerce").round(5)

    # settlements.geojson
    feats = []
    for _, row in gdf.iterrows():
        geom = row["geometry"]
        feats.append({"type": "Feature", "properties": _props(row),
                      "geometry": round_coords(geom) if geom is not None else None})
    write_json(PROCESSED / "settlements.geojson",
               {"type": "FeatureCollection", "features": feats})

    # vacant_points.geojson (overlay) — centroids of settlements with vacancies.
    vac = gdf[gdf["vacant_count"] > 0]
    vfeats = []
    for _, row in vac.iterrows():
        if pd.isna(row["centroid_lon"]):
            continue
        vfeats.append({"type": "Feature", "properties": _props(row),
                       "geometry": {"type": "Point",
                                    "coordinates": [row["centroid_lon"], row["centroid_lat"]]}})
    write_json(PROCESSED / "vacant_points.geojson",
               {"type": "FeatureCollection", "features": vfeats})

    # worst_100 — desert first, then nearest_gp_km desc, then gps_per_1000 asc, pop desc.
    w = gdf.copy()
    w["_km"] = pd.to_numeric(w["nearest_gp_km"], errors="coerce").fillna(-1)
    w["_per"] = pd.to_numeric(w["gps_per_1000"], errors="coerce").fillna(0)
    w["_pop"] = pd.to_numeric(w["population"], errors="coerce").fillna(0)
    w = w.sort_values(by=["is_desert", "_km", "_per", "_pop"],
                      ascending=[False, False, True, False]).head(100)
    worst = [dict(rank=i + 1, **_props(row)) for i, (_, row) in enumerate(w.iterrows())]
    write_json(PROCESSED / "worst_100.json", worst)
    pd.DataFrame(worst).to_csv(PROCESSED / "worst_100.csv", index=False)

    # meta.json
    manifest = read_json(RAW / "fetch_manifest.json") if (RAW / "fetch_manifest.json").exists() else {}
    report = a.report
    stats = report.get("stats", {})
    meta = {
        "generated": manifest.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        "active_rows": stats.get("active_rows"),
        "vacant_rows": stats.get("vacant_rows", 0),
        "settlement_count": int(len(gdf)),
        "desert_count": stats.get("desert_count"),
        "degraded": manifest.get("degraded", False) or report.get("degraded", False),
    }
    write_json(PROCESSED / "meta.json", meta)

    a.stat("emitted_features", len(feats))
    print(f"\nemitted {len(feats)} settlements, {len(vfeats)} vacant points, "
          f"worst_100 ({len(worst)}), meta {meta}")
    a.finalize()  # exits 1 on any hard failure


if __name__ == "__main__":
    main()
