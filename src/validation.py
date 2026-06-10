"""
validation.py - All quality checks
=====================================
Validates SAFE folder containing Sentinel-2 L2A exists, checks data and cloud coverage returning bool values.

"""

import os
import numpy as np

def validate_path(safe_path: str) -> str:
    """
    validate_path - Validates SAFE folder exists, raises FileNotFound if not

    Args:
        safe_path(str): File path string

    Returns:
        safe_path(str): File path string 
    
    Raises:
        ValueError: If path does not end with .SAFE
        FileNotFoundError: if safe_path does not exist 
    """
    if not safe_path.endswith(".SAFE"):
        raise ValueError(f"Path does not appear to be a SAFE folder: {safe_path}")
    if not os.path.exists(safe_path):
        raise FileNotFoundError(f"SAFE folder not found: {safe_path}")
    return safe_path

def validate_bands(band_array: np.ndarray) -> bool:
    """
    validate_bands - Validates data - checks array is 2D, shape, no negative value,
                                      no corrupt rows, raises ValueError if invalid.

    Args:
        band_array(np.ndarray): shape (pixels, 10) - stacked array of 10 bands at 20m resolution.
    
    Returns:
        bool: True if all checks pass.

    Raises:
        ValueError: If array is not 2D
        ValueError: If array does not have 10 columns
        ValueError: If array contains negative values
        ValueError: If array contains all-zero rows
    """
    if band_array.ndim != 2:
        raise ValueError(f"band_array must be 2D, got {band_array.ndim}D")
    if band_array.shape[1] != 10:
        raise ValueError(f"band_array must have 10 columns, got {band_array.shape[1]} columns")
    if np.any(band_array < 0):
        raise ValueError("band_array contains negative values")
    if np.any(np.all(band_array == 0, axis=1)):
        raise ValueError("band_array contains all-zero rows — possible corrupt data")
    return True

def validate_quality(scl_array: np.ndarray, cloud_threshold: float = 0.10) -> bool:
    """
    validate_quality - Checks cloud coverage doesnt exceed threshold, raises ValueError
                       if quality is insufficient.

    Args:
        scl_array(np.ndarray): Shape (5490, 5490), value ranges 0-11.
        cloud_threshold(float): Maximum acceptable cloud coverage as a proportion. Default 0.10 (10%).
    
    Returns:
        bool: True if all checks pass.

    Raises:
        ValueError: If SCL array contains no valid pixels.
        ValueError: If cloud coverage exceeds threshold.
    """
    cloud_pixels = np.sum((scl_array == 8) | (scl_array == 9) | (scl_array == 10))
    valid_pixels = np.sum(scl_array != 0)
    if valid_pixels == 0:
        raise ValueError("SCL array contains no valid pixels — image may be entirely nodata")
    cloud_coverage = cloud_pixels / valid_pixels
    if cloud_coverage > cloud_threshold:
        raise ValueError(f"Cloud coverage {cloud_coverage:.2%} exceeds threshold {cloud_threshold:.2%}")
    return True