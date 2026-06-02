#!/usr/bin/env bash
# Build the single vector-tile archive: two layers (settlements polygons + vacant points)
# baked with all display properties, so MapLibre styles/popups need no runtime data join.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="tiles/settlements.pmtiles"
SET="processed/settlements.geojson"
VAC="processed/vacant_points.geojson"

[ -f "$SET" ] || { echo "missing $SET — run the pipeline first" >&2; exit 1; }

tippecanoe -o "$OUT" --force \
  -Z5 -z11 \
  --simplification=8 \
  --detect-shared-borders \
  --coalesce-densest-as-needed \
  --maximum-tile-bytes=500000 \
  --attribute-type=ksh_code:string \
  -L "settlements:$SET" \
  -L "vacant:$VAC"

BYTES=$(wc -c < "$OUT")
echo "tiles: $OUT  ${BYTES} bytes"
if [ "$BYTES" -lt 8388608 ]; then echo "A-TILE-BYTES OK (<8MB)"; else echo "A-TILE-BYTES FAIL (>=8MB)" >&2; exit 1; fi

# A-TILE-KSH: leading-zero KSH codes must survive as strings (not int-coerced) in the tiles.
# (grep -c reads to EOF so tippecanoe-decode isn't SIGPIPE'd under `set -o pipefail`.)
if command -v tippecanoe-decode >/dev/null 2>&1; then
  HIT=$(tippecanoe-decode "$OUT" 2>/dev/null | grep -c '"ksh_code": *"0[0-9]' || true)
  if [ "${HIT:-0}" -gt 0 ]; then
    echo "A-TILE-KSH OK (${HIT} leading-zero codes preserved as strings)"
  else
    echo "A-TILE-KSH FAIL (no leading-zero ksh_code string found)" >&2; exit 1
  fi
fi
