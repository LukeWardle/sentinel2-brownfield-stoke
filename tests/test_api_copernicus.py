"""
test_api_copernicus.py - Unit tests for api_copernicus.py

Updated for P0-8 (search_products takes the shared connection as an
argument rather than opening its own) and P0-10 (refreshable auth bundle
with expiry tracking; download refreshes before attempts and on 401).
The download tests passing a bare token string are retained deliberately —
they pin the back-compatibility path.
"""

import json
import os
import time
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api_copernicus import (
    authenticate,
    download_safe,
    ensure_fresh,
    get_access_token,
    get_bounding_box,
    search_products,
)


def _mock_settings(username="user@example.com", password="secret"):
    settings = MagicMock()
    settings.copernicus_username = username
    settings.copernicus_password = password
    return settings


# --- authenticate / token tests ---
def test_authenticate_returns_bundle_with_expiry():
    """authenticate returns access/refresh tokens and a future expiry."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "access_12345",
        "refresh_token": "refresh_67890",
        "expires_in": 600,
    }
    with patch("src.api_copernicus.get_settings", return_value=_mock_settings()):
        with patch("src.api_copernicus.requests.post", return_value=mock_response):
            auth = authenticate()
    assert auth["access_token"] == "access_12345"
    assert auth["refresh_token"] == "refresh_67890"
    assert auth["expires_at"] > time.time()


def test_authenticate_raises_when_credentials_missing():
    with patch(
        "src.api_copernicus.get_settings",
        return_value=_mock_settings(username=None, password=None),
    ):
        with pytest.raises(ValueError):
            authenticate()


def test_get_access_token_returns_string():
    """Back-compat wrapper still returns the bare token string."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "test_token_12345"}

    with patch("src.api_copernicus.get_settings", return_value=_mock_settings()):
        with patch("src.api_copernicus.requests.post", return_value=mock_response):
            token = get_access_token()
            assert isinstance(token, str)
            assert token == "test_token_12345"


def test_get_access_token_raises_on_401():
    mock_response = MagicMock()
    mock_response.status_code = 401
    with patch("src.api_copernicus.get_settings", return_value=_mock_settings()):
        with patch("src.api_copernicus.requests.post", return_value=mock_response):
            with pytest.raises(ValueError):
                get_access_token()


def test_get_access_token_raises_on_500():
    mock_response = MagicMock()
    mock_response.status_code = 500
    with patch("src.api_copernicus.get_settings", return_value=_mock_settings()):
        with patch("src.api_copernicus.requests.post", return_value=mock_response):
            with pytest.raises(ValueError):
                get_access_token()


def test_get_access_token_raises_on_403():
    mock_response = MagicMock()
    mock_response.status_code = 403
    with patch("src.api_copernicus.get_settings", return_value=_mock_settings()):
        with patch("src.api_copernicus.requests.post", return_value=mock_response):
            with pytest.raises(ValueError):
                get_access_token()


# --- ensure_fresh tests (P0-10) ---
def test_ensure_fresh_returns_same_bundle_when_not_near_expiry():
    auth = {"access_token": "a", "refresh_token": "r", "expires_at": time.time() + 600}
    with patch("src.api_copernicus.requests.post") as mock_post:
        result = ensure_fresh(auth)
    assert result is auth
    mock_post.assert_not_called()


def test_ensure_fresh_uses_refresh_grant_when_near_expiry():
    auth = {
        "access_token": "old",
        "refresh_token": "refresh_67890",
        "expires_at": time.time() + 10,  # inside the 60s margin
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_in": 600,
    }
    with patch(
        "src.api_copernicus.requests.post", return_value=mock_response
    ) as mock_post:
        result = ensure_fresh(auth)
    assert result["access_token"] == "new_access"
    assert result["refresh_token"] == "new_refresh"
    sent = mock_post.call_args.kwargs.get("data") or mock_post.call_args.args[1]
    assert sent["grant_type"] == "refresh_token"


def test_ensure_fresh_falls_back_to_password_when_refresh_rejected():
    auth = {
        "access_token": "old",
        "refresh_token": "stale_refresh",
        "expires_at": time.time() - 1,
    }
    refresh_rejected = MagicMock()
    refresh_rejected.status_code = 400
    password_ok = MagicMock()
    password_ok.status_code = 200
    password_ok.json.return_value = {
        "access_token": "fresh_via_password",
        "refresh_token": "r2",
        "expires_in": 600,
    }
    with patch("src.api_copernicus.get_settings", return_value=_mock_settings()):
        with patch(
            "src.api_copernicus.requests.post",
            side_effect=[refresh_rejected, password_ok],
        ):
            result = ensure_fresh(auth)
    assert result["access_token"] == "fresh_via_password"


def test_ensure_fresh_force_refreshes_even_when_token_valid():
    auth = {"access_token": "a", "refresh_token": "r", "expires_at": time.time() + 600}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "forced", "expires_in": 600}
    with patch("src.api_copernicus.requests.post", return_value=mock_response):
        result = ensure_fresh(auth, force=True)
    assert result["access_token"] == "forced"


# --- get_bounding_box tests ---
def test_get_bounding_box_returns_dict():
    boundary = {
        "type": "Polygon",
        "coordinates": [
            [[0.0, 50.0], [1.0, 50.0], [1.0, 51.0], [0.0, 51.0], [0.0, 50.0]]
        ],
    }
    result = get_bounding_box(boundary)
    assert isinstance(result, dict)
    assert "west" in result
    assert "east" in result
    assert "south" in result
    assert "north" in result


def test_get_bounding_box_correct_values():
    boundary = {
        "type": "Polygon",
        "coordinates": [
            [[0.0, 50.0], [2.0, 50.0], [2.0, 52.0], [0.0, 52.0], [0.0, 50.0]]
        ],
    }
    result = get_bounding_box(boundary)
    assert result["west"] == 0.0
    assert result["east"] == 2.0
    assert result["south"] == 50.0
    assert result["north"] == 52.0


def test_get_bounding_box_negative_coordinates():
    boundary = {
        "type": "Polygon",
        "coordinates": [
            [
                [-2.25, 52.95],
                [-1.95, 52.95],
                [-1.95, 53.10],
                [-2.25, 53.10],
                [-2.25, 52.95],
            ]
        ],
    }
    result = get_bounding_box(boundary)
    assert result["west"] == -2.25
    assert result["east"] == -1.95
    assert result["south"] == 52.95
    assert result["north"] == 53.10


def test_get_bounding_box_single_point_boundary():
    boundary = {
        "type": "Polygon",
        "coordinates": [[[1.0, 51.0], [1.0, 51.0], [1.0, 51.0], [1.0, 51.0]]],
    }
    result = get_bounding_box(boundary)
    assert result["west"] == result["east"] == 1.0
    assert result["south"] == result["north"] == 51.0


# --- search_products tests (P0-8: connection passed in) ---
def _mock_db_with_boundary():
    """Helper that returns a mock db connection with a valid Stoke boundary."""
    mock_db_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-2.25, 52.95],
                        [-1.95, 52.95],
                        [-1.95, 53.10],
                        [-2.25, 53.10],
                        [-2.25, 52.95],
                    ]
                ],
            }
        )
    ]
    return mock_db_conn


def _one_product_response(cloud=5.0):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "value": [
            {
                "Id": "test-product-id",
                "Name": "S2C_MSIL2A_20260525.SAFE",
                "Attributes": [{"Name": "cloudCover", "Value": cloud}],
                "ContentDate": {"Start": "2026-05-25T11:06:21Z"},
            }
        ]
    }
    return mock_response


def test_search_products_returns_list():
    conn = _mock_db_with_boundary()
    with patch("src.api_copernicus.requests.get", return_value=_one_product_response()):
        products = search_products("E06000021", "2026-05-25", "test_token", conn)
        assert isinstance(products, list)
        assert len(products) == 1


def test_search_products_returns_correct_keys():
    conn = _mock_db_with_boundary()
    with patch("src.api_copernicus.requests.get", return_value=_one_product_response()):
        products = search_products("E06000021", "2026-05-25", "test_token", conn)
        assert "product_id" in products[0]
        assert "product_name" in products[0]
        assert "cloud_cover" in products[0]
        assert "sensing_date" in products[0]


def test_search_products_raises_on_no_results():
    conn = _mock_db_with_boundary()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": []}
    with patch("src.api_copernicus.requests.get", return_value=mock_response):
        with pytest.raises(ValueError):
            search_products("E06000021", "2026-05-25", "test_token", conn)


def test_search_products_raises_on_invalid_gss_code():
    mock_db_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    with pytest.raises(ValueError):
        search_products("INVALID", "2026-05-25", "test_token", mock_db_conn)


def test_search_products_raises_on_api_error():
    conn = _mock_db_with_boundary()
    mock_response = MagicMock()
    mock_response.status_code = 500
    with patch("src.api_copernicus.requests.get", return_value=mock_response):
        with pytest.raises(ValueError):
            search_products("E06000021", "2026-05-25", "test_token", conn)


def test_search_products_cloud_cover_extracted():
    conn = _mock_db_with_boundary()
    with patch(
        "src.api_copernicus.requests.get", return_value=_one_product_response(7.5)
    ):
        products = search_products("E06000021", "2026-05-25", "test_token", conn)
        assert products[0]["cloud_cover"] == 7.5


def test_search_products_does_not_close_shared_connection():
    """P0-8 contract: the shared connection is the caller's — search must
    not close it."""
    conn = _mock_db_with_boundary()
    with patch("src.api_copernicus.requests.get", return_value=_one_product_response()):
        search_products("E06000021", "2026-05-25", "test_token", conn)
    conn.close.assert_not_called()


# --- download_safe tests ---
def test_download_safe_raises_on_failed_download():
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_session.get.return_value = mock_response

    with patch("src.api_copernicus.requests.Session", return_value=mock_session):
        with pytest.raises(ValueError):
            download_safe("test-id", "test-product", "test_token", "/tmp")


def test_download_safe_raises_on_bad_zip(tmp_path):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [b"not a zip file"]
    mock_session.get.return_value = mock_response

    with patch("src.api_copernicus.requests.Session", return_value=mock_session):
        with pytest.raises(ValueError):
            download_safe("test-id", "test-product", "test_token", str(tmp_path))


def test_download_safe_raises_if_safe_folder_missing(tmp_path):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200

    zip_path = tmp_path / "test-product.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("wrong_folder/file.txt", "content")

    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    mock_response.iter_content.return_value = [zip_bytes]
    mock_session.get.return_value = mock_response

    with patch("src.api_copernicus.requests.Session", return_value=mock_session):
        with pytest.raises(ValueError):
            download_safe("test-id", "test-product", "test_token", str(tmp_path))


def test_download_safe_returns_correct_path(tmp_path):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200

    zip_path = tmp_path / "test-product.zip"
    safe_dir = "test-product.SAFE"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{safe_dir}/MTD_MSIL2A.xml", "<root/>")

    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    mock_response.iter_content.return_value = [zip_bytes]
    mock_session.get.return_value = mock_response

    with patch("src.api_copernicus.requests.Session", return_value=mock_session):
        result = download_safe("test-id", "test-product", "test_token", str(tmp_path))
        assert result == str(tmp_path / safe_dir)
        assert os.path.exists(result)


def test_download_safe_retries_on_chunked_encoding_error(tmp_path):
    mock_session = MagicMock()

    zip_path = tmp_path / "test-product.zip"
    safe_dir = "test-product.SAFE"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{safe_dir}/MTD_MSIL2A.xml", "<root/>")
    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 200
    mock_response_fail.iter_content.side_effect = (
        requests.exceptions.ChunkedEncodingError("connection broken")
    )

    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.iter_content.return_value = [zip_bytes]

    mock_session.get.side_effect = [mock_response_fail, mock_response_success]

    with patch("src.api_copernicus.requests.Session", return_value=mock_session):
        with patch("src.api_copernicus.time.sleep", return_value=None):
            result = download_safe(
                "test-id", "test-product", "test_token", str(tmp_path), max_retries=2
            )
            assert os.path.exists(result)


def test_download_safe_raises_after_max_retries(tmp_path):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_content.side_effect = requests.exceptions.ChunkedEncodingError(
        "connection broken"
    )
    mock_session.get.return_value = mock_response

    with patch("src.api_copernicus.requests.Session", return_value=mock_session):
        with patch("src.api_copernicus.time.sleep", return_value=None):
            with pytest.raises(ValueError):
                download_safe(
                    "test-id",
                    "test-product",
                    "test_token",
                    str(tmp_path),
                    max_retries=2,
                )


def test_download_safe_refreshes_before_each_attempt_with_auth_bundle(tmp_path):
    """P0-10: given an auth bundle, the token is checked/refreshed before
    the request is made."""
    mock_session = MagicMock()
    zip_path = tmp_path / "test-product.zip"
    safe_dir = "test-product.SAFE"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{safe_dir}/MTD_MSIL2A.xml", "<root/>")
    with open(zip_path, "rb") as f:
        zip_bytes = f.read()
    ok = MagicMock()
    ok.status_code = 200
    ok.iter_content.return_value = [zip_bytes]
    mock_session.get.return_value = ok

    auth = {"access_token": "a", "refresh_token": "r", "expires_at": time.time() + 600}
    with patch("src.api_copernicus.requests.Session", return_value=mock_session):
        with patch(
            "src.api_copernicus.ensure_fresh", side_effect=lambda a, force=False: a
        ) as mock_fresh:
            result = download_safe("test-id", "test-product", auth, str(tmp_path))
    assert os.path.exists(result)
    mock_fresh.assert_called()


def test_download_safe_401_triggers_forced_refresh_and_retry(tmp_path):
    """P0-10: a mid-download 401 forces a refresh and the attempt is
    retried rather than failing outright."""
    mock_session = MagicMock()
    zip_path = tmp_path / "test-product.zip"
    safe_dir = "test-product.SAFE"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{safe_dir}/MTD_MSIL2A.xml", "<root/>")
    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    unauthorized = MagicMock()
    unauthorized.status_code = 401
    ok = MagicMock()
    ok.status_code = 200
    ok.iter_content.return_value = [zip_bytes]
    mock_session.get.side_effect = [unauthorized, ok]

    auth = {"access_token": "a", "refresh_token": "r", "expires_at": time.time() + 600}
    refreshed = dict(auth, access_token="a2")

    calls = []

    def fake_ensure_fresh(a, force=False):
        calls.append(force)
        return refreshed if force else a

    with patch("src.api_copernicus.requests.Session", return_value=mock_session):
        with patch("src.api_copernicus.ensure_fresh", side_effect=fake_ensure_fresh):
            with patch("src.api_copernicus.time.sleep", return_value=None):
                result = download_safe(
                    "test-id", "test-product", auth, str(tmp_path), max_retries=3
                )
    assert os.path.exists(result)
    assert True in calls  # the forced refresh happened
