"""
pca.py - Spectral decomposition, choose k and project.
======================================================
Decomposes the covariance matrix to find the eigenvalues and eigenvectors.
Sorts the eigenvalues from largest to smallest, reorganising the eigenvectors to correspond with
eigenvalues. Find the k components for variance threshold and then projects centred data
onto the top k components - top 3 will be used for false colour map.
"""
import numpy as np

def spectral_decomposition(covariance_matrix: np.ndarray) -> tuple:
    """
    Decomposes covariance matrix using numpy.linalg.eigh, returns eigenvalues and eigenvectors.
    
    Args:
        covariance_matrix (np.ndarray): shape (10, 10)

    Returns:
        eigenvalues (np.ndarray): shape (10,)
        eigenvectors (np.ndarray): shape (10, 10)

    Raises:
        ValueError: If not a 2D array.
        ValueError: Covariance matrix not square, should be (10, 10).
        ValueError: If passed an empty array.
    """
    if covariance_matrix.ndim != 2:
        raise ValueError(f"covariance_matrix must be 2D, got {covariance_matrix.ndim}D")
    if covariance_matrix.shape[0] != covariance_matrix.shape[1]:
        raise ValueError(f"covariance_matrix must be square, got shape {covariance_matrix.shape}")
    if covariance_matrix.shape[0] == 0:
        raise ValueError("covariance_matrix is empty")
    eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
    return eigenvalues, eigenvectors

def sort_variance(eigenvalues: np.ndarray, eigenvectors: np.ndarray) -> tuple:
    """
    Orders eigenvalues largest to smallest - matches eigenvectors to order.
    
    Args:
        eigenvalues (np.ndarray): shape (10,)
        eigenvectors (np.ndarray): shape (10, 10)

    Returns:
        sorted_eigenvalues (np.ndarray): shape (10,)
        sorted_eigenvectors (np.ndarray): shape (10, 10)

    Raises:
        ValueError: If eigenvalues and eigenvectors length dont match.
        ValueError: If arrays are empty.
    """
    if len(eigenvalues) != eigenvectors.shape[1]:
        raise ValueError(" eigenvalues length doesnt match length of eigenvectors.")
    if eigenvalues.shape[0] == 0 or eigenvectors.shape[0] == 0:
        raise ValueError("eigenvalue or eigenvectors is empty") 
    sort_order = np.argsort(eigenvalues)[::-1]
    sorted_eigenvalues = eigenvalues[sort_order]
    sorted_eigenvectors = eigenvectors[:, sort_order]
    return sorted_eigenvalues, sorted_eigenvectors

def cumulative_variance_for_k(sorted_eigenvalues: np.ndarray,
                              variance_threshold: float=0.80) -> int:
    """
    Calculates the cumulative covariance, returns k components that reach 95% threshold.
    
    Args:
        sorted_eigenvalues (np.ndarray): shape (10,).
        variance_threshold (float): float = 0.95.

    Returns:
        k (int): Number of components needed to reach variance_threshold.

    Raises:
        ValueError: If an empty array is passed.
        ValueError: if the array is all zero.
        ValueError: if variance_threshold is out of range, should be between 0-1.
    """
    if sorted_eigenvalues.shape[0] == 0:
        raise ValueError("sorted_eigenvalues array is empty.")
    if np.all(sorted_eigenvalues == 0):
        raise ValueError("sorted_eigenvalues are all zero — cannot calculate variance")
    if not 0 < variance_threshold <= 1:
        raise ValueError(f"variance_threshold must be between 0 and 1, got {variance_threshold}")
    total_variance = np.sum(sorted_eigenvalues)
    cumulative_variance = np.cumsum(sorted_eigenvalues) / total_variance
    k = int(np.searchsorted(cumulative_variance, variance_threshold) + 1)
    return k

def project(centred_array: np.ndarray, eigenvectors: np.ndarray,
            k: int) -> np.ndarray:
    """
    projects centred data onto the top k eigenvectors.

    Args:
        centred_array (np.ndarray): shape (pixels, 10).
        eigenvectors (np.ndarray): shape (10, 10).
        k (int): Number of top eigenvectors to project onto.
    Returns:
        X_reduced (np.ndarray): shape (pixels, k)

    Raises:
        ValueError: If passed an empty centred_array
        ValueError: if k exceeds number of eigenvectors
        ValueError: If there is a shape mismatch between centred_array and eigenvector rows.
    """
    if centred_array.shape[0] == 0:
        raise ValueError("centred_array is empty.")
    if k > len(eigenvectors):
        raise ValueError("k exceeds the number of eigenvectors.")
    if centred_array.shape[1] != eigenvectors.shape[0]:
        raise ValueError("Mismatch shape between centred_array and eigenvectors.")
    X_reduced = centred_array @ eigenvectors[:, :k]
    return X_reduced