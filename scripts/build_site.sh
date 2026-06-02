#!/usr/bin/env bash
# Assemble the deployable static site into dist/ from committed web/ + tiles/ + processed/.
# No pipeline run required — deploys from a clean checkout.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf dist
mkdir -p dist/data

cp -R web/index.html web/css web/js web/vendor web/favicon.svg dist/
cp tiles/settlements.pmtiles dist/data/
cp processed/worst_100.json processed/meta.json dist/data/
cp docs/overview.png dist/og-image.png   # link-preview image referenced by the og:image meta tag
touch dist/.nojekyll

echo "dist/ assembled:"
find dist -type f | sort
echo "total size: $(du -sh dist | cut -f1)"
