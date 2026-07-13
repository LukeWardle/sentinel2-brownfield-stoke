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

def make_bands_and_scl(shape=(10, 10), fill_scl=4):
    """
    Creates a 3D band array of shape (h, w, 10) and 2D SCL array of shape
    (h, w). Bands are filled with random non-zero uint16 values in the
    Sentinel-2 DN range, SCL is filled with class 4 (vegetation). Non-zero
    fills let tests distinguish clipped pixels (which become zero) from
    originals.
    """
    height, width = shape
    band_array = np.random.randint(1, 10000, (height, width, 10), dtype=np.uint16)
    scl_array = np.full(shape, fill_scl, dtype=np.uint8)
    return band_array, scl_array

def make_tile_metadata(left=499980.0, top=5900040.0, resolution=20):
    """Creates a tile metadata dict."""
    return {'left': left, 'top': top, 'resolution': resolution}

# --- clip_to_council_boundary tests ---
def test_clip_returns_tuple():
    """Tests that clip_to_council_boundary returns a tuple of length 2."""
    band_array, scl_array = make_bands_and_scl()
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()
    result = clip_to_council_boundary(band_array, scl_array,
                                      tile_metadata, 'E06000021', conn)
    assert isinstance(result, tuple)
    assert len(result) == 2

def test_clip_returns_ndarray_types():
    """Tests that both returned values are numpy arrays."""
    band_array, scl_array = make_bands_and_scl()
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()
    clipped_bands, clipped_scl = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, 'E06000021', conn)
    assert isinstance(clipped_bands, np.ndarray)
    assert isinstance(clipped_scl, np.ndarray)

def test_clip_bands_shape_preserved():
    """Tests that clipped bands array retains the input 3D shape."""
    band_array, scl_array = make_bands_and_scl(shape=(20, 20))
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()
    clipped_bands, _ = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, 'E06000021', conn)
    assert clipped_bands.shape == band_array.shape
    assert clipped_bands.shape[2] == 10

def test_clip_scl_shape_preserved():
    """Tests that clipped SCL array retains the input 2D shape."""
    band_array, scl_array = make_bands_and_scl(shape=(20, 20))
    tile_metadata = make_tile_metadata()
    conn = make_mock_connection()
    _, clipped_scl = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, 'E06000021', conn)
    assert clipped_scl.shape == scl_array.shape

def test_clip_small_boundary_reduces_valid_scl_count():
    """Tests that a boundary covering only part of the tile reduces the
    number of non-zero SCL pixels."""
    band_array, scl_array = make_bands_and_scl(shape=(100, 100))
    tile_metadata = make_tile_metadata()

    # Boundary partially overlapping the tile
    small_boundary = [[[500000, 5899000],
                       [500500, 5899000],
                       [500500, 5899500],
                       [500000, 5899500],
                       [500000, 5899000]]]
    conn = make_mock_connection(boundary_coords=small_boundary)

    _, clipped_scl = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, 'E06000021', conn)
    assert (clipped_scl != 0).sum() < (scl_array != 0).sum()

def test_clip_large_boundary_keeps_all_pixels():
    """Tests that a boundary covering the entire tile leaves both arrays
    unchanged."""
    band_array, scl_array = make_bands_and_scl(shape=(10, 10))
    tile_metadata = make_tile_metadata(left=0.0, top=10000.0, resolution=20)

    # Boundary much larger than the tile extent
    large_boundary = [[[-1000000, -1000000],
                       [1000000, -1000000],
                       [1000000, 1000000],
                       [-1000000, 1000000],
                       [-1000000, -1000000]]]
    conn = make_mock_connection(boundary_coords=large_boundary)

    clipped_bands, clipped_scl = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, 'E06000021', conn)
    assert np.array_equal(clipped_bands, band_array)
    assert np.array_equal(clipped_scl, scl_array)

def test_clip_boundary_outside_image_zeros_all_pixels():
    """Tests that a boundary entirely outside the tile zeros every pixel
    in both arrays."""
    band_array, scl_array = make_bands_and_scl(shape=(10, 10))
    tile_metadata = make_tile_metadata(left=0.0, top=200.0, resolution=20)

    # Boundary far outside the tile extent
    outside_boundary = [[[999000, 999000],
                         [999100, 999000],
                         [999100, 999100],
                         [999000, 999100],
                         [999000, 999000]]]
    conn = make_mock_connection(boundary_coords=outside_boundary)

    clipped_bands, clipped_scl = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, 'E06000021', conn)
    assert np.all(clipped_bands == 0)
    assert np.all(clipped_scl == 0)

def test_clip_invalid_gss_code_raises_value_error():
    """Tests that an invalid GSS code raises a ValueError."""
    band_array, scl_array = make_bands_and_scl()
    tile_metadata = make_tile_metadata()

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None

    with pytest.raises(ValueError):
        clip_to_council_boundary(band_array, scl_array,
                                 tile_metadata, 'INVALID', mock_conn)

def test_clip_null_boundary_raises_value_error():
    """Tests that a NULL boundary result raises a ValueError."""
    band_array, scl_array = make_bands_and_scl()
    tile_metadata = make_tile_metadata()

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [None]

    with pytest.raises(ValueError):
        clip_to_council_boundary(band_array, scl_array,
                                 tile_metadata, 'E06000021', mock_conn)

def test_clip_unsupported_geometry_raises_value_error():
    """Tests that an unsupported geometry type raises a ValueError."""
    band_array, scl_array = make_bands_and_scl()
    tile_metadata = make_tile_metadata()

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [json.dumps({
        'type': 'Point',
        'coordinates': [500000, 5880000]
    })]

    with pytest.raises(ValueError):
        clip_to_council_boundary(band_array, scl_array,
                                 tile_metadata, 'E06000021', mock_conn)

def test_clip_handles_multipolygon():
    """Tests that MultiPolygon boundaries are handled without error and
    return arrays of the expected shapes."""
    band_array, scl_array = make_bands_and_scl(shape=(10, 10))
    tile_metadata = make_tile_metadata()

    # MultiPolygon with two separate polygons within the tile extent
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

    clipped_bands, clipped_scl = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, 'E06000021', conn)
    assert clipped_bands.shape == band_array.shape
    assert clipped_scl.shape == scl_array.shape

def test_clip_inside_unchanged_outside_zeroed():
    """Tests that pixels inside the boundary retain their original band and
    SCL values while pixels outside are zeroed in both arrays.

    Uses a 10x10 tile at (left=0, top=200, resolution=20) so pixel (row, col)
    sits at UTM (col*20, 200 - row*20). The boundary is a rectangle from
    x=[-100, 75], y=[135, 210] which encloses exactly the top-left 4x4 block
    (rows 0-3, cols 0-3) — all other pixels fall outside.
    """
    band_array, scl_array = make_bands_and_scl(shape=(10, 10))
    tile_metadata = make_tile_metadata(left=0.0, top=200.0, resolution=20)

    # Rectangle enclosing exactly rows 0-3, cols 0-3
    corner_boundary = [[[-100, 135],
                        [75, 135],
                        [75, 210],
                        [-100, 210],
                        [-100, 135]]]
    conn = make_mock_connection(boundary_coords=corner_boundary)

    clipped_bands, clipped_scl = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, 'E06000021', conn)

    # Inside-boundary pixels unchanged
    assert np.array_equal(clipped_bands[:4, :4, :], band_array[:4, :4, :])
    assert np.array_equal(clipped_scl[:4, :4], scl_array[:4, :4])

    # Outside-boundary pixels zeroed across every band and in SCL
    assert np.all(clipped_bands[4:, :, :] == 0)
    assert np.all(clipped_bands[:, 4:, :] == 0)
    assert np.all(clipped_scl[4:, :] == 0)
    assert np.all(clipped_scl[:, 4:] == 0)