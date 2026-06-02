"""Great-circle distance + a 3D unit-sphere KD-tree for nearest-neighbour search
that avoids lon-wrap and 2D-degree distortion."""
from __future__ import annotations

import numpy as np

EARTH_KM = 6371.0088


def latlon_to_xyz(lat, lon):
    """(lat, lon) in degrees -> unit-sphere xyz. Arrays or scalars."""
    lat = np.radians(np.asarray(lat, dtype=float))
    lon = np.radians(np.asarray(lon, dtype=float))
    cl = np.cos(lat)
    return np.stack([cl * np.cos(lon), cl * np.sin(lon), np.sin(lat)], axis=-1)


def chord_to_km(chord: np.ndarray) -> np.ndarray:
    """Euclidean chord length on the unit sphere -> great-circle km."""
    chord = np.clip(np.asarray(chord, dtype=float), 0.0, 2.0)
    central_angle = 2.0 * np.arcsin(chord / 2.0)
    return EARTH_KM * central_angle


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two (arrays of) points."""
    lat1, lon1, lat2, lon2 = map(lambda a: np.radians(np.asarray(a, dtype=float)),
                                 (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return EARTH_KM * 2 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
