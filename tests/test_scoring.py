import math

from lib.scoring import classify


def test_zero_functioning_is_desert():
    assert classify(0, 0.0) == ("desert", 0)
    assert classify(0, None) == ("desert", 0)
    assert classify(0, 5.0) == ("desert", 0)   # even if per_1000 looks high, no functioning körzet


def test_served_without_population_is_best_tier():
    assert classify(1, None) == ("ok", 4)
    assert classify(2, float("nan")) == ("ok", 4)


def test_bands_by_gps_per_1000():
    assert classify(1, 0.0) == ("critical", 1)
    assert classify(1, 0.19) == ("critical", 1)
    assert classify(1, 0.3) == ("low", 2)
    assert classify(1, 0.5) == ("moderate", 3)
    assert classify(1, 0.7) == ("ok", 4)


def test_band_boundaries_are_lower_inclusive():
    assert classify(1, 0.2) == ("low", 2)        # 0.2 is NOT critical
    assert classify(1, 0.4) == ("moderate", 3)   # 0.4 is NOT low
    assert classify(1, 0.6) == ("ok", 4)         # 0.6 is NOT moderate


def test_nan_is_treated_as_missing():
    assert classify(3, math.nan) == ("ok", 4)
