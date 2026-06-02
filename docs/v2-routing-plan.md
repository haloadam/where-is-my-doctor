# v2 — Accurate road-distance routing (OSRM)

## Context

v1 reports `nearest_gp_km` / `nearest_gp_minutes` as **straight-line (haversine) distance × 1.4**,
with travel time at a flat 50 km/h (`pipeline/lib/config.py: ROAD_FACTOR=1.4, AVG_SPEED_KMH=50`,
applied in `pipeline/06_join_and_score.py: nearest_gp()`). This is the number that tells a villager
in a desert how far the nearest *working* doctor is — and a flat ×1.4 misrepresents rural Hungary:
rivers and the Tisza/Danube with few bridges, dead-end valley roads, ferries, and the Balaton all
make the real drive much longer than the crow flies (sometimes 2–3×), while the *time* depends on
road class, not a constant speed.

v2 replaces this with **real driving distance + time from OSRM** (Open Source Routing Machine) on the
Hungarian road network. The schema was deliberately built for this: `nearest_gp_km`,
`nearest_gp_minutes`, `nearest_gp_settlement` already exist and are baked into the tiles, so the
frontend and tile shape do **not** change.

> Decision recap: during planning you chose **"Straight-line × 1.4 (v1)"** over self-hosted OSRM, on
> the basis that the schema stays OSRM-upgradeable. This is that upgrade.

## Key constraint that shapes the design

Two things change on **different cadences**:
- **Roads** are ~stable month to month.
- **Vacancies → which settlements are deserts, and which seats are *filled*** change every month.

So we must **not** recompute routes every month (OSRM preprocessing is heavy and the recon advised
keeping the monthly cron router-free). Instead:

> **Precompute a stable road-distance *cache* occasionally; do a cheap min-over-filled-seats lookup
> every month.**

A road distance between two fixed settlements doesn't change, so it can be cached and reused across
many monthly builds while the *set* of filled seats is re-evaluated each run.

## Architecture

```
        (occasional: manual / ~annual)                 (every month, existing cron)
   ┌─────────────────────────────────────┐        ┌──────────────────────────────────┐
   │ scripts/osrm_build.sh                │        │ pipeline/06_join_and_score.py     │
   │   Geofabrik HU PBF → OSRM (Docker)   │        │   read processed/road_cache.csv   │
   │ pipeline/08_road_cache.py            │  --->  │   for each desert: min road dist  │
   │   each settlement → K nearest seats  │  CSV   │   over its cached seats that are  │
   │   query OSRM /table (km + minutes)   │        │   FILLED this month               │
   │   → processed/road_cache.csv         │        │   else haversine×1.4 fallback     │
   └─────────────────────────────────────┘        └──────────────────────────────────┘
```

The cache keys on **settlement → its K nearest *seat-capable* settlements** (a "seat" = a settlement
that hosts ≥1 körzet surgery; ~1,760 of the 3,155, and a stable set). Caching nearest-seats rather
than a full 3,155² matrix keeps it to ~50k rows; caching *seats* (not just current deserts) means the
cache survives the monthly desert-set churn.

## Work items

### 1. OSRM service — `scripts/osrm_build.sh`
- Download `https://download.geofabrik.de/europe/hungary-latest.osm.pbf` (~300 MB) into `raw/`
  (gitignored; add a `routing` entry to `pipeline/lib/config.py: URLS` or fetch in this script).
- Run the official `osrm/osrm-backend` Docker image, **MLD pipeline**:
  `osrm-extract -p /opt/car.lua hungary-latest.osm.pbf` → `osrm-partition` → `osrm-customize`, then
  `osrm-routed --algorithm mld --max-table-size 4000` on `:5000`.
  (Hungary preprocess is minutes / well under ~4 GB RAM — far lighter than the planet.)
- Pin the image tag + record the PBF download date for reproducibility.

### 2. Precompute step — `pipeline/08_road_cache.py` (outside the monthly 01–07 chain)
- Inputs: `interim/settlement_geom.parquet` (centroids), `interim/practices.parquet` (seat names).
- Build the **seat universe**: distinct seat settlements resolved to KSH code + centroid, reusing the
  exact normalize/`name_norm` join already in `06.nearest_gp()` (factor that bridge into
  `lib/` so both steps share it — avoids a second, divergent seat→KSH join).
- For each of the 3,155 settlements: **haversine-prefilter the K≈20 nearest seat settlements**
  (`scipy.cKDTree` on the 3D unit sphere — reuse `lib/haversine.py`), so OSRM only sees ~63k pairs,
  not millions.
- Query local OSRM **`/table/v1/driving`** with `?annotations=duration,distance` (distance is *not*
  returned by default), 1 source × K destinations per call (or batched). OSRM snaps centroids to the
  nearest road node automatically.
- Output `processed/road_cache.csv`: `from_ksh, to_ksh, to_name, road_km, drive_minutes` (+ a sidecar
  `road_cache_meta.json`: `computed_at, osrm_image, profile, pbf_date, K`). Committed (small, ~2 MB).
- **Assertions** (`lib/assertions.py`):
  - `A-ROAD-COVERAGE` (≥99% of settlements have ≥1 routable cached seat) — hard.
  - `A-ROAD-SANE` (`road_km ≥ haversine_km` for ~all; flag pairs with ratio >3.0 or with no route —
    islands/exclaves/disconnected graph) — warn + log count.
  - no NaN/negative distances — hard.

### 3. Monthly lookup — extend `pipeline/06_join_and_score.py: nearest_gp()`
- If `processed/road_cache.csv` exists: for each desert, take the **min `road_km` over its cached
  candidate seats that are *currently filled*** (filled = seat of ≥1 körzet not in `vac_set`); set
  `nearest_gp_km / nearest_gp_minutes / nearest_gp_settlement` from that row.
- **Fallback** to the current haversine×1.4 path when: no cache file, or a desert has no *filled*
  seat among its K cached candidates (rare with K≈20; log the count).
- Add a transparency column **`nearest_gp_method`** ∈ {`road`, `straight`} to the schema + tiles, so
  the popup can label each value honestly.
- New assertion `A-ROAD-USED` (warn): ≥95% of deserts resolved via `road` when a cache is present —
  catches a stale cache that no longer covers the current filled-seat set (→ time to regenerate).

### 4. CI — new `.github/workflows/routing.yml`
- Triggers: `workflow_dispatch` + optional low-frequency cron (e.g. annually) — **not** the monthly cron.
- Steps: checkout → run `osrm/osrm-backend` Docker image (download PBF → extract/partition/customize →
  `osrm-routed`) → `python pipeline/08_road_cache.py` → commit `processed/road_cache.csv` +
  `road_cache_meta.json`. Pushing the cache change triggers the existing `deploy.yml` via its push path.
- `data.yml` is **unchanged** — it just reads the committed cache (06 now prefers it). No router,
  Docker, or PBF in the monthly job.

### 5. Frontend — `web/js/map.js`, `web/index.html`
- Popup "Legközelebbi háziorvos" row: when `nearest_gp_method === "road"`, label it **közúti távolság**
  and show drive time prominently (e.g. *"Szulok — 12,3 km · ~18 perc autóval"*); when `straight`,
  keep the *légvonal × 1,4 (becslés)* wording + tooltip.
- Worst-100 table: the `Távolság (km)` column tooltip switches text by method; optionally add a
  `Becsült idő (perc)` value to the card/popup.
- Footer methodology: replace the "*légvonal × 1,4 közelítés (v1)*" note with the OSRM description and
  keep a one-line note that a small fallback share may still be straight-line.

## Edge cases & risks

| Risk | Handling |
|---|---|
| Centroid sits off-road (field) | OSRM snaps to nearest node; `representative_point()` already keeps it inside the polygon. Flag large snap distances. |
| Island / exclave / disconnected graph → no route | OSRM returns null → haversine fallback, counted in `A-ROAD-SANE`. |
| All K cached seats vacant this month | Fallback to haversine; pick K≈20–30 so this is rare; `A-ROAD-USED` warns if it gets common. |
| Seat set drifts (new surgery location) | Cache is by *seat*, which is stable; `A-ROAD-USED` flags drift → regenerate via `routing.yml`. |
| Reproducibility | Pin OSRM image tag + PBF date in `road_cache_meta.json`; cache is committed and diffable. |
| `road_km` (table) vs turn-by-turn differ slightly | Documented OSRM behaviour; fine for nearest-GP ranking. |

## Phasing

- **A. Local proof:** `osrm_build.sh` + `08_road_cache.py`; generate `road_cache.csv` locally; eyeball
  road-vs-haversine ratios for a sample of deserts.
- **B. Wire-in:** 06 prefers the cache + `nearest_gp_method` + assertions; rebuild tiles.
- **C. Frontend:** közúti/légvonal labelling + drive-time.
- **D. CI:** `routing.yml` for reproducible regeneration.

## Verification

```bash
# local OSRM + cache
bash scripts/osrm_build.sh                 # → osrm-routed on :5000
python pipeline/08_road_cache.py           # → processed/road_cache.csv (A-ROAD-* assertions)

# sanity: road >= straight-line, ratio mostly 1.1–1.8, flag >3 / no-route
python - <<'PY'
import pandas as pd; c=pd.read_csv("processed/road_cache.csv"); print(c.describe())
PY

# rebuild with road distances and confirm method in tiles + popup
python pipeline/run_all.py                 # 06 now uses the cache
tippecanoe-decode tiles/settlements.pmtiles 2>/dev/null | grep -m1 nearest_gp_method
python scripts/serve.py 8080 dist          # popup shows "közúti távolság · ~N perc autóval"
```

Spot-check a handful of desert→nearest-GP pairs against Google Maps driving distance; confirm the
worst-100 ordering shifts sensibly (e.g. settlements far by road but near by line jump up the list).

## Out of scope for v2 (note for later)
- Public-transport / no-car accessibility (many affected residents are elderly without a car).
- Isochrones ("within 30 min" bands) and a per-county aggregate view.
- Substitute-doctor (helyettesítő) hours, if that data ever becomes machine-readable.
