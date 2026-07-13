"""
test_scl_filtering.py - Unit tests for module scl_filtering.py

"""
import numpy as np
from src.scl_filtering import mask_nodata

# --- mask_nodata tests ---
def test_mask_nodata_removes_nodata_pixels():
    """
    Tests that mask_nodata drops pixels with SCL class 0 and returns the
    expected pixel count, mask sum and original grid shape.
    """
    band_array = np.ones((3, 3, 10))  # 3x3 grid, 10 bands
    scl_array = np.array(
        [[0, 4, 4], [0, 4, 4], [4, 0, 4]], dtype=np.uint8
    )  # 3 nodata (class 0), 6 vegetation (class 4)
    result, mask, original_shape = mask_nodata(band_array, scl_array)
    assert result.shape[0] == 6
    assert mask.sum() == 6
    assert original_shape == (3, 3)

def test_mask_nodata_returns_correct_output_shapes():
    """
    Tests that mask_nodata returns a 2D flat masked array with the correct
    band count, a 1D boolean mask covering every pixel in the input grid,
    and the original 2D grid shape as a tuple.
    """
    band_array = np.ones((3, 3, 10))
    scl_array = np.array(
        [[0, 4, 4], [0, 4, 4], [4, 0, 4]], dtype=np.uint8
    )
    result, mask, original_shape = mask_nodata(band_array, scl_array)
    assert result.ndim == 2
    assert result.shape[1] == 10
    assert mask.ndim == 1
    assert mask.shape[0] == 3 * 3
    assert isinstance(original_shape, tuple)
    assert original_shape == (3, 3)

def test_mask_nodata_flat_output_preserves_pixel_band_correspondence():
    """
    Tests that the 3D-to-flat reshape preserves pixel-band correspondence
    in row-major order. Each pixel in the 2x2 test grid carries unique
    band values so any ordering bug in the reshape or masking would show
    as mismatched rows.
    """
    band_array = np.array([
        [[1, 2, 3], [4, 5, 6]],       # row 0: pixel (0,0)=[1,2,3], pixel (0,1)=[4,5,6]
        [[7, 8, 9], [10, 11, 12]]     # row 1: pixel (1,0)=[7,8,9], pixel (1,1)=[10,11,12]
    ])
    scl_array = np.array([[4, 0], [4, 4]], dtype=np.uint8)  # drop pixel (0,1)
    result, _, _ = mask_nodata(band_array, scl_array)
    expected = np.array([[1, 2, 3], [7, 8, 9], [10, 11, 12]])
    assert np.array_equal(result, expected)

def test_mask_nodata_drops_scl_class_1():
    """
    Tests that SCL class 1 (defective/saturated) is dropped alongside
    class 0 (nodata).
    """
    band_array = np.ones((2, 2, 10))
    scl_array = np.array([[4, 1], [0, 4]], dtype=np.uint8)  # 2 valid, 1 defective, 1 nodata
    result, mask, _ = mask_nodata(band_array, scl_array)
    assert result.shape[0] == 2
    assert mask.sum() == 2

def test_mask_nodata_all_valid_returns_all_pixels():
    """
    Tests that when every SCL pixel is valid, the flat masked output
    equals the flattened band array with no rows dropped.
    """
    band_array = np.arange(2 * 2 * 10).reshape(2, 2, 10)
    scl_array = np.full((2, 2), 4, dtype=np.uint8)
    result, mask, _ = mask_nodata(band_array, scl_array)
    assert result.shape[0] == 4
    assert mask.sum() == 4
    assert np.array_equal(result, band_array.reshape(4, 10))

def test_mask_nodata_all_scl_zero_returns_empty():
    """
    Tests that when every SCL pixel is class 0 — as happens when the whole
    tile is outside the council boundary — the masked output is empty. This
    scenario is indistinguishable to mask_nodata from a genuinely all-nodata
    image, which is the intended behaviour.
    """
    band_array = np.ones((2, 2, 10))
    scl_array = np.zeros((2, 2), dtype=np.uint8)
    result, mask, original_shape = mask_nodata(band_array, scl_array)
    assert result.shape[0] == 0
    assert mask.sum() == 0
    assert original_shape == (2, 2)