"""
test_visualise.py - Unit tests for module visualise.py
"""
import pytest
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
from src.visualise import convert_k_to_rgb, false_map_creation, report_creation, create_interactive_map


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

# --- false_map_creation tests ---
def test_false_map_creation_creates_file(tmp_path):
    """
    Tests that false_map_creation creates a PNG file in output_dir
    with a filename starting with false_colour_map_.
    """
    rgb_array = np.array([
        [255, 0, 0],
        [0, 255, 0],
        [0, 0, 255],
        [255, 255, 255],
    ], dtype=np.uint8)
    false_map_creation(rgb_array, str(tmp_path))

    files = os.listdir(tmp_path)
    matching = [f for f in files if f.startswith("false_colour_map_") and f.endswith(".png")]
    assert len(matching) == 1
    assert len(matching) == 1


def test_false_map_creation_reconstructs_correct_shape_with_mask(tmp_path):
    """
    Tests that false_map_creation correctly reconstructs a 2x2 original image
    from 3 valid pixels using mask and original_shape, placing the masked-out
    pixel back as black (0,0,0) in its correct position.
    """
    rgb_array = np.array([
        [255, 0, 0],
        [0, 255, 0],
        [0, 0, 255],
    ], dtype=np.uint8)
    # Original was 2x2 = 4 pixels. Pixel index 1 (top-right) was masked out.
    mask = np.array([True, False, True, True])
    original_shape = (2, 2)

    false_map_creation(rgb_array, str(tmp_path), mask, original_shape)

    files = os.listdir(tmp_path)
    matching = [f for f in files if f.startswith("false_colour_map_") and f.endswith(".png")]
    assert len(matching) == 1


def test_false_map_creation_falls_back_to_square_when_mask_none(tmp_path):
    """
    Tests that false_map_creation falls back to square reshape logic
    when mask and original_shape are None — e.g. when scl_array was
    never provided to mask_nodata.
    """
    rgb_array = np.ones((9, 3), dtype=np.uint8)  # 9 pixels = 3x3 square
    false_map_creation(rgb_array, str(tmp_path), mask=None, original_shape=None)

    files = os.listdir(tmp_path)
    matching = [f for f in files if f.startswith("false_colour_map_") and f.endswith(".png")]
    assert len(matching) == 1


def test_false_map_creation_raises_valueerror_for_wrong_columns():
    """
    Tests that false_map_creation raises ValueError when rgb_array
    does not have exactly 3 columns.
    """
    rgb_array = np.ones((10, 2), dtype=np.uint8)
    with pytest.raises(ValueError):
        false_map_creation(rgb_array, "some/dir")


def test_false_map_creation_raises_filenotfounderror_for_missing_dir():
    """
    Tests that false_map_creation raises FileNotFoundError when
    output_dir does not exist.
    """
    rgb_array = np.ones((9, 3), dtype=np.uint8)
    with pytest.raises(FileNotFoundError):
        false_map_creation(rgb_array, "/nonexistent/output/dir")

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

# --- create_interactive_map tests ---
def test_create_interactive_map_creates_file(tmp_path):
    """Tests that create_interactive_map creates an HTML file in the output directory."""
    candidate_sites = [
        {
            'centroid_utm_x': 555331.19,
            'centroid_utm_y': 5871939.23,
            'pixel_count': 100,
            'mean_bsi': 0.15,
            'matched_site_reference': 'SITE001'
        },
        {
            'centroid_utm_x': 556000.00,
            'centroid_utm_y': 5872000.00,
            'pixel_count': 50,
            'mean_bsi': 0.08,
            'matched_site_reference': None
        }
    ]
    create_interactive_map(candidate_sites, str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert len(html_files) == 1


def test_create_interactive_map_file_is_html(tmp_path):
    """Tests that the output file is valid HTML containing Folium map content."""
    candidate_sites = [
        {
            'centroid_utm_x': 555331.19,
            'centroid_utm_y': 5871939.23,
            'pixel_count': 100,
            'mean_bsi': 0.15,
            'matched_site_reference': None
        }
    ]
    create_interactive_map(candidate_sites, str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    content = html_files[0].read_text()
    assert 'leaflet' in content.lower()


def test_create_interactive_map_empty_sites_no_file(tmp_path):
    """Tests that empty candidate_sites produces no output file."""
    create_interactive_map([], str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert len(html_files) == 0


def test_create_interactive_map_filename_contains_gss_code(tmp_path):
    """Tests that the output filename contains the GSS code."""
    candidate_sites = [
        {
            'centroid_utm_x': 555331.19,
            'centroid_utm_y': 5871939.23,
            'pixel_count': 100,
            'mean_bsi': 0.15,
            'matched_site_reference': None
        }
    ]
    create_interactive_map(candidate_sites, str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert 'E06000021' in html_files[0].name

