"""
test_api_copernicus.py - Unit tests for api_copernicus.py
"""
import pytest
import json
import os
import zipfile
import requests
from unittest.mock import patch, MagicMock, mock_open
from src.api_copernicus import get_access_token, get_bounding_box, search_products, download_safe

# --- get_access_token tests ---
def test_get_access_token_returns_string():
    """Tests that get_access_token returns a string token on success."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'access_token': 'test_token_12345'}

    with patch('src.api_copernicus.requests.post', return_value=mock_response):
        token = get_access_token()
        assert isinstance(token, str)
        assert token == 'test_token_12345'

def test_get_access_token_raises_on_401():
    """Tests that get_access_token raises ValueError on invalid credentials."""
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch('src.api_copernicus.requests.post', return_value=mock_response):
        with pytest.raises(ValueError):
            get_access_token()

def test_get_access_token_raises_on_500():
    """Tests that get_access_token raises ValueError on server error."""
    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch('src.api_copernicus.requests.post', return_value=mock_response):
        with pytest.raises(ValueError):
            get_access_token()

def test_get_access_token_raises_on_403():
    """Tests that get_access_token raises ValueError on forbidden response."""
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch('src.api_copernicus.requests.post', return_value=mock_response):
        with pytest.raises(ValueError):
            get_access_token()

# --- get_bounding_box tests ---
def test_get_bounding_box_returns_dict():
    """Tests that get_bounding_box returns a dict with correct keys."""
    boundary = {
        'type': 'Polygon',
        'coordinates': [[[0.0, 50.0], [1.0, 50.0], [1.0, 51.0], [0.0, 51.0], [0.0, 50.0]]]
    }
    result = get_bounding_box(boundary)
    assert isinstance(result, dict)
    assert 'west' in result
    assert 'east' in result
    assert 'south' in result
    assert 'north' in result

def test_get_bounding_box_correct_values():
    """Tests that get_bounding_box returns correct min/max coordinates."""
    boundary = {
        'type': 'Polygon',
        'coordinates': [[[0.0, 50.0], [2.0, 50.0], [2.0, 52.0], [0.0, 52.0], [0.0, 50.0]]]
    }
    result = get_bounding_box(boundary)
    assert result['west'] == 0.0
    assert result['east'] == 2.0
    assert result['south'] == 50.0
    assert result['north'] == 52.0

def test_get_bounding_box_negative_coordinates():
    """Tests that get_bounding_box handles negative coordinates correctly — e.g. UK west longitude."""
    boundary = {
        'type': 'Polygon',
        'coordinates': [[[-2.25, 52.95], [-1.95, 52.95], [-1.95, 53.10], [-2.25, 53.10], [-2.25, 52.95]]]
    }
    result = get_bounding_box(boundary)
    assert result['west'] == -2.25
    assert result['east'] == -1.95
    assert result['south'] == 52.95
    assert result['north'] == 53.10

def test_get_bounding_box_single_point_boundary():
    """Tests that get_bounding_box handles a degenerate boundary with identical coordinates."""
    boundary = {
        'type': 'Polygon',
        'coordinates': [[[1.0, 51.0], [1.0, 51.0], [1.0, 51.0], [1.0, 51.0]]]
    }
    result = get_bounding_box(boundary)
    assert result['west'] == result['east'] == 1.0
    assert result['south'] == result['north'] == 51.0

# --- search_products tests ---
def _mock_db_with_boundary():
    """Helper that returns a mock db connection with a valid Stoke boundary."""
    mock_db_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [json.dumps({
        'type': 'Polygon',
        'coordinates': [[[-2.25, 52.95], [-1.95, 52.95], [-1.95, 53.10], [-2.25, 53.10], [-2.25, 52.95]]]
    })]
    return mock_db_conn

def test_search_products_returns_list():
    """Tests that search_products returns a list of products on success."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'value': [{
            'Id': 'test-product-id',
            'Name': 'S2C_MSIL2A_20260525.SAFE',
            'Attributes': [{'Name': 'cloudCover', 'Value': 5.0}],
            'ContentDate': {'Start': '2026-05-25T11:06:21Z'}
        }]
    }

    with patch('src.api_copernicus.get_db_connection', return_value=_mock_db_with_boundary()):
        with patch('src.api_copernicus.requests.get', return_value=mock_response):
            products = search_products('E06000021', '2026-05-25', 'test_token')
            assert isinstance(products, list)
            assert len(products) == 1

def test_search_products_returns_correct_keys():
    """Tests that each product dict contains the correct keys."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'value': [{
            'Id': 'test-product-id',
            'Name': 'S2C_MSIL2A_20260525.SAFE',
            'Attributes': [{'Name': 'cloudCover', 'Value': 5.0}],
            'ContentDate': {'Start': '2026-05-25T11:06:21Z'}
        }]
    }

    with patch('src.api_copernicus.get_db_connection', return_value=_mock_db_with_boundary()):
        with patch('src.api_copernicus.requests.get', return_value=mock_response):
            products = search_products('E06000021', '2026-05-25', 'test_token')
            assert 'product_id' in products[0]
            assert 'product_name' in products[0]
            assert 'cloud_cover' in products[0]
            assert 'sensing_date' in products[0]

def test_search_products_raises_on_no_results():
    """Tests that search_products raises ValueError when no products are found."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'value': []}

    with patch('src.api_copernicus.get_db_connection', return_value=_mock_db_with_boundary()):
        with patch('src.api_copernicus.requests.get', return_value=mock_response):
            with pytest.raises(ValueError):
                search_products('E06000021', '2026-05-25', 'test_token')

def test_search_products_raises_on_invalid_gss_code():
    """Tests that search_products raises ValueError for an invalid GSS code."""
    mock_db_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None

    with patch('src.api_copernicus.get_db_connection', return_value=mock_db_conn):
        with pytest.raises(ValueError):
            search_products('INVALID', '2026-05-25', 'test_token')

def test_search_products_raises_on_api_error():
    """Tests that search_products raises ValueError on API error response."""
    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch('src.api_copernicus.get_db_connection', return_value=_mock_db_with_boundary()):
        with patch('src.api_copernicus.requests.get', return_value=mock_response):
            with pytest.raises(ValueError):
                search_products('E06000021', '2026-05-25', 'test_token')

def test_search_products_cloud_cover_extracted():
    """Tests that cloud cover value is correctly extracted from product attributes."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'value': [{
            'Id': 'test-product-id',
            'Name': 'S2C_MSIL2A_20260525.SAFE',
            'Attributes': [{'Name': 'cloudCover', 'Value': 7.5}],
            'ContentDate': {'Start': '2026-05-25T11:06:21Z'}
        }]
    }

    with patch('src.api_copernicus.get_db_connection', return_value=_mock_db_with_boundary()):
        with patch('src.api_copernicus.requests.get', return_value=mock_response):
            products = search_products('E06000021', '2026-05-25', 'test_token')
            assert products[0]['cloud_cover'] == 7.5

# --- download_safe tests ---
def test_download_safe_raises_on_failed_download():
    """Tests that download_safe raises ValueError if the download request fails."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_session.get.return_value = mock_response

    with patch('src.api_copernicus.requests.Session', return_value=mock_session):
        with pytest.raises(ValueError):
            download_safe('test-id', 'test-product', 'test_token', '/tmp')

def test_download_safe_raises_on_bad_zip(tmp_path):
    """Tests that download_safe raises ValueError if the downloaded file is not a valid zip."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [b'not a zip file']
    mock_session.get.return_value = mock_response

    with patch('src.api_copernicus.requests.Session', return_value=mock_session):
        with pytest.raises(ValueError):
            download_safe('test-id', 'test-product', 'test_token', str(tmp_path))

def test_download_safe_raises_if_safe_folder_missing(tmp_path):
    """Tests that download_safe raises ValueError if the SAFE folder is missing after extraction."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200

    zip_path = tmp_path / "test-product.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("wrong_folder/file.txt", "content")

    with open(zip_path, 'rb') as f:
        zip_bytes = f.read()

    mock_response.iter_content.return_value = [zip_bytes]
    mock_session.get.return_value = mock_response

    with patch('src.api_copernicus.requests.Session', return_value=mock_session):
        with pytest.raises(ValueError):
            download_safe('test-id', 'test-product', 'test_token', str(tmp_path))

def test_download_safe_returns_correct_path(tmp_path):
    """Tests that download_safe returns the correct SAFE folder path on success."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200

    zip_path = tmp_path / "test-product.zip"
    safe_dir = "test-product.SAFE"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr(f"{safe_dir}/MTD_MSIL2A.xml", "<root/>")

    with open(zip_path, 'rb') as f:
        zip_bytes = f.read()

    mock_response.iter_content.return_value = [zip_bytes]
    mock_session.get.return_value = mock_response

    with patch('src.api_copernicus.requests.Session', return_value=mock_session):
        result = download_safe('test-id', 'test-product', 'test_token', str(tmp_path))
        assert result == str(tmp_path / safe_dir)
        assert os.path.exists(result)

def test_download_safe_retries_on_chunked_encoding_error(tmp_path):
    """Tests that download_safe retries on ChunkedEncodingError and succeeds on second attempt."""
    mock_session = MagicMock()

    zip_path = tmp_path / "test-product.zip"
    safe_dir = "test-product.SAFE"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr(f"{safe_dir}/MTD_MSIL2A.xml", "<root/>")
    with open(zip_path, 'rb') as f:
        zip_bytes = f.read()

    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 200
    mock_response_fail.iter_content.side_effect = requests.exceptions.ChunkedEncodingError("connection broken")

    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.iter_content.return_value = [zip_bytes]

    mock_session.get.side_effect = [mock_response_fail, mock_response_success]

    with patch('src.api_copernicus.requests.Session', return_value=mock_session):
        with patch('src.api_copernicus.time.sleep', return_value=None):
            result = download_safe('test-id', 'test-product', 'test_token', str(tmp_path), max_retries=2)
            assert os.path.exists(result)

def test_download_safe_raises_after_max_retries(tmp_path):
    """Tests that download_safe raises ValueError after all retry attempts are exhausted."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_content.side_effect = requests.exceptions.ChunkedEncodingError("connection broken")
    mock_session.get.return_value = mock_response

    with patch('src.api_copernicus.requests.Session', return_value=mock_session):
        with patch('src.api_copernicus.time.sleep', return_value=None):
            with pytest.raises(ValueError):
                download_safe('test-id', 'test-product', 'test_token', str(tmp_path), max_retries=2)