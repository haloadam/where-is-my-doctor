#!/usr/bin/env python
"""Print + validate the pipeline configuration (sanity check)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config as C


def main():
    print(f"ROOT = {C.ROOT}")
    print(f"KSH_YEAR = {C.KSH_YEAR}")
    print("\nSource URLs:")
    for k, v in C.URLS.items():
        print(f"  {k:8s} -> {v}")
    print("\nExpected baselines:")
    for k, v in C.EXPECT.items():
        print(f"  {k} = {v}")
    print("\nAccess tiers (gps_per_1000):")
    print(f"  desert -> band {C.DESERT_BAND}")
    for hi, name, band in C.ACCESS_TIERS:
        print(f"  < {hi} -> {name} (band {band})")
    for p in (C.RAW, C.INTERIM, C.PROCESSED, C.TILES):
        assert p.exists(), f"missing dir {p}"
    print("\nconfig OK")


if __name__ == "__main__":
    main()
