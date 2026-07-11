"""
api_copernicus.py - Copernicus API authentication and SAFE file download
========================================================================
Provides four functions for interacting with the Copernicus Data Space
Ecosystem API. get_access_token authenticates using credentials stored
in the .env file and returns a bearer token. get_bounding_box extracts
a simple bounding box from a GeoJSON boundary polygon. search_products
queries the OData catalogue for Sentinel-2 L2A products matching a given
council area and date. download_safe downloads and extracts the matching
SAFE folder to the raw_data directory ready for pipeline processing.

Credentials are loaded from .env and must never be hardcoded or committed
to version control.
"""
import os
import sys
import json
import zipfile
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_query import get_db_connection

load_dotenv()


def get_access_token() -> str:
    """
    Authenticates with the Copernicus Data Space Ecosystem using Keycloak token
    endpoint at https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token.
    Returns access token required for all subsequent API calls.
    Credentials loaded from .env file — never hardcoded.

    Returns:
        token (str): Access token required for all subsequent API calls.

    Raises:
        ValueError: If authentication fails.
    """
    username = os.getenv('COPERNICUS_USERNAME')
    password = os.getenv('COPERNICUS_PASSWORD')
    response = requests.post(
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        data={
            "client_id": "cdse-public",
            "username": username,
            "password": password,
            "grant_type": "password"
        }
    )
    if response.status_code != 200:
        raise ValueError(f"Authentication failed — status code {response.status_code}")

    token = response.json()['access_token']
    return token

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
    coordinates = boundary['coordinates'][0]
    lons = [coord[0] for coord in coordinates]
    lats = [coord[1] for coord in coordinates]
    return {
        'west': min(lons),
        'east': max(lons),
        'south': min(lats),
        'north': max(lats)
    }

def search_products(gss_code: str,
                    date: str,
                    token: str,
                    cloud_threshold: float = 0.10) -> list:
    """
    Queries Copernicus OData catalogue for Sentinel-2 L2A products matching the
    council area (retrieved from database by GSS code), date and cloud cover
    threshold. Returns list of matching products ordered by sensing date
    ascending.

    Args:
        gss_code (str): GSS code for the council area to search — used to retrieve
                        the council boundary bounding box from the database.
        date (str): Date of the image to search for in YYYY-MM-DD format.
        token (str): Access token returned by get_access_token.
        cloud_threshold (float): Maximum acceptable cloud cover as a decimal —
                                 default 0.10 (10%). Products exceeding this
                                 threshold are excluded from results.

    Returns:
        products (list): List of dicts containing product_id, product_name,
                         cloud_cover and sensing_date.

    Raises:
        ValueError: If no boundary found for GSS code or no products found.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ST_AsGeoJSON(boundary)
        FROM council_boundaries
        WHERE gss_code = %s
    """, (gss_code,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

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

    if not data.get('value'):
        raise ValueError(
            f"No products found for GSS code {gss_code} on {date} "
            f"with cloud cover below {cloud_threshold * 100}%"
        )

    products = [
        {
            'product_id': item['Id'],
            'product_name': item['Name'].removesuffix('.SAFE'),
            'cloud_cover': next(
                (attr['Value'] for attr in item.get('Attributes', [])
                 if attr['Name'] == 'cloudCover'), None
            ),
            'sensing_date': item['ContentDate']['Start']
        }
        for item in data['value']
    ]

    return products

def download_safe(product_id: str,
                  product_name: str,
                  token: str,
                  output_dir: str,
                  max_retries: int = 3) -> str:
    """
    Downloads SAFE file zip for the given product ID using the
    Copernicus OData download endpoint, extracts to output_dir and
    returns the path to the extracted SAFE folder. Retries up to
    max_retries times with exponential backoff on network failures.

    Args:
        product_id (str): Copernicus product ID returned by search_products,
                          used to construct the OData download URL.
        product_name (str): Product name returned by search_products,
                            used to identify the extracted SAFE folder.
        token (str): Access token returned by get_access_token.
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

    url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
    headers = {"Authorization": f"Bearer {token}"}
    zip_path = os.path.join(output_dir, f"{product_name}.zip")

    for attempt in range(1, max_retries + 1):
        try:
            print(f"Download attempt {attempt} of {max_retries}...")
            session = requests.Session()
            session.headers.update(headers)
            response = session.get(url, headers=headers, stream=True)

            if response.status_code != 200:
                raise ValueError(f"Download failed — status code {response.status_code}")

            with open(zip_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)

            # Verify zip is valid before extracting
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
            except zipfile.BadZipFile:
                raise ValueError("Downloaded file is not a valid zip — download may have been corrupted")

            os.remove(zip_path)

            safe_path = os.path.join(output_dir, f"{product_name}.SAFE")

            if not os.path.exists(safe_path):
                raise ValueError(f"Extracted SAFE folder not found at expected path: {safe_path}")

            return safe_path

        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"Download failed on attempt {attempt} — retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                raise ValueError(f"Download failed after {max_retries} attempts: {e}")

        except ValueError:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise