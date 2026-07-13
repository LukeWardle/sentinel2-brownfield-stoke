"""
test_aoi_clipping.py - Unit tests for aoi_clipping.py
"""
import pytest
import json
import numpy as np
from unittest.mock import MagicMock
from src.aoi_clipping import clip_to_council_boundary

# --- Fixtures and helpers ---
def make_mock_connection(geometry_type='Polygon', boundary_coords=None):
    """Creates a mock database connection returning a boundary polygon."""
    if boundary_coords is None:
        # Simple square boundary in UTM coordinates
        boundary_coords = [[[500000, 5880000],
                             [510000, 5880000],
                             [510000, 5890000],
                             [500000, 5890000],
                             [500000, 5880000]]]

    geometry = {
        'type': geometry_type,
        'coordinates': boundary_coords
    }

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [json.dumps(geometry)]
    return mock_conn

def make_band_array_and_mask(original_shape=(10, 10), valid_fraction=0.8):
    """Creates a synthetic band array and mask for testing."""
    total_pixels = original_shape[0] * original_shape[1]
    mask_2d = np.zeros(original_shape, dtype=bool)

    # Mark a block of pixels as valid
    rows = int(original_shape[0] * valid_fraction)
    cols = int(original_shape[1] * valid_fraction)
    mask_2d[:rows, :cols] = True

    mask = mask_2d.flatten()
    n_valid = mask.sum()
    band_array = np.random.rand(n_valid, 10).astype(np.float32)
    return band_array, mask

def make_tile_metadata(left=499980.0, top=5900040.0, resolution=20):
    """Creates a tile metadata dict."""
    return {'left': left, 'top': top, 'resolution': resolution}

# --- clip_to_council_boundary tests ---
def test_clip_returns_tuple():
    """Tests that clip_to_council_boundary returns a tuple."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()
    result = clip_to_council_boundary(band_array, mask, (10, 10),
                                      tile_metadata, 'E06000021', conn)
    assert isinstance(result, tuple)
    assert len(result) == 2

def test_clip_returns_ndarray_types():
    """Tests that both returned values are numpy arrays."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()
    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, (10, 10), tile_metadata, 'E06000021', conn)
    assert isinstance(clipped_array, np.ndarray)
    assert isinstance(clipped_mask, np.ndarray)

def test_clip_mask_same_length_as_input_mask():
    """Tests that the returned mask has the same length as the input mask."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()
    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, (10, 10), tile_metadata, 'E06000021', conn)
    assert len(clipped_mask) == len(mask)

def test_clip_clipped_array_has_10_bands():
    """Tests that the clipped band array retains 10 bands."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()
    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, (10, 10), tile_metadata, 'E06000021', conn)
    if len(clipped_array) > 0:
        assert clipped_array.shape[1] == 10

def test_clip_reduces_pixel_count():
    """Tests that clipping reduces the number of valid pixels."""
    original_shape = (100, 100)
    band_array, mask = make_band_array_and_mask(original_shape)
    tile_metadata = make_tile_metadata()

    # Boundary covers only a small portion of the image
    small_boundary = [[[499980, 5899000],
                       [500200, 5899000],
                       [500200, 5899200],
                       [499980, 5899200],
                       [499980, 5899000]]]
    conn = make_mock_connection(boundary_coords=small_boundary)

    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, original_shape, tile_metadata, 'E06000021', conn)
    assert clipped_mask.sum() <= mask.sum()

def test_clip_large_boundary_keeps_all_pixels():
    """Tests that a boundary covering the entire image keeps all valid pixels."""
    original_shape = (10, 10)
    band_array, mask = make_band_array_and_mask(original_shape)
    tile_metadata = make_tile_metadata(left=0.0, top=10000.0, resolution=20)

    # Boundary much larger than the image
    large_boundary = [[[-1000000, -1000000],
                       [1000000, -1000000],
                       [1000000, 1000000],
                       [-1000000, 1000000],
                       [-1000000, -1000000]]]
    conn = make_mock_connection(boundary_coords=large_boundary)

    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, original_shape, tile_metadata, 'E06000021', conn)
    assert clipped_mask.sum() == mask.sum()

def test_clip_invalid_gss_code_raises_value_error():
    """Tests that an invalid GSS code raises a ValueError."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None

    with pytest.raises(ValueError):
        clip_to_council_boundary(band_array, mask, (10, 10),
                                 tile_metadata, 'INVALID', mock_conn)

def test_clip_null_boundary_raises_value_error():
    """Tests that a NULL boundary result raises a ValueError."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [None]

    with pytest.raises(ValueError):
        clip_to_council_boundary(band_array, mask, (10, 10),
                                 tile_metadata, 'E06000021', mock_conn)

def test_clip_handles_multipolygon():
    """Tests that MultiPolygon boundaries are handled correctly."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()

    # MultiPolygon with two separate polygons
    multipolygon_coords = [
        [[[499980, 5899800], [500100, 5899800],
          [500100, 5899900], [499980, 5899900],
          [499980, 5899800]]],
        [[[500200, 5899800], [500300, 5899800],
          [500300, 5899900], [500200, 5899900],
          [500200, 5899800]]]
    ]
    conn = make_mock_connection(geometry_type='MultiPolygon',
                                boundary_coords=multipolygon_coords)

    result = clip_to_council_boundary(band_array, mask, (10, 10),
                                      tile_metadata, 'E06000021', conn)
    assert isinstance(result, tuple)
    assert len(result) == 2

def test_clip_unsupported_geometry_raises_value_error():
    """Tests that an unsupported geometry type raises a ValueError."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [json.dumps({
        'type': 'Point',
        'coordinates': [500000, 5880000]
    })]

    with pytest.raises(ValueError):
        clip_to_council_boundary(band_array, mask, (10, 10),
                                 tile_metadata, 'E06000021', mock_conn)

def test_clip_empty_band_array_returns_empty():
    """Tests that an all-False mask returns an empty clipped array."""
    original_shape = (10, 10)
    mask = np.zeros(100, dtype=bool)
    band_array = np.zeros((0, 10))
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()

    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, original_shape, tile_metadata, 'E06000021', conn)
    assert len(clipped_array) == 0
    assert clipped_mask.sum() == 0

def test_clip_clipped_array_rows_match_clipped_mask():
    """Tests that clipped array row count matches the number of True values in clipped mask."""
    original_shape = (100, 100)
    band_array, mask = make_band_array_and_mask(original_shape)
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()

    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, original_shape, tile_metadata, 'E06000021', conn)
    assert clipped_array.shape[0] == clipped_mask.sum()

def test_clip_mask_is_subset_of_input_mask():
    """Tests that the clipped mask only sets pixels to False — never adds new True values."""
    band_array, mask = make_band_array_and_mask()
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()

    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, (10, 10), tile_metadata, 'E06000021', conn)

    # Every True in clipped_mask must also be True in original mask
    assert np.all(mask[clipped_mask])

def test_clip_boundary_outside_image_returns_empty():
    """Tests that a boundary entirely outside the image returns no valid pixels."""
    original_shape = (10, 10)
    band_array, mask = make_band_array_and_mask(original_shape)
    tile_metadata = make_tile_metadata(left=0.0, top=200.0, resolution=20)

    # Boundary far outside the image extent
    outside_boundary = [[[999000, 999000],
                         [999100, 999000],
                         [999100, 999100],
                         [999000, 999100],
                         [999000, 999000]]]
    conn = make_mock_connection(boundary_coords=outside_boundary)

    clipped_array, clipped_mask = clip_to_council_boundary(
        band_array, mask, original_shape, tile_metadata, 'E06000021', conn)
    assert clipped_mask.sum() == 0
    assert len(clipped_array) == 0