"""
test_preprocess.py - Unit tests for preprocess.py

"""
import pytest
import numpy as np
from src.preprocess import centre_data, compute_covariance, compute_bsi, compute_ndvi

# --- centre_data tests ---
def test_centre_data_means_zero_after_centring():
    """
    Tests that column means are zero after centring.
    """
    arr = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    result = centre_data(arr)
    assert np.allclose(np.mean(result, axis=0), 0)

def test_centre_data_returns_correct_shape():
    """
    Tests that centre_data returns the array correct shape.
    """
    arr = np.ones((100, 10))
    result = centre_data(arr)
    assert result.shape == arr.shape

def test_centre_data_raises_valueerror_1d_array():
    """
    Tests centre_data raises a ValueError when passed a 1D array.
    """
    arr = np.ones((100,))
    with pytest.raises(ValueError):
        centre_data(arr)

def test_centre_data_raises_valueerror_for_empty_array():
    """
    Tests centre_data raises a ValueError when passed an empty array.
    """
    arr = np.empty((0, 10))
    with pytest.raises(ValueError):
        centre_data(arr)

def test_centre_data_correct_values():
    """
    Tests that centre_data returns correct values using a known input array.
    Columns means [3.0, 5.0] are subtracted
    expected result [[-2, -2], [0, 0], [2, 2]].
    """
    arr = np.array([[1.0, 3.0], [3.0, 5.0], [5.0, 7.0]])
    expected = np.array([[-2.0, -2.0], [0.0, 0.0], [2.0, 2.0]])
    result = centre_data(arr)
    assert np.allclose(result, expected)

def test_centre_data_returns_float():
    """
    Tests that centre_data returns a float array when given uint16 input - 
    band_array from load_bands is uint16 and centring require float arithmetic.
    """
    arr = np.ones((100, 10), dtype=np.uint16)
    result = centre_data(arr)
    assert result.dtype == np.float64

# --- compute_covariance tests ---
def test_compute_covariance_return_correct_shape():
    """
    Tests that compute_covariance returns the array correct shape.
    """
    arr = np.ones((100, 10))
    result = compute_covariance(arr)
    assert result.shape == (10, 10)

def test_compute_covariance_raises_valueerror_1d_array():
    """
    Tests compute_covariance raises a ValueError when passed a 1D array.
    """
    arr = np.ones((100,))
    with pytest.raises(ValueError):
        compute_covariance(arr)

def test_compute_covariance_valueerror_for_empty_array():
    """
    Tests compute_covariance raises a ValueError when passed an empty array.
    """
    arr = np.empty((0, 10))
    with pytest.raises(ValueError):
        compute_covariance(arr)

def test_compute_covariance_correct_values():
    """
    Tests that compute_covariance returns correct values using a known input array.
    Expected covariance: (1/2) * arr.T @ arr
    """
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    expected = (1/2) * arr.T @ arr
    result = compute_covariance(arr)
    assert np.allclose(result, expected)

# --- compute_bsi tests ---
def test_compute_bsi_correct_values():
    """
    Tests that compute_bsi correctly calculates BSI using known band values,
    matching the formula ((B11+B04)-(B08+B02))/((B11+B04)+(B08+B02)).
    """
    bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
    bands_10m = ["B02", "B03", "B04", "B08"]
    band_array = np.zeros((2, 10))
    bands_list = bands_20m + bands_10m
    band_array[:, bands_list.index('B11')] = [10, 20]
    band_array[:, bands_list.index('B04')] = [10, 20]
    band_array[:, bands_list.index('B08')] = [5, 5]
    band_array[:, bands_list.index('B02')] = [5, 5]
    result = compute_bsi(band_array, bands_20m, bands_10m)
    expected = np.array([10/30, 30/50])
    assert np.allclose(result, expected)

def test_compute_bsi_zero_denominator_returns_zero():
    """
    Tests that compute_bsi returns 0 for a pixel where the denominator
    would be zero, instead of raising a division error or returning inf/nan.
    """
    bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
    bands_10m = ["B02", "B03", "B04", "B08"]
    band_array = np.zeros((1, 10))
    result = compute_bsi(band_array, bands_20m, bands_10m)
    assert result[0] == 0

def test_compute_bsi_correct_shape():
    """
    Tests that compute_bsi returns a 1D array with one BSI value per pixel.
    """
    bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
    bands_10m = ["B02", "B03", "B04", "B08"]
    band_array = np.ones((50, 10))
    result = compute_bsi(band_array, bands_20m, bands_10m)
    assert result.shape == (50,)

# --- compute_ndvi tests ---
def test_compute_ndvi_correct_values():
    """
    Tests that compute_ndvi correctly calculates NDVI using known band values,
    matching the formula ((B08-B04)/(B08+B04)).
    """
    bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
    bands_10m = ["B02", "B03", "B04", "B08"]
    band_array = np.zeros((2, 10))
    bands_list = bands_20m + bands_10m
    band_array[:, bands_list.index('B08')] = [10, 8]
    band_array[:, bands_list.index('B04')] = [5, 3]
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    expected = np.array([5/15, 5/11])
    assert np.allclose(result, expected)

def test_compute_ndvi_zero_denominator_returns_zero():
    """
    Tests that compute_ndvi returns 0 for a pixel where the denominator
    would be zero, instead of raising a division error or returning inf/nan.
    """
    bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
    bands_10m = ["B02", "B03", "B04", "B08"]
    band_array = np.zeros((1, 10))
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    assert result[0] == 0

def test_compute_ndvi_correct_shape():
    """
    Tests that compute_bsi returns a 1D array with one BSI value per pixel.
    """
    bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
    bands_10m = ["B02", "B03", "B04", "B08"]
    band_array = np.ones((50, 10))
    result = compute_ndvi(band_array, bands_20m, bands_10m)
    assert result.shape == (50,)