"""
test_data.py - Unit tests for module data.py

"""
import pytest
import os
import numpy as np
import rasterio
from src.data import load_bands, load_scl, mask_nodata 
from src.data import _arrange_band_array
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
@pytest.fixture
def safe_path():
    safe_path = str(PROJECT_ROOT / "raw_data" / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE" / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE")
    return safe_path

# --- load_bands tests ---
def test_load_bands_missing_band_raises_valueerror(tmp_path):
    """
    Tests that load_bands raises ValueError when band files are missing.
    Creates a valid SAFE folder structure but with empty R20m and R10m folders.
    """
    # Create fake SAFE folder structure
    granule = tmp_path / "GRANULE" / "fake_granule" / "IMG_DATA"
    (granule / "R20m").mkdir(parents=True)
    (granule / "R10m").mkdir(parents=True)
    
    with pytest.raises(ValueError):
        load_bands(str(tmp_path))

def test_load_bands_invalid_path_raises_error():
    """
    Tests that load_bands raises FileNotFoundError for an invalid path.
    """
    with pytest.raises(FileNotFoundError):
        load_bands("/invalid/path/that/does/not/exist")

def test_load_bands_returns_valid_array(safe_path):
    """
    Tests that load_bands returns a valid 2D numpy array with correct
    shape (pixels, 10), dtype uint16 and at least one pixel.
    """
    # NOTE: This test is specific to Version 1 data — 10 bands, uint16, Sentinel-2 L2A
    # Will need updating in Version 2 when band selection or data source changes
    result = load_bands(safe_path)
    assert result.ndim == 2
    assert result.shape[1] == 10
    assert result.shape[0] > 0
    assert result.dtype == np.uint16

def test_load_bands_empty_granule_raises_valueerror(tmp_path):
    """
    Tests that load_bands raises ValueError when GRANULE folder is empty.
    """
    (tmp_path / "GRANULE").mkdir()
    with pytest.raises(ValueError):
        load_bands(str(tmp_path))

def test_load_bands_correct_data_arrangement(safe_path):
    """
    Tests that load_bands correctly arranges data so each row contains
    10 band readings for one pixel location — not one band across 10 locations.
    Verifies B05 (column 0) matches direct rasterio load of B05 band.
    """
    band_array = load_bands(safe_path)
    # Load B05 directly with rasterio for comparison
    granule = os.path.join(safe_path, "GRANULE")
    granule_name = os.listdir(granule)[0]
    r20m = os.path.join(granule, granule_name, "IMG_DATA", "R20m")
    b05_file = [f for f in os.listdir(r20m) if "_B05_" in f][0]
    with rasterio.open(os.path.join(r20m, b05_file)) as src:
        b05_direct = src.read(1).flatten()
    # B05 is first band loaded — should be column 0
    assert np.array_equal(band_array[:, 0], b05_direct)

# --- _arrange_band_array tests ---
def test_arrange_band_array_correct_data_arrangement():
    """
    Tests that _arrange_band_array correctly arranges bands so each row
    contains readings from one pixel location across all bands.
    Uses known small arrays to verify correctness without satellite data.
    """
    # Create 3 fake bands of shape (2, 2) with known values
    band1 = np.array([[1, 2], [3, 4]])
    band2 = np.array([[5, 6], [7, 8]])
    band3 = np.array([[9, 10], [11, 12]])
    
    result = _arrange_band_array([band1, band2, band3])
    
    # First pixel (top-left) should have readings [1, 5, 9]
    assert np.array_equal(result[0], [1, 5, 9])
    # Second pixel (top-right) should have readings [2, 6, 10]
    assert np.array_equal(result[1], [2, 6, 10])
    # Shape should be (4 pixels, 3 bands)
    assert result.shape == (4, 3)

# --- load_scl tests ---
def test_load_scl_returns_valid_array(safe_path):
    """
    Tests that load_scl returns a valid 2D numpy array with correct
    shape (5490, 5490), dtype uint8.
    """
    result = load_scl(safe_path)
    assert result.ndim == 2
    assert result.shape[1] == 5490
    assert result.shape[0] > 0
    assert result.dtype == np.uint8

def test_load_scl_invalid_path_raises_error():
    """
    Tests that load_scl raises FileNotFoundError for an invalid path.
    """
    with pytest.raises(FileNotFoundError):
        load_scl("/invalid/path/that/does/not/exist")

def test_load_scl_missing_scl_raises_valueerror(tmp_path):
    """
    Tests that load_scl raises ValueError when band files are missing.
    Creates a valid SAFE folder structure but with empty R20m folder.
    """
    # Create fake SAFE folder structure
    granule = tmp_path / "GRANULE" / "fake_granule" / "IMG_DATA"
    (granule / "R20m").mkdir(parents=True)

    with pytest.raises(ValueError):
        load_scl(str(tmp_path))

def test_load_scl_empty_granule_raises_valueerror(tmp_path):
    """
    Tests that load_scl raises ValueError when GRANULE folder is empty.
    """
    (tmp_path / "GRANULE").mkdir()
    with pytest.raises(ValueError):
        load_scl(str(tmp_path))

# --- mask_nodata tests ---
def test_mask_nodata_returns_unchanged_array_when_scl_is_none():
    """
    Tests if scl_array = 0, result is unchanged.
    """
    arr = np.ones((100, 10))
    result = mask_nodata(arr, scl_array = None)
    assert np.array_equal(result, arr)

def test_mask_nodata_removes_nodata_pixels():
    """
    Tests that mask_nodata removes pixels with value of 0
    """
    band_array = np.ones((9, 10))  # 9 pixels, 10 bands
    scl_array = np.array([0, 4, 4, 0, 4, 4, 4, 0, 4]).reshape(3, 3) # 3 nodata (0), 6 vegetation (4)
    result = mask_nodata(band_array, scl_array)
    assert result.shape[0] == 6  # only 6 valid pixels remain

def test_mask_nodata_returns_correct_shape():
    """
    Tests that mask_nodata returns correct shape after removing nodata pixels.
    """
    band_array = np.ones((9, 10))
    scl_array = np.array([0, 4, 4, 0, 4, 4, 4, 0, 4]).reshape(3, 3)
    result = mask_nodata(band_array, scl_array)
    assert result.ndim == 2
    assert result.shape[1] == 10
    assert result.shape[0] == 6