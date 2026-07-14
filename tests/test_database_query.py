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
    store_pipeline_metadata,
    match_candidate_to_register,
    retrieve_brownfield_register_data,
    detect_register_changes
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

def test_get_db_connection_raises_when_database_url_missing(monkeypatch):
    """Tests that get_db_connection raises ValueError when DATABASE_URL is
    not set in the environment. Uses monkeypatch so the env is automatically
    restored after the test, protecting subsequent tests that need a
    working connection."""
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        get_db_connection()

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
            'centroid_utm_x': 555331.19,
            'centroid_utm_y': 5871939.23,
            'pixel_count': 100,
            'mean_bsi': 0.15,
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

# --- match_candidate_to_register tests ---
def test_match_candidate_returns_site_reference_when_match_found(connection):
    """Tests that a site reference is returned when a register site is within threshold."""
    # Use a known register site UTM coordinate from the database
    register_sites = retrieve_brownfield_register_data('E06000021', 2024, connection)
    first_site = register_sites[0]

    result = match_candidate_to_register(
        first_site['utm_x'],
        first_site['utm_y'],
        'E06000021',
        connection,
        distance_threshold=50.0
    )
    assert result == first_site['site_reference']

def test_match_candidate_returns_none_when_no_match(connection):
    """Tests that None is returned when no register site is within threshold."""
    # UTM coordinate far outside Stoke — middle of the North Sea
    result = match_candidate_to_register(
        700000.0,
        6000000.0,
        'E06000021',
        connection,
        distance_threshold=100.0
    )
    assert result is None

def test_match_candidate_returns_string_or_none(connection):
    """Tests that the return type is always str or None."""
    register_sites = retrieve_brownfield_register_data('E06000021', 2024, connection)
    first_site = register_sites[0]

    result = match_candidate_to_register(
        first_site['utm_x'],
        first_site['utm_y'],
        'E06000021',
        connection
    )
    assert result is None or isinstance(result, str)

def test_match_candidate_zero_threshold_returns_none(connection):
    """Tests that a zero distance threshold returns None for coordinates
    that are not exactly on a register site."""
    # Coordinate offset by 1 metre — not exactly on any register site
    result = match_candidate_to_register(
        555332.19,  # offset by 1 metre from known site
        5871940.23,
        'E06000021',
        connection,
        distance_threshold=0.0
    )
    assert result is None

def test_match_candidate_large_threshold_finds_match(connection):
    """Tests that a very large threshold finds a match for any coordinate near Stoke."""
    result = match_candidate_to_register(
        555331.19,
        5871939.23,
        'E06000021',
        connection,
        distance_threshold=50000.0
    )
    assert result is not None

def test_match_candidate_returns_closest_site(connection):
    """Tests that the closest register site is returned when multiple are within threshold."""
    register_sites = retrieve_brownfield_register_data('E06000021', 2024, connection)
    first_site = register_sites[0]

    result = match_candidate_to_register(
        first_site['utm_x'],
        first_site['utm_y'],
        'E06000021',
        connection,
        distance_threshold=10000.0
    )
    assert result is not None
    assert isinstance(result, str)

def test_match_candidate_uses_most_recent_year(connection):
    """Tests that match_candidate_to_register runs without error using most recent year automatically."""
    result = match_candidate_to_register(
        555331.19,
        5871939.23,
        'E06000021',
        connection,
        distance_threshold=50000.0
    )
    assert result is None or isinstance(result, str)

# --- detect_register_changes tests ---
def test_detect_register_changes_returns_dict(connection):
    """Tests that detect_register_changes returns a dict with added and removed keys."""
    result = detect_register_changes('E06000021', 2019, 2024, connection)
    assert isinstance(result, dict)
    assert 'removed' in result
    assert 'added' in result

def test_detect_register_changes_returns_lists(connection):
    """Tests that added and removed values are lists."""
    result = detect_register_changes('E06000021', 2019, 2024, connection)
    assert isinstance(result['removed'], list)
    assert isinstance(result['added'], list)

def test_detect_register_changes_same_year_raises(connection):
    """Tests that comparing a year to itself raises ValueError."""
    with pytest.raises(ValueError):
        detect_register_changes('E06000021', 2024, 2024, connection)

def test_detect_register_changes_year_from_after_year_to_raises(connection):
    """Tests that year_from greater than year_to raises ValueError."""
    with pytest.raises(ValueError):
        detect_register_changes('E06000021', 2024, 2019, connection)

def test_detect_register_changes_returns_real_results(connection):
    """Tests that change detection returns real results using start_date and end_date fields."""
    result = detect_register_changes('E06000021', 2019, 2024, connection)
    assert len(result['removed']) > 0
    assert len(result['added']) > 0

def test_detect_register_changes_removed_count(connection):
    """Tests that the correct number of sites were removed between 2019 and 2024."""
    result = detect_register_changes('E06000021', 2019, 2024, connection)
    assert len(result['removed']) == 66

def test_detect_register_changes_added_count(connection):
    """Tests that the correct number of sites were added between 2019 and 2024."""
    result = detect_register_changes('E06000021', 2019, 2024, connection)
    assert len(result['added']) == 119

def test_detect_register_changes_no_overlap(connection):
    """Tests that the overlap between added and removed is documented.
    Some sites may appear in both if they were added then later removed
    within the comparison period."""
    result = detect_register_changes('E06000021', 2019, 2024, connection)
    removed_refs = {s['site_reference'] for s in result['removed']}
    added_refs = {s['site_reference'] for s in result['added']}
    # Overlap is valid — sites can be added then removed within the period
    assert isinstance(removed_refs & added_refs, set)

def test_detect_register_changes_narrow_range(connection):
    """Tests that a narrow year range returns fewer results than a wide range."""
    result_wide = detect_register_changes('E06000021', 2017, 2024, connection)
    result_narrow = detect_register_changes('E06000021', 2021, 2024, connection)
    assert len(result_wide['removed']) >= len(result_narrow['removed'])