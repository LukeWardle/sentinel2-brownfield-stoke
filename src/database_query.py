"""
database_query.py - Runtime database queries and candidate site storage.
========================================================================
Provides five functions for interacting with the sentinel2_brownfield
PostgreSQL database at runtime. get_db_connection creates a single
connection using credentials from .env, which is passed into all
subsequent functions. retrieve_council_boundary_gss retrieves a council
boundary polygon by GSS code for AOI clipping. retrieve_brownfield_register_data
retrieves all register sites for a given council and year for candidate
site matching. store_candidate_sites and store_pipeline_metadata write
pipeline results to the database after each run.

Credentials are loaded from .env and must never be hardcoded or committed
to version control.
"""
import os
import psycopg2
import json
from dotenv import load_dotenv

load_dotenv()

def retrieve_council_boundary_gss(gss_code: str, connection) -> dict:
    """
    Queries council_boundaries table by GSS code and returns the council boundary
    polygon converted to UTM coordinates. Used by AOI clipping to constrain
    satellite image processing to the correct council area.

    Args:
        gss_code (str): GSS code for the council area to retrieve — e.g. 'E06000021'
                        for Stoke-on-Trent.
        connection: Active psycopg2 database connection created by get_db_connection.

    Returns:
        boundary_polygon (dict): Boundary geometry in UTM coordinates ready for
                                 AOI clipping, containing the polygon coordinates
                                 as a GeoJSON-compatible structure.

    Raises:
        ValueError: If no boundary is found for the given GSS code.
    """
    cursor = connection.cursor()
    cursor.execute("""
        SELECT ST_AsGeoJSON(ST_Transform(ST_SetSRID(boundary, 4326), 32630))
        FROM council_boundaries
        WHERE gss_code = %s
    """, (gss_code,))
    result = cursor.fetchone()
    cursor.close()
    if result is None:
        raise ValueError(f"No boundary found for GSS code: {gss_code}")

    boundary_polygon = json.loads(result[0])
    return boundary_polygon

def retrieve_brownfield_register_data(gss_code: str, year: int, connection) -> list:
    """
    Queries brownfield_sites table for all register sites matching the given GSS
    code and year. Returns site locations in UTM coordinates ready for comparison
    against candidate sites from the clustering module.

    Args:
        gss_code (str): GSS code for the council area to retrieve — e.g. 'E06000021'
                        for Stoke-on-Trent.
        year (int): Year of the brownfield register to retrieve — e.g. 2024.
        connection: Active psycopg2 database connection created by get_db_connection.

    Returns:
        register_sites (list): List of dicts, one per site, each containing
                               site_reference, utm_x and utm_y — ready for
                               comparison against candidate sites from the
                               clustering module.

    Raises:
        ValueError: If no register data is found for the given GSS code and year.
    """
    cursor = connection.cursor()

    cursor.execute("""
        SELECT site_reference, utm_x, utm_y
        FROM brownfield_sites
        WHERE gss_code = %s AND year = %s
    """, (gss_code, year))
    results = cursor.fetchall()
    cursor.close()
    if not results:
        raise ValueError(f"No brownfield register data found for GSS code {gss_code} and year {year}")

    register_sites = [
        {"site_reference": row[0], "utm_x": row[1], "utm_y": row[2]}
        for row in results
    ]

    return register_sites

def store_candidate_sites(candidate_sites: list,
                          gss_code: str,
                          image_date: str,
                          run_timestamp: str,
                          connection) -> None:
    """
    Stores candidate brownfield sites identified by the clustering module into the
    candidate_sites table. Each site record includes GSS code, image date,
    run timestamp, UTM coordinates, pixel count, BSI value and register match status.

    Args:
        candidate_sites (list): List of dicts, one per candidate site, each containing
                                utm_x, utm_y, pixel_count, bsi_value and
                                matched_site_reference (None if unmatched).
        gss_code (str): GSS code for the council area being processed.
        image_date (str): Date of the Sentinel-2 image in YYYY-MM-DD format.
        run_timestamp (str): Timestamp of the pipeline run in YYYY-MM-DD HH:MM:SS format.
        connection: Active psycopg2 database connection created by get_db_connection.

    Returns:
        None — writes directly to the candidate_sites table.

    Raises:
        ValueError: If candidate_sites is empty or a site dict is missing required fields.
    """
    if not candidate_sites:
        raise ValueError("candidate_sites is empty — nothing to store")

    cursor = connection.cursor()

    for site in candidate_sites:
        cursor.execute("""
            INSERT INTO candidate_sites
            (gss_code, image_date, run_timestamp, utm_x, utm_y, pixel_count, bsi_value, matched_site_reference)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            gss_code,
            image_date,
            run_timestamp,
            site['centroid_utm_x'],
            site['centroid_utm_y'],
            site['pixel_count'],
            site['mean_bsi'],
            site.get('matched_site_reference', None)
        ))
    connection.commit()
    cursor.close()

def store_pipeline_metadata(gss_code: str,
                            image_date: str,
                            run_timestamp: str,
                            status: str,
                            candidate_sites_found: int,
                            matched_to_register: int,
                            unmatched: int,
                            connection) -> None:
    """
    Stores pipeline run metadata into the pipeline_runs table after each completed
    run. Records council, image date, timestamp, success or failure status,
    and counts of candidate sites found, matched and unmatched against the
    brownfield register.

    Args:
        gss_code (str): GSS code for the council area that was processed.
        image_date (str): Date of the Sentinel-2 image in YYYY-MM-DD format.
        run_timestamp (str): Timestamp of the pipeline run in YYYY-MM-DD HH:MM:SS format.
        status (str): Pipeline run status — either 'success' or 'failure'.
        candidate_sites_found (int): Total number of candidate sites identified.
        matched_to_register (int): Number of candidate sites matched to a registered site.
        unmatched (int): Number of candidate sites with no register match.
        connection: Active psycopg2 database connection created by get_db_connection.

    Returns:
        None — writes directly to the pipeline_runs table.

    Raises:
        ValueError: If status is not 'success' or 'failure', or if any count is negative.
    """
    if status not in ('success', 'failure'):
        raise ValueError(f"Invalid status '{status}' — must be 'success' or 'failure'")

    if any(count < 0 for count in [candidate_sites_found, matched_to_register, unmatched]):
        raise ValueError("Candidate site counts cannot be negative")

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO pipeline_runs
        (gss_code, image_date, run_timestamp, status, candidate_sites_found, matched_to_register, unmatched)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        gss_code,
        image_date,
        run_timestamp,
        status,
        candidate_sites_found,
        matched_to_register,
        unmatched
    ))
    connection.commit()
    cursor.close()

def get_db_connection():
    """
    Creates and returns a connection to the sentinel2_brownfield PostgreSQL database
    using credentials loaded from .env. Call once in main.py and pass the returned
    connection into all database_query functions.

    Returns:
        connection: Active psycopg2 database connection.

    Raises:
        ValueError: If database connection fails.
    """
    try:
        connection = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        return connection
    except Exception as e:
        raise ValueError(f"Database connection failed: {e}")
    
def match_candidate_to_register(utm_x: float,
                                 utm_y: float,
                                 gss_code: str,
                                 year: int,
                                 connection,
                                 distance_threshold: float = 100.0) -> str | None:
    """
    Checks whether a candidate site's UTM coordinates match any registered
    brownfield site within the given distance threshold. Uses PostGIS ST_DWithin
    for efficient spatial proximity checking.

    Args:
        utm_x (float): UTM X coordinate of the candidate site centroid in EPSG:32630.
        utm_y (float): UTM Y coordinate of the candidate site centroid in EPSG:32630.
        gss_code (str): GSS code for the council area being processed.
        year (int): Year of the brownfield register to match against — e.g. 2024.
        connection: Active psycopg2 database connection from
                    database_query.get_db_connection.
        distance_threshold (float): Maximum distance in metres between candidate
                                    site centroid and register site for a match
                                    to be recorded. Default 100 metres.

    Returns:
        str | None: site_reference of the matched register site if found within
                    distance_threshold, or None if no match found.
    """
    cursor = connection.cursor()

    cursor.execute("""
        SELECT site_reference
        FROM brownfield_sites
        WHERE gss_code = %s
        AND year = %s
        AND ST_DWithin(
            location,
            ST_SetSRID(ST_MakePoint(%s, %s), 32630),
            %s
        )
        ORDER BY ST_Distance(
            location,
            ST_SetSRID(ST_MakePoint(%s, %s), 32630)
        ) ASC
        LIMIT 1
    """, (gss_code, year, utm_x, utm_y, distance_threshold, utm_x, utm_y))

    result = cursor.fetchone()
    cursor.close()
    return result[0] if result else None

def detect_register_changes(gss_code: str,
                            year_from: int,
                            year_to: int,
                            connection) -> dict:
    """
    Compares brownfield register data across two years for a given council,
    identifying sites that have been added or removed between the two years.
    Sites removed likely indicate development has taken place. Sites added
    indicate newly identified brownfield land.

    Args:
        gss_code (str): GSS code for the council area to analyse.
        year_from (int): The earlier year to compare from.
        year_to (int): The later year to compare to.
        connection: Active psycopg2 database connection from
                    database_query.get_db_connection.

    Returns:
        dict: Contains two keys:
              'removed' — list of dicts for sites in year_from but not year_to,
              each containing site_reference and name_address.
              'added' — list of dicts for sites in year_to but not year_from,
              each containing site_reference and name_address.

    Raises:
        ValueError: If year_from >= year_to or no data exists for either year.
    """
    if year_from >= year_to:
        raise ValueError(
            f"year_from ({year_from}) must be less than year_to ({year_to})"
        )

    cursor = connection.cursor()

    # Check data exists for both years
    for year in [year_from, year_to]:
        cursor.execute(
            "SELECT COUNT(*) FROM brownfield_sites WHERE gss_code = %s AND year = %s",
            (gss_code, year)
        )
        if cursor.fetchone()[0] == 0:
            cursor.close()
            raise ValueError(
                f"No brownfield register data found for GSS code '{gss_code}' "
                f"and year {year}"
            )

    # Sites removed — in year_from but not in year_to
    cursor.execute("""
        SELECT site_reference, name_address
        FROM brownfield_sites
        WHERE gss_code = %s AND year = %s
        AND site_reference NOT IN (
            SELECT site_reference FROM brownfield_sites
            WHERE gss_code = %s AND year = %s
        )
        ORDER BY site_reference
    """, (gss_code, year_from, gss_code, year_to))

    removed = [
        {'site_reference': row[0], 'name_address': row[1]}
        for row in cursor.fetchall()
    ]

    # Sites added — in year_to but not in year_from
    cursor.execute("""
        SELECT site_reference, name_address
        FROM brownfield_sites
        WHERE gss_code = %s AND year = %s
        AND site_reference NOT IN (
            SELECT site_reference FROM brownfield_sites
            WHERE gss_code = %s AND year = %s
        )
        ORDER BY site_reference
    """, (gss_code, year_to, gss_code, year_from))

    added = [
        {'site_reference': row[0], 'name_address': row[1]}
        for row in cursor.fetchall()
    ]

    cursor.close()

    return {
        'removed': removed,
        'added': added
    }