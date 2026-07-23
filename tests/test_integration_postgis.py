"""
test_integration_postgis.py - Real-SQL integration tests (P1-9).
================================================================
Exercises the actual queries against live PostGIS — no mocks. Runs
locally and in CI (tests.yml already provisions Postgres+PostGIS with
migrations 001-004 applied; conftest seeds the E06000021 boundary).

Scope note: the ticket's premise ("all tests fully mocked") predates the
FND work — exclusion-filter, persistence-filter and evaluation tests
already hit the real database. This file closes the remaining gaps:
boundary retrieval with its SRID transform, ST_DWithin register matching,
the candidate store round-trip including geometry area/SRID, and
change-detection date logic with the dynamic MAX(year) vintage (P0-9).

Isolation pattern: sentinel year 2099, ITEST- reference prefixes, and
explicit cleanup (store_candidate_sites commits, so rollback alone is not
enough — cleanup deletes and commits in teardown).
"""

import pytest

from src.database_query import (
    detect_register_changes,
    get_db_connection,
    match_candidate_to_register,
    retrieve_council_boundary_gss,
    store_candidate_sites,
)

GSS = "E06000021"
RUN_TS = "2099-12-02 12:00:00"


@pytest.fixture
def connection():
    conn = get_db_connection()
    yield conn
    conn.rollback()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM candidate_sites WHERE gss_code = %s AND run_timestamp = %s",
        (GSS, RUN_TS),
    )
    cursor.execute(
        "DELETE FROM brownfield_sites WHERE gss_code = %s AND site_reference LIKE 'ITEST-%%'",
        (GSS,),
    )
    conn.commit()
    cursor.close()
    conn.close()


def _insert_register_site(
    connection, ref, utm_x, utm_y, year=2099, start_date=None, end_date=None
):
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO brownfield_sites
        (site_reference, gss_code, year, name_address, utm_x, utm_y, hectares,
         planning_status, start_date, end_date, location)
        VALUES (%s, %s, %s, 'Integration test site', %s, %s, 1.0, 'test',
                %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 32630))
        """,
        (ref, GSS, year, utm_x, utm_y, start_date, end_date, utm_x, utm_y),
    )
    cursor.close()


# --- retrieve_council_boundary_gss: real SRID transform ---
def test_boundary_retrieval_transforms_to_utm(connection):
    boundary = retrieve_council_boundary_gss(GSS, connection)
    assert boundary["type"] in ("Polygon", "MultiPolygon")
    ring = (
        boundary["coordinates"][0]
        if boundary["type"] == "Polygon"
        else boundary["coordinates"][0][0]
    )
    xs = [pt[0] for pt in ring]
    ys = [pt[1] for pt in ring]
    # EPSG:32630 for Stoke: easting ~5-6e5, northing ~5.8-5.9e6 — the
    # transform actually ran (raw values would be lon/lat ~ -2 / 53)
    assert all(1e5 < x < 9e5 for x in xs)
    assert all(5.5e6 < y < 6.2e6 for y in ys)


def test_boundary_retrieval_unknown_gss_raises(connection):
    with pytest.raises(ValueError, match="No boundary"):
        retrieve_council_boundary_gss("E99999999", connection)


# --- match_candidate_to_register: real ST_DWithin ---
def test_match_within_threshold_hits(connection):
    _insert_register_site(connection, "ITEST-MATCH", 561000.0, 5871000.0)
    ref = match_candidate_to_register(561050.0, 5871000.0, GSS, connection)
    assert ref == "ITEST-MATCH"  # 50m away, inside 100m


def test_match_beyond_threshold_returns_none(connection):
    _insert_register_site(connection, "ITEST-FAR", 561000.0, 5871000.0)
    ref = match_candidate_to_register(561500.0, 5871000.0, GSS, connection)
    assert ref is None  # 500m away


def test_match_prefers_nearest_site(connection):
    _insert_register_site(connection, "ITEST-NEAR", 561010.0, 5871000.0)
    _insert_register_site(connection, "ITEST-FARTHER", 561080.0, 5871000.0)
    ref = match_candidate_to_register(561000.0, 5871000.0, GSS, connection)
    assert ref == "ITEST-NEAR"


# --- store_candidate_sites: geometry round-trip ---
def test_store_candidate_geometry_area_and_srid(connection):
    # 2x2 pixel square at 20m resolution -> 40m x 40m = 1600 m^2
    square = {
        "type": "Polygon",
        "coordinates": [
            [
                [561000.0, 5871000.0],
                [561040.0, 5871000.0],
                [561040.0, 5871040.0],
                [561000.0, 5871040.0],
                [561000.0, 5871000.0],
            ]
        ],
    }
    site = {
        "centroid_utm_x": 561020.0,
        "centroid_utm_y": 5871020.0,
        "pixel_count": 4,
        "mean_bsi": 0.12,
        "matched_site_reference": None,
        "geometry": square,
    }
    store_candidate_sites([site], GSS, "2099-11-30", RUN_TS, connection)

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT ST_Area(geom), ST_SRID(geom), pixel_count
        FROM candidate_sites
        WHERE gss_code = %s AND run_timestamp = %s
        """,
        (GSS, RUN_TS),
    )
    area, srid, pixel_count = cursor.fetchone()
    cursor.close()
    assert srid == 32630
    assert area == pytest.approx(1600.0)
    assert area == pytest.approx(pixel_count * 400.0)  # FND-2 area contract


def test_store_candidate_null_geometry_allowed(connection):
    site = {
        "centroid_utm_x": 561020.0,
        "centroid_utm_y": 5871020.0,
        "pixel_count": 5,
        "mean_bsi": 0.10,
        "matched_site_reference": None,
        "geometry": None,
    }
    store_candidate_sites([site], GSS, "2099-11-30", RUN_TS, connection)
    cursor = connection.cursor()
    cursor.execute(
        "SELECT geom FROM candidate_sites WHERE gss_code = %s AND run_timestamp = %s",
        (GSS, RUN_TS),
    )
    assert cursor.fetchone()[0] is None
    cursor.close()


def test_store_candidate_persists_feature_columns(connection):
    """Migration 004 columns flow through store_candidate_sites."""
    site = {
        "centroid_utm_x": 561020.0,
        "centroid_utm_y": 5871020.0,
        "pixel_count": 5,
        "mean_bsi": 0.10,
        "matched_site_reference": None,
        "geometry": None,
        "std_bsi": 0.01,
        "mean_ndvi": 0.11,
        "std_ndvi": 0.02,
        "mean_b04": 0.1,
        "mean_b08": 0.2,
        "mean_b11": 0.3,
        "compactness": 0.78,
        "prior_date_count": 2,
    }
    store_candidate_sites([site], GSS, "2099-11-30", RUN_TS, connection)
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT std_bsi, mean_ndvi, compactness, prior_date_count
        FROM candidate_sites WHERE gss_code = %s AND run_timestamp = %s
        """,
        (GSS, RUN_TS),
    )
    std_bsi, mean_ndvi, compactness, prior = cursor.fetchone()
    cursor.close()
    assert std_bsi == pytest.approx(0.01)
    assert mean_ndvi == pytest.approx(0.11)
    assert compactness == pytest.approx(0.78)
    assert prior == 2


# --- detect_register_changes: real date logic, dynamic vintage (P0-9) ---
def test_change_detection_date_windows(connection):
    _insert_register_site(
        connection, "ITEST-ADDED", 561000, 5871000, start_date="2023-06-01"
    )
    _insert_register_site(
        connection, "ITEST-REMOVED", 562000, 5872000, end_date="2022-06-01"
    )
    _insert_register_site(
        connection, "ITEST-OUTSIDE", 563000, 5873000, start_date="2018-01-01"
    )
    changes = detect_register_changes(GSS, 2021, 2024, connection)
    added_refs = {s["site_reference"] for s in changes["added"]}
    removed_refs = {s["site_reference"] for s in changes["removed"]}
    assert "ITEST-ADDED" in added_refs
    assert "ITEST-REMOVED" in removed_refs
    assert "ITEST-OUTSIDE" not in added_refs
    # Dynamic MAX(year) vintage: our year-2099 inserts define the searched
    # vintage, so real 2024 register rows cannot leak into results
    assert all(ref.startswith("ITEST-") for ref in added_refs | removed_refs)


def test_change_detection_rejects_inverted_years(connection):
    with pytest.raises(ValueError):
        detect_register_changes(GSS, 2024, 2021, connection)
