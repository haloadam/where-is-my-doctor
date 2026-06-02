"""Access-class banding — pure, importable, and unit-tested (see tests/test_scoring.py)."""
from __future__ import annotations

import pandas as pd

from lib.config import ACCESS_TIERS, DESERT_BAND


def classify(active_count: int, per_1000) -> tuple[str, int]:
    """Map (functioning-körzet count, GPs per 1000) -> (access_class, access_band).

    - 0 functioning körzets -> 'desert' (the is_desert flag drives the purple override).
    - population missing/0 (per_1000 is None/NaN) but served -> best tier (count-only).
    - otherwise band by gps_per_1000 against ACCESS_TIERS.
    """
    if active_count == 0:
        return "desert", DESERT_BAND
    if per_1000 is None or pd.isna(per_1000):
        return ACCESS_TIERS[-1][1], ACCESS_TIERS[-1][2]
    for hi, name, band in ACCESS_TIERS:
        if per_1000 < hi:
            return name, band
    return ACCESS_TIERS[-1][1], ACCESS_TIERS[-1][2]
