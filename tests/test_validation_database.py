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


# --- Fixtures ---

def make_mock_connection(count=1):
    """Creates a mock database connection returning a given count."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [count]
    return mock_conn


def make_valid_candidate_site(**overrides):
    """Creates a valid candidate site dict with optional overrides."""
    site = {
        'centroid_utm_x': 555331.19,
        'centroid_utm_y': 5871939.23,
        'pixel_count': 100,
        'mean_bsi': 0.15
    }
    site.update(overrides)
    return site


# --- validate_council_boundary_gss tests ---

def test_validate_gss_returns_true_for_valid_code():
    """Tests that a valid GSS code that exists in the database returns True."""
    conn = make_mock_connection(count=1)
    result = validate_council_boundary_gss('E06000021', conn)
    assert result is True


def test_validate_gss_raises_for_non_string():
    """Tests that a non-string GSS code raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        validate_council_boundary_gss(123456, conn)


def test_validate_gss_raises_for_wrong_format():
    """Tests that an incorrectly formatted GSS code raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        validate_council_boundary_gss('INVALID', conn)


def test_validate_gss_raises_for_too_short():
    """Tests that a GSS code that is too short raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        validate_council_boundary_gss('E0600002', conn)


def test_validate_gss_raises_for_too_long():
    """Tests that a GSS code that is too long raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        validate_council_boundary_gss('E060000211', conn)


def test_validate_gss_raises_for_invalid_prefix():
    """Tests that a GSS code with an invalid prefix letter raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        validate_council_boundary_gss('X06000021', conn)


def test_validate_gss_raises_for_not_found_in_database():
    """Tests that a valid format GSS code not in the database raises ValueError."""
    conn = make_mock_connection(count=0)
    with pytest.raises(ValueError):
        validate_council_boundary_gss('E06000021', conn)


def test_validate_gss_accepts_all_valid_prefixes():
    """Tests that GSS codes with E, N, S and W prefixes are all accepted."""
    for prefix in ['E', 'N', 'S', 'W']:
        conn = make_mock_connection(count=1)
        result = validate_council_boundary_gss(f'{prefix}06000021', conn)
        assert result is True


def test_validate_gss_empty_string_raises():
    """Tests that an empty string raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        validate_council_boundary_gss('', conn)


# --- brownfield_data_validation tests ---

def test_brownfield_validation_returns_true_for_valid_data():
    """Tests that valid GSS code and year with data returns True."""
    conn = make_mock_connection(count=218)
    result = brownfield_data_validation('E06000021', 2024, conn)
    assert result is True


def test_brownfield_validation_raises_for_non_integer_year():
    """Tests that a non-integer year raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', '2024', conn)


def test_brownfield_validation_raises_for_year_too_low():
    """Tests that a year below 2000 raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', 1999, conn)


def test_brownfield_validation_raises_for_year_too_high():
    """Tests that a year above 2100 raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', 2101, conn)


def test_brownfield_validation_raises_for_no_data():
    """Tests that a valid GSS code and year with no data raises ValueError."""
    conn = make_mock_connection(count=0)
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', 2024, conn)


def test_brownfield_validation_raises_for_zero_year():
    """Tests that year 0 raises ValueError."""
    conn = make_mock_connection()
    with pytest.raises(ValueError):
        brownfield_data_validation('E06000021', 0, conn)


def test_brownfield_validation_accepts_boundary_years():
    """Tests that boundary years 2000 and 2100 are accepted."""
    for year in [2000, 2100]:
        conn = make_mock_connection(count=10)
        result = brownfield_data_validation('E06000021', year, conn)
        assert result is True


# --- store_candidate_sites_validation tests ---

def test_candidate_sites_validation_returns_true_for_valid_data():
    """Tests that a valid list of candidate sites returns True."""
    sites = [make_valid_candidate_site()]
    result = store_candidate_sites_validation(sites)
    assert result is True


def test_candidate_sites_validation_raises_for_empty_list():
    """Tests that an empty list raises ValueError."""
    with pytest.raises(ValueError):
        store_candidate_sites_validation([])


def test_candidate_sites_validation_raises_for_missing_utm_x():
    """Tests that a site missing centroid_utm_x raises ValueError."""
    sites = [make_valid_candidate_site()]
    del sites[0]['centroid_utm_x']
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_missing_utm_y():
    """Tests that a site missing centroid_utm_y raises ValueError."""
    sites = [make_valid_candidate_site()]
    del sites[0]['centroid_utm_y']
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_missing_pixel_count():
    """Tests that a site missing pixel_count raises ValueError."""
    sites = [make_valid_candidate_site()]
    del sites[0]['pixel_count']
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_missing_mean_bsi():
    """Tests that a site missing mean_bsi raises ValueError."""
    sites = [make_valid_candidate_site()]
    del sites[0]['mean_bsi']
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_zero_pixel_count():
    """Tests that a pixel count of zero raises ValueError."""
    sites = [make_valid_candidate_site(pixel_count=0)]
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_negative_pixel_count():
    """Tests that a negative pixel count raises ValueError."""
    sites = [make_valid_candidate_site(pixel_count=-1)]
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_bsi_above_1():
    """Tests that a BSI value above 1 raises ValueError."""
    sites = [make_valid_candidate_site(mean_bsi=1.1)]
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_bsi_below_minus_1():
    """Tests that a BSI value below -1 raises ValueError."""
    sites = [make_valid_candidate_site(mean_bsi=-1.1)]
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_accepts_boundary_bsi_values():
    """Tests that BSI values of exactly -1 and 1 are accepted."""
    for bsi in [-1.0, 1.0]:
        sites = [make_valid_candidate_site(mean_bsi=bsi)]
        result = store_candidate_sites_validation(sites)
        assert result is True


def test_candidate_sites_validation_raises_for_utm_x_out_of_range():
    """Tests that a UTM X coordinate outside valid range raises ValueError."""
    sites = [make_valid_candidate_site(centroid_utm_x=1500000)]
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_utm_y_out_of_range():
    """Tests that a UTM Y coordinate outside valid range raises ValueError."""
    sites = [make_valid_candidate_site(centroid_utm_y=11000000)]
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_raises_for_negative_utm():
    """Tests that negative UTM coordinates raise ValueError."""
    sites = [make_valid_candidate_site(centroid_utm_x=-1000)]
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


def test_candidate_sites_validation_multiple_sites_all_valid():
    """Tests that multiple valid sites all pass validation."""
    sites = [make_valid_candidate_site() for _ in range(10)]
    result = store_candidate_sites_validation(sites)
    assert result is True


def test_candidate_sites_validation_fails_on_second_invalid_site():
    """Tests that validation fails if any site in the list is invalid."""
    sites = [
        make_valid_candidate_site(),
        make_valid_candidate_site(pixel_count=-1)
    ]
    with pytest.raises(ValueError):
        store_candidate_sites_validation(sites)


# --- store_pipeline_metadata_validation tests ---

def test_pipeline_metadata_validation_returns_true_for_valid_data():
    """Tests that valid pipeline metadata returns True."""
    result = store_pipeline_metadata_validation(
        'E06000021', '2026-05-25', 'success', 10, 5, 5)
    assert result is True


def test_pipeline_metadata_validation_raises_for_invalid_status():
    """Tests that an invalid status raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'invalid', 10, 5, 5)


def test_pipeline_metadata_validation_raises_for_negative_candidate_count():
    """Tests that a negative candidate_sites_found raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', -1, 0, 0)


def test_pipeline_metadata_validation_raises_for_negative_matched():
    """Tests that a negative matched_to_register raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', 10, -1, 5)


def test_pipeline_metadata_validation_raises_for_negative_unmatched():
    """Tests that a negative unmatched raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', 10, 5, -1)


def test_pipeline_metadata_validation_raises_for_invalid_date_format():
    """Tests that an incorrectly formatted date raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '25-05-2026', 'success', 10, 5, 5)


def test_pipeline_metadata_validation_raises_for_invalid_date_separators():
    """Tests that a date with wrong separators raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026/05/25', 'success', 10, 5, 5)


def test_pipeline_metadata_validation_raises_for_invalid_gss_code():
    """Tests that an invalid GSS code format raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'INVALID', '2026-05-25', 'success', 10, 5, 5)


def test_pipeline_metadata_validation_raises_when_matched_plus_unmatched_exceeds_total():
    """Tests that matched + unmatched exceeding total raises ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', 10, 8, 5)


def test_pipeline_metadata_validation_accepts_failure_status():
    """Tests that status of 'failure' is accepted."""
    result = store_pipeline_metadata_validation(
        'E06000021', '2026-05-25', 'failure', 0, 0, 0)
    assert result is True


def test_pipeline_metadata_validation_accepts_zero_counts():
    """Tests that all zero counts are valid for a failed run."""
    result = store_pipeline_metadata_validation(
        'E06000021', '2026-05-25', 'failure', 0, 0, 0)
    assert result is True


def test_pipeline_metadata_validation_raises_for_non_integer_counts():
    """Tests that non-integer counts raise ValueError."""
    with pytest.raises(ValueError):
        store_pipeline_metadata_validation(
            'E06000021', '2026-05-25', 'success', '10', 5, 5)


def test_pipeline_metadata_validation_matched_equals_total_is_valid():
    """Tests that all candidates being matched is valid."""
    result = store_pipeline_metadata_validation(
        'E06000021', '2026-05-25', 'success', 10, 10, 0)
    assert result is True


def test_pipeline_metadata_validation_unmatched_equals_total_is_valid():
    """Tests that all candidates being unmatched is valid."""
    result = store_pipeline_metadata_validation(
        'E06000021', '2026-05-25', 'success', 10, 0, 10)
    assert result is True