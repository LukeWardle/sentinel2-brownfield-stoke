"""
test_features.py - Unit tests for the P1-6 feature extraction module.
"""

import math
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.features import (
    FEATURE_COLUMNS,
    MODEL_INPUT_COLUMNS,
    attach_features,
    compactness_from_geometry,
    compute_candidate_features,
    count_prior_dates,
)

BANDS_20M = ["B05", "B06", "B07", "B8A", "B11", "B12"]
BANDS_10M = ["B02", "B03", "B04", "B08"]
# combined order: index("B11")=4, index("B04")=8, index("B08")=9


def _scene():
    """4 valid pixels, 10 bands, one candidate group of pixels [0, 1, 2]."""
    n = 4
    normalised = np.zeros((n, 10))
    normalised[:, 4] = [0.30, 0.32, 0.34, 0.99]  # B11
    normalised[:, 8] = [0.10, 0.12, 0.14, 0.99]  # B04
    normalised[:, 9] = [0.20, 0.22, 0.24, 0.99]  # B08
    bsi = np.array([0.10, 0.12, 0.14, 0.99])
    ndvi = np.array([0.05, 0.07, 0.09, 0.99])
    groups = {0: [0, 1, 2]}
    return groups, normalised, bsi, ndvi


def test_compute_candidate_features_keys_and_values():
    groups, normalised, bsi, ndvi = _scene()
    feats = compute_candidate_features(
        groups, normalised, bsi, ndvi, BANDS_20M, BANDS_10M
    )
    f = feats[0]
    assert set(f.keys()) == {
        "std_bsi",
        "mean_ndvi",
        "std_ndvi",
        "mean_b04",
        "mean_b08",
        "mean_b11",
    }
    assert f["mean_b04"] == np.mean([0.10, 0.12, 0.14])
    assert f["mean_b08"] == np.mean([0.20, 0.22, 0.24])
    assert f["mean_b11"] == np.mean([0.30, 0.32, 0.34])
    assert f["mean_ndvi"] == np.mean([0.05, 0.07, 0.09])
    assert f["std_bsi"] == np.std([0.10, 0.12, 0.14])
    # The 4th pixel (0.99 everywhere) is not in the group and must not leak
    assert f["mean_b11"] < 0.5


def test_compute_candidate_features_uses_band_name_lookup_not_position():
    """Reordering the band lists must not change results — indices come
    from .index('B04') etc., the same contract as preprocess."""
    groups, normalised, bsi, ndvi = _scene()
    baseline = compute_candidate_features(
        groups, normalised, bsi, ndvi, BANDS_20M, BANDS_10M
    )[0]
    # Same combined list, expressed differently
    feats = compute_candidate_features(
        groups, normalised, bsi, ndvi, BANDS_20M[:4], BANDS_20M[4:] + BANDS_10M
    )[0]
    assert feats == baseline


def test_compactness_square_is_pi_over_four():
    """Unit square: 4*pi*1 / 16 = pi/4 ~ 0.785."""
    square = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    }
    assert compactness_from_geometry(square) == pytest.approx(math.pi / 4)


def test_compactness_long_thin_is_lower_than_square():
    thin = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [10, 0], [10, 0.5], [0, 0.5], [0, 0]]],
    }
    square = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    }
    assert compactness_from_geometry(thin) < compactness_from_geometry(square)


def test_compactness_multipolygon_and_none():
    multi = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            [[[5, 5], [6, 5], [6, 6], [5, 6], [5, 5]]],
        ],
    }
    value = compactness_from_geometry(multi)
    assert value is not None
    assert 0 < value < math.pi / 4  # two squares share perimeter, less compact
    assert compactness_from_geometry(None) is None


def test_compactness_hole_reduces_area():
    holed = {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
            [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]],
        ],
    }
    solid = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
    }
    assert compactness_from_geometry(holed) < compactness_from_geometry(solid)


def test_count_prior_dates_returns_int_from_query():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = [3]
    count = count_prior_dates(561000, 5871000, "E06000021", "2026-05-25", conn)
    assert count == 3
    sql = cursor.execute.call_args.args[0]
    assert "image_date <> %s" in sql  # current date excluded
    assert "ST_DWithin" in sql


def test_attach_features_merges_in_place_and_handles_missing():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = [0]
    sites = [
        {
            "site_id": 0,
            "centroid_utm_x": 561000,
            "centroid_utm_y": 5871000,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
        },
        {  # not present in spectral features -> None values, no crash
            "site_id": 99,
            "centroid_utm_x": 561100,
            "centroid_utm_y": 5871100,
            "geometry": None,
        },
    ]
    spectral = {
        0: {
            "std_bsi": 0.01,
            "mean_ndvi": 0.1,
            "std_ndvi": 0.02,
            "mean_b04": 0.1,
            "mean_b08": 0.2,
            "mean_b11": 0.3,
        }
    }
    attach_features(sites, spectral, "E06000021", "2026-05-25", conn)
    assert sites[0]["std_bsi"] == 0.01
    assert sites[0]["compactness"] is not None
    assert sites[0]["prior_date_count"] == 0
    assert sites[1]["std_bsi"] is None
    assert sites[1]["compactness"] is None


def test_model_input_columns_contract():
    assert MODEL_INPUT_COLUMNS[:2] == ["pixel_count", "bsi_value"]
    assert MODEL_INPUT_COLUMNS[2:] == FEATURE_COLUMNS
    assert len(MODEL_INPUT_COLUMNS) == 10
