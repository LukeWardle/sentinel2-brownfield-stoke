"""
test_preprocess.py - Unit tests for preprocess.py
"""
import pytest
import numpy as np
from src.preprocess import (
    normalise_band_array,
    centre_data,
    compute_covariance,
    compute_bsi,
    compute_ndvi
)
from src.data_loading_satellite import bands_20m, bands_10m

# --- Shared fixtures ---
BANDS_20M = ['B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B11', 'B12']
BANDS_10M = ['B02', 'B03', 'B04', 'B08']

def make_band_array(pixels=100, bands=10):
    """Creates a realistic band array with values in Sentinel-2 DN range."""
    return np.random.randint(0, 10000, (pixels, bands)).astype(np.float64)

def make_normalised_array(pixels=100, bands=10):
    """Creates a normalised band array with values in 0-1 range."""
    return np.random.rand(pixels, bands).astype(np.float64)

# --- normalise_band_array tests ---
def test_normalise_band_array_returns_correct_shape():
    """Tests that normalise_band_array returns array with same shape."""
    band_array = make_band_array()
    result = normalise_band_array(band_array)
    assert result.shape == band_array.shape

def test_normalise_band_array_values_in_range():
    """Tests that normalised values are in 0-1 range for typical DN values."""
    band_array = np.full((100, 10), 5000.0)
    result = normalise_band_array(band_array)
    assert np.allclose(result, 0.5)

def test_normalise_band_array_zero_input():
    """Tests that zero DN values normalise to zero."""
    band_array = np.zeros((100, 10))
    result = normalise_band_array(band_array)
    assert np.all(result == 0.0)

def test_normalise_band_array_max_input():
    """Tests that DN value of 10000 normalises to 1.0."""
    band_array = np.full((100, 10), 10000.0)
    result = normalise_band_array(band_array)
    assert np.allclose(result, 1.0)

def test_normalise_band_array_returns_float():
    """Tests that output is float dtype."""
    band_array = make_band_array()
    result = normalise_band_array(band_array)
    assert np.issubdtype(result.dtype, np.floating)

def test_normalise_band_array_single_pixel():
    """Tests normalisation with a single pixel."""
    band_array = np.array([[10000.0] * 10])
    result = normalise_band_array(band_array)
    assert result.shape == (1, 10)
    assert np.allclose(result, 1.0)

def test_normalise_band_array_single_band():
    """Tests normalisation with a single band."""
    band_array = np.full((100, 1), 5000.0)
    result = normalise_band_array(band_array)
    assert result.shape == (100, 1)
    assert np.allclose(result, 0.5)

# --- centre_data tests ---
def test_centre_data_returns_correct_shape():
    """Tests that centre_data returns array with same shape."""
    band_array = make_normalised_array()
    result = centre_data(band_array)
    assert result.shape == band_array.shape

def test_centre_data_column_means_near_zero():
    """Tests that column means are approximately zero after centring."""
    band_array = make_normalised_array(1000, 10)
    result = centre_data(band_array)
    assert np.allclose(result.mean(axis=0), 0.0, atol=1e-10)

def test_centre_data_already_centred():
    """Tests that already centred data remains unchanged."""
    band_array = np.random.randn(100, 10)
    band_array -= band_array.mean(axis=0)
    result = centre_data(band_array)
    assert np.allclose(result.mean(axis=0), 0.0, atol=1e-10)

def test_centre_data_single_pixel():
    """Tests centring with a single pixel."""
    band_array = np.array([[1.0, 2.0, 3.0]])
    result = centre_data(band_array)
    assert result.shape == (1, 3)

def test_centre_data_preserves_variance():
    """Tests that centring does not change the variance of the data."""
    band_array = make_normalised_array(1000, 10)
    result = centre_data(band_array)
    assert np.allclose(band_array.std(axis=0), result.std(axis=0), atol=1e-10)

# --- compute_covariance tests ---
def test_compute_covariance_returns_square_matrix():
    """Tests that compute_covariance returns a square matrix."""
    centred = centre_data(make_normalised_array(100, 10))
    result = compute_covariance(centred)
    assert result.shape == (10, 10)

def test_compute_covariance_is_symmetric():
    """Tests that the covariance matrix is symmetric."""
    centred = centre_data(make_normalised_array(100, 10))
    result = compute_covariance(centred)
    assert np.allclose(result, result.T)

def test_compute_covariance_diagonal_non_negative():
    """Tests that diagonal elements (variances) are non-negative."""
    centred = centre_data(make_normalised_array(100, 10))
    result = compute_covariance(centred)
    assert np.all(np.diag(result) >= 0)

def test_compute_covariance_single_band():
    """Tests covariance with a single band returns 1x1 matrix."""
    centred = centre_data(make_normalised_array(100, 1))
    result = compute_covariance(centred)
    assert result.shape == (1, 1)

def test_compute_covariance_uncorrelated_data():
    """Tests that uncorrelated bands produce near-diagonal covariance matrix."""
    np.random.seed(42)
    centred = np.random.randn(10000, 5)
    result = compute_covariance(centred)
    off_diagonal = result - np.diag(np.diag(result))
    assert np.all(np.abs(off_diagonal) < 0.1)

# --- compute_bsi tests ---
def make_bsi_bands():
    """Creates a realistic normalised band array for BSI testing."""
    pixels = 100
    bands = len(bands_20m) + len(bands_10m)
    return np.random.rand(pixels, bands), bands_20m, bands_10m

def test_compute_bsi_returns_correct_shape():
    """Tests that compute_bsi returns a 1D array with one value per pixel."""
    band_array, bands_20m, bands_10m = make_bsi_bands()
    result = compute_bsi(band_array, bands_20m, bands_10m)
    assert result.shape == (band_array.shape[0],)

def test_compute_bsi_values_in_valid_range():
    """Tests that BSI values are in the valid -1 to 1 range."""
    band_array, bands_20m, bands_10m = make_bsi_bands()
    result = compute_bsi(band_array, bands_20m, bands_10m)
    assert np.all(result >= -1.0)
    assert np.all(result <= 1.0)

def test_compute_bsi_bare_soil_positive():
    """Tests that pixels with high SWIR and low NIR produce positive BSI."""
    pixels = 10
    band_array = np.zeros((pixels, len(bands_20m) + len(bands_10m)))
    b11_idx = bands_20m.index('B11')
    b04_idx = len(bands_20m) + bands_10m.index('B04')
    b08_idx = bands_20m.index('B08A') if 'B08A' in bands_20m else bands_20m.index('B8A')
    b02_idx = len(bands_20m) + bands_10m.index('B02')
    band_array[:, b11_idx] = 0.8
    band_array[:, b04_idx] = 0.6
    band_array[:, b08_idx] = 0.1
    band_array[:, b02_idx] = 0.1
    result = compute_bsi(band_array, bands_20m, bands_10m)
    assert np.all(result > 0)

def test_compute_bsi_returns_float():
    """Tests that BSI output is float dtype."""
    band_array, bands_20m, bands_10m = make_bsi_bands()
    result = compute_bsi(band_array, bands_20m, bands_10m)
    assert np.issubdtype(result.dtype, np.floating)

def test_compute_bsi_single_pixel():
    """Tests BSI computation with a single pixel."""
    band_array = np.random.rand(1, len(bands_20m) + len(bands_10m))
    result = compute_bsi(band_array, bands_20m, bands_10m)
    assert result.shape == (1,)

# --- compute_ndvi tests ---
def make_ndvi_bands():
    """Creates a realistic normalised band array for NDVI testing."""
    pixels = 100
    bands = len(bands_20m) + len(bands_10m)
    return np.random.rand(pixels, bands), bands_20m, bands_10m

def test_compute_ndvi_returns_correct_shape():
    """Tests that compute_ndvi returns a 1D array with one value per pixel."""
    band_array, bands_20m, bands_10m = make_ndvi_bands()
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    assert result.shape == (band_array.shape[0],)

def test_compute_ndvi_values_in_valid_range():
    """Tests that NDVI values are in the valid -1 to 1 range."""
    band_array, bands_20m, bands_10m = make_ndvi_bands()
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    assert np.all(result >= -1.0)
    assert np.all(result <= 1.0)

def test_compute_ndvi_vegetation_positive():
    """Tests that pixels with high NIR and low Red produce positive NDVI."""
    pixels = 10
    band_array = np.zeros((pixels, len(bands_20m) + len(bands_10m)))
    b08_idx = len(bands_20m) + bands_10m.index('B08')
    b04_idx = len(bands_20m) + bands_10m.index('B04')
    band_array[:, b08_idx] = 0.8
    band_array[:, b04_idx] = 0.1
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    assert np.all(result > 0)

def test_compute_ndvi_bare_soil_low():
    """Tests that pixels with equal NIR and Red produce NDVI near zero."""
    pixels = 10
    band_array = np.zeros((pixels, len(bands_20m) + len(bands_10m)))
    b08_idx = len(bands_20m) + bands_10m.index('B08')
    b04_idx = len(bands_20m) + bands_10m.index('B04')
    band_array[:, b08_idx] = 0.5
    band_array[:, b04_idx] = 0.5
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    assert np.allclose(result, 0.0, atol=1e-10)

def test_compute_ndvi_returns_float():
    """Tests that NDVI output is float dtype."""
    band_array, bands_20m, bands_10m = make_ndvi_bands()
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    assert np.issubdtype(result.dtype, np.floating)

def test_compute_ndvi_single_pixel():
    """Tests NDVI computation with a single pixel."""
    band_array = np.random.rand(1, len(bands_20m) + len(bands_10m))
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    assert result.shape == (1,)