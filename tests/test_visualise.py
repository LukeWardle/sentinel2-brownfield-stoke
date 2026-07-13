"""
test_visualise.py - Unit tests for visualise.py
"""
import pytest
import numpy as np
import os
from pathlib import Path
from src.visualise import convert_k_to_rgb, false_map_creation, report_creation, create_interactive_map

# --- Shared fixtures ---
def make_sorted_eigenvalues():
    return np.array([8.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.03, 0.01, 0.01])

def make_candidate_sites(n=3):
    sites = []
    for i in range(n):
        sites.append({
            'centroid_utm_x': 555331.19 + (i * 100),
            'centroid_utm_y': 5871939.23 + (i * 100),
            'pixel_count': 100 + (i * 10),
            'hectares': round((100 + (i * 10)) * 0.04, 2),
            'mean_bsi': 0.10 + (i * 0.05),
            'matched_site_reference': 'SITE001' if i == 0 else None
        })
    return sites

def make_change_detection():
    return {
        'added': [{'site_reference': 'NEW001', 'name_address': 'New Site, Hanley'}],
        'removed': [{'site_reference': 'OLD001', 'name_address': 'Old Site, Burslem'}]
    }

# --- convert_k_to_rgb tests ---
def test_convert_k_to_rgb_returns_correct_shape():
    """Tests that convert_k_to_rgb returns shape (pixels, 3)."""
    X_reduced = np.random.rand(100, 5)
    result = convert_k_to_rgb(X_reduced)
    assert result.shape == (100, 3)

def test_convert_k_to_rgb_values_in_range():
    """Tests that all output values are in range 0-255."""
    X_reduced = np.random.rand(100, 5)
    result = convert_k_to_rgb(X_reduced)
    assert result.min() >= 0
    assert result.max() <= 255

def test_convert_k_to_rgb_dtype_is_uint8():
    """Tests that output dtype is uint8."""
    X_reduced = np.random.rand(100, 5)
    result = convert_k_to_rgb(X_reduced)
    assert result.dtype == np.uint8

def test_convert_k_to_rgb_raises_for_fewer_than_3_components():
    """Tests that fewer than 3 components raises ValueError."""
    X_reduced = np.random.rand(100, 2)
    with pytest.raises(ValueError):
        convert_k_to_rgb(X_reduced)

def test_convert_k_to_rgb_raises_for_empty_array():
    """Tests that an empty array raises ValueError."""
    X_reduced = np.zeros((0, 5))
    with pytest.raises(ValueError):
        convert_k_to_rgb(X_reduced)

def test_convert_k_to_rgb_raises_for_zero_variance_component():
    """Tests that a component with zero variance raises ValueError."""
    X_reduced = np.random.rand(100, 3)
    X_reduced[:, 0] = 1.0
    with pytest.raises(ValueError):
        convert_k_to_rgb(X_reduced)

def test_convert_k_to_rgb_exactly_3_components():
    """Tests that exactly 3 components works correctly."""
    X_reduced = np.random.rand(100, 3)
    X_reduced[:, 0] += 1.0
    result = convert_k_to_rgb(X_reduced)
    assert result.shape == (100, 3)

def test_convert_k_to_rgb_many_components():
    """Tests that more than 3 components uses only the first 3."""
    X_reduced = np.random.rand(100, 10)
    result = convert_k_to_rgb(X_reduced)
    assert result.shape == (100, 3)

def test_convert_k_to_rgb_single_pixel():
    """Tests that a single pixel raises ValueError due to zero variance."""
    X_reduced = np.random.rand(1, 5)
    with pytest.raises(ValueError):
        convert_k_to_rgb(X_reduced)

def test_convert_k_to_rgb_large_array():
    """Tests that a large array is handled correctly."""
    X_reduced = np.random.rand(10000, 5)
    result = convert_k_to_rgb(X_reduced)
    assert result.shape == (10000, 3)

# --- false_map_creation tests ---
def test_false_map_creation_creates_file(tmp_path):
    """Tests that false_map_creation creates a PNG file."""
    rgb_array = np.random.randint(0, 255, (10000, 3), dtype=np.uint8)
    false_map_creation(rgb_array, str(tmp_path))
    png_files = list(tmp_path.glob('false_colour_map_*.png'))
    assert len(png_files) == 1

def test_false_map_creation_file_is_png(tmp_path):
    """Tests that the output file is a valid PNG."""
    rgb_array = np.random.randint(0, 255, (10000, 3), dtype=np.uint8)
    false_map_creation(rgb_array, str(tmp_path))
    png_files = list(tmp_path.glob('false_colour_map_*.png'))
    content = png_files[0].read_bytes()
    assert content[:4] == b'\x89PNG'

def test_false_map_creation_with_mask(tmp_path):
    """Tests that false_map_creation works correctly with mask and original_shape."""
    original_shape = (100, 100)
    mask = np.ones(10000, dtype=bool)
    mask[:1000] = False
    n_valid = mask.sum()
    rgb_array = np.random.randint(0, 255, (n_valid, 3), dtype=np.uint8)
    false_map_creation(rgb_array, str(tmp_path), mask=mask, original_shape=original_shape)
    png_files = list(tmp_path.glob('false_colour_map_*.png'))
    assert len(png_files) == 1

def test_false_map_creation_filename_contains_timestamp(tmp_path):
    """Tests that the filename contains a timestamp."""
    rgb_array = np.random.randint(0, 255, (10000, 3), dtype=np.uint8)
    false_map_creation(rgb_array, str(tmp_path))
    png_files = list(tmp_path.glob('false_colour_map_*.png'))
    assert 'false_colour_map_' in png_files[0].name

def test_false_map_creation_without_mask(tmp_path):
    """Tests that false_map_creation works without mask using square fallback."""
    rgb_array = np.random.randint(0, 255, (10000, 3), dtype=np.uint8)
    false_map_creation(rgb_array, str(tmp_path), mask=None, original_shape=None)
    png_files = list(tmp_path.glob('false_colour_map_*.png'))
    assert len(png_files) == 1

def test_false_map_creation_non_square_pixel_count(tmp_path):
    """Tests false_map_creation with non-square pixel count falls back correctly."""
    rgb_array = np.random.randint(0, 255, (9999, 3), dtype=np.uint8)
    false_map_creation(rgb_array, str(tmp_path))
    png_files = list(tmp_path.glob('false_colour_map_*.png'))
    assert len(png_files) == 1

# --- report_creation tests ---
def test_report_creation_creates_pdf_file(tmp_path):
    """Tests that report_creation creates a PDF file."""
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        make_candidate_sites(), make_change_detection()
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    assert len(pdf_files) == 1

def test_report_creation_file_is_valid_pdf(tmp_path):
    """Tests that the output file is a valid PDF."""
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        make_candidate_sites(), make_change_detection()
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    content = pdf_files[0].read_bytes()
    assert content[:4] == b'%PDF'

def test_report_creation_raises_for_none_candidate_sites(tmp_path):
    """Tests that None candidate_sites raises ValueError."""
    with pytest.raises(ValueError):
        report_creation(
            2, make_sorted_eigenvalues(), str(tmp_path),
            'E06000021', '2026-05-25',
            None, make_change_detection()
        )

def test_report_creation_raises_for_invalid_change_detection(tmp_path):
    """Tests that invalid change_detection dict raises ValueError."""
    with pytest.raises(ValueError):
        report_creation(
            2, make_sorted_eigenvalues(), str(tmp_path),
            'E06000021', '2026-05-25',
            make_candidate_sites(), {'wrong_key': []}
        )

def test_report_creation_raises_for_missing_added_key(tmp_path):
    """Tests that change_detection missing added key raises ValueError."""
    with pytest.raises(ValueError):
        report_creation(
            2, make_sorted_eigenvalues(), str(tmp_path),
            'E06000021', '2026-05-25',
            make_candidate_sites(), {'removed': []}
        )

def test_report_creation_raises_for_missing_removed_key(tmp_path):
    """Tests that change_detection missing removed key raises ValueError."""
    with pytest.raises(ValueError):
        report_creation(
            2, make_sorted_eigenvalues(), str(tmp_path),
            'E06000021', '2026-05-25',
            make_candidate_sites(), {'added': []}
        )

def test_report_creation_empty_candidate_sites(tmp_path):
    """Tests that empty candidate_sites produces a valid PDF."""
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        [], make_change_detection()
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    assert len(pdf_files) == 1

def test_report_creation_empty_change_detection(tmp_path):
    """Tests that empty added and removed lists produces a valid PDF."""
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        make_candidate_sites(), {'added': [], 'removed': []}
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    assert len(pdf_files) == 1

def test_report_creation_filename_contains_timestamp(tmp_path):
    """Tests that the PDF filename contains a timestamp."""
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        make_candidate_sites(), make_change_detection()
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    assert 'results_report_' in pdf_files[0].name

def test_report_creation_many_candidate_sites(tmp_path):
    """Tests that more than 20 candidate sites produces a valid PDF."""
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        make_candidate_sites(25), make_change_detection()
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    assert len(pdf_files) == 1

def test_report_creation_all_matched_sites(tmp_path):
    """Tests PDF generation when all candidate sites are register-matched."""
    sites = make_candidate_sites(3)
    for site in sites:
        site['matched_site_reference'] = 'SITE001'
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        sites, {'added': [], 'removed': []}
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    assert len(pdf_files) == 1

def test_report_creation_all_unmatched_sites(tmp_path):
    """Tests PDF generation when all candidate sites are unregistered."""
    sites = make_candidate_sites(3)
    for site in sites:
        site['matched_site_reference'] = None
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        sites, {'added': [], 'removed': []}
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    assert len(pdf_files) == 1

def test_report_creation_large_change_detection(tmp_path):
    """Tests PDF generation with more than 10 sites in change detection."""
    change_detection = {
        'added': [{'site_reference': f'NEW{i:03d}', 'name_address': f'New Site {i}'} for i in range(20)],
        'removed': [{'site_reference': f'OLD{i:03d}', 'name_address': f'Old Site {i}'} for i in range(15)]
    }
    report_creation(
        2, make_sorted_eigenvalues(), str(tmp_path),
        'E06000021', '2026-05-25',
        make_candidate_sites(), change_detection
    )
    pdf_files = list(tmp_path.glob('results_report_*.pdf'))
    assert len(pdf_files) == 1

# --- create_interactive_map tests ---
def test_create_interactive_map_creates_file(tmp_path):
    """Tests that create_interactive_map creates an HTML file."""
    create_interactive_map(make_candidate_sites(), str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert len(html_files) == 1

def test_create_interactive_map_file_is_html(tmp_path):
    """Tests that the output file contains Folium map content."""
    create_interactive_map(make_candidate_sites(), str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    content = html_files[0].read_text(encoding='utf-8')
    assert 'leaflet' in content.lower()

def test_create_interactive_map_empty_sites_no_file(tmp_path):
    """Tests that empty candidate_sites produces no output file."""
    create_interactive_map([], str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert len(html_files) == 0

def test_create_interactive_map_filename_contains_gss_code(tmp_path):
    """Tests that the output filename contains the GSS code."""
    create_interactive_map(make_candidate_sites(), str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert 'E06000021' in html_files[0].name

def test_create_interactive_map_filename_contains_timestamp(tmp_path):
    """Tests that the output filename contains a timestamp."""
    create_interactive_map(make_candidate_sites(), str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert 'interactive_map_' in html_files[0].name

def test_create_interactive_map_single_site(tmp_path):
    """Tests that a single candidate site produces a valid map."""
    create_interactive_map(make_candidate_sites(1), str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert len(html_files) == 1

def test_create_interactive_map_all_matched(tmp_path):
    """Tests map generation when all sites are register-matched."""
    sites = make_candidate_sites(3)
    for site in sites:
        site['matched_site_reference'] = 'SITE001'
    create_interactive_map(sites, str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert len(html_files) == 1

def test_create_interactive_map_all_unmatched(tmp_path):
    """Tests map generation when all sites are unregistered."""
    sites = make_candidate_sites(3)
    for site in sites:
        site['matched_site_reference'] = None
    create_interactive_map(sites, str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert len(html_files) == 1

def test_create_interactive_map_contains_legend(tmp_path):
    """Tests that the map contains the SiteSignal legend."""
    create_interactive_map(make_candidate_sites(), str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    content = html_files[0].read_text(encoding='utf-8')
    assert 'SiteSignal' in content

def test_create_interactive_map_contains_gss_code_in_content(tmp_path):
    """Tests that the map HTML contains the GSS code."""
    create_interactive_map(make_candidate_sites(), str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    content = html_files[0].read_text(encoding='utf-8')
    assert 'E06000021' in content

def test_create_interactive_map_large_number_of_sites(tmp_path):
    """Tests map generation with a large number of candidate sites."""
    sites = make_candidate_sites(50)
    create_interactive_map(sites, str(tmp_path), 'E06000021')
    html_files = list(tmp_path.glob('interactive_map_*.html'))
    assert len(html_files) == 1