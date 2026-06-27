"""
preprocess.py - Centre data and build covariance matrix
========================================================
Takes the band_array matrix and centres it around 0, removing brightness
differences in the centred_array output. The covariance matrix is produced
from the centred_array.

Also computes the Bare Soil Index (BSI) directly from band_array, using
bands_20m and bands_10m to locate the correct columns for B02, B04, B08
and B11.
"""

import numpy as np
from src.data import bands_20m, bands_10m

def centre_data(band_array: np.ndarray) -> np.ndarray:
    """
    Centres the band_array values around 0 by subtracting the column mean from each band.

    Args:
        band_array (np.ndarray): stacked array of the 10 band data.

    Returns:
        centred_array (np.ndarray): array containing values centred around 0.

    Raises:
        ValueError: If band_array is not 2D
        ValueError: If band_array contains no pixels.

    """
    if band_array.ndim != 2:
        raise ValueError(f"band_array must be 2D, got {band_array.ndim}D")
    if band_array.shape[0] == 0:
        raise ValueError("band_array contains no pixels")
    centred_array = band_array - np.mean(band_array, axis=0)
    return centred_array

def compute_covariance(centred_array: np.ndarray) -> np.ndarray:
    """
    Computes the covariance matrix using the formula $\\Sigma = (1/n)X^TX$.

    Args:
        centred_array (np.ndarray): array of centred band pixel values.

    Returns:
        covariance_matrix (np.ndarray): shape (10, 10)

    Raises:
        ValueError: If centred_array is not 2D
        ValueError: If centred_array contains no pixels.
    """
    if centred_array.ndim != 2:
        raise ValueError(f"centred_array must be 2D, got {centred_array.ndim}D")
    if centred_array.shape[0] == 0:
        raise ValueError("centred_array contains no pixels")
    covariance_matrix = (1/centred_array.shape[0]) * (centred_array.T @ centred_array)
    return covariance_matrix

def compute_bsi(band_array: np.ndarray, bands_20m: list, bands_10m: list) -> np.ndarray:
    """
    Computes Bare Soil Index using the formulation ((B11+B04)-(B08+B02))/((B11+B04)+(B08+B02))
    
    Args:
        band_array (np.ndarray): shape (pixels, n_bands)
        bands_20m (list): List of bands for 20m
        bands_10m (list): List of bands for 10m
    
    Returns:
        bsi_array (np.ndarray): An array containing the BSI values.
    """
    bands_list = bands_20m + bands_10m

    # Find column index for B11 and then extract its values from band_array.
    b11 = bands_list.index('B11')
    b11_values = band_array[:, b11]

    # Find column index for B04 and then extract its values from band_array.
    b04 = bands_list.index('B04')
    b04_values = band_array[:, b04]

    # Find column index for B08 and then extract its values from band_array.
    b08 = bands_list.index('B08')
    b08_values = band_array[:, b08]

    # Find column index for B02 and then extract its values from band_array.
    b02 = bands_list.index('B02')
    b02_values = band_array[:, b02]

    denominator = (b11_values + b04_values) + (b08_values + b02_values)
    numerator = (b11_values + b04_values) - (b08_values + b02_values)
    safe_denominator = np.where(denominator == 0, 1, denominator)
    bsi_array = np.where(denominator == 0, 0, numerator / safe_denominator)
    return bsi_array
