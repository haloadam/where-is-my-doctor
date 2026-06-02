"""Single source of constants for the GP Desert Map pipeline.

Run `python pipeline/00_config.py` to print a summary / validate paths.
All other steps do `from lib.config import ...` (works because running
`python pipeline/NN_step.py` puts `pipeline/` on sys.path[0]).
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
SNAPSHOTS = RAW / "snapshots"
INTERIM = ROOT / "interim"
PROCESSED = ROOT / "processed"
TILES = ROOT / "tiles"
WEB = ROOT / "web"
DATA_MANUAL = ROOT / "data" / "manual"

for _p in (RAW, SNAPSHOTS, INTERIM, PROCESSED, TILES):
    _p.mkdir(parents=True, exist_ok=True)

# --- Source URLs (all verified live during recon) ----------------------------
KSH_YEAR = 2025  # bumps annually; gazetteer filename embeds the year

URLS = {
    # NEAK active GP practices — one bulk XLSX (replaces the orvoskereso scrape).
    "active": "https://www.neak.gov.hu/pfile/file?path=/letoltheto/altfin_dok/szerzodott_szolgaltatok/Haziorvosi_szolgalatok_xls&inline=true",
    # NEAK vacant GP practices — PDF (real text, no OCR).
    "vacancy": "https://www.neak.gov.hu/pfile/file?path=/letoltheto/altfin_dok/szerzodott_szolgaltatok/Betoltetlen_haziorvosi_szolgalatok&inline=true",
    # OKFO persistently-vacant HTML table (adds the "tartosan betoltetlen" flag).
    "okfo": "https://alapellatas.okfo.gov.hu/tajekoztato-a-tartosan-betoltetlen-haziorvosi-korzetekrol/",
    # KSH Helysegnevtar gazetteer — per-settlement population + KSH codes.
    "ksh": f"https://www.ksh.hu/docs/helysegnevtar/hnt_letoltes_{KSH_YEAR}.xlsx",
    # OSM admin_level=8 settlement polygons (czinkos Gist, raw).
    "osm": "https://gist.githubusercontent.com/czinkos/bedb669ca606627780483e1949ad4bb4/raw/hungary_settlements.geojson",
}

# Raw filenames on disk (extension matters for the magic-byte check).
RAW_FILES = {
    "active": RAW / "active.xlsx",
    "vacancy": RAW / "vacancy.pdf",
    "okfo": RAW / "okfo.html",
    "ksh": RAW / "ksh_hnt.xlsx",
    "osm": RAW / "osm_admin8.geojson",
}

# Magic bytes per source (first bytes of a valid file).
MAGIC = {
    "active": b"PK",      # XLSX = zip
    "vacancy": b"%PDF",
    "okfo": None,         # HTML — checked as "looks like text/html", not magic
    "ksh": b"PK",
    "osm": None,          # GeoJSON — starts with '{' possibly after whitespace
}

# Browser-ish headers (NEAK / OKFO 403 plain UAs).
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HTTP_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "hu,en;q=0.8"}

# --- Scoring -----------------------------------------------------------------
ROAD_FACTOR = 1.4        # straight-line km -> approx road km (v1 fallback; OSRM-upgradeable)
AVG_SPEED_KMH = 50.0     # for nearest_gp_minutes estimate (v1 fallback)

# v2 routing (OSRM road distances). The cache is precomputed occasionally and committed;
# the monthly pipeline only reads it (06 prefers it, falls back to haversine x1.4).
OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5001")
ROAD_K = 20              # nearest seat settlements cached per settlement (haversine-prefilter)
ROAD_CACHE = PROCESSED / "road_cache.csv"
ROAD_CACHE_META = PROCESSED / "road_cache_meta.json"

# Access tiers for SERVED settlements, keyed on gps_per_1000.
# Deserts (active_gp_count == 0) are a separate category handled before these.
# (max_exclusive, class_name, band) — band: 0 desert, 1 critical .. 4 ok.
DESERT_BAND = 0
ACCESS_TIERS = [
    (0.20, "critical", 1),          # red
    (0.40, "low", 2),               # orange
    (0.60, "moderate", 3),          # yellow
    (float("inf"), "ok", 4),        # green
]

# --- Assertion baselines (re-verified against the real bytes) ----------------
EXPECT = {
    "ACTIVE_ROWS": (6367, 0.02),         # value, tolerance fraction
    "COUNTIES": 20,
    "MEMBERSHIPS": (8147, 0.03),
    "MEMBERSHIP_FANOUT": (1.20, 1.40),   # mean served-settlements per korzet (low, high)
    "DISTINCT_K_CODES": 3177,
    "VACANCY_ROWS": (1021, 0.05),        # 970..1072
    "VAC_TYPES": {"V": 415, "F": 350, "G": 256},
    "VAC_TYPE_TOL": 0.10,
    "KSH_ROWS": (3178, 0.03),
    "VAC_XCHECK_TOL": 0.01,              # pdfplumber vs stdlib cross-check
    "VAC_JOIN_MIN": 0.99,                # fraction of vacancy korzets present in active
    "JOIN_MIN": 0.99,                    # fraction of col-K codes present in gazetteer
    "SEAT_JOIN_MIN": 0.98,               # fraction of GP seats resolved to a centroid
    "OKFO_JOIN_MIN": 0.90,               # warn-only
    "POP_NULL_MAX": 0.01,                # warn-only
    "DESERT_SANITY_MAX": 0.25,           # warn-only (true value ~21%: served only by vacant posts)
    "TILE_BYTES_MAX": 8 * 1024 * 1024,   # 8 MB
    "ROAD_COVERAGE_MIN": 0.99,           # 08: fraction of settlements with >=1 routable seat
    "ROAD_USED_MIN": 0.95,               # 06: fraction of deserts resolved via road (else stale cache)
}

# Hungary map view
MAP_CENTER = [19.503304, 47.162494]  # lon, lat
MAP_ZOOM = 7
