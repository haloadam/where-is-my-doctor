#!/usr/bin/env bash
# Create/refresh the pinned Python 3.12 virtualenv. Hard-fails if 3.12 is unavailable,
# because the geo stack (shapely/pyproj/pyogrio/geopandas/scipy) has no reliable cp314 wheels.
set -euo pipefail
cd "$(dirname "$0")/.."

PY312="$(command -v python3.12 || true)"
if [ -z "$PY312" ] && [ -x /opt/homebrew/opt/python@3.12/bin/python3.12 ]; then
  PY312=/opt/homebrew/opt/python@3.12/bin/python3.12
fi
if [ -z "$PY312" ]; then
  echo "ERROR: python3.12 not found. Install it first:  brew install python@3.12" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  "$PY312" -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

ACTIVE_VER="$(python -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
if [ "$ACTIVE_VER" != "3.12" ]; then
  echo "ERROR: active interpreter is $ACTIVE_VER, expected 3.12" >&2
  exit 1
fi

python -m pip install -U pip
python -m pip install -r requirements.txt
echo "bootstrap OK — venv ready (Python $ACTIVE_VER). Activate with: . .venv/bin/activate"
