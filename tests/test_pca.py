"""
test_pca.py - Unit tests for pca.py
"""
import pytest
import numpy as np
from src.pca import spectral_decomposition, sort_variance, cumulative_variance_for_k, project

# --- Shared fixtures ---
def make_covariance_matrix(n_bands=10):
    """Creates a valid symmetric positive semi-definite covariance matrix."""
    A = np.random.rand(n_bands, n_bands)
    return A @ A.T

def make_sorted_eigenvalues(n=10):
    """Creates a sorted eigenvalue array in descending order."""
    vals = np.random.rand(n)
    return np.sort(vals)[::-1]

# --- spectral_decomposition tests ---
def test_spectral_decomposition_returns_tuple():
    """Tests that spectral_decomposition returns a tuple."""
    cov = make_covariance_matrix()
    result = spectral_decomposition(cov)
    assert isinstance(result, tuple)
    assert len(result) == 2

def test_spectral_decomposition_eigenvalues_shape():
    """Tests that eigenvalues array has correct shape."""
    cov = make_covariance_matrix(10)
    eigenvalues, _ = spectral_decomposition(cov)
    assert eigenvalues.shape == (10,)

def test_spectral_decomposition_eigenvectors_shape():
    """Tests that eigenvectors array has correct shape."""
    cov = make_covariance_matrix(10)
    _, eigenvectors = spectral_decomposition(cov)
    assert eigenvectors.shape == (10, 10)

def test_spectral_decomposition_eigenvalues_non_negative():
    """Tests that eigenvalues are non-negative for a valid covariance matrix."""
    cov = make_covariance_matrix()
    eigenvalues, _ = spectral_decomposition(cov)
    assert np.all(eigenvalues >= -1e-10)

def test_spectral_decomposition_eigenvectors_orthogonal():
    """Tests that eigenvectors are orthogonal (V^T V = I)."""
    cov = make_covariance_matrix()
    _, eigenvectors = spectral_decomposition(cov)
    product = eigenvectors.T @ eigenvectors
    assert np.allclose(product, np.eye(10), atol=1e-10)

def test_spectral_decomposition_single_band():
    """Tests decomposition with a single band covariance matrix."""
    cov = np.array([[4.0]])
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    assert eigenvalues.shape == (1,)
    assert eigenvectors.shape == (1, 1)

def test_spectral_decomposition_symmetric_input():
    """Tests that a symmetric matrix produces real eigenvalues."""
    cov = make_covariance_matrix()
    eigenvalues, _ = spectral_decomposition(cov)
    assert np.all(np.isreal(eigenvalues))

# --- sort_variance tests ---
def test_sort_variance_returns_tuple():
    """Tests that sort_variance returns a tuple of two arrays."""
    cov = make_covariance_matrix()
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    result = sort_variance(eigenvalues, eigenvectors)
    assert isinstance(result, tuple)
    assert len(result) == 2

def test_sort_variance_descending_order():
    """Tests that eigenvalues are sorted in descending order."""
    cov = make_covariance_matrix()
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    sorted_eigenvalues, _ = sort_variance(eigenvalues, eigenvectors)
    assert np.all(sorted_eigenvalues[:-1] >= sorted_eigenvalues[1:])

def test_sort_variance_preserves_eigenvalue_sum():
    """Tests that sorting preserves the total variance."""
    cov = make_covariance_matrix()
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    sorted_eigenvalues, _ = sort_variance(eigenvalues, eigenvectors)
    assert np.allclose(eigenvalues.sum(), sorted_eigenvalues.sum())

def test_sort_variance_already_sorted():
    """Tests that already sorted input remains unchanged."""
    eigenvalues = np.array([8.0, 4.0, 2.0, 1.0])
    eigenvectors = np.eye(4)
    sorted_eigenvalues, _ = sort_variance(eigenvalues, eigenvectors)
    assert np.allclose(sorted_eigenvalues, eigenvalues)

def test_sort_variance_eigenvectors_shape_preserved():
    """Tests that eigenvector shape is preserved after sorting."""
    cov = make_covariance_matrix(10)
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    _, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    assert sorted_eigenvectors.shape == (10, 10)

def test_sort_variance_single_component():
    """Tests sort_variance with a single eigenvalue."""
    eigenvalues = np.array([5.0])
    eigenvectors = np.array([[1.0]])
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    assert sorted_eigenvalues[0] == 5.0

# --- cumulative_variance_for_k tests ---
def test_cumulative_variance_for_k_returns_int():
    """Tests that cumulative_variance_for_k returns an integer."""
    sorted_eigenvalues = make_sorted_eigenvalues()
    result = cumulative_variance_for_k(sorted_eigenvalues)
    assert isinstance(result, (int, np.integer))

def test_cumulative_variance_for_k_minimum_one():
    """Tests that k is always at least 1."""
    sorted_eigenvalues = make_sorted_eigenvalues()
    result = cumulative_variance_for_k(sorted_eigenvalues)
    assert result >= 1

def test_cumulative_variance_for_k_maximum_n_bands():
    """Tests that k never exceeds the number of bands."""
    sorted_eigenvalues = make_sorted_eigenvalues(10)
    result = cumulative_variance_for_k(sorted_eigenvalues)
    assert result <= 10

def test_cumulative_variance_for_k_default_threshold_080():
    """Tests that default threshold of 0.80 is used."""
    sorted_eigenvalues = np.array([8.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.03, 0.01, 0.01])
    result = cumulative_variance_for_k(sorted_eigenvalues)
    total = sorted_eigenvalues.sum()
    cumulative = np.cumsum(sorted_eigenvalues)
    expected_k = int(np.searchsorted(cumulative, 0.80 * total)) + 1
    assert result == expected_k

def test_cumulative_variance_for_k_threshold_095():
    """Tests that a higher threshold requires more components."""
    sorted_eigenvalues = np.array([8.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.03, 0.01, 0.01])
    k_80 = cumulative_variance_for_k(sorted_eigenvalues, variance_threshold=0.80)
    k_95 = cumulative_variance_for_k(sorted_eigenvalues, variance_threshold=0.95)
    assert k_95 >= k_80

def test_cumulative_variance_for_k_threshold_100():
    """Tests that threshold of 1.0 requires all components."""
    sorted_eigenvalues = make_sorted_eigenvalues(10)
    result = cumulative_variance_for_k(sorted_eigenvalues, variance_threshold=1.0)
    assert result == 10

def test_cumulative_variance_for_k_first_component_dominant():
    """Tests that when first component explains 90%+ variance, k=1 at 0.80 threshold."""
    sorted_eigenvalues = np.array([9.0, 0.5, 0.3, 0.1, 0.05, 0.02, 0.01, 0.01, 0.005, 0.005])
    result = cumulative_variance_for_k(sorted_eigenvalues, variance_threshold=0.80)
    assert result == 1

# --- project tests ---
def test_project_returns_correct_shape():
    """Tests that project returns array with correct shape (pixels, k)."""
    centred = np.random.rand(100, 10)
    cov = compute_covariance_from_centred(centred)
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    k = 3
    result = project(centred, sorted_eigenvectors, k)
    assert result.shape == (100, k)

def test_project_k_equals_one():
    """Tests projection with k=1."""
    centred = np.random.rand(100, 10)
    cov = compute_covariance_from_centred(centred)
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    result = project(centred, sorted_eigenvectors, 1)
    assert result.shape == (100, 1)

def test_project_k_equals_n_bands():
    """Tests projection with k equal to number of bands."""
    centred = np.random.rand(100, 10)
    cov = compute_covariance_from_centred(centred)
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    result = project(centred, sorted_eigenvectors, 10)
    assert result.shape == (100, 10)

def test_project_returns_float():
    """Tests that projected values are float dtype."""
    centred = np.random.rand(100, 10)
    cov = compute_covariance_from_centred(centred)
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    result = project(centred, sorted_eigenvectors, 3)
    assert np.issubdtype(result.dtype, np.floating)

def test_project_single_pixel():
    """Tests projection with a single pixel."""
    centred = np.random.rand(1, 10)
    cov = compute_covariance_from_centred(np.random.rand(100, 10))
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    result = project(centred, sorted_eigenvectors, 3)
    assert result.shape == (1, 3)

def test_project_preserves_pixel_count():
    """Tests that projection preserves the number of pixels."""
    n_pixels = 500
    centred = np.random.rand(n_pixels, 10)
    cov = compute_covariance_from_centred(centred)
    eigenvalues, eigenvectors = spectral_decomposition(cov)
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    result = project(centred, sorted_eigenvectors, 5)
    assert result.shape[0] == n_pixels

def compute_covariance_from_centred(centred):
    """Helper to compute covariance from centred array."""
    from src.preprocess import compute_covariance
    return compute_covariance(centred)