"""
test_validation_database.py - Unit tests for validation_database.py
"""
import pytest
from unittest.mock import MagicMock
from src.validation_database import (
    validate_council_boundary_gss,
    brownfield_data_validation,
    store_candidate_sites_validation,
    store_pipeline_metadata_validation
)

# --- Shared fixtures ---
@pytest.fixture
def mock_connection():
    """Creates a mock database connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor

def make_valid_candidate_site():
    return {
        'centroid_utm_x': 555331.19,
        'centroid_utm_y': 5871939.23,
        'pixel_count': 100,
        'hectares': 4.0,
        'mean_bsi': 0.15,
        'matched_site_reference': None
    }

# --- validate_council_boundary_gss tests ---
def test_validate_council_boundary_gss_valid(mock_connection):
    """Tests that a valid GSS code returns True."""
    conn, cursor = mock_connection
    cursor.fetchone.return_value = [1]
    result = validate_council_boundary_gss('E06000021', conn)
    assert result is True

def test_validate_council_boundary_gss_invalid_format(mock_connection):
    """Tests that invalid GSS code format raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        validate_council_boundary_gss('INVALID', conn)

def test_validate_council_boundary_gss_empty_string(mock_connection):
    """Tests that empty string raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        validate_council_boundary_gss('', conn)

def test_validate_council_boundary_gss_not_in_database(mock_connection):
    """Tests that GSS code not found in database raises ValueError."""
    conn, cursor = mock_connection
    cursor.fetchone.return_value = [0]
    with pytest.raises(ValueError):
        validate_council_boundary_gss('E06000021', conn)

def test_validate_council_boundary_gss_none(mock_connection):
    """Tests that None raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises((ValueError, AttributeError)):
        validate_council_boundary_gss(None, conn)

def test_validate_council_boundary_gss_lowercase(mock_connection):
    """Tests that lowercase GSS code raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        validate_council_boundary_gss('e06000021', conn)

def test_validate_council_boundary_gss_too_short(mock_connection):
    """Tests that GSS code that is too short raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        validate_council_boundary_gss('E060001', conn)

def test_validate_council_boundary_gss_too_long(mock_connection):
    """Tests that GSS code that is too long raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        validate_council_boundary_gss('E060000211', conn)

# --- brownfield_data_validation tests ---
def test_brownfield_data_validation_valid(mock_connection):
    """Tests that valid GSS code and year returns True."""
    conn, cursor = mock_connection
    cursor.fetchone.return_value = [218]
    result = brownfield_data_validation('E06000021', 2024, conn)
    assert result is True

def test_brownfield_data_validation_no_data(mock_connection):
    """Tests that missing data raises ValueError."""
    conn, cursor = mock_connection
    cursor.fetchone.return_value = [0]
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', 2024, conn)

def test_brownfield_data_validation_invalid_year_low(mock_connection):
    """Tests that year below valid range raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', 1999, conn)

def test_brownfield_data_validation_invalid_year_high(mock_connection):
    """Tests that year above valid range raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', 2101, conn)

def test_brownfield_data_validation_invalid_gss(mock_connection):
    """Tests that invalid GSS code format raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        brownfield_data_validation('INVALID', 2024, conn)

def test_brownfield_data_validation_year_zero(mock_connection):
    """Tests that year 0 raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', 0, conn)

def test_brownfield_data_validation_negative_year(mock_connection):
    """Tests that negative year raises ValueError."""
    conn, cursor = mock_connection
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', -1, conn)

def test_brownfield_data_validation_boundary_year_2000(mock_connection):
    """Tests that year 2000 is accepted as valid."""
    conn, cursor = mock_connection
    cursor.fetchone.return_value = [10]
    result = brownfield_data_validation('E06000021', 2000, conn)
    assert result is True

def test_brownfield_data_validation_boundary_year_2100(mock_connection):
    """Tests that year 2100 is accepted as valid."""
    conn, cursor = mock_connection
    cursor.fetchone.return_value = [10]
    result = brownfield_data_validation('E06000021', 2100, conn)
    assert result is True

# --- store_candidate_sites_validation tests ---
def test_store_candidate_sites_validation_valid():
    """Tests that a valid list of candidate sites returns True."""
    sites = [make_valid_candidate_site()]
    result = store_candidate_sites_validation(sites)
    assert result is True

def test_store_candidate_sites_validation_empty_list():
    """Tests that an empty list raises ValueError."""
    with pytest.raises(ValueError):
        store_candidate_sites_validation([])

def test_store_candidate_sites_validation_missing_utm_x():
    """Tests that missing centroid_utm_x raises ValueError."""
    site = make_valid_candidate_site()
    del site['centroid_utm_x']
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_missing_utm_y():
    """Tests that missing centroid_utm_y raises ValueError."""
    site = make_valid_candidate_site()
    del site['centroid_utm_y']
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_missing_pixel_count():
    """Tests that missing pixel_count raises ValueError."""
    site = make_valid_candidate_site()
    del site['pixel_count']
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_missing_mean_bsi():
    """Tests that missing mean_bsi raises ValueError."""
    site = make_valid_candidate_site()
    del site['mean_bsi']
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_negative_pixel_count():
    """Tests that negative pixel count raises ValueError."""
    site = make_valid_candidate_site()
    site['pixel_count'] = -1
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_zero_pixel_count():
    """Tests that zero pixel count raises ValueError."""
    site = make_valid_candidate_site()
    site['pixel_count'] = 0
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_bsi_out_of_range_high():
    """Tests that BSI above 1.0 raises ValueError."""
    site = make_valid_candidate_site()
    site['mean_bsi'] = 1.5
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_bsi_out_of_range_low():
    """Tests that BSI below -1.0 raises ValueError."""
    site = make_valid_candidate_site()
    site['mean_bsi'] = -1.5
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_utm_x_out_of_range():
    """Tests that UTM x coordinate outside valid UK range raises ValueError."""
    site = make_valid_candidate_site()
    site['centroid_utm_x'] = 0.0
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_utm_y_out_of_range():
    """Tests that UTM y coordinate outside valid UK range raises ValueError."""
    site = make_valid_candidate_site()
    site['centroid_utm_y'] = 0.0
    with pytest.raises(ValueError):
        store_candidate_sites_validation([site])

def test_store_candidate_sites_validation_multiple_sites():
    """Tests that multiple valid sites returns True."""
    sites = [make_valid_candidate_site() for _ in range(5)]
    result = store_candidate_sites_validation(sites)
    assert result is True

def test_store_candidate_sites_validation_matched_site_reference_none():
    """Tests that None matched_site_reference is valid."""
    site = make_valid_candidate_site()
    site['matched_site_reference'] = None
    result = store_candidate_sites_validation([site])
    assert result is True

def test_store_candidate_sites_validation_matched_site_reference_string():
    """Tests that string matched_site_reference is valid."""
    site = make_valid_candidate_site()
    site['matched_site_reference'] = 'SITE001'
    result = store_candidate_sites_validation([site])
    assert result is True

# --- store_pipeline_metadata_validation tests ---
def test_store_pipeline_metadata_validation_valid():
    """Tests that valid metadata returns True."""
    result = store_pipeline_metadata_validation(
        'E06000021', '2026-05-25', 'success', 218, 39, 179
    )
    assert result is True

def test_store_pipeline_metadata_validation_failure_status():
    """Tests that failure status is accepted."""
    result = store_pipeline_metadata_validation(
        'E06000021', '2026-05-25', 'failure', 0, 0, 0
    )
    assert result is True

def test_store_pipeline_metadata_validation_invalid_status():
    """Tests that invalid status raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'unknown', 218, 39, 179
        )

def test_store_pipeline_metadata_validation_invalid_gss():
    """Tests that invalid GSS code raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'INVALID', '2026-05-25', 'success', 218, 39, 179
        )

def test_store_pipeline_metadata_validation_invalid_date_format():
    """Tests that invalid date format raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '25/05/2026', 'success', 218, 39, 179
        )

def test_store_pipeline_metadata_validation_negative_counts():
    """Tests that negative counts raise ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', -1, 0, 0
        )

def test_store_pipeline_metadata_validation_negative_matched():
    """Tests that negative matched count raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', 218, -1, 179
        )

def test_store_pipeline_metadata_validation_negative_unmatched():
    """Tests that negative unmatched count raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', 218, 39, -1
        )

def test_store_pipeline_metadata_validation_matched_plus_unmatched_exceeds_total():
    """Tests that matched + unmatched exceeding total raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', 100, 80, 80
        )

def test_store_pipeline_metadata_validation_zero_counts():
    """Tests that zero counts are valid for failure status."""
    result = store_pipeline_metadata_validation(
        'E06000021', '2026-05-25', 'failure', 0, 0, 0
    )
    assert result is True

def test_store_pipeline_metadata_validation_empty_date():
    """Tests that empty date string raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '', 'success', 218, 39, 179
        )