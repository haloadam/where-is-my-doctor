# Data schema & contract

This documents the data flowing between pipeline steps and the published outputs. All KSH settlement
codes are **5-digit zero-padded strings** (e.g. `05403`) — never integers (782 distinct codes have a
leading zero).

## Published outputs (committed / deployed)

### `tiles/settlements.pmtiles`
Vector tiles with two layers, all display properties baked in (so the frontend needs no runtime join):

- **`settlements`** (polygons) — properties below.
- **`vacant`** (points) — centroids of settlements with `vacant_count > 0`, same properties.

### `settlements` feature properties (also `processed/settlements.geojson`, the tiler input)

| property | type | nullable | meaning |
|---|---|---|---|
| `ksh_code` | string(5) | no | KSH settlement code; **not** the tile feature id |
| `name` | string | no | official settlement name (KSH) |
| `county` | string | no | *vármegye* (county) |
| `population` | int | yes | *Lakó-népesség* (resident population), KSH |
| `active_gp_count` | int | no | functioning (non-vacant) körzets serving the settlement |
| `gps_per_1000` | float | yes | `active_gp_count / population * 1000`; null if population null/0 |
| `access_class` | enum | no | `desert` / `critical` / `low` / `moderate` / `ok` |
| `access_band` | int 0–4 | no | 0 desert … 4 ok; drives the MapLibre `fill-color` |
| `is_desert` | 0/1 | no | 1 if `active_gp_count == 0` (purple override) |
| `nearest_gp_km` | float | no | distance to nearest functioning GP (0 for served settlements) |
| `nearest_gp_minutes` | float | no | driving time estimate |
| `nearest_gp_settlement` | string | yes | name of the nearest GP-hosting settlement |
| `nearest_gp_method` | enum | yes | `road` (OSRM) or `straight` (haversine × 1.4 fallback) |
| `vacant_count` | int | no | vacant körzets serving the settlement |
| `persistently_vacant_count` | int | no | of those, vacant > 6 months (OKFŐ); ≤ `vacant_count` |
| `longest_vacancy_days` | int | yes | days since the oldest serving vacancy; null if none |
| `centroid_lat` / `centroid_lon` | float | no | representative point of the polygon |

### `processed/worst_100.{json,csv}`
The 100 worst-served settlements (deserts first), one object per settlement with the properties above
plus a `rank` field. Drives the table on the page.

### `processed/road_cache.csv`
Stable road-distance cache (regenerated occasionally by `pipeline/08_road_cache.py`):
`from_ksh, to_ksh, to_name, road_km, drive_minutes, haversine_km`.

### `processed/meta.json`
`generated` (ISO timestamp), `active_rows`, `vacant_rows` (observed counts), `settlement_count`,
`desert_count`, `degraded` (true if a source fetch fell back to a snapshot).

### `processed/build_report.json`
Every build-time assertion result (`name`, `ok`, `hard`, `step`, `detail`) plus `stats`.

## Intermediate parquet contracts (gitignored, under `interim/`)

| file | produced by | key columns |
|---|---|---|
| `practices.parquet` | `02_parse_active` | `hsz_kod`(9-digit), `county`, `type`(V/F/G), `seat_name`, `postal`, … (cols A–M) |
| `practice_membership.parquet` | `02_parse_active` | `hsz_kod`, `ksh_code`(5-digit), `served_name` — one row per (körzet, served settlement) |
| `vacancies.parquet` | `03_parse_vacancy` | `hsz_kod`, `type`, `postal`, `vacancy_start`, `is_persistent`, `persistent_start` |
| `settlements_ksh.parquet` | `04_parse_ksh` | `ksh_code`, `name`, `name_norm`, `county`, `legal_status`, `population` (canonical 3,155 universe) |
| `code_remap.parquet` | `04_parse_ksh` | `raw_code` → `canonical_code` (Budapest kerület → parent 13578) |
| `settlement_geom.parquet` | `05_geometry_bridge` | above + `geometry`, `centroid_lat`, `centroid_lon` |
| `settlements_scored.parquet` | `06_join_and_score` | above + all scored properties |
