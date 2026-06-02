import numpy as np

from lib.haversine import chord_to_km, haversine_km, latlon_to_xyz


def test_known_distance_budapest_szeged():
    # straight-line Budapest -> Szeged is ~161 km
    d = float(haversine_km(47.4979, 19.0402, 46.2530, 20.1414))
    assert 150 < d < 172


def test_zero_distance():
    assert float(haversine_km(47.5, 19.0, 47.5, 19.0)) < 1e-6


def test_unit_sphere_norm():
    xyz = latlon_to_xyz([47.5, 46.25], [19.0, 20.14])
    norms = np.linalg.norm(xyz, axis=-1)
    assert np.allclose(norms, 1.0, atol=1e-9)


def test_chord_matches_haversine():
    # chord length on the unit sphere -> km should agree with the haversine formula
    a = latlon_to_xyz([47.4979], [19.0402])[0]
    b = latlon_to_xyz([46.2530], [20.1414])[0]
    chord = float(np.linalg.norm(a - b))
    assert abs(float(chord_to_km(chord)) - float(haversine_km(47.4979, 19.0402, 46.2530, 20.1414))) < 0.5
