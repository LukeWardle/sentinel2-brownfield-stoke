"""
test_exclusion_filter.py - Unit tests for exclusion_filter.py
"""

import pytest

from src.database_query import get_db_connection
from src.exclusion_filter import (
    _fraction_inside,
    filter_candidates_by_exclusion,
    retrieve_exclusion_zones,
)
from src.exclusion_loader import store_exclusion_zones


@pytest.fixture
def connection():
    """Creates a database connection and rolls back writes after each test."""
    conn = get_db_connection()
    yield conn
    conn.rollback()
    conn.close()


# A 100m square exclusion zone in UTM 32630 (roughly Stoke area easting/northing).
# Candidates are described by boundary vertices relative to this square.
EXCLUSION_SQUARE = [
    [560000, 5870000],
    [560100, 5870000],
    [560100, 5870100],
    [560000, 5870100],
    [560000, 5870000],
]


def _candidate(site_id, boundary):
    return {"site_id": site_id, "centroid_utm_x": 0, "centroid_utm_y": 0}, {
        "site_id": site_id,
        "boundary": boundary,
    }


# --- _fraction_inside tests ---
def test_fraction_inside_fully_inside_is_one():
    """A boundary entirely within an exclusion zone returns 1.0."""
    import numpy as np
    from matplotlib.path import Path as MplPath

    path = MplPath(np.array(EXCLUSION_SQUARE))
    boundary = [
        [560025, 5870025],
        [560075, 5870025],
        [560075, 5870075],
        [560025, 5870075],
    ]
    assert _fraction_inside(boundary, [path]) == 1.0


def test_fraction_inside_fully_outside_is_zero():
    """A boundary entirely outside returns 0.0."""
    import numpy as np
    from matplotlib.path import Path as MplPath

    path = MplPath(np.array(EXCLUSION_SQUARE))
    boundary = [[560200, 5870200], [560300, 5870200], [560300, 5870300]]
    assert _fraction_inside(boundary, [path]) == 0.0


def test_fraction_inside_empty_boundary_is_zero():
    """An empty boundary returns 0.0 rather than erroring."""
    assert _fraction_inside([], []) == 0.0


# --- filter_candidates_by_exclusion tests ---
def test_filter_drops_candidate_majority_inside():
    """A candidate mostly inside an exclusion zone is dropped."""
    props, poly = _candidate(
        "s1",
        [[560025, 5870025], [560075, 5870025], [560075, 5870075], [560025, 5870075]],
    )
    kept, dropped = filter_candidates_by_exclusion([props], [poly], [EXCLUSION_SQUARE])
    assert dropped == 1
    assert kept == []


def test_filter_keeps_candidate_outside():
    """A candidate entirely outside all exclusion zones is kept."""
    props, poly = _candidate(
        "s2",
        [[560200, 5870200], [560300, 5870200], [560300, 5870300], [560200, 5870300]],
    )
    kept, dropped = filter_candidates_by_exclusion([props], [poly], [EXCLUSION_SQUARE])
    assert dropped == 0
    assert len(kept) == 1


def test_filter_keeps_candidate_edge_clip():
    """A candidate with only one vertex inside (25%) survives the >50% rule."""
    # Three vertices well outside, one inside the square
    props, poly = _candidate(
        "s3",
        [
            [560050, 5870050],  # inside
            [560500, 5870500],  # outside
            [560600, 5870500],  # outside
            [560600, 5870600],
        ],
    )  # outside
    kept, dropped = filter_candidates_by_exclusion([props], [poly], [EXCLUSION_SQUARE])
    assert dropped == 0
    assert len(kept) == 1


def test_filter_no_exclusion_zones_keeps_all():
    """With no exclusion zones loaded, every candidate is kept."""
    props, poly = _candidate("s4", EXCLUSION_SQUARE)
    kept, dropped = filter_candidates_by_exclusion([props], [poly], [])
    assert dropped == 0
    assert len(kept) == 1


def test_filter_candidate_without_polygon_is_kept():
    """A candidate with no matching boundary polygon is kept (nothing to test)."""
    props = {"site_id": "s5", "centroid_utm_x": 0, "centroid_utm_y": 0}
    kept, dropped = filter_candidates_by_exclusion([props], [], [EXCLUSION_SQUARE])
    assert dropped == 0
    assert len(kept) == 1


# --- retrieve_exclusion_zones tests (real DB, rolled back) ---
def test_retrieve_exclusion_zones_returns_stored_polygon(connection):
    """A stored exclusion polygon is retrieved and transformed to UTM."""
    # Store a WGS84 polygon for Stoke, then read it back in UTM
    polygons = [
        {
            "source_ref": "way/test",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-2.18, 53.00],
                        [-2.17, 53.00],
                        [-2.17, 53.01],
                        [-2.18, 53.01],
                        [-2.18, 53.00],
                    ]
                ],
            },
        }
    ]
    store_exclusion_zones(polygons, "E06000021", "building", "osm", connection)
    rings = retrieve_exclusion_zones("E06000021", connection, source="osm")
    assert len(rings) >= 1
    # Coordinates should be in UTM range (hundreds of thousands), not lat/lon
    assert rings[0][0][0] > 1000


def test_retrieve_exclusion_zones_empty_council_returns_empty(connection):
    """A council with no exclusion zones returns an empty list, not an error."""
    rings = retrieve_exclusion_zones("E06000021", connection, source="nonexistent")
    assert rings == []
