"""
test_exclusion_loader.py - Unit tests for exclusion_loader.py
"""

from unittest.mock import MagicMock, patch

import pytest

from src.database_query import get_db_connection
from src.exclusion_loader import (
    EXCLUSION_CLASSES,
    build_overpass_query,
    fetch_osm_polygons,
    load_exclusions_for_council,
    parse_osm_element,
    store_exclusion_zones,
)


# --- Shared fixtures ---
@pytest.fixture
def connection():
    """Creates a database connection and rolls back writes after each test."""
    conn = get_db_connection()
    yield conn
    conn.rollback()
    conn.close()


BBOX = {"west": -2.20, "east": -2.10, "south": 52.95, "north": 53.05}


def _way_element(way_id=1, closed=True):
    """A simple OSM way element in Overpass 'out geom' form."""
    geometry = [
        {"lat": 53.00, "lon": -2.15},
        {"lat": 53.00, "lon": -2.14},
        {"lat": 53.01, "lon": -2.14},
    ]
    if closed:
        geometry.append({"lat": 53.00, "lon": -2.15})
    return {"type": "way", "id": way_id, "geometry": geometry}


def _relation_element(rel_id=10, with_hole=False, two_outers=False):
    """An OSM relation element with outer (and optionally inner) way members."""
    outer = {
        "type": "way",
        "role": "outer",
        "geometry": [
            {"lat": 53.00, "lon": -2.15},
            {"lat": 53.00, "lon": -2.13},
            {"lat": 53.02, "lon": -2.13},
            {"lat": 53.02, "lon": -2.15},
            {"lat": 53.00, "lon": -2.15},
        ],
    }
    members = [outer]
    if with_hole:
        members.append(
            {
                "type": "way",
                "role": "inner",
                "geometry": [
                    {"lat": 53.005, "lon": -2.145},
                    {"lat": 53.005, "lon": -2.140},
                    {"lat": 53.010, "lon": -2.140},
                    {"lat": 53.005, "lon": -2.145},
                ],
            }
        )
    if two_outers:
        members.append(
            {
                "type": "way",
                "role": "outer",
                "geometry": [
                    {"lat": 53.03, "lon": -2.12},
                    {"lat": 53.03, "lon": -2.11},
                    {"lat": 53.04, "lon": -2.11},
                    {"lat": 53.03, "lon": -2.12},
                ],
            }
        )
    return {"type": "relation", "id": rel_id, "members": members}


# --- build_overpass_query tests ---
def test_build_overpass_query_includes_way_and_relation():
    """Query must request both ways and relations so multipolygons are caught."""
    query = build_overpass_query(BBOX, "building")
    assert "way" in query
    assert "relation" in query


def test_build_overpass_query_bbox_order_south_west_north_east():
    """Overpass expects bbox as south,west,north,east."""
    query = build_overpass_query(BBOX, "building")
    assert "52.95,-2.2,53.05,-2.1" in query


def test_build_overpass_query_uses_class_tags():
    """Query for car_park must contain the amenity=parking tag filter."""
    query = build_overpass_query(BBOX, "car_park")
    assert 'amenity"="parking' in query


def test_build_overpass_query_unknown_class_raises():
    """Unknown class must raise ValueError, not build a bad query."""
    with pytest.raises(ValueError):
        build_overpass_query(BBOX, "not_a_class")


def test_all_classes_build_without_error():
    """Every defined class must produce a query string."""
    for exclusion_class in EXCLUSION_CLASSES:
        assert isinstance(build_overpass_query(BBOX, exclusion_class), str)


# --- parse_osm_element tests ---
def test_parse_way_returns_polygon():
    """A way element parses to a GeoJSON Polygon."""
    parsed = parse_osm_element(_way_element(way_id=42))
    assert parsed["geometry"]["type"] == "Polygon"
    assert parsed["source_ref"] == "way/42"


def test_parse_way_closes_open_ring():
    """An unclosed way ring is closed (first point repeated at the end)."""
    parsed = parse_osm_element(_way_element(closed=False))
    ring = parsed["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]


def test_parse_relation_returns_polygon_with_hole():
    """A relation with one outer and one inner parses to a Polygon with a hole."""
    parsed = parse_osm_element(_relation_element(with_hole=True))
    coords = parsed["geometry"]["coordinates"]
    assert parsed["geometry"]["type"] == "Polygon"
    assert len(coords) == 2  # outer ring + one hole
    assert parsed["source_ref"] == "relation/10"


def test_parse_relation_two_outers_returns_multipolygon():
    """A relation with two outer rings parses to a MultiPolygon."""
    parsed = parse_osm_element(_relation_element(two_outers=True))
    assert parsed["geometry"]["type"] == "MultiPolygon"
    assert len(parsed["geometry"]["coordinates"]) == 2


def test_parse_element_no_geometry_returns_none():
    """An element with no usable geometry returns None."""
    assert parse_osm_element({"type": "way", "id": 1, "geometry": []}) is None


def test_parse_relation_no_outer_returns_none():
    """A relation with only inner members (no outer) returns None."""
    element = {
        "type": "relation",
        "id": 5,
        "members": [
            {
                "type": "way",
                "role": "inner",
                "geometry": [
                    {"lat": 53.0, "lon": -2.1},
                    {"lat": 53.0, "lon": -2.0},
                    {"lat": 53.1, "lon": -2.0},
                    {"lat": 53.0, "lon": -2.1},
                ],
            },
        ],
    }
    assert parse_osm_element(element) is None


# --- fetch_osm_polygons tests ---
def test_fetch_osm_polygons_parses_mixed_elements():
    """Fetch parses a mixed way + relation response into two polygons."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "elements": [_way_element(way_id=1), _relation_element(rel_id=2)]
    }
    with patch("src.exclusion_loader.requests.post", return_value=mock_response):
        result = fetch_osm_polygons(BBOX, "building")
    assert len(result) == 2
    refs = {p["source_ref"] for p in result}
    assert refs == {"way/1", "relation/2"}


def test_fetch_osm_polygons_skips_unusable_elements():
    """Elements without geometry are dropped, not stored."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "elements": [_way_element(way_id=1), {"type": "way", "id": 9, "geometry": []}]
    }
    with patch("src.exclusion_loader.requests.post", return_value=mock_response):
        result = fetch_osm_polygons(BBOX, "building")
    assert len(result) == 1


def test_fetch_osm_polygons_non_200_raises():
    """A failed Overpass request raises ValueError."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    with patch("src.exclusion_loader.requests.post", return_value=mock_response):
        with pytest.raises(ValueError):
            fetch_osm_polygons(BBOX, "building")


# --- store_exclusion_zones tests (real DB, rolled back) ---
def test_store_exclusion_zones_inserts_rows(connection):
    """Stored polygons are written to exclusion_zones and readable back."""
    polygons = [parse_osm_element(_way_element(way_id=1))]
    store_exclusion_zones(polygons, "E06000021", "building", "osm", connection)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT count(*) FROM exclusion_zones
        WHERE gss_code = %s AND exclusion_class = %s AND source = %s
        """,
        ("E06000021", "building", "osm"),
    )
    assert cursor.fetchone()[0] == 1
    cursor.close()


def test_store_exclusion_zones_replaces_existing(connection):
    """Re-storing the same class replaces rather than duplicates rows."""
    polygons = [parse_osm_element(_way_element(way_id=1))]
    store_exclusion_zones(polygons, "E06000021", "building", "osm", connection)
    store_exclusion_zones(polygons, "E06000021", "building", "osm", connection)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT count(*) FROM exclusion_zones
        WHERE gss_code = %s AND exclusion_class = %s AND source = %s
        """,
        ("E06000021", "building", "osm"),
    )
    assert cursor.fetchone()[0] == 1
    cursor.close()


# --- load_exclusions_for_council tests ---
def test_load_exclusions_for_council_returns_counts(connection):
    """Orchestrator loops requested classes and returns a per-class count."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"elements": [_way_element(way_id=1)]}
    with patch("src.exclusion_loader.requests.post", return_value=mock_response):
        counts = load_exclusions_for_council(
            "E06000021", connection, classes=["building", "car_park"]
        )
    assert counts == {"building": 1, "car_park": 1}


def test_load_exclusions_for_council_invalid_gss_raises(connection):
    """A GSS code with no boundary raises ValueError."""
    with pytest.raises(ValueError):
        load_exclusions_for_council("E09999999", connection, classes=["building"])
