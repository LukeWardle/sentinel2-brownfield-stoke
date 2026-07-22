"""
api_copernicus.py - Copernicus API authentication and SAFE file download
========================================================================
Provides functions for interacting with the Copernicus Data Space
Ecosystem API. authenticate performs the password-grant login and returns
a token bundle with expiry tracking; ensure_fresh transparently refreshes
it (P0-10). get_bounding_box extracts a simple bounding box from a GeoJSON
boundary polygon. search_products queries the OData catalogue for
Sentinel-2 L2A products using the pipeline's shared database connection
(P0-8). download_safe downloads and extracts the matching SAFE folder,
refreshing the token before each attempt and on a mid-stream 401 so that
600MB+ downloads survive the ~10-minute token lifetime.

Credentials come from the centralised settings layer (src.settings, P0-3)
and must never be hardcoded or committed to version control.
"""

import json
import os
import sys
import time
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.settings import get_settings

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
    "/protocol/openid-connect/token"
)

# Refresh when fewer than this many seconds of token lifetime remain.
TOKEN_REFRESH_MARGIN_S = 60


def authenticate() -> dict:
    """
    Authenticates with the Copernicus Data Space Ecosystem using the
    password grant and returns a token bundle that tracks its own expiry,
    enabling transparent refresh during long downloads (P0-10).

    Returns:
        auth (dict): access_token (str), refresh_token (str or None),
                     expires_at (float, epoch seconds).

    Raises:
        ValueError: If credentials are missing from settings or
                    authentication fails.
    """
    settings = get_settings()
    if not settings.copernicus_username or not settings.copernicus_password:
        raise ValueError(
            "Copernicus credentials are not set. Add COPERNICUS_USERNAME and "
            "COPERNICUS_PASSWORD to your .env file — see .env.example."
        )
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": "cdse-public",
            "username": settings.copernicus_username,
            "password": settings.copernicus_password,
            "grant_type": "password",
        },
    )
    if response.status_code != 200:
        raise ValueError(f"Authentication failed — status code {response.status_code}")

    payload = response.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "expires_at": time.time() + float(payload.get("expires_in", 600)),
    }


def ensure_fresh(auth: dict, force: bool = False) -> dict:
    """
    Returns a token bundle guaranteed to be valid for at least
    TOKEN_REFRESH_MARGIN_S more seconds. If the current token is near
    expiry (or force=True, e.g. after a mid-stream 401), attempts the
    refresh-token grant first and falls back to full re-authentication.

    Args:
        auth (dict): Token bundle from authenticate().
        force (bool): Refresh even if the token has not expired yet.

    Returns:
        auth (dict): A valid token bundle — the same object if still fresh.
    """
    if not force and time.time() < auth["expires_at"] - TOKEN_REFRESH_MARGIN_S:
        return auth

    if auth.get("refresh_token"):
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": "cdse-public",
                "grant_type": "refresh_token",
                "refresh_token": auth["refresh_token"],
            },
        )
        if response.status_code == 200:
            payload = response.json()
            return {
                "access_token": payload["access_token"],
                "refresh_token": payload.get("refresh_token", auth["refresh_token"]),
                "expires_at": time.time() + float(payload.get("expires_in", 600)),
            }

    # Refresh grant unavailable or rejected — re-authenticate from scratch.
    return authenticate()


def get_access_token() -> str:
    """
    Back-compatibility wrapper: authenticates and returns just the access
    token string. Prefer authenticate()/ensure_fresh for anything
    long-running — a bare string cannot be refreshed.

    Returns:
        token (str): Access token for Bearer authorisation.

    Raises:
        ValueError: If authentication fails.
    """
    return authenticate()["access_token"]


def get_bounding_box(boundary: dict) -> dict:
    """
    Extracts a simple bounding box from a GeoJSON boundary polygon.
    Used to create a simplified search area for the Copernicus API
    rather than sending the full complex boundary polygon.

    Args:
        boundary (dict): GeoJSON boundary polygon in EPSG:4326.

    Returns:
        bbox (dict): Bounding box containing west, east, south, north coordinates.
    """
    coordinates = boundary["coordinates"][0]
    lons = [coord[0] for coord in coordinates]
    lats = [coord[1] for coord in coordinates]
    return {
        "west": min(lons),
        "east": max(lons),
        "south": min(lats),
        "north": max(lats),
    }


def search_products(
    gss_code: str,
    date: str,
    token: str,
    connection,
    cloud_threshold: float = 0.10,
) -> list:
    """
    Queries Copernicus OData catalogue for Sentinel-2 L2A products matching the
    council area (retrieved from the database by GSS code), date and cloud
    cover threshold. Uses the pipeline's single shared database connection
    (P0-8) rather than opening its own, honouring the one-connection design
    decision; the connection is left open for the caller.

    Args:
        gss_code (str): GSS code for the council area to search — used to retrieve
                        the council boundary bounding box from the database.
        date (str): Date of the image to search for in YYYY-MM-DD format.
        token (str): Access token — from authenticate()["access_token"] or
                     get_access_token().
        connection: Active psycopg2 connection from database_query.get_db_connection.
        cloud_threshold (float): Maximum acceptable cloud cover as a decimal —
                                 default 0.10 (10%). Products exceeding this
                                 threshold are excluded from results.

    Returns:
        products (list): List of dicts containing product_id, product_name,
                         cloud_cover and sensing_date.

    Raises:
        ValueError: If no boundary found for GSS code or no products found.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT ST_AsGeoJSON(boundary)
        FROM council_boundaries
        WHERE gss_code = %s
    """,
        (gss_code,),
    )
    result = cursor.fetchone()
    cursor.close()

    if result is None:
        raise ValueError(f"No boundary found for GSS code: {gss_code}")

    boundary = json.loads(result[0])
    bbox = get_bounding_box(boundary)

    footprint = (
        f"POLYGON(("
        f"{bbox['west']} {bbox['south']},"
        f"{bbox['east']} {bbox['south']},"
        f"{bbox['east']} {bbox['north']},"
        f"{bbox['west']} {bbox['north']},"
        f"{bbox['west']} {bbox['south']}"
        f"))"
    )

    date_start = f"{date}T00:00:00.000Z"
    date_end = f"{date}T23:59:59.000Z"
    cloud_percentage = cloud_threshold * 100

    url = (
        f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products?"
        f"$filter=Collection/Name eq 'SENTINEL-2' "
        f"and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
        f"and att/OData.CSC.DoubleAttribute/Value lt {cloud_percentage}) "
        f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        f"and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') "
        f"and OData.CSC.Intersects(area=geography'SRID=4326;{footprint}') "
        f"and ContentDate/Start gt {date_start} "
        f"and ContentDate/Start lt {date_end}"
        f"&$orderby=ContentDate/Start asc"
        f"&$top=10"
    )

    response = requests.get(url, headers={"Authorization": f"Bearer {token}"})

    if response.status_code != 200:
        raise ValueError(f"Search failed — status code {response.status_code}")

    data = response.json()

    if not data.get("value"):
        raise ValueError(
            f"No products found for GSS code {gss_code} on {date} "
            f"with cloud cover below {cloud_threshold * 100}%"
        )

    products = [
        {
            "product_id": item["Id"],
            "product_name": item["Name"].removesuffix(".SAFE"),
            "cloud_cover": next(
                (
                    attr["Value"]
                    for attr in item.get("Attributes", [])
                    if attr["Name"] == "cloudCover"
                ),
                None,
            ),
            "sensing_date": item["ContentDate"]["Start"],
        }
        for item in data["value"]
    ]

    return products


def download_safe(
    product_id: str,
    product_name: str,
    auth,
    output_dir: str,
    max_retries: int = 3,
) -> str:
    """
    Downloads the SAFE file zip for the given product ID, extracts it to
    output_dir and returns the path to the extracted SAFE folder. Retries
    up to max_retries times with exponential backoff on network failures.

    Token handling (P0-10): when auth is a token bundle from authenticate(),
    the token is checked and refreshed before every attempt, and an HTTP 401
    (token expired mid-download on a 600MB+ file) triggers a forced refresh
    and a retry rather than a hard failure. A plain token string is also
    accepted for back-compatibility, in which case no refresh is possible.

    Args:
        product_id (str): Copernicus product ID returned by search_products,
                          used to construct the OData download URL.
        product_name (str): Product name returned by search_products,
                            used to identify the extracted SAFE folder.
        auth: Token bundle dict from authenticate(), or a bare access-token
              string (no refresh capability).
        output_dir (str): Directory to extract the SAFE folder into —
                          typically the project raw_data/ directory.
        max_retries (int): Maximum number of download attempts before
                           raising an error. Default 3.

    Returns:
        safe_path (str): Full path to the extracted SAFE folder, ready
                         to be passed into data_loading_satellite.load_bands.

    Raises:
        ValueError: If all download attempts fail, the zip extraction fails,
                    or the extracted SAFE folder is missing its expected
                    structure.
    """
    refreshable = isinstance(auth, dict)

    url = (
        f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
    )
    zip_path = os.path.join(output_dir, f"{product_name}.zip")

    for attempt in range(1, max_retries + 1):
        try:
            print(f"Download attempt {attempt} of {max_retries}...")
            if refreshable:
                auth = ensure_fresh(auth)
                token = auth["access_token"]
            else:
                token = auth
            headers = {"Authorization": f"Bearer {token}"}
            session = requests.Session()
            session.headers.update(headers)
            response = session.get(url, headers=headers, stream=True)

            if response.status_code == 401 and refreshable:
                # Token expired between refresh and request, or was revoked —
                # force a refresh and retry this attempt's slot.
                print("Token rejected (401) — refreshing and retrying...")
                auth = ensure_fresh(auth, force=True)
                raise requests.exceptions.ConnectionError("401 token expiry")

            if response.status_code != 200:
                raise ValueError(
                    f"Download failed — status code {response.status_code}"
                )

            with open(zip_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)

            # Verify zip is valid before extracting
            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(output_dir)
            except zipfile.BadZipFile:
                raise ValueError(
                    "Downloaded file is not a valid zip — download may have been corrupted"
                )

            os.remove(zip_path)

            safe_path = os.path.join(output_dir, f"{product_name}.SAFE")

            if not os.path.exists(safe_path):
                raise ValueError(
                    f"Extracted SAFE folder not found at expected path: {safe_path}"
                )

            return safe_path

        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as e:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if attempt < max_retries:
                wait = 2**attempt
                print(
                    f"Download failed on attempt {attempt} — retrying in {wait}s: {e}"
                )
                time.sleep(wait)
            else:
                raise ValueError(f"Download failed after {max_retries} attempts: {e}")

        except ValueError:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise
