"""
api_copernicus.py - Copernicus API authentication module for downloading SAFE files.
====================================================================================
Provides three functions for interacting with the Copernicus Data Space
Ecosystem API. get_access_token authenticates using credentials stored
in the .env file and returns a bearer token. search_products queries the
OData catalogue for Sentinel-2 L2A products matching a given council area
and date. download_safe downloads and extracts the matching SAFE folder
to the raw_data directory ready for pipeline processing.

Credentials are loaded from .env and must never be hardcoded or committed
to version control.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_access_token() -> str:
    """
    Authenticates with the Copernicus Data Space Ecosystem using Keycloak token
    endpoint at https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token.
    Returns access token required for all subsequent API calls.
    Credentials loaded from .env file — never hardcoded.
    Raises ValueError if authentication fails.
    
    Returns:
        token (str): Access token require for all subsequent API calls.

    Raises:
        ValueError: if authentication fails.
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
    else:
        token = response.json()['access_token']

    return token

def search_products(gss_code: str, 
                    date: str, 
                    token: str, 
                    cloud_threshold: float=0.10) -> list:
    """
    Queries Copernicus OData catalogue for Sentinel-2 L2A products matching the
    council area (retrieved from database by GSS code), date and cloud cover
    threshold. Returns list of matching products ordered by cloud cover
    ascending — lowest cloud cover first. 
    Raises ValueError if no products found for given parameters.

    Args:
        gss_code (str): GSS code for the council area to search — used to retrieve
                        the council boundary polygon from the database.
        date (str): Date of the image to search for in YYYY-MM-DD format.
        token (str): Access token returned by get_access_token.
        cloud_threhold (float=0.10): Maximum acceptable cloud cover as a decimal —
                                     default 0.10 (10%). Products exceeding this
                                     threshold are excluded from results.

    Returns:
        products (list): List of dicts containing product_id, product_name, 
                         cloud_cover, sensing_date, ordered by cloud cover
                         ascending - lowest cloud cover first.

    Raises:
        ValueError: If no products are found matching the given parameters.
    """
    pass

def download_safe(product_id: str, 
                  product_name: str, 
                  token: str, 
                  output_dir: str) -> str:
    """
    Downloads SAFE file zip for the given product ID using the 
    Copernicus OData download endpoint, 
    extracts to output_dir and returns the path to the extracted SAFE folder. 
    Raises ValueError if download fails or extracted SAFE folder is missing 
    expected structure

    Args:
        product_id (str): Copernicus product ID returned by search_products,
                          used to construct the OData download URL.
        product_name (str): Product name returned by search_products,
                            used to identify the extracted SAFE folder.
        token (str): Access token returned by get_access_token.
        output_dir (str): Directory to extract the SAFE folder into —
                          typically the project raw_data/ directory.

    Returns:
        safe_path (str): Full path to extracted SAFE folder, ready
                         to be passed into data_loading_satellite.load_bands.

    Raises:
        ValueError: If download fails, the zip extraction fails,
                    or the extracted SAFE folder is missing its expected structure.
    """
    pass