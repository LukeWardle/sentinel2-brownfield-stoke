"""
test_main.py - Unit tests for module main.py
"""
import pytest
import os
import rasterio
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from src.main import run_pipeline

PROJECT_ROOT = Path(__file__).parent.parent

# --- Fixtures ---
@pytest.fixture
def valid_gss_code():
    return 'E06000021'

@pytest.fixture
def valid_date():
    return '2026-05-25'

@pytest.fixture
def mock_data():
    """Creates all mock data needed for pipeline tests."""
    n_valid = 800
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [1]
    mock_rasterio_src = MagicMock()
    mock_rasterio_src.__enter__ = MagicMock(return_value=mock_rasterio_src)
    mock_rasterio_src.__exit__ = MagicMock(return_value=False)
    mock_rasterio_src.bounds.left = 499980.0
    mock_rasterio_src.bounds.top = 5900040.0

    return {
        'token': 'test_token',
        'product': {
            'product_id': 'test-id',
            'product_name': 'S2C_TEST',
            'cloud_cover': 5.0,
            'sensing_date': '2026-05-25T11:06:21Z'
        },
        'safe_path': '/tmp/test.SAFE',
        'band_array': np.random.rand(1000, 10).astype(np.float32),
        'scl_array': np.ones((32, 32), dtype=np.uint8) * 4,
        'mask': np.ones(1000, dtype=bool),
        'masked_array': np.random.rand(n_valid, 10).astype(np.float32),
        'original_shape': (32, 32),
        'normalised': np.random.rand(n_valid, 10).astype(np.float32),
        'bsi': np.random.uniform(-0.5, 0.5, n_valid),
        'ndvi': np.random.uniform(-0.5, 0.5, n_valid),
        'centred': np.random.rand(n_valid, 10).astype(np.float32),
        'covariance': np.eye(10),
        'eigenvalues': np.array([8.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.03, 0.01, 0.01]),
        'eigenvectors': np.eye(10),
        'X_reduced': np.random.rand(n_valid, 3),
        'candidate_groups': {0: list(range(50)), 1: list(range(50, 100))},
        'site_properties': [
            {
                'site_id': 0, 'pixel_count': 50, 'hectares': 2.0,
                'mean_bsi': 0.15, 'centroid_utm_x': 555331.19,
                'centroid_utm_y': 5871939.23, 'matched_site_reference': 'SITE001'
            },
            {
                'site_id': 1, 'pixel_count': 50, 'hectares': 2.0,
                'mean_bsi': 0.08, 'centroid_utm_x': 556000.00,
                'centroid_utm_y': 5872000.00, 'matched_site_reference': None
            }
        ],
        'polygons': [{'site_id': 0, 'boundary': []}, {'site_id': 1, 'boundary': []}],
        'rgb': np.random.randint(0, 255, (n_valid, 3), dtype=np.uint8),
        'change_detection': {
            'added': [{'site_reference': 'NEW001', 'name_address': 'New Site'}],
            'removed': [{'site_reference': 'OLD001', 'name_address': 'Old Site'}]
        },
        'tile_metadata': {'left': 499980.0, 'top': 5900040.0, 'resolution': 20},
        'conn': mock_conn,
        'rasterio_src': mock_rasterio_src,
            }

def get_patches(mock_data, safe_path='/tmp/test.SAFE'):
    """Returns a dict of all patches needed for run_pipeline tests."""
    return {
        'src.main.get_access_token': MagicMock(return_value=mock_data['token']),
        'src.main.search_products': MagicMock(return_value=[mock_data['product']]),
        'src.main.download_safe': MagicMock(return_value=safe_path),
        'src.main.get_db_connection': MagicMock(return_value=mock_data['conn']),
        'src.main.validate_council_boundary_gss': MagicMock(return_value=True),
        'src.main.validate_path': MagicMock(return_value=None),
        'src.main.load_bands': MagicMock(return_value=mock_data['band_array']),
        'src.main.load_scl': MagicMock(return_value=mock_data['scl_array']),
        'src.main.mask_nodata': MagicMock(return_value=(mock_data['masked_array'], mock_data['mask'], mock_data['original_shape'])),
        'src.main.validate_bands': MagicMock(return_value=None),
        'src.main.validate_quality': MagicMock(return_value=None),
        'src.main.get_tile_metadata': MagicMock(return_value=mock_data['tile_metadata']),
        'src.main.clip_to_council_boundary': MagicMock(return_value=(mock_data['masked_array'], mock_data['mask'])),
        'src.main.normalise_band_array': MagicMock(return_value=mock_data['normalised']),
        'src.main.compute_bsi': MagicMock(return_value=mock_data['bsi']),
        'src.main.compute_ndvi': MagicMock(return_value=mock_data['ndvi']),
        'src.main.centre_data': MagicMock(return_value=mock_data['centred']),
        'src.main.compute_covariance': MagicMock(return_value=mock_data['covariance']),
        'src.main.spectral_decomposition': MagicMock(return_value=(mock_data['eigenvalues'], mock_data['eigenvectors'])),
        'src.main.sort_variance': MagicMock(return_value=(mock_data['eigenvalues'], mock_data['eigenvectors'])),
        'src.main.cumulative_variance_for_k': MagicMock(return_value=3),
        'src.main.project': MagicMock(return_value=mock_data['X_reduced']),
        'src.main.group_pixels_for_candidate_sites': MagicMock(return_value=mock_data['candidate_groups']),
        'src.main.calculate_site_properties': MagicMock(return_value=mock_data['site_properties']),
        'src.main.generate_boundary_polygons': MagicMock(return_value=mock_data['polygons']),
        'src.main.match_candidate_to_register': MagicMock(return_value=None),
        'src.main.store_candidate_sites_validation': MagicMock(return_value=True),
        'src.main.store_candidate_sites': MagicMock(return_value=None),
        'src.main.detect_register_changes': MagicMock(return_value=mock_data['change_detection']),
        'src.main.store_pipeline_metadata_validation': MagicMock(return_value=True),
        'src.main.store_pipeline_metadata': MagicMock(return_value=None),
        'src.main.convert_k_to_rgb': MagicMock(return_value=mock_data['rgb']),
        'src.main.false_map_creation': MagicMock(return_value=None),
        'src.main.report_creation': MagicMock(return_value=None),
        'src.main.create_interactive_map': MagicMock(return_value=None),
        'src.main.shutil.rmtree': MagicMock(return_value=None),
        'src.main.os.path.exists': MagicMock(return_value=True),
    }

def run_with_mocks(gss_code, date, output_dir, mock_data, overrides=None):
    """Runs run_pipeline with all standard mocks applied, with optional overrides."""
    patches = get_patches(mock_data)
    if overrides:
        patches.update(overrides)

    patchers = {k: patch(k, v) for k, v in patches.items()}
    started = {k: p.start() for k, p in patchers.items()}

    try:
        run_pipeline(gss_code, date, output_dir)
    finally:
        for p in patchers.values():
            p.stop()

    return started

# --- run_pipeline tests ---
def test_run_pipeline_creates_output_dir_if_missing(tmp_path, mock_data):
    """Tests that run_pipeline creates output_dir if it does not exist."""
    new_output_dir = str(tmp_path / "does_not_exist_yet")
    assert not os.path.exists(new_output_dir)
    run_with_mocks('E06000021', '2026-05-25', new_output_dir, mock_data)
    assert os.path.exists(new_output_dir)

def test_run_pipeline_raises_for_invalid_gss_code(tmp_path, mock_data):
    """Tests that an invalid GSS code raises ValueError."""
    with pytest.raises(ValueError):
        run_with_mocks('INVALID', '2026-05-25', str(tmp_path), mock_data, overrides={
            'src.main.validate_council_boundary_gss': MagicMock(side_effect=ValueError("Invalid GSS code"))
        })

def test_run_pipeline_raises_for_no_products_found(tmp_path, mock_data):
    """Tests that ValueError is raised when no Copernicus products are found."""
    with pytest.raises(ValueError):
        run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data, overrides={
            'src.main.search_products': MagicMock(side_effect=ValueError("No products found"))
        })

def test_run_pipeline_raises_for_failed_download(tmp_path, mock_data):
    """Tests that ValueError is raised when SAFE file download fails."""
    with pytest.raises(ValueError):
        run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data, overrides={
            'src.main.download_safe': MagicMock(side_effect=ValueError("Download failed"))
        })

def test_run_pipeline_raises_for_band_validation_failure(tmp_path, mock_data):
    """Tests that ValueError is raised when band validation fails."""
    with pytest.raises(ValueError):
        run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data, overrides={
            'src.main.validate_bands': MagicMock(side_effect=ValueError("Band validation failed"))
        })

def test_run_pipeline_raises_for_quality_validation_failure(tmp_path, mock_data):
    """Tests that ValueError is raised when quality validation fails."""
    with pytest.raises(ValueError):
        run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data, overrides={
            'src.main.validate_quality': MagicMock(side_effect=ValueError("Cloud cover too high"))
        })

def test_run_pipeline_stores_failure_status_on_error(tmp_path, mock_data):
    """Tests that pipeline metadata is stored with failure status when pipeline fails."""
    mock_store = MagicMock()
    with pytest.raises(ValueError):
        run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data, overrides={
            'src.main.search_products': MagicMock(side_effect=ValueError("No products")),
            'src.main.store_pipeline_metadata': mock_store
        })
    mock_store.assert_called_once()
    assert mock_store.call_args[0][3] == 'failure'

def test_run_pipeline_closes_db_connection_on_failure(tmp_path, mock_data):
    """Tests that database connection is closed even when pipeline fails."""
    with pytest.raises(ValueError):
        run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data, overrides={
            'src.main.validate_council_boundary_gss': MagicMock(side_effect=ValueError("Invalid"))
        })
    mock_data['conn'].close.assert_called_once()

def test_run_pipeline_deletes_safe_file_after_processing(tmp_path, mock_data):
    """Tests that the SAFE file is deleted after pipeline completes."""
    mock_rmtree = MagicMock()
    run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data, overrides={
        'src.main.shutil.rmtree': mock_rmtree,
        'src.main.os.path.exists': MagicMock(return_value=True)
    })
    mock_rmtree.assert_called_once()

def test_run_pipeline_calls_copernicus_api(tmp_path, mock_data):
    """Tests that the Copernicus API is called to download the SAFE file."""
    mocks = run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data)
    mocks['src.main.get_access_token'].assert_called_once()
    mocks['src.main.search_products'].assert_called_once()
    mocks['src.main.download_safe'].assert_called_once()

def test_run_pipeline_calls_aoi_clipping(tmp_path, mock_data):
    """Tests that AOI clipping is called during pipeline execution."""
    mocks = run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data)
    mocks['src.main.clip_to_council_boundary'].assert_called_once()

def test_run_pipeline_calls_bsi_and_ndvi(tmp_path, mock_data):
    """Tests that BSI and NDVI are computed during pipeline execution."""
    mocks = run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data)
    mocks['src.main.compute_bsi'].assert_called_once()
    mocks['src.main.compute_ndvi'].assert_called_once()

def test_run_pipeline_calls_clustering(tmp_path, mock_data):
    """Tests that clustering is called during pipeline execution."""
    mocks = run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data)
    mocks['src.main.group_pixels_for_candidate_sites'].assert_called_once()

def test_run_pipeline_calls_register_matching(tmp_path, mock_data):
    """Tests that register matching is called for each candidate site."""
    mocks = run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data)
    assert mocks['src.main.match_candidate_to_register'].call_count == len(mock_data['site_properties'])

def test_run_pipeline_calls_store_candidate_sites(tmp_path, mock_data):
    """Tests that candidate sites are stored in the database."""
    mocks = run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data)
    mocks['src.main.store_candidate_sites'].assert_called_once()

def test_run_pipeline_calls_change_detection(tmp_path, mock_data):
    """Tests that change detection is called during pipeline execution."""
    mocks = run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data)
    mocks['src.main.detect_register_changes'].assert_called_once()

def test_run_pipeline_calls_all_visualisation_functions(tmp_path, mock_data):
    """Tests that all three visualisation outputs are generated."""
    mocks = run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data)
    mocks['src.main.false_map_creation'].assert_called_once()
    mocks['src.main.report_creation'].assert_called_once()
    mocks['src.main.create_interactive_map'].assert_called_once()

def test_run_pipeline_stores_success_status_on_completion(tmp_path, mock_data):
    """Tests that pipeline metadata is stored with success status on completion."""
    mock_store = MagicMock()
    run_with_mocks('E06000021', '2026-05-25', str(tmp_path), mock_data, overrides={
        'src.main.store_pipeline_metadata': mock_store
    })
    mock_store.assert_called_once()
    assert mock_store.call_args[0][3] == 'success'