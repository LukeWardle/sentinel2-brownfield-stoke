"""
test_pca.py - Unit tests for module pca.py
"""
import pytest
import numpy as np 
from src.pca import spectral_decomposition, sort_variance, cumulative_variance_for_k, project

# --- spectral_decomposition tests ---
def test_spectral_decomposition_returns_valid_eigenvalues_and_eigenvectors():
    """
    Tests that spectral_decomposition returns valid eigenvalues and eigenvectors.
    """
    covariance_matrix = np.array([[4.0, 2.0], [2.0, 3.0]])
    eigenvalues, eigenvectors = spectral_decomposition(covariance_matrix)
    assert eigenvalues.shape == (2,)
    assert eigenvectors.shape == (2, 2)
    assert np.all(np.isreal(eigenvalues))
    assert eigenvalues.dtype == np.float64
    assert eigenvectors.dtype == np.float64

def test_spectral_decomposition_non_sq_matrix():
    """
    Tests that a ValueError is raised for non-squared matrix.
    """
    covariance_matrix = np.ones((3, 5))
    with pytest.raises(ValueError):
        spectral_decomposition(covariance_matrix)

def test_spectral_decomposition_non_2d_array():
    """
    Tests that a ValueError is raised for non-2D arrays.
    """
    covariance_matrix = np.ones((10,))
    with pytest.raises(ValueError):
        spectral_decomposition(covariance_matrix)

def test_spectral_decomposition_empty_matrix():
    """
    Tests that a ValueError is raised for empty matrix.
    """
    covariance_matrix = np.empty((0, 0))
    with pytest.raises(ValueError):
        spectral_decomposition(covariance_matrix)

# --- sort_variance tests ---
def test_sort_variance_sorted_eigen_match():
    """
    Tests that eigenvalues, and eigenvectors match after sorting.
    """
    eigenvalues = np.array([3.0, 8.0, 1.0])
    eigenvectors = np.array([
        [0, 1, 2],
        [0, 1, 2],
        [0, 1, 2]
    ])
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    assert np.array_equal(sorted_eigenvalues, [8.0, 3.0, 1.0])
    assert np.array_equal(sorted_eigenvectors[0], [1, 0, 2])

def test_sort_variance_length_mismatch():
    """
    Tests that a ValueError is raised if theres a length mismatch between
    eigenvalues and eigenvectors.
    """
    eigenvalues = np.array([1.0, 2.0, 3.0])
    eigenvectors = np.array([
        [0, 1],
        [0, 1]
    ])
    with pytest.raises(ValueError):
        sort_variance(eigenvalues, eigenvectors)

def test_sort_variance_empty_array():
    """
    Tests that a ValueError is raised if sort_variance is given an empty array.
    """
    eigenvalues = np.empty((0, 0))
    eigenvectors = np.empty((0, 0))
    with pytest.raises(ValueError):
        sort_variance(eigenvalues, eigenvectors)

def test_sort_variance_handles_negative_eigenvalues():
    """
    Tests that sort_variance correctly sorts and matches eigenvalues when eigenvalues
    contain small negative values from floating point precision errors.
    """
    eigenvalues = np.array([5.0, -0.0001, 2.0])
    eigenvectors = np.array([
        [0, 1, 2],
        [0, 1, 2],
        [0, 1, 2]
    ])
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    assert np.array_equal(sorted_eigenvalues, [5.0, 2.0, -0.0001])
    assert np.array_equal(sorted_eigenvectors[0], [0, 2, 1])

def test_sort_variance_all_equal_eigenvalues():
    """
    Tests that sort_variance does not crash when all eigenvalues are equal.
    Order is not deterministic when values tie, only checks values are preserved.
    """
    eigenvalues = np.array([4.0, 4.0, 4.0])
    eigenvectors = np.array([
        [0, 1, 2],
        [0, 1, 2],
        [0, 1, 2]
    ])
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    assert np.array_equal(sorted_eigenvalues, eigenvalues)

# --- cumulative_variance_for_k tests ---
def test_cumulative_variance_for_k_correct_k():
    """
    Tests that cumulative_variance_for_k returns correct k using known eigenvalues.
    [6, 3, 1, 0] with 0.95 threshold: cumulative [0.6, 0.9, 1.0, 1.0] - reaches threshold at index 2, k=3.
    """
    eigenvalues = np.array([6.0, 3.0, 1.0, 0.0])
    result = cumulative_variance_for_k(eigenvalues, variance_threshold=0.95)
    assert result == 3

def test_cumulative_variance_for_k_empty_array():
    """
    Tests that ValueError is raised when cumulative_variance_for_k
    is given an empty array.
    """
    eigenvalues = np.empty((0, 0))
    with pytest.raises(ValueError):
        cumulative_variance_for_k(eigenvalues)

def test_cumulative_variance_for_k_all_zero_array():
    """
    Test that a ValueError is raised when given a all eigenvalues are zero.
    """
    eigenvalues = np.zeros(10)
    with pytest.raises(ValueError):
        cumulative_variance_for_k(eigenvalues)

def test_cumulative_variance_for_k_out_of_range_threshold():
    """
    Tests that a ValueError is raised when cumulative_variance_for_k
    is given a threshold out of range.
    """
    eigenvalues = np.array([1, 2, 3])
    threshold = 5.0
    with pytest.raises(ValueError):
        cumulative_variance_for_k(eigenvalues, threshold)

def test_cumulative_variance_for_k_threshold_at_boundary():
    """
    Tests that cumulative_variance_for_k handles threshold of exactly 1.0 correctly,
    requiring all components to reach 100% variance.
    """
    eigenvalues = np.array([6.0, 3.0, 1.0])
    result = cumulative_variance_for_k(eigenvalues, variance_threshold=1.0)
    assert result == 3

# --- project tests ---
def test_project_returns_correct_shape_and_values():
    """
    Tests that project returns correct shape and values using a known small example.
    Uses identity-like eigenvectors with k=2 to confirm only the first k columns
    are used, even through 3 eigenvectors are available.
    """
    centred_array = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    eigenvectors = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ])
    k = 2
    result = project(centred_array, eigenvectors, k)
    expected = np.array([[1.0, 2.0], [4.0, 5.0]])
    assert result.shape == (2, 2)
    assert np.array_equal(result, expected)

def test_project_empty_array_input():
    """
    Tests that a ValueError is raised if centred_array is empty.
    """
    centred_array = np.empty((0, 10))
    eigenvectors = np.ones((10, 10))
    with pytest.raises(ValueError):
        project(centred_array, eigenvectors, 3)

def test_project_k_exceeds_eigenvector_length():
    """
    Tests that a ValueError is raised if k exceeds the number of eigenvectors.
    """
    centred_array = np.ones([10, 2])
    eigenvectors = np.ones([2, 2])
    k = 5
    with pytest.raises(ValueError):
        project(centred_array, eigenvectors, k)

def test_project_shape_alignment_centred_array_eigenvectors():
    """
    Tests that a ValueError is raised if centred_array and eigenvectors shape are 
    mismatched.
    """
    centred_array = np.array([[1.0, 2.0], [4.0, 5.0]])
    eigenvectors = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ])
    k = 2
    with pytest.raises(ValueError):
        project(centred_array, eigenvectors, k)
    