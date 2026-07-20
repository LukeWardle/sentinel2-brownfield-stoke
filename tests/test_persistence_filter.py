"""
test_persistence_filter.py - Unit tests for the P1-4 temporal persistence filter.
=================================================================================
Real DB with rollback: prior-run candidate rows are inserted, the filter is
exercised against them, and everything is rolled back.
"""

import pytest

from src.database_query import get_db_connection
from src.persistence_filter import (
    count_prior_detection_dates,
    filter_candidates_by_persistence,
)

GSS = "E06000021"
CURRENT_DATE = "2099-06-01"
PRIOR_DATE = "2099-03-01"
BASE_X, BASE_Y = 561000.0, 5871000.0


@pytest.fixture
def connection():
    conn = get_db_connection()
    yield conn
    conn.rollback()
    conn.close()


def _insert_prior_candidate(connection, utm_x, utm_y, image_date=PRIOR_DATE):
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO candidate_sites
        (gss_code, image_date, run_timestamp, utm_x, utm_y, pixel_count, bsi_value)
        VALUES (%s, %s, '2099-03-01 12:00:00', %s, %s, 10, 0.2)
        """,
        (GSS, image_date, utm_x, utm_y),
    )
    cursor.close()


def _site(site_id, utm_x, utm_y):
    return {"site_id": site_id, "centroid_utm_x": utm_x, "centroid_utm_y": utm_y}


def test_count_prior_dates_finds_nearby_detection(connection):
    _insert_prior_candidate(connection, BASE_X, BASE_Y)
    count = count_prior_detection_dates(
        BASE_X + 10, BASE_Y + 10, GSS, CURRENT_DATE, connection
    )
    assert count >= 1


def test_count_prior_dates_ignores_distant_detection(connection):
    _insert_prior_candidate(connection, BASE_X, BASE_Y)
    count = count_prior_detection_dates(
        BASE_X + 5000, BASE_Y + 5000, GSS, CURRENT_DATE, connection
    )
    assert count == 0


def test_count_prior_dates_excludes_current_date(connection):
    """A same-date detection must not count as persistence support."""
    _insert_prior_candidate(connection, BASE_X, BASE_Y, image_date=CURRENT_DATE)
    count = count_prior_detection_dates(BASE_X, BASE_Y, GSS, CURRENT_DATE, connection)
    assert count == 0


def test_filter_keeps_persistent_drops_transient(connection):
    _insert_prior_candidate(connection, BASE_X, BASE_Y)
    persistent = _site("p", BASE_X + 10, BASE_Y)
    transient = _site("t", BASE_X + 5000, BASE_Y)
    kept, dropped = filter_candidates_by_persistence(
        [persistent, transient], GSS, CURRENT_DATE, connection, min_prior_dates=1
    )
    assert dropped == 1
    assert [s["site_id"] for s in kept] == ["p"]


def test_filter_skips_when_no_history(connection):
    """Without enough prior dates stored, everything passes with 0 dropped —
    the first run for a council must never erase itself."""
    sites = [_site("a", BASE_X, BASE_Y)]
    kept, dropped = filter_candidates_by_persistence(
        sites, "E99999999", CURRENT_DATE, connection, min_prior_dates=1
    )
    assert dropped == 0
    assert kept == sites
