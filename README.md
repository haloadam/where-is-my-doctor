# GP Desert Map — Hungary · Háziorvosi sivatagok Magyarországon

A free, static, monthly-updated interactive map of GP (háziorvos) access across every Hungarian
settlement. It shows which settlements have **no functioning family doctor** (their körzet is
vacant), how far residents must travel to the nearest working GP, and which practices are unfilled.

Built from official open data, rendered with MapLibre + PMTiles, and hosted on GitHub Pages.

![overview](docs/overview.png)

## What it shows

- **Choropleth** coloured by GP access (`gps_per_1000`, computed from *functioning* körzets):
  green = ok · yellow = moderate · orange = low · red = critical · **purple = desert**.
- A settlement is a **desert** when every körzet serving it is *vacant* (betöltetlen) — the permanent
  GP post is empty (a temporary substitute may stand in). ~21% of settlements (mostly small villages).
- **Vacancy overlay** (toggleable): currently-vacant and *persistently*-vacant (tartósan betöltetlen)
  körzets as points; persistent ones get a yellow ring.
- **Click any settlement** for population, working/vacant körzet counts, GPs per 1,000, nearest GP
  and distance, and how long the post has been empty.
- A sortable **100-worst-served** table and a **data-freshness** badge.

## Data sources

| Input | Source | Notes |
|---|---|---|
| Active GP practices | NEAK `Haziorvosi_szolgalatok` XLSX | 6,367 körzets; col K lists served settlements by KSH code |
| Vacant practices | NEAK `Betoltetlen_haziorvosi_szolgalatok` PDF | 1,021 vacant körzets (parsed, no OCR) |
| Persistence flag | OKFŐ `tartósan betöltetlen` HTML table | adds the >6-month-vacant flag |
| Population + KSH codes | KSH Helységnévtár XLSX | per-settlement resident population |
| Settlement geometry | OpenStreetMap `admin_level=8` (czinkos Gist) | 3,155 settlements |

Licensing: KSH data is CC BY 4.0 (*Forrás: KSH*). NEAK/OKFŐ vacancy lists are public-interest
(közérdekű) data by district. OSM boundaries are ODbL. See the page footer for links.

> **Methodology note.** Distances are straight-line × 1.4 (a road-factor approximation) in v1;
> the schema is OSRM-upgradeable. Budapest is treated as one unit (the 23 kerület körzets are
> aggregated to match the single OSM city polygon).

## Quickstart

The system Python is likely 3.14, which is too new for the geo wheels — the pipeline pins **3.12**.

```bash
brew install python@3.12 tippecanoe     # toolchain
bash scripts/bootstrap.sh               # creates .venv (3.12) + installs requirements
. .venv/bin/activate

python pipeline/run_all.py              # fetch live sources → parse → score → emit → tile
bash scripts/build_site.sh              # assemble dist/
python scripts/serve.py 8080 dist       # Range-capable preview (http.server is NOT — PMTiles needs Range)
# open http://localhost:8080
```

`run_all.py` runs steps `01`–`07` then builds the tiles. Step `07` runs the full assertion suite and
**exits non-zero on any hard failure**, so a broken upstream file fails the build instead of shipping
bad data.

## Pipeline

```
pipeline/
  00_config.py          constants, URLs, assertion baselines
  01_download.py        fetch 4 sources → raw/ (+ dated snapshot, magic-byte check, fail-safe reuse)
  02_parse_active.py    active XLSX → explode col K → (körzet, settlement) memberships
  03_parse_vacancy.py   vacancy PDF (pdfplumber) + OKFŐ HTML → vacancies (cross-checked)
  04_parse_ksh.py       KSH gazetteer → canonical 3,155-settlement universe (Budapest aggregated)
  05_geometry_bridge.py OSM admin_level=8 → polygons, name-joined to KSH (3155/3155, 100%)
  06_join_and_score.py  functioning vs vacant körzets → access class, desert flag, nearest GP
  07_emit.py            settlements.geojson + vacant_points + worst_100 + meta + RUN ALL ASSERTIONS
  run_all.py            orchestrator (01–07 + build_tiles.sh)
```

`raw/` and `interim/` are gitignored (re-derivable). The committed outputs are
`tiles/settlements.pmtiles`, `processed/{worst_100.*,meta.json,build_report.json}`, and `web/`.

## Deployment (GitHub Pages)

Two decoupled workflows using the official Pages flow:

- **`data.yml`** — monthly cron (+ manual): fetches sources, runs the pipeline, builds tiles, commits
  `processed/` + `tiles/`. No router/Docker at runtime.
- **`deploy.yml`** — on data/web change (+ manual): assembles `dist/` and deploys via
  `actions/deploy-pages`. Deploys from a clean checkout with no pipeline run.

Enable Pages → *Build and deployment* → **GitHub Actions**, then trigger `deploy.yml` once.

## Tech

MapLibre GL JS + a single `.pmtiles` archive (vector tiles, byte-range served) — all display
properties baked into the tiles, so styling and popups need no runtime data join. Vendored libraries
(no CDN) for unattended-deploy resilience. Target: < 8 MB tiles, < 5 s first paint on mobile
(current: ~4 MB).
