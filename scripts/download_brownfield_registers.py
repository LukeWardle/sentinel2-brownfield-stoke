"""
download_brownfield_registers.py - Downloads UK brownfield register data
========================================================================
Downloads brownfield land data from the planning.data.gov.uk API for a
specific council (by GSS code) or all UK councils. Uses the planning.data.gov.uk
entity API which provides structured access to aggregated brownfield registers
updated daily across 354 local authorities.

Usage:
    python scripts/download_brownfield_registers.py              — loads all councils
    python scripts/download_brownfield_registers.py E06000021    — loads Stoke only

Source: https://www.planning.data.gov.uk/dataset/brownfield-land
Licence: Open Government Licence v3.0
"""
import os
import sys
import requests
import psycopg2
from pyproj import Transformer
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "https://www.planning.data.gov.uk"


def connect_db():
    """Connects to PostgreSQL database using credentials from .env."""
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )


def get_lpa_entity_id_for_gss(gss_code: str) -> int | None:
    """
    Fetches the planning.data.gov.uk local-planning-authority entity ID
    for a given GSS code.

    Args:
        gss_code (str): GSS code e.g. 'E06000021' for Stoke-on-Trent.

    Returns:
        int | None: LPA entity ID if found, None if not found.
    """
    # Step 1 — find the local-authority entity and its linked LPA reference
    la_url = f"{BASE_URL}/entity.json?dataset=local-authority&field=entity&field=statistical-geography&field=local-planning-authority&limit=500"
    la_response = requests.get(la_url, timeout=30)

    if la_response.status_code != 200:
        raise ValueError(f"Local authority lookup failed — status code {la_response.status_code}")

    lpa_reference = None
    for entity in la_response.json().get('entities', []):
        if entity.get('statistical-geography') == gss_code:
            lpa_reference = entity.get('local-planning-authority')
            break

    if not lpa_reference:
        return None

    # Step 2 — find the LPA entity ID using the LPA reference
    lpa_url = f"{BASE_URL}/entity.json?dataset=local-planning-authority&reference={lpa_reference}&field=entity&limit=10"
    lpa_response = requests.get(lpa_url, timeout=30)

    if lpa_response.status_code != 200:
        raise ValueError(f"LPA lookup failed — status code {lpa_response.status_code}")

    entities = lpa_response.json().get('entities', [])
    if not entities:
        return None

    return entities[0].get('entity')


def fetch_brownfield_sites(lpa_entity_id: int) -> list:
    """
    Fetches all brownfield sites for a council.
    First gets the total count, then fetches all in one request.
    """
    # Get total count first
    count_url = f"{BASE_URL}/entity.json?dataset=brownfield-land&geometry_entity={lpa_entity_id}&limit=1"
    count_response = requests.get(count_url, timeout=30)
    if count_response.status_code != 200:
        return []
    total = count_response.json().get('count', 0)
    print(f"  Total sites: {total}")

    if total == 0:
        return []

    # Fetch all sites in one request using exact count as limit
    # Max safe limit is 100 — paginate if needed
    if total <= 100:
        url = f"{BASE_URL}/entity.json?dataset=brownfield-land&geometry_entity={lpa_entity_id}&limit={total}"
        response = requests.get(url, timeout=60)
        if response.status_code != 200:
            return []
        return response.json().get('entities', [])
    else:
        # Multiple requests needed — use offset pagination
        all_sites = []
        fetched = 0
        while fetched < total:
            url = f"{BASE_URL}/entity.json?dataset=brownfield-land&geometry_entity={lpa_entity_id}&limit=100&offset={fetched}"
            response = requests.get(url, timeout=60)
            if response.status_code != 200:
                break
            sites = response.json().get('entities', [])
            if not sites:
                break
            all_sites.extend(sites)
            fetched += len(sites)
            print(f"  Fetched {fetched}/{total}")
        return all_sites

def parse_point(point_str: str):
    """
    Parses a WGS84 POINT string into (longitude, latitude) floats.
    Returns None if parsing fails.
    """
    try:
        point_str = str(point_str).strip()
        if not point_str or point_str in ('nan', 'None', ''):
            return None
        point_str = point_str.replace('POINT (', '').replace('POINT(', '').replace(')', '').strip()
        parts = point_str.split()
        if len(parts) != 2:
            return None
        return float(parts[0]), float(parts[1])
    except (ValueError, AttributeError):
        return None


def load_sites_into_database(sites: list, gss_code: str, cursor, conn) -> tuple:
    """
    Loads brownfield sites into the brownfield_sites table.

    Args:
        sites (list): List of site dicts from planning.data.gov.uk API.
        gss_code (str): GSS code for the council area.
        cursor: Active psycopg2 cursor.
        conn: Active psycopg2 connection.

    Returns:
        tuple: (count, errors)

    Raises:
        ValueError: If sites list is empty.
    """
    if not sites:
        return 0, 0

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32630", always_xy=True)
    year = datetime.now().year
    count = 0
    errors = 0
    first_error = True

    for site in sites:
        try:
            point = parse_point(site.get('point', ''))
            if point is None:
                errors += 1
                continue

            lon, lat = point
            utm_x, utm_y = transformer.transform(lon, lat)

            cursor.execute("""
                INSERT INTO brownfield_sites
                (site_reference, gss_code, year, name_address, utm_x, utm_y,
                 hectares, planning_status, location)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                        ST_SetSRID(ST_MakePoint(%s, %s), 32630))
                ON CONFLICT DO NOTHING
            """, (
                str(site.get('reference', '')),
                gss_code,
                year,
                str(site.get('site-address', site.get('name', ''))),
                utm_x,
                utm_y,
                float(site['hectares']) if site.get('hectares') else None,
                str(site.get('planning-permission-status', '')),
                utm_x,
                utm_y
            ))

            conn.commit()
            count += 1

        except Exception as e:
            conn.rollback()
            errors += 1
            if first_error:
                print(f"  First error: {e}")
                first_error = False

    return count, errors


if __name__ == "__main__":
    gss_code_filter = sys.argv[1] if len(sys.argv) > 1 else None

    conn = connect_db()
    cursor = conn.cursor()
    total_count = 0
    total_errors = 0

    try:
        if gss_code_filter:
            # Single council mode
            print(f"Fetching brownfield data for GSS code: {gss_code_filter}")
            lpa_entity_id = get_lpa_entity_id_for_gss(gss_code_filter)

            if lpa_entity_id is None:
                raise ValueError(f"No LPA entity found for GSS code: {gss_code_filter}")

            print(f"LPA Entity ID: {lpa_entity_id}")
            sites = fetch_brownfield_sites(lpa_entity_id)
            count, errors = load_sites_into_database(sites, gss_code_filter, cursor, conn)
            total_count += count
            total_errors += errors
            print(f"Loaded {count} sites, {errors} errors")

        else:
            # All councils mode
            print("Fetching all local planning authorities...")
            lpa_url = f"{BASE_URL}/entity.json?dataset=local-planning-authority&limit=500&field=entity&field=reference&field=name"
            lpa_response = requests.get(lpa_url, timeout=30)

            if lpa_response.status_code != 200:
                raise ValueError(f"LPA list fetch failed — status code {lpa_response.status_code}")

            lpas = lpa_response.json().get('entities', [])
            print(f"Found {len(lpas)} LPAs")

            # Get known GSS codes from database
            cursor.execute("SELECT gss_code FROM council_boundaries")
            known_gss = {row[0] for row in cursor.fetchall()}

            # Build LPA reference to GSS code lookup
            la_url = f"{BASE_URL}/entity.json?dataset=local-authority&field=statistical-geography&field=local-planning-authority&limit=500"
            la_response = requests.get(la_url, timeout=30)
            lpa_ref_to_gss = {}

            for entity in la_response.json().get('entities', []):
                gss = entity.get('statistical-geography', '')
                lpa_ref = entity.get('local-planning-authority', '')
                if gss and lpa_ref and gss in known_gss:
                    lpa_ref_to_gss[lpa_ref] = gss

            for lpa in lpas:
                lpa_ref = lpa.get('reference', '')
                lpa_entity_id = lpa.get('entity')
                gss = lpa_ref_to_gss.get(lpa_ref)

                if not gss or not lpa_entity_id:
                    continue

                print(f"Processing {gss}...")
                sites = fetch_brownfield_sites(lpa_entity_id)
                count, errors = load_sites_into_database(sites, gss, cursor, conn)
                total_count += count
                total_errors += errors

                if count > 0:
                    print(f"  {gss}: {count} sites loaded")

        if total_count == 0:
            raise ValueError(
                "Zero sites loaded — check GSS code is valid and "
                "council boundary exists in the database"
            )

        print(f"\nComplete — {total_count} sites loaded, {total_errors} errors")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    finally:
        cursor.close()
        conn.close()