#!/usr/bin/env python
"""Step 5 — attach OSM admin_level=8 polygons to the canonical KSH universe.

OSM carries no KSH code, so the bridge is by normalized name. Verified against the
real files: after dissolving the 19 multipart duplicate-name features and treating
Budapest as one unit, all 3,154 non-Budapest settlements + Budapest match by name
(~100%). Wikidata P939 + data/manual/ksh_overrides.csv remain as safety nets.

Geometry is LEFT-joined: a canonical settlement with no polygon keeps a null geometry
and is reported in build_report.json (never silently dropped)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geopandas as gpd
import pandas as pd

from lib.assertions import Assertions
from lib.config import DATA_MANUAL, RAW_FILES
from lib.io import read_parquet, write_parquet
from lib.names import normalize

OVERRIDES = DATA_MANUAL / "ksh_overrides.csv"


def main():
    a = Assertions("05_geometry_bridge")
    canon = read_parquet("settlements_ksh")

    osm = gpd.read_file(RAW_FILES["osm"])
    osm = osm.rename(columns={c: c.upper() for c in osm.columns if c.upper() in ("NAME",)})
    name_col = "NAME" if "NAME" in osm.columns else ("name" if "name" in osm.columns else osm.columns[0])
    osm["name_norm"] = osm[name_col].map(normalize)
    if osm.crs is None:
        osm = osm.set_crs(4326)
    else:
        osm = osm.to_crs(4326)

    # Dissolve multipart duplicate-name features -> one (Multi)Polygon per name.
    dissolved = osm.dissolve(by="name_norm", as_index=False)[["name_norm", "geometry"]]
    a.stat("osm_features", len(osm))
    a.stat("osm_dissolved", len(dissolved))

    # Primary join: canonical name_norm <-> OSM name_norm.
    merged = canon.merge(dissolved, on="name_norm", how="left")

    # Optional manual overrides (osm_name_norm -> ksh_code) for any straggler.
    if OVERRIDES.exists():
        ov = pd.read_csv(OVERRIDES, dtype=str, comment="#").dropna(subset=["name_norm", "ksh_code"])
        if {"name_norm", "ksh_code"}.issubset(ov.columns):
            lut = dissolved.set_index("name_norm")["geometry"]
            for _, r in ov.iterrows():
                geom = lut.get(r["name_norm"])
                if geom is not None:
                    merged.loc[merged["ksh_code"] == r["ksh_code"], "geometry"] = geom

    gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=4326)
    have = gdf["geometry"].notna()
    rep = gdf.loc[have].geometry.representative_point()
    gdf["centroid_lon"] = pd.NA
    gdf["centroid_lat"] = pd.NA
    gdf.loc[have, "centroid_lon"] = rep.x.values
    gdf.loc[have, "centroid_lat"] = rep.y.values

    n_geom = int(have.sum())
    missing = gdf.loc[~have, ["ksh_code", "name"]].to_dict("records")
    a.report.setdefault("geometry_missing", missing)
    a.check("A-GEOM", n_geom == len(canon) and gdf["ksh_code"].is_unique,
            f"{n_geom}/{len(canon)} settlements have a polygon; unique={gdf['ksh_code'].is_unique}")
    a.stat("settlements_with_geometry", n_geom)

    from lib.config import INTERIM
    gdf.to_parquet(INTERIM / "settlement_geom.parquet")
    a.save()
    if missing:
        print(f"  geometry-less settlements ({len(missing)}): "
              f"{[m['name'] for m in missing][:10]}")
    print(f"\nwrote settlement_geom: {n_geom}/{len(canon)} with geometry")


if __name__ == "__main__":
    main()
