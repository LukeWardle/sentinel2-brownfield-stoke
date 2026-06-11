"""
test_validation.py - Unit tests for module validation.py

"""

import pytest
import os
import numpy as np
from src.validation import validate_path, validate_bands, validate_quality
from pathlib import Path

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


# --- validate_path tests ---
def test_validate_path_valid_safe_path(safe_path):
    """
    Tests that validate_path returns the path unchanged when given a valid SAFE folder path.
    """
    result = validate_path(safe_path)
    assert result == safe_path


def test_validate_path_end_with_safe():
    """
    Tests that validate_path raises ValueError when path does not end with .SAFE.
    """
    with pytest.raises(ValueError):
        validate_path("/some/path/that/does/not/end/with/safe")


def test_validate_path_ends_with_safe_but_missing():
    """
    Tests that validate_path raises FileNotFoundError when path ends with .SAFE but folder does not exist.
    """
    with pytest.raises(FileNotFoundError):
        validate_path("/nonexistent/folder.SAFE")


# --- validate_bands ---
def test_validate_bands_valid_array():
    """
    Tests that validate_bands returns True if valid array.
    """
    arr = np.ones((100, 10))
    result = validate_bands(arr)
    assert result == True


def test_validate_bands_1D_array():
    """
    Tests that validate_bands raises ValueError when array dimension != 2.
    """
    arr = np.ones((100,))
    with pytest.raises(ValueError):
        validate_bands(arr)


def test_validate_bands_wrong_column_count():
    """
    Test that validate_bands raises ValueError if array column count != 10
    """
    arr = np.ones((100, 5))
    with pytest.raises(ValueError):
        validate_bands(arr)


def test_validate_bands_negative_values():
    """
    Tests that validate_bands raises ValueError when array has negative values.
    """
    arr = np.ones((100, 10)) * -1
    with pytest.raises(ValueError):
        validate_bands(arr)


def test_validate_bands_all_zero_rows():
    """
    Tests that validate_bands raises ValueError is array has all zero rows.
    """
    arr = np.ones((100, 10))
    arr[0] = 0
    with pytest.raises(ValueError):
        validate_bands(arr)


# --- validate_quality ---
def test_validate_quality_valid_scl_low_cloud():
    """
    Tests that validate_quality returns valid array with low cloud.
    """
    scl = np.full((10, 10), 4, dtype=np.uint8)  # all vegetation (value 4), no cloud
    result = validate_quality(scl)
    assert result == True


def test_validate_quality_cloud_coverage_exceeds_threshold():
    """
    Test that validate_quality raises a ValueError when threshold is exceeded.
    """
    scl = np.full((10, 10), 4, dtype=np.uint8)
    scl[:, :5] = 9  # half the pixels are cloud (50% — exceeds 10% threshold)
    with pytest.raises(ValueError):
        validate_quality(scl)


def test_validate_quality_scl_all_zero_array():
    """
    Tests that validate_quality raises a ValueError is the array is all-zero.
    """
    scl = np.zeros((10, 10), dtype=np.uint8)  # all nodata
    with pytest.raises(ValueError):
        validate_quality(scl)
