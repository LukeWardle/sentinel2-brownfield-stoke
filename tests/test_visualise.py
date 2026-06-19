"""
test_visualise.py - Unit tests for module visualise.py
"""
import pytest
import numpy as np
import os
from src.visualise import convert_k_to_rgb, false_map_creation, report_creation


# --- convert_k_to_rgb tests ---
def test_convert_k_to_rgb_returns_correct_shape_and_range():
    """
    Tests that convert_k_to_rgb returns shape (pixels, 3) with values
    normalised correctly into the 0-255 range using a known example.
    """
    X_reduced = np.array([
        [0.0, 10.0, 100.0],
        [5.0, 20.0, 150.0],
        [10.0, 30.0, 200.0],
    ])
    result = convert_k_to_rgb(X_reduced)
    assert result.shape == (3, 3)
    assert result.dtype == np.uint8
    assert result.min() >= 0
    assert result.max() <= 255
    # First column min (0.0) should map to 0, max (10.0) should map to 255
    assert result[0, 0] == 0
    assert result[2, 0] == 255


def test_convert_k_to_rgb_uses_only_first_three_columns():
    """
    Tests that convert_k_to_rgb only uses the first 3 columns when
    X_reduced has more than 3 components.
    """
    X_reduced = np.tile(np.arange(10).reshape(-1, 1), (1, 5)).astype(float)
    result = convert_k_to_rgb(X_reduced)
    assert result.shape == (10, 3)

def test_convert_k_to_rgb_raises_valueerror_for_zero_variance_column():
    """
    Tests that convert_k_to_rgb raises ValueError when a component
    has zero variance (all identical values), which would otherwise
    cause a division by zero during normalisation.
    """
    X_reduced = np.ones((10, 3))
    with pytest.raises(ValueError):
        convert_k_to_rgb(X_reduced)


def test_convert_k_to_rgb_raises_valueerror_for_empty_array():
    """
    Tests that convert_k_to_rgb raises ValueError when X_reduced is empty.
    """
    X_reduced = np.empty((0, 3))
    with pytest.raises(ValueError):
        convert_k_to_rgb(X_reduced)


def test_convert_k_to_rgb_raises_valueerror_for_fewer_than_3_columns():
    """
    Tests that convert_k_to_rgb raises ValueError when X_reduced has
    fewer than 3 components.
    """
    X_reduced = np.ones((10, 2))
    with pytest.raises(ValueError):
        convert_k_to_rgb(X_reduced)


# --- report_creation tests ---
def test_report_creation_creates_file(tmp_path):
    """
    Tests that report_creation creates a markdown file in output_dir
    with a filename starting with results_report_.
    """
    sorted_eigenvalues = np.array([6.0, 3.0, 1.0])
    k = 2
    report_creation(k, sorted_eigenvalues, str(tmp_path))

    files = os.listdir(tmp_path)
    matching = [f for f in files if f.startswith("results_report_") and f.endswith(".md")]
    assert len(matching) == 1


def test_report_creation_contains_correct_variance_explained(tmp_path):
    """
    Tests that report_creation writes the correct variance explained
    percentage into the report content, using a known example.
    [6, 3, 1] with k=2: variance explained = (6+3)/10 = 90.00%
    """
    sorted_eigenvalues = np.array([6.0, 3.0, 1.0])
    k = 2
    report_creation(k, sorted_eigenvalues, str(tmp_path))

    files = os.listdir(tmp_path)
    filepath = os.path.join(tmp_path, files[0])
    with open(filepath) as f:
        content = f.read()

    assert "90.00%" in content
    assert "PC1: 60.00%" in content
    assert "PC2: 30.00%" in content
    assert "PC3: 10.00%" in content


def test_report_creation_raises_filenotfounderror_for_missing_dir():
    """
    Tests that report_creation raises FileNotFoundError when output_dir
    does not exist.
    """
    sorted_eigenvalues = np.array([6.0, 3.0, 1.0])
    with pytest.raises(FileNotFoundError):
        report_creation(2, sorted_eigenvalues, "/nonexistent/output/dir")


# --- false_map_creation tests ---
# NOTE: false_map_creation has a known bug — it assumes pixel count forms
# a perfect square when reshaping, which is false once mask_nodata removes
# pixels. Tests deferred until reshape logic is fixed using actual image
# dimensions passed through the pipeline. See session log for details.