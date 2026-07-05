"""
test_database_query.py - Unit tests for database_query.py
"""
import pytest
import psycopg2
from src.database_query import (
    get_db_connection,
    retrieve_council_boundary_gss,
    retrieve_brownfield_register_data,
    store_candidate_sites,
    store_pipeline_metadata
)


@pytest.fixture
def connection():
    """Creates a database connection and rolls back writes after each test."""
    conn = get_db_connection()
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


# --- get_db_connection tests ---
def test_get_db_connection_returns_connection():
    """Tests that get_db_connection returns a valid psycopg2 connection."""
    conn = get_db_connection()
    assert conn is not None
    assert conn.closed == 0
    conn.close()


# --- retrieve_council_boundary_gss tests ---
def test_retrieve_council_boundary_gss_returns_dict(connection):
    """Tests that retrieve_council_boundary_gss returns a dict for a valid GSS code."""
    result = retrieve_council_boundary_gss('E06000021', connection)
    assert isinstance(result, dict)


def test_retrieve_council_boundary_gss_contains_geometry(connection):
    """Tests that the returned dict contains geometry coordinates."""
    result = retrieve_council_boundary_gss('E06000021', connection)
    assert 'coordinates' in result
    assert 'type' in result


def test_retrieve_council_boundary_gss_invalid_raises(connection):
    """Tests that an invalid GSS code raises a ValueError."""
    with pytest.raises(ValueError):
        retrieve_council_boundary_gss('INVALID', connection)


# --- retrieve_brownfield_register_data tests ---
def test_retrieve_brownfield_register_data_returns_list(connection):
    """Tests that retrieve_brownfield_register_data returns a list."""
    result = retrieve_brownfield_register_data('E06000021', 2024, connection)
    assert isinstance(result, list)


def test_retrieve_brownfield_register_data_correct_count(connection):
    """Tests that 218 sites are returned for Stoke 2024."""
    result = retrieve_brownfield_register_data('E06000021', 2024, connection)
    assert len(result) == 218


def test_retrieve_brownfield_register_data_contains_correct_keys(connection):
    """Tests that each site dict contains site_reference, utm_x and utm_y."""
    result = retrieve_brownfield_register_data('E06000021', 2024, connection)
    assert 'site_reference' in result[0]
    assert 'utm_x' in result[0]
    assert 'utm_y' in result[0]


def test_retrieve_brownfield_register_data_invalid_year_raises(connection):
    """Tests that an invalid year raises a ValueError."""
    with pytest.raises(ValueError):
        retrieve_brownfield_register_data('E06000021', 1900, connection)


# --- store_candidate_sites tests ---
def test_store_candidate_sites_empty_raises(connection):
    """Tests that an empty candidate_sites list raises a ValueError."""
    with pytest.raises(ValueError):
        store_candidate_sites([], 'E06000021', '2026-05-25', '2026-05-25 12:00:00', connection)


def test_store_candidate_sites_stores_correctly(connection):
    """Tests that candidate sites are stored correctly in the database."""
    candidate_sites = [
        {
            'utm_x': 555331.19,
            'utm_y': 5871939.23,
            'pixel_count': 100,
            'bsi_value': 0.15,
            'matched_site_reference': None
        }
    ]
    store_candidate_sites(candidate_sites, 'E06000021', '2026-05-25', '2026-05-25 12:00:00', connection)
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM candidate_sites WHERE gss_code = 'E06000021'")
    count = cursor.fetchone()[0]
    assert count >= 1
    cursor.close()


# --- store_pipeline_metadata tests ---
def test_store_pipeline_metadata_invalid_status_raises(connection):
    """Tests that an invalid status raises a ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata('E06000021', '2026-05-25', '2026-05-25 12:00:00', 'invalid', 10, 5, 5, connection)


def test_store_pipeline_metadata_negative_count_raises(connection):
    """Tests that negative counts raise a ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata('E06000021', '2026-05-25', '2026-05-25 12:00:00', 'success', -1, 0, 0, connection)


def test_store_pipeline_metadata_stores_correctly(connection):
    """Tests that pipeline metadata is stored correctly in the database."""
    store_pipeline_metadata('E06000021', '2026-05-25', '2026-05-25 12:00:00', 'success', 10, 5, 5, connection)
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM pipeline_runs WHERE gss_code = 'E06000021'")
    count = cursor.fetchone()[0]
    assert count >= 1
    cursor.close()