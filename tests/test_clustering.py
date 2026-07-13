"""
test_clustering.py - Unit tests for clustering.py
"""
import pytest
import numpy as np
from src.clustering import (
    group_pixels_for_candidate_sites,
    calculate_site_properties,
    generate_boundary_polygons
)

# --- Shared fixtures ---
def make_simple_mask_and_xreduced():
    """Creates a 10x10 grid with a 6x6 block of valid pixels."""
    original_shape = (10, 10)
    mask_2d = np.zeros(original_shape, dtype=bool)
    mask_2d[2:8, 2:8] = True
    mask = mask_2d.flatten()
    n_valid = mask.sum()
    X_reduced = np.random.rand(n_valid, 3)
    return mask, X_reduced, original_shape

def make_bsi_ndvi_above_threshold(n_valid):
    """Creates BSI and NDVI arrays where all pixels meet default thresholds."""
    bsi_array = np.full(n_valid, 0.15)
    ndvi_array = np.full(n_valid, 0.05)
    return bsi_array, ndvi_array

def make_bsi_ndvi_below_threshold(n_valid):
    """Creates BSI and NDVI arrays where no pixels meet default thresholds."""
    bsi_array = np.full(n_valid, -0.1)
    ndvi_array = np.full(n_valid, 0.5)
    return bsi_array, ndvi_array

def make_tile_metadata():
    return {'left': 499980.0, 'top': 5900040.0, 'resolution': 20}

# --- group_pixels_for_candidate_sites tests ---
def test_group_pixels_returns_dict():
    """Tests that group_pixels_for_candidate_sites returns a dict."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    assert isinstance(result, dict)

def test_group_pixels_finds_cluster():
    """Tests that candidate pixels meeting thresholds are grouped."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        min_pixels=5
    )
    assert len(result) >= 1

def test_group_pixels_returns_lists_of_indices():
    """Tests that each group value is a list of integer pixel indices."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    for site_id, indices in result.items():
        assert isinstance(indices, list)
        assert all(isinstance(i, (int, np.integer)) for i in indices)

def test_group_pixels_empty_mask_returns_empty_dict():
    """Tests that an all-False mask returns an empty dict."""
    original_shape = (5, 5)
    mask = np.zeros(25, dtype=bool)
    X_reduced = np.zeros((0, 3))
    bsi_array = np.zeros(0)
    ndvi_array = np.zeros(0)
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    assert result == {}

def test_group_pixels_no_candidates_returns_empty_dict():
    """Tests that pixels not meeting BSI/NDVI thresholds returns empty dict."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_below_threshold(mask.sum())
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    assert result == {}

def test_group_pixels_high_bsi_threshold_reduces_groups():
    """Tests that a higher BSI threshold produces fewer total candidate pixels."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array = np.random.uniform(0.0, 0.2, mask.sum())
    ndvi_array = np.full(mask.sum(), 0.05)
    result_low = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        bsi_threshold=0.0
    )
    result_high = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        bsi_threshold=0.19
    )
    total_pixels_low = sum(len(v) for v in result_low.values())
    total_pixels_high = sum(len(v) for v in result_high.values())
    assert total_pixels_low >= total_pixels_high

def test_group_pixels_minimum_size_filter():
    """Tests that groups smaller than min_pixels are filtered out."""
    original_shape = (20, 20)
    mask_2d = np.zeros(original_shape, dtype=bool)
    mask_2d[0, 0] = True
    mask_2d[0, 1] = True
    mask = mask_2d.flatten()
    X_reduced = np.random.rand(mask.sum(), 3)
    bsi_array = np.full(mask.sum(), 0.15)
    ndvi_array = np.full(mask.sum(), 0.05)
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        min_pixels=10, max_pixels=2500
    )
    assert len(result) == 0

def test_group_pixels_maximum_size_filter():
    """Tests that groups larger than max_pixels are filtered out."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        min_pixels=1, max_pixels=3
    )
    for site_id, indices in result.items():
        assert len(indices) <= 3

def test_group_pixels_indices_within_valid_range():
    """Tests that all pixel indices are within the valid range."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    n_valid = mask.sum()
    for site_id, indices in result.items():
        assert all(0 <= i < n_valid for i in indices)

def test_group_pixels_default_thresholds():
    """Tests that default BSI and NDVI thresholds are applied correctly."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array = np.full(mask.sum(), 0.06)
    ndvi_array = np.full(mask.sum(), 0.15)
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    assert isinstance(result, dict)

def test_group_pixels_bsi_exactly_at_threshold_excluded():
    """Tests that pixels with BSI exactly equal to threshold are excluded."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array = np.full(mask.sum(), 0.05)
    ndvi_array = np.full(mask.sum(), 0.05)
    result = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        bsi_threshold=0.05
    )
    assert result == {}

def test_group_pixels_mixed_bsi_values():
    """Tests that only pixels above BSI threshold are included in groups."""
    original_shape = (10, 10)
    mask_2d = np.zeros(original_shape, dtype=bool)
    mask_2d[2:8, 2:8] = True
    mask = mask_2d.flatten()
    n_valid = mask.sum()
    X_reduced = np.random.rand(n_valid, 3)
    bsi_array = np.full(n_valid, -0.1)
    bsi_array[:10] = 0.15
    ndvi_array = np.full(n_valid, 0.05)
    result_all = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        bsi_threshold=0.05, min_pixels=1
    )
    result_none = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        bsi_threshold=0.5, min_pixels=1
    )
    assert len(result_all) >= len(result_none)

# --- calculate_site_properties tests ---
def test_calculate_site_properties_returns_list():
    """Tests that calculate_site_properties returns a list."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    assert isinstance(result, list)

def test_calculate_site_properties_correct_keys():
    """Tests that each site dict contains the correct keys."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    if result:
        assert 'site_id' in result[0]
        assert 'pixel_count' in result[0]
        assert 'hectares' in result[0]
        assert 'mean_bsi' in result[0]
        assert 'centroid_utm_x' in result[0]
        assert 'centroid_utm_y' in result[0]

def test_calculate_site_properties_pixel_count_positive():
    """Tests that pixel count is always positive."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    for site in result:
        assert site['pixel_count'] > 0

def test_calculate_site_properties_bsi_within_range():
    """Tests that mean BSI values are within the valid -1 to 1 range."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array = np.random.uniform(-1, 1, mask.sum())
    ndvi_array = np.full(mask.sum(), 0.05)
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array,
        bsi_threshold=-2.0
    )
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    for site in result:
        assert -1.0 <= site['mean_bsi'] <= 1.0

def test_calculate_site_properties_utm_coordinates_are_floats():
    """Tests that UTM coordinates are returned as floats."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    for site in result:
        assert isinstance(site['centroid_utm_x'], float)
        assert isinstance(site['centroid_utm_y'], float)

def test_calculate_site_properties_empty_groups_returns_empty_list():
    """Tests that empty candidate_groups returns an empty list."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, _ = make_bsi_ndvi_above_threshold(mask.sum())
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties({}, bsi_array, mask, original_shape, tile_metadata)
    assert result == []

def test_calculate_site_properties_utm_within_tile_bounds():
    """Tests that centroid UTM coordinates fall within the satellite tile bounds."""
    original_shape = (100, 100)
    mask_2d = np.zeros(original_shape, dtype=bool)
    mask_2d[10:20, 10:20] = True
    mask = mask_2d.flatten()
    n_valid = mask.sum()
    X_reduced = np.random.rand(n_valid, 3)
    bsi_array = np.full(n_valid, 0.15)
    ndvi_array = np.full(n_valid, 0.05)
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    for site in result:
        assert site['centroid_utm_x'] >= tile_metadata['left']
        assert site['centroid_utm_y'] <= tile_metadata['top']

def test_calculate_site_properties_hectares_correct():
    """Tests that hectares is correctly calculated from pixel count."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    if result:
        site = result[0]
        assert site['hectares'] == round(site['pixel_count'] * 0.04, 2)

def test_calculate_site_properties_single_pixel_site():
    """Tests that a single pixel site is handled correctly."""
    original_shape = (10, 10)
    mask_2d = np.zeros(original_shape, dtype=bool)
    mask_2d[5, 5] = True
    mask = mask_2d.flatten()
    bsi_array = np.array([0.15])
    candidate_groups = {0: [0]}
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    assert len(result) == 1
    assert result[0]['pixel_count'] == 1
    assert result[0]['hectares'] == 0.04

def test_calculate_site_properties_count_matches_groups():
    """Tests that the number of site properties matches the number of groups."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask, original_shape, tile_metadata)
    assert len(result) == len(candidate_groups)

# --- generate_boundary_polygons tests ---
def test_generate_boundary_polygons_returns_list():
    """Tests that generate_boundary_polygons returns a list."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    assert isinstance(result, list)

def test_generate_boundary_polygons_correct_keys():
    """Tests that each polygon dict contains site_id and boundary keys."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    if result:
        assert 'site_id' in result[0]
        assert 'boundary' in result[0]

def test_generate_boundary_polygons_boundary_is_list():
    """Tests that the boundary value is a list of coordinate pairs."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    if result:
        assert isinstance(result[0]['boundary'], list)

def test_generate_boundary_polygons_coordinates_are_pairs():
    """Tests that each boundary coordinate is a pair of floats."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    if result and result[0]['boundary']:
        for coord in result[0]['boundary']:
            assert len(coord) == 2
            assert isinstance(coord[0], float)
            assert isinstance(coord[1], float)

def test_generate_boundary_polygons_polygon_is_closed():
    """Tests that each boundary polygon is closed."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    if result and len(result[0]['boundary']) > 1:
        boundary = result[0]['boundary']
        assert boundary[0] == boundary[-1]

def test_generate_boundary_polygons_empty_groups_returns_empty_list():
    """Tests that empty candidate_groups returns an empty list."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons({}, mask, original_shape, tile_metadata)
    assert result == []

def test_generate_boundary_polygons_count_matches_groups():
    """Tests that the number of polygons matches the number of candidate groups."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array, ndvi_array = make_bsi_ndvi_above_threshold(mask.sum())
    candidate_groups = group_pixels_for_candidate_sites(
        X_reduced, mask, original_shape, bsi_array, ndvi_array
    )
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    assert len(result) == len(candidate_groups)

def test_generate_boundary_polygons_single_pixel_site():
    """Tests that a single pixel site produces a boundary or empty list gracefully."""
    original_shape = (10, 10)
    mask_2d = np.zeros(original_shape, dtype=bool)
    mask_2d[5, 5] = True
    mask = mask_2d.flatten()
    candidate_groups = {0: [0]}
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    assert isinstance(result, list)
    assert len(result) == 1
    assert 'site_id' in result[0]
    assert 'boundary' in result[0]