"""
validation_database.py - Database input validation
===================================================
Provides four functions for validating data before database operations.
validate_council_boundary_gss checks GSS code format and confirms it exists
in the council_boundaries table. brownfield_data_validation confirms register
data exists for a given GSS code and year. store_candidate_sites_validation
validates candidate site data before insertion. store_pipeline_metadata_validation
validates pipeline run metadata before insertion.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def validate_council_boundary_gss(gss_code: str, connection) -> bool:
    """
    Validates GSS code format and confirms it exists in the council_boundaries
    table. Raises ValueError if format is invalid or GSS code is not found.

    Args:
        gss_code (str): GSS code to validate — e.g. 'E06000021' for Stoke-on-Trent.
        connection: Active psycopg2 database connection from
                    database_query.get_db_connection.

    Returns:
        bool: True if GSS code is valid and exists in the database.

    Raises:
        ValueError: If GSS code format is invalid or not found in database.
    """
    if not isinstance(gss_code, str):
        raise ValueError(f"GSS code must be a string, got {type(gss_code)}")

    if not re.match(r"^[ENSW]\d{8}$", gss_code):
        raise ValueError(
            f"Invalid GSS code format '{gss_code}' — must be a letter "
            f"(E, N, S or W) followed by 8 digits e.g. 'E06000021'"
        )

    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM council_boundaries WHERE gss_code = %s", (gss_code,)
    )
    count = cursor.fetchone()[0]
    cursor.close()

    if count == 0:
        raise ValueError(
            f"GSS code '{gss_code}' not found in council_boundaries table — "
            f"run scripts/setup_boundaries.py first"
        )

    return True


def brownfield_data_validation(gss_code: str, year: int, connection) -> bool:
    """
    Confirms that brownfield register data exists in the brownfield_sites table
    for the given GSS code and year combination. Raises ValueError if no
    matching records are found.

    Args:
        gss_code (str): GSS code for the council area to validate.
        year (int): Year of the brownfield register to validate — e.g. 2024.
        connection: Active psycopg2 database connection from
                    database_query.get_db_connection.

    Returns:
        bool: True if register data exists for the given GSS code and year.

    Raises:
        ValueError: If no register data found, year is invalid, or GSS code
                    format is invalid.
    """
    if not re.match(r"^[A-Z]\d{8}$", str(gss_code)):
        raise ValueError(f"Invalid GSS code format: {gss_code}")

    if not isinstance(year, int):
        raise ValueError(f"Year must be an integer, got {type(year)}")

    if year < 2000 or year > 2100:
        raise ValueError(f"Year {year} is outside valid range 2000-2100")

    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM brownfield_sites WHERE gss_code = %s AND year = %s",
        (gss_code, year),
    )
    count = cursor.fetchone()[0]
    cursor.close()

    if count == 0:
        raise ValueError(
            f"No brownfield register data found for GSS code '{gss_code}' "
            f"and year {year} — run scripts/setup_brownfield.py first"
        )

    return True


def store_candidate_sites_validation(candidate_sites: list) -> bool:
    """
    Validates candidate site data before database insertion. Checks UTM
    coordinates are within valid UK range, pixel counts are positive, and
    BSI values fall within the expected range of -1 to 1.

    Args:
        candidate_sites (list): List of dicts, one per candidate site, each
                                containing centroid_utm_x, centroid_utm_y,
                                pixel_count and mean_bsi.

    Returns:
        bool: True if all candidate sites pass validation.

    Raises:
        ValueError: If candidate_sites is empty, missing required fields,
                    UTM coordinates are outside valid UK range, pixel count
                    is not positive, or BSI value is outside -1 to 1.
    """
    if not candidate_sites:
        raise ValueError("candidate_sites is empty — nothing to validate")

    required_keys = {"centroid_utm_x", "centroid_utm_y", "pixel_count", "mean_bsi"}

    for i, site in enumerate(candidate_sites):
        missing = required_keys - set(site.keys())
        if missing:
            raise ValueError(f"Site at index {i} is missing required fields: {missing}")

        if (
            not isinstance(site["pixel_count"], (int, float))
            or site["pixel_count"] <= 0
        ):
            raise ValueError(
                f"Site at index {i} has invalid pixel_count {site['pixel_count']} "
                f"— must be a positive number"
            )

        if not (-1.0 <= site["mean_bsi"] <= 1.0):
            raise ValueError(
                f"Site at index {i} has BSI value {site['mean_bsi']} "
                f"outside valid range -1 to 1"
            )

        # UK UTM Zone 30N (EPSG:32630) valid bounds for Great Britain
        # Easting: 400,000 to 700,000
        # Northing: 5,500,000 to 6,400,000
        if not (400000 <= site["centroid_utm_x"] <= 700000):
            raise ValueError(
                f"Site at index {i} has UTM X {site['centroid_utm_x']} "
                f"outside valid UK range 400,000-700,000"
            )

        if not (5500000 <= site["centroid_utm_y"] <= 6400000):
            raise ValueError(
                f"Site at index {i} has UTM Y {site['centroid_utm_y']} "
                f"outside valid UK range 5,500,000-6,400,000"
            )

    return True


def store_pipeline_metadata_validation(
    gss_code: str,
    image_date: str,
    status: str,
    candidate_sites_found: int,
    matched_to_register: int,
    unmatched: int,
) -> bool:
    """
    Validates pipeline run metadata before database insertion. Checks status
    is a valid value, all counts are non-negative integers, and image_date
    is correctly formatted.

    Args:
        gss_code (str): GSS code for the council area that was processed.
        image_date (str): Date of the Sentinel-2 image in YYYY-MM-DD format.
        status (str): Pipeline run status — either 'success' or 'failure'.
        candidate_sites_found (int): Total number of candidate sites identified.
        matched_to_register (int): Number matched to a registered site.
        unmatched (int): Number with no register match.

    Returns:
        bool: True if all metadata passes validation.

    Raises:
        ValueError: If status is invalid, counts are negative, date format
                    is incorrect, or GSS code format is invalid.
    """
    if not isinstance(gss_code, str) or not re.match(r"^[ENSW]\d{8}$", gss_code):
        raise ValueError(
            f"Invalid GSS code format '{gss_code}' — must be a letter "
            f"(E, N, S or W) followed by 8 digits"
        )

    if status not in ("success", "failure"):
        raise ValueError(f"Invalid status '{status}' — must be 'success' or 'failure'")

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", image_date):
        raise ValueError(
            f"Invalid image_date format '{image_date}' — must be YYYY-MM-DD"
        )

    for name, value in [
        ("candidate_sites_found", candidate_sites_found),
        ("matched_to_register", matched_to_register),
        ("unmatched", unmatched),
    ]:
        if not isinstance(value, int):
            raise ValueError(f"{name} must be an integer, got {type(value)}")
        if value < 0:
            raise ValueError(f"{name} cannot be negative, got {value}")

    if matched_to_register + unmatched > candidate_sites_found:
        raise ValueError(
            f"matched_to_register ({matched_to_register}) + unmatched ({unmatched}) "
            f"cannot exceed candidate_sites_found ({candidate_sites_found})"
        )

    return True
