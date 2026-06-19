"""
preprocess.py - Centre data and build covariance matrix
========================================================
Takes the band_array matrix and centres it around 0, removing brightness differences 
in the centred_array output. The covariance matrix is produced from the centred_array.
"""

import numpy as np

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