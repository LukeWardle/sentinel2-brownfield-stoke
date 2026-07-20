"""
test_exclusion_filter.py - Unit tests for the FND-4 exclusion filter.
=====================================================================
Overlap is computed in PostGIS (real DB, rolled back after each test), so
these tests exercise the actual ST_Area(ST_Intersection(...)) path — no
mocked geometry math.
"""

import json

import pytest

from src.database_query import get_db_connection
from src.exclusion_filter import (
    HARD_EXCLUSION_CLASSES,
    compute_exclusion_overlap,
    filter_candidates_by_exclusion,
    report_register_recall,
)


@pytest.fixture
def connection():
    """Creates a database connection and rolls back writes after each test."""
    conn = get_db_connection()
    yield conn
    conn.rollback()
    conn.close()


def _utm_square(x0, y0, size):
    """A closed GeoJSON square in EPSG:32630 with corner (x0, y0)."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [x0, y0],
                [x0 + size, y0],
                [x0 + size, y0 + size],
                [x0, y0 + size],
                [x0, y0],
            ]
        ],
    }


def _insert_zone(connection, geometry_utm, exclusion_class, gss_code="E06000021"):
    """Inserts an exclusion zone, transforming the UTM square to stored 4326."""
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO exclusion_zones (gss_code, exclusion_class, source, source_ref, geom)
        VALUES (%s, %s, 'test', 'test/1',
                ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 32630), 4326))
        """,
        (gss_code, exclusion_class, json.dumps(geometry_utm)),
    )
    cursor.close()


BASE_X, BASE_Y = 560000.0, 5870000.0


# --- compute_exclusion_overlap ---
def test_overlap_full_containment_is_one(connection):
    """A candidate identical to a hard-class zone overlaps ~1.0."""
    square = _utm_square(BASE_X, BASE_Y, 100)
    _insert_zone(connection, square, "car_park")
    overlap = compute_exclusion_overlap(square, "E06000021", connection, source="test")
    assert overlap > 0.99


def test_overlap_disjoint_is_zero(connection):
    """A candidate far from every zone overlaps 0.0."""
    _insert_zone(connection, _utm_square(BASE_X, BASE_Y, 100), "car_park")
    far = _utm_square(BASE_X + 10000, BASE_Y + 10000, 100)
    overlap = compute_exclusion_overlap(far, "E06000021", connection, source="test")
    assert overlap == 0.0


def test_overlap_half_is_half(connection):
    """A candidate half-on a zone measures ~0.5 — true area, not vertex ratio."""
    _insert_zone(connection, _utm_square(BASE_X, BASE_Y, 100), "car_park")
    half_on = _utm_square(BASE_X + 50, BASE_Y, 100)  # 50m overlap of a 100m square
    overlap = compute_exclusion_overlap(half_on, "E06000021", connection, source="test")
    assert 0.45 < overlap < 0.55


def test_overlap_ignores_non_hard_classes(connection):
    """Building zones are NOT hard masks — overlap with them measures 0."""
    square = _utm_square(BASE_X, BASE_Y, 100)
    _insert_zone(connection, square, "building")
    overlap = compute_exclusion_overlap(square, "E06000021", connection, source="test")
    assert overlap == 0.0


def test_overlap_none_geometry_is_zero(connection):
    """A candidate with no geometry cannot be tested — overlap 0."""
    assert compute_exclusion_overlap(None, "E06000021", connection) == 0.0


# --- filter_candidates_by_exclusion ---
def _props_and_polys(site_id, geometry):
    return (
        {"site_id": site_id, "centroid_utm_x": 0.0, "centroid_utm_y": 0.0},
        {"site_id": site_id, "geometry": geometry},
    )


def test_filter_drops_majority_inside(connection):
    """A candidate fully on a car park is dropped."""
    square = _utm_square(BASE_X, BASE_Y, 100)
    _insert_zone(connection, square, "car_park")
    props, poly = _props_and_polys("s1", square)
    kept, dropped = filter_candidates_by_exclusion(
        [props], [poly], "E06000021", connection, source="test"
    )
    assert dropped == 1
    assert kept == []


def test_filter_keeps_half_overlap(connection):
    """Exactly-half overlap does not exceed the strict > 0.5 threshold."""
    _insert_zone(connection, _utm_square(BASE_X, BASE_Y, 100), "car_park")
    props, poly = _props_and_polys("s2", _utm_square(BASE_X + 50, BASE_Y, 100))
    kept, dropped = filter_candidates_by_exclusion(
        [props], [poly], "E06000021", connection, source="test"
    )
    assert dropped == 0
    assert len(kept) == 1


def test_filter_keeps_candidate_on_building(connection):
    """A candidate fully on a BUILDING survives — buildings are features,
    not hard masks (the 70-register-site lesson)."""
    square = _utm_square(BASE_X, BASE_Y, 100)
    _insert_zone(connection, square, "building")
    props, poly = _props_and_polys("s3", square)
    kept, dropped = filter_candidates_by_exclusion(
        [props], [poly], "E06000021", connection, source="test"
    )
    assert dropped == 0
    assert len(kept) == 1


def test_filter_keeps_candidate_without_geometry(connection):
    """No geometry means nothing to test — candidate kept."""
    props = {"site_id": "s4", "centroid_utm_x": 0.0, "centroid_utm_y": 0.0}
    kept, dropped = filter_candidates_by_exclusion(
        [props], [], "E06000021", connection, source="test"
    )
    assert dropped == 0
    assert len(kept) == 1


def test_hard_classes_exclude_building_and_infrastructure():
    """The contaminated classes must never be in the hard exclusion set."""
    assert "building" not in HARD_EXCLUSION_CLASSES
    assert "infrastructure" not in HARD_EXCLUSION_CLASSES


# --- report_register_recall ---
def test_register_recall_returns_counts(connection):
    """The guardrail returns integer counts and never raises for a valid GSS."""
    result = report_register_recall("E06000021", connection)
    assert set(result.keys()) == {"register_sites", "inside_exclusions"}
    assert result["register_sites"] >= 0
    assert 0 <= result["inside_exclusions"] <= max(result["register_sites"], 0)
