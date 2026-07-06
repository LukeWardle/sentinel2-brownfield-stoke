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


# --- Shared test fixtures ---

def make_simple_mask_and_xreduced():
    """Creates a simple 5x5 grid with a cluster of valid pixels in the centre."""
    original_shape = (5, 5)
    mask_2d = np.zeros(original_shape, dtype=bool)
    mask_2d[1:4, 1:4] = True  # 3x3 block of valid pixels = 9 pixels
    mask = mask_2d.flatten()
    n_valid = mask.sum()
    X_reduced = np.random.rand(n_valid, 3) * 0.05  # very similar spectral values
    return mask, X_reduced, original_shape


def make_tile_metadata():
    return {'left': 499980.0, 'top': 5900040.0, 'resolution': 20}


# --- group_pixels_for_candidate_sites tests ---

def test_group_pixels_returns_dict():
    """Tests that group_pixels_for_candidate_sites returns a dict."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    result = group_pixels_for_candidate_sites(X_reduced, mask, original_shape)
    assert isinstance(result, dict)


def test_group_pixels_finds_cluster():
    """Tests that a clear cluster of similar pixels is identified as one group."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    result = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                              similarity_threshold=1.0)
    assert len(result) >= 1


def test_group_pixels_returns_lists_of_indices():
    """Tests that each group value is a list of integer pixel indices."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    result = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                              similarity_threshold=1.0)
    for site_id, indices in result.items():
        assert isinstance(indices, list)
        assert all(isinstance(i, (int, np.integer)) for i in indices)


def test_group_pixels_empty_mask_returns_empty_dict():
    """Tests that an all-False mask returns an empty dict."""
    original_shape = (5, 5)
    mask = np.zeros(25, dtype=bool)
    X_reduced = np.zeros((0, 3))
    result = group_pixels_for_candidate_sites(X_reduced, mask, original_shape)
    assert result == {}


def test_group_pixels_very_low_threshold_reduces_groups():
    """Tests that a very low similarity threshold produces fewer or no groups."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    X_reduced = np.random.rand(mask.sum(), 3) * 10  # very different spectral values
    result = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                              similarity_threshold=0.0001)
    assert len(result) == 0


def test_group_pixels_high_threshold_finds_groups():
    """Tests that a very high similarity threshold groups everything together."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    result = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                              similarity_threshold=100.0)
    assert len(result) >= 1


def test_group_pixels_minimum_size_filter():
    """Tests that groups smaller than 5 pixels are filtered out."""
    original_shape = (5, 5)
    mask_2d = np.zeros(original_shape, dtype=bool)
    mask_2d[0, 0] = True  # only 1 pixel — below minimum size
    mask_2d[0, 1] = True  # 2 pixels total — still below minimum
    mask = mask_2d.flatten()
    X_reduced = np.zeros((mask.sum(), 3))
    result = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                              similarity_threshold=1.0)
    assert len(result) == 0


def test_group_pixels_indices_within_valid_range():
    """Tests that all pixel indices are within the valid range of the masked array."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    result = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                              similarity_threshold=1.0)
    n_valid = mask.sum()
    for site_id, indices in result.items():
        assert all(0 <= i < n_valid for i in indices)


# --- calculate_site_properties tests ---

def test_calculate_site_properties_returns_list():
    """Tests that calculate_site_properties returns a list."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    bsi_array = np.random.rand(mask.sum())
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask,
                                       original_shape, tile_metadata)
    assert isinstance(result, list)


def test_calculate_site_properties_correct_keys():
    """Tests that each site dict contains the correct keys."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    bsi_array = np.random.rand(mask.sum())
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask,
                                       original_shape, tile_metadata)
    if result:
        assert 'site_id' in result[0]
        assert 'pixel_count' in result[0]
        assert 'mean_bsi' in result[0]
        assert 'centroid_utm_x' in result[0]
        assert 'centroid_utm_y' in result[0]


def test_calculate_site_properties_pixel_count_positive():
    """Tests that pixel count is always positive."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    bsi_array = np.random.rand(mask.sum())
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask,
                                       original_shape, tile_metadata)
    for site in result:
        assert site['pixel_count'] > 0


def test_calculate_site_properties_bsi_within_range():
    """Tests that mean BSI values are within the valid -1 to 1 range."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    bsi_array = np.random.uniform(-1, 1, mask.sum())
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask,
                                       original_shape, tile_metadata)
    for site in result:
        assert -1.0 <= site['mean_bsi'] <= 1.0


def test_calculate_site_properties_utm_coordinates_are_floats():
    """Tests that UTM coordinates are returned as floats."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    bsi_array = np.random.rand(mask.sum())
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask,
                                       original_shape, tile_metadata)
    for site in result:
        assert isinstance(site['centroid_utm_x'], float)
        assert isinstance(site['centroid_utm_y'], float)


def test_calculate_site_properties_empty_groups_returns_empty_list():
    """Tests that empty candidate_groups returns an empty list."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    bsi_array = np.random.rand(mask.sum())
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties({}, bsi_array, mask, original_shape, tile_metadata)
    assert result == []


def test_calculate_site_properties_utm_within_tile_bounds():
    """Tests that centroid UTM coordinates fall within the satellite tile bounds."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    bsi_array = np.random.rand(mask.sum())
    tile_metadata = make_tile_metadata()
    result = calculate_site_properties(candidate_groups, bsi_array, mask,
                                       original_shape, tile_metadata)
    for site in result:
        assert site['centroid_utm_x'] >= tile_metadata['left']
        assert site['centroid_utm_y'] <= tile_metadata['top']


# --- generate_boundary_polygons tests ---

def test_generate_boundary_polygons_returns_list():
    """Tests that generate_boundary_polygons returns a list."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    assert isinstance(result, list)


def test_generate_boundary_polygons_correct_keys():
    """Tests that each polygon dict contains site_id and boundary keys."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    if result:
        assert 'site_id' in result[0]
        assert 'boundary' in result[0]


def test_generate_boundary_polygons_boundary_is_list():
    """Tests that the boundary value is a list of coordinate pairs."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    if result:
        assert isinstance(result[0]['boundary'], list)


def test_generate_boundary_polygons_coordinates_are_pairs():
    """Tests that each boundary coordinate is a pair of floats."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    if result and result[0]['boundary']:
        for coord in result[0]['boundary']:
            assert len(coord) == 2
            assert isinstance(coord[0], float)
            assert isinstance(coord[1], float)


def test_generate_boundary_polygons_polygon_is_closed():
    """Tests that each boundary polygon is closed — first and last points are identical."""
    mask, X_reduced, original_shape = make_simple_mask_and_xreduced()
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
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
    candidate_groups = group_pixels_for_candidate_sites(X_reduced, mask, original_shape,
                                                        similarity_threshold=1.0)
    tile_metadata = make_tile_metadata()
    result = generate_boundary_polygons(candidate_groups, mask, original_shape, tile_metadata)
    assert len(result) == len(candidate_groups)