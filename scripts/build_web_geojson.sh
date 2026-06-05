#!/usr/bin/env bash
# Build the WebGL-free fallback's data: a simplified settlements polygon GeoJSON plus the
# vacant-points GeoJSON, both trimmed to the properties the popup/table need. These feed the
# Leaflet (Canvas2D) renderer used when WebGL is unavailable; committed under tiles/ next to
# settlements.pmtiles and copied into dist/data/ by build_site.sh.
#
# Topology-aware simplification (mapshaper visvalingam keep-shapes) keeps shared settlement
# borders aligned so the choropleth has no slivers/gaps. Source geojson is gitignored and
# regenerable from the pipeline; the outputs here ARE committed (the deploy uses a clean checkout).
set -euo pipefail
cd "$(dirname "$0")/.."

SET="processed/settlements.geojson"
VAC="processed/vacant_points.geojson"
OUT_SET="tiles/settlements.web.geojson"
OUT_VAC="tiles/vacant.web.geojson"

[ -f "$SET" ] || { echo "missing $SET — run the pipeline first" >&2; exit 1; }
[ -f "$VAC" ] || { echo "missing $VAC — run the pipeline first" >&2; exit 1; }

# Fields read by popupHtml() (web/js/shared.js) — ksh_code is dropped (unused in the UI).
FIELDS="name,county,population,active_gp_count,gps_per_1000,access_class,access_band,is_desert,nearest_gp_km,nearest_gp_minutes,nearest_gp_settlement,nearest_gp_method,vacant_count,persistently_vacant_count,longest_vacancy_days"

# Polygons: drop unused fields, simplify with shared-border preservation, quantise coords (~11 m).
npx --yes mapshaper@0.7.22 "$SET" \
  -filter-fields "$FIELDS" \
  -simplify visvalingam 7% keep-shapes \
  -o precision=0.0001 format=geojson "$OUT_SET"

# Vacant points: just trim fields + quantise (no geometry to simplify).
npx --yes mapshaper "$VAC" \
  -filter-fields "$FIELDS" \
  -o precision=0.0001 format=geojson "$OUT_VAC"

for f in "$OUT_SET" "$OUT_VAC"; do
  raw=$(wc -c < "$f")
  gz=$(gzip -c "$f" | wc -c)
  echo "$f  raw=$((raw/1024))KB  gz=$((gz/1024))KB"
done
