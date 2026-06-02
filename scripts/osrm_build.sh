#!/usr/bin/env bash
# v2 routing: build a local OSRM (car profile) for Hungary and start the router on :5000.
# One-time / occasional — its output (processed/road_cache.csv) is committed and reused monthly.
# Idempotent: skips the PBF download and preprocess if already present.
set -euo pipefail
cd "$(dirname "$0")/.."

OSRM_DIR="osrm"
PBF="hungary-latest.osm.pbf"
PBF_URL="https://download.geofabrik.de/europe/hungary-latest.osm.pbf"
IMAGE="${OSRM_IMAGE:-osrm/osrm-backend:latest}"
PORT="${OSRM_PORT:-5001}"   # 5000 is taken by AirPlay Receiver on macOS
NAME="gp-osrm"
mkdir -p "$OSRM_DIR"

dr() { docker run --rm -t -v "$PWD/$OSRM_DIR:/data" "$IMAGE" "$@"; }

if [ ! -f "$OSRM_DIR/$PBF" ]; then
  echo "↓ downloading $PBF ..."
  curl -sSL -o "$OSRM_DIR/$PBF" "$PBF_URL"
fi
echo "PBF: $(du -h "$OSRM_DIR/$PBF" | cut -f1)"

if [ ! -f "$OSRM_DIR/hungary-latest.osrm.mldgr" ]; then
  echo "▸ osrm-extract (car) ..."; dr osrm-extract -p /opt/car.lua "/data/$PBF"
  echo "▸ osrm-partition ...";     dr osrm-partition /data/hungary-latest.osrm
  echo "▸ osrm-customize ...";     dr osrm-customize /data/hungary-latest.osrm
else
  echo "preprocessed graph already present — skipping extract/partition/customize"
fi

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "$PORT:5000" -v "$PWD/$OSRM_DIR:/data" "$IMAGE" \
  osrm-routed --algorithm mld --max-table-size 4000 /data/hungary-latest.osrm >/dev/null
echo "✓ osrm-routed up on http://localhost:$PORT  (container: $NAME, image: $IMAGE)"
echo "  record for reproducibility:"; docker image inspect "$IMAGE" -f 'image={{index .RepoDigests 0}}' 2>/dev/null || true
