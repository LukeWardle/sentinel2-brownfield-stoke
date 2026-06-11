"""
test_preprocess.py - Unit tests for preprocess.py

"""
import pytest
import numpy as np
from src.preprocess import centre_data, compute_covariance

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