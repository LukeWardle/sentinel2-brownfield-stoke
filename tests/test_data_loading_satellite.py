"""
test_data_loading_satellite.py - Unit tests for module data_loading_satellite.py

"""

import os
from pathlib import Path

import numpy as np
import pytest
import rasterio

from src.data_loading_satellite import _arrange_band_array, load_bands, load_scl

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def safe_path():
    safe_path = str(
        PROJECT_ROOT
        / "raw_data"
        / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE"
        / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE"
    )
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
    Tests that load_bands returns a valid 3D numpy array with correct
    shape (height, width, 10), dtype uint16 and non-empty spatial dims.
    """
    # NOTE: This test is specific to Version 2 data — 10 bands, uint16, Sentinel-2 L2A
    # on the 20m grid. 3D shape is preserved so AOI clipping can operate on the raw
    # spatial arrays before mask_nodata flattens them.
    result = load_bands(safe_path)
    assert result.ndim == 3
    assert result.shape[2] == 10
    assert result.shape[0] > 0
    assert result.shape[1] > 0
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
    Tests that load_bands correctly arranges data so band_array[row, col, band]
    holds the reading for one pixel and one band — not scrambled across the grid.
    Verifies B05 (band index 0) matches a direct rasterio load of the B05 file.
    """
    band_array = load_bands(safe_path)
    # Load B05 directly with rasterio for comparison
    granule = os.path.join(safe_path, "GRANULE")
    granule_name = os.listdir(granule)[0]
    r20m = os.path.join(granule, granule_name, "IMG_DATA", "R20m")
    b05_file = [f for f in os.listdir(r20m) if "_B05_" in f][0]
    with rasterio.open(os.path.join(r20m, b05_file)) as src:
        b05_direct = src.read(1)
    # B05 is first band loaded — should be at band index 0 across the full 2D grid
    assert np.array_equal(band_array[:, :, 0], b05_direct)


# --- _arrange_band_array tests ---
def test_arrange_band_array_correct_data_arrangement():
    """
    Tests that _arrange_band_array correctly arranges bands so
    result[row, col, :] contains readings from that pixel across all bands.
    Uses known small arrays to verify correctness without satellite data.
    """
    # Create 3 fake bands of shape (2, 2) with known values
    band1 = np.array([[1, 2], [3, 4]])
    band2 = np.array([[5, 6], [7, 8]])
    band3 = np.array([[9, 10], [11, 12]])

    result = _arrange_band_array([band1, band2, band3])

    # Shape should be (height=2, width=2, n_bands=3)
    assert result.shape == (2, 2, 3)
    # Top-left pixel (row 0, col 0) should have readings [1, 5, 9]
    assert np.array_equal(result[0, 0], [1, 5, 9])
    # Top-right pixel (row 0, col 1) should have readings [2, 6, 10]
    assert np.array_equal(result[0, 1], [2, 6, 10])


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
