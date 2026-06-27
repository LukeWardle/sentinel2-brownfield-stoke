"""
test_scl_filtering.py - Unit tests for module scl_filtering.py

"""
import numpy as np
from src.scl_filtering import mask_nodata

# --- mask_nodata tests ---
def test_mask_nodata_returns_unchanged_array_when_scl_is_none():
    """
    Tests that when scl_array is None, band_array is returned unchanged,
    and mask and original_shape are both None.
    """
    arr = np.ones((100, 10))
    result, mask, original_shape = mask_nodata(arr, scl_array = None)
    assert np.array_equal(result, arr)
    assert mask is None
    assert original_shape is None

def test_mask_nodata_removes_nodata_pixels():
    """
    Tests that mask_nodata removes pixels with value of 0, and correctly
    returns the mask and original_shape alongside the filtered array.
    """
    band_array = np.ones((9, 10))  # 9 pixels, 10 bands
    scl_array = np.array([0, 4, 4, 0, 4, 4, 4, 0, 4]).reshape(3, 3) # 3 nodata (0), 6 vegetation (4)
    result, mask, original_shape = mask_nodata(band_array, scl_array)
    assert result.shape[0] == 6  # only 6 valid pixels remain
    assert mask.sum() == 6
    assert original_shape == (3, 3)

def test_mask_nodata_returns_correct_shape():
    """
    Tests that mask_nodata returns correct shape after removing nodata pixels.
    """
    band_array = np.ones((9, 10))
    scl_array = np.array([0, 4, 4, 0, 4, 4, 4, 0, 4]).reshape(3, 3)
    result, mask, original_shape = mask_nodata(band_array, scl_array)
    assert result.ndim == 2
    assert result.shape[1] == 10
    assert result.shape[0] == 6