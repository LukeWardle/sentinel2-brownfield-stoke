"""
test_api_recorded.py - Recorded-response tests for the Copernicus API
(P1-10).
=====================================================================
Uses the `responses` library to intercept the real HTTP transport, so —
unlike the MagicMock unit tests — these exercise the actual request
construction: the OData $filter assembly, query encoding, auth headers,
grant bodies and the multi-request refresh flow, entirely offline.

Fixtures are hand-recorded from real CDSE response shapes (Id/Name/
Attributes/ContentDate as the catalogue returns them) rather than
captured live — no credentials or network needed, deterministic forever.
"""

import time
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import responses

from src.api_copernicus import (
    TOKEN_URL,
    authenticate,
    download_safe,
    ensure_fresh,
    search_products,
)

CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
ZIPPER_URL = "https://zipper.dataspace.copernicus.eu/odata/v1/Products(prod-1)/$value"

CATALOGUE_BODY = {
    "value": [
        {
            "Id": "prod-1",
            "Name": "S2C_MSIL2A_20260525T110621_N0511_R137_T30UWE_20260525T143000.SAFE",
            "Attributes": [
                {"Name": "cloudCover", "Value": 4.87},
                {"Name": "productType", "Value": "S2MSI2A"},
            ],
            "ContentDate": {"Start": "2026-05-25T11:06:21.024Z"},
        }
    ]
}


def _mock_settings():
    settings = MagicMock()
    settings.copernicus_username = "user@example.com"
    settings.copernicus_password = "secret"
    return settings


def _db_conn_with_boundary():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = [
        '{"type":"Polygon","coordinates":[[[-2.25,52.95],[-1.95,52.95],'
        "[-1.95,53.10],[-2.25,53.10],[-2.25,52.95]]]}"
    ]
    return conn


# --- authenticate over the wire ---
@responses.activate
def test_authenticate_sends_password_grant_and_parses_bundle():
    responses.add(
        responses.POST,
        TOKEN_URL,
        json={
            "access_token": "acc",
            "refresh_token": "ref",
            "expires_in": 600,
        },
        status=200,
    )
    with patch("src.api_copernicus.get_settings", return_value=_mock_settings()):
        auth = authenticate()

    assert auth["access_token"] == "acc"
    body = responses.calls[0].request.body
    assert "grant_type=password" in body
    assert "client_id=cdse-public" in body
    assert "username=user%40example.com" in body


@responses.activate
def test_ensure_fresh_sends_refresh_grant():
    responses.add(
        responses.POST,
        TOKEN_URL,
        json={"access_token": "new", "expires_in": 600},
        status=200,
    )
    stale = {"access_token": "old", "refresh_token": "ref", "expires_at": time.time()}
    fresh = ensure_fresh(stale)
    assert fresh["access_token"] == "new"
    assert "grant_type=refresh_token" in responses.calls[0].request.body
    assert "refresh_token=ref" in responses.calls[0].request.body


# --- search_products: OData filter construction ---
@responses.activate
def test_search_builds_correct_odata_filter():
    responses.add(responses.GET, CATALOGUE_URL, json=CATALOGUE_BODY, status=200)
    products = search_products(
        "E06000021", "2026-05-25", "tok", _db_conn_with_boundary()
    )

    assert products[0]["product_id"] == "prod-1"
    assert products[0]["cloud_cover"] == 4.87
    assert products[0]["product_name"].endswith("20260525T143000")  # .SAFE stripped

    url = responses.calls[0].request.url
    # The parts of the $filter that matter, as actually sent on the wire
    assert "SENTINEL-2" in url
    assert "S2MSI2A" in url
    assert "cloudCover" in url
    assert "10.0" in url  # default 0.10 threshold as a percentage
    assert "2026-05-25T00" in url and "2026-05-25T23" in url
    # bbox footprint from the boundary, not the raw polygon
    assert "POLYGON" in url
    assert "-2.25" in url and "53.1" in url
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"


@responses.activate
def test_search_custom_cloud_threshold_reaches_the_wire():
    responses.add(responses.GET, CATALOGUE_URL, json=CATALOGUE_BODY, status=200)
    search_products(
        "E06000021", "2026-05-25", "tok", _db_conn_with_boundary(), cloud_threshold=0.25
    )
    assert "25.0" in responses.calls[0].request.url


@responses.activate
def test_search_empty_catalogue_raises():
    responses.add(responses.GET, CATALOGUE_URL, json={"value": []}, status=200)
    with pytest.raises(ValueError, match="No products found"):
        search_products("E06000021", "2026-05-25", "tok", _db_conn_with_boundary())


@responses.activate
def test_search_server_error_raises():
    responses.add(responses.GET, CATALOGUE_URL, status=503)
    with pytest.raises(ValueError, match="Search failed"):
        search_products("E06000021", "2026-05-25", "tok", _db_conn_with_boundary())


# --- download_safe over the wire ---
def _zip_bytes(tmp_path, safe_dir="prod-name.SAFE"):
    zip_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{safe_dir}/MTD_MSIL2A.xml", "<root/>")
    return zip_path.read_bytes()


@responses.activate
def test_download_happy_path_extracts_safe(tmp_path):
    responses.add(responses.GET, ZIPPER_URL, body=_zip_bytes(tmp_path), status=200)
    result = download_safe("prod-1", "prod-name", "tok", str(tmp_path))
    assert result.endswith("prod-name.SAFE")
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"


@responses.activate
def test_download_forbidden_raises(tmp_path):
    responses.add(responses.GET, ZIPPER_URL, status=403)
    with pytest.raises(ValueError, match="403"):
        download_safe("prod-1", "prod-name", "tok", str(tmp_path))


@responses.activate
def test_download_401_with_bundle_refreshes_and_succeeds(tmp_path):
    """Full P0-10 flow on the wire: 401 -> refresh grant to the token
    endpoint -> retried download succeeds with the new token."""
    responses.add(responses.GET, ZIPPER_URL, status=401)
    responses.add(
        responses.POST,
        TOKEN_URL,
        json={"access_token": "new-tok", "expires_in": 600},
        status=200,
    )
    responses.add(responses.GET, ZIPPER_URL, body=_zip_bytes(tmp_path), status=200)

    auth = {
        "access_token": "old-tok",
        "refresh_token": "ref",
        "expires_at": time.time() + 600,
    }
    with patch("src.api_copernicus.time.sleep", return_value=None):
        result = download_safe("prod-1", "prod-name", auth, str(tmp_path))

    assert result.endswith("prod-name.SAFE")
    token_calls = [c for c in responses.calls if c.request.url.startswith(TOKEN_URL)]
    assert any("grant_type=refresh_token" in c.request.body for c in token_calls)
    final_download = responses.calls[-1].request
    assert final_download.headers["Authorization"] == "Bearer new-tok"
