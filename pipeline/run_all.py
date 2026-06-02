#!/usr/bin/env python
"""Run the full pipeline (01–07) then build the vector tiles.
Any step that exits non-zero aborts the run (07 exits 1 on a hard assertion failure)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    "pipeline/01_download.py",
    "pipeline/02_parse_active.py",
    "pipeline/03_parse_vacancy.py",
    "pipeline/04_parse_ksh.py",
    "pipeline/05_geometry_bridge.py",
    "pipeline/06_join_and_score.py",
    "pipeline/07_emit.py",
]


def main():
    for step in STEPS:
        print(f"\n===== {step} =====", flush=True)
        subprocess.run([sys.executable, step], cwd=ROOT, check=True)
    print("\n===== scripts/build_tiles.sh =====", flush=True)
    subprocess.run(["bash", "scripts/build_tiles.sh"], cwd=ROOT, check=True)
    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
