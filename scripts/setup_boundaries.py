"""
setup_boundaries.py - One-time setup script to load UK council boundaries into PostgreSQL
==========================================================================================
Loads all 358 UK local authority boundaries from the GeoJSON file into the
council_boundaries table in the sentinel2_brownfield PostgreSQL database.
Run once after database creation, or whenever the boundary file is updated.

Usage: python scripts/setup_boundaries.py
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

import ijson
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database_query import get_db_connection

load_dotenv()

BOUNDARY_FILE = PROJECT_ROOT / "data" / "uk_local_authority_boundaries.geojson"


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts Decimal objects to float.
    Required because ijson returns coordinate values as Decimal, not float."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def load_boundaries():
    """Loads all UK council boundaries from GeoJSON into council_boundaries table."""
    conn = get_db_connection()
    cursor = conn.cursor()

    print("Connected to database successfully")
    print(f"Loading boundaries from {BOUNDARY_FILE}")

    count = 0
    errors = 0

    with open(BOUNDARY_FILE, "rb") as f:
        for feature in ijson.items(f, "features.item"):
            try:
                props = feature["properties"]
                gss_code = props["LAD24CD"]
                name = props["LAD24NM"]
                geometry_json = json.dumps(feature["geometry"], cls=DecimalEncoder)

                cursor.execute(
                    """
                    INSERT INTO council_boundaries (gss_code, name, boundary)
                    VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                """,
                    (gss_code, name, geometry_json),
                )

                conn.commit()
                count += 1
                if count % 50 == 0:
                    print(f"Loaded {count} boundaries...")

            except Exception as e:
                print(f"Error loading {props.get('LAD24CD', 'unknown')}: {e}")
                conn.rollback()
                errors += 1

    cursor.close()
    conn.close()

    print(f"Complete — {count} boundaries loaded, {errors} errors")


if __name__ == "__main__":
    load_boundaries()
