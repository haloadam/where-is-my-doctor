import pandas as pd

from lib.seats import filled_seat_codes, resolve_seats, seat_points

# Minimal synthetic settlement universe (plain DataFrame — the seat helpers don't need geometry).
GDF = pd.DataFrame([
    {"name_norm": "szulok", "ksh_code": "12345", "name": "Szulok", "centroid_lat": 46.0, "centroid_lon": 17.6},
    {"name_norm": "budapest", "ksh_code": "13578", "name": "Budapest", "centroid_lat": 47.5, "centroid_lon": 19.05},
])
PRACTICES = pd.DataFrame([
    {"hsz_kod": "000000001", "seat_name": "Szulok"},
    {"hsz_kod": "000000002", "seat_name": "Budapest XI."},   # kerület name -> collapses to Budapest
    {"hsz_kod": "000000003", "seat_name": "Nowhere"},        # unresolved
])


def test_resolve_seats_coverage_and_budapest_collapse():
    p, cov = resolve_seats(PRACTICES, GDF)
    assert cov == 2 / 3                                       # Nowhere is unresolved
    bp = p[p["hsz_kod"] == "000000002"].iloc[0]
    assert bp["seat_ksh"] == "13578"                          # "Budapest XI." -> parent 13578


def test_seat_points_distinct_with_centroids():
    seats, cov = seat_points(PRACTICES, GDF)
    assert set(seats["seat_ksh"]) == {"12345", "13578"}
    assert cov == 2 / 3


def test_filled_seat_codes_excludes_vacant():
    # körzet 1 is vacant -> Szulok no longer a filled seat; 2 (Budapest) is filled; 3 unresolved.
    filled = filled_seat_codes(PRACTICES, GDF, vac_set={"000000001"})
    assert filled == {"13578"}
