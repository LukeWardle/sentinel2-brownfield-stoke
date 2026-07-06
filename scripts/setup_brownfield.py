"""
setup_brownfield.py - Annual script to load Stoke-on-Trent brownfield register into PostgreSQL
==============================================================================================
Loads all available years of the Stoke-on-Trent brownfield register from the data/ folder
into the brownfield_sites table in the sentinel2_brownfield PostgreSQL database.
Run once after database creation, then annually when a new register is published.

Usage: python scripts/setup_brownfield.py
"""
import os
import sys
import pandas as pd
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.coordinate_conversion_pixel import convert_bng_to_utm

REGISTER_FILES = {
    2019: PROJECT_ROOT / "data" / "brownfield_register_2019.csv",
    2020: PROJECT_ROOT / "data" / "brownfield_register_2020.csv",
    2021: PROJECT_ROOT / "data" / "brownfield_register_2021.csv",
    2022: PROJECT_ROOT / "data" / "brownfield_register_2022.xlsx",
    2023: PROJECT_ROOT / "data" / "brownfield_register_2023.csv",
    2024: PROJECT_ROOT / "data" / "brownfield_register_2024.csv",
}

GSS_CODE = sys.argv[1] if len(sys.argv) > 1 else "E06000021"


def connect_db():
    """Connects to PostgreSQL database using credentials from .env."""
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )


def load_register(year: int, filepath: Path, cursor, conn):
    """Loads a single year's brownfield register into the brownfield_sites table."""
    print(f"Loading {year} register from {filepath.name}...")

    df = pd.read_excel(filepath)
    count = 0
    errors = 0

    for idx, row in df.iterrows():
        try:
            utm = convert_bng_to_utm(row['GeoX'], row['GeoY'])

            cursor.execute("""
                INSERT INTO brownfield_sites 
                (site_reference, gss_code, year, name_address, utm_x, utm_y, hectares, planning_status, location)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 32630))
            """, (
                str(row.get('SiteReference', '')),
                GSS_CODE,
                year,
                str(row.get('SiteNameAddress', '')),
                utm['x'],
                utm['y'],
                float(row['Hectares']) if pd.notna(row.get('Hectares')) else None,
                str(row.get('PlanningStatus', '')),
                utm['x'],
                utm['y']
            ))

            conn.commit()
            count += 1

        except Exception as e:
            print(f"  Error loading site {row.get('SiteReference', 'unknown')}: {e}")
            conn.rollback()
            errors += 1

    print(f"  {year}: {count} sites loaded, {errors} errors")
    return count, errors


def load_all_registers():
    """Loads all available years of the brownfield register."""
    conn = connect_db()
    cursor = conn.cursor()
    print("Connected to database successfully")

    total_count = 0
    total_errors = 0

    for year, filepath in REGISTER_FILES.items():
        if filepath.exists():
            count, errors = load_register(year, filepath, cursor, conn)
            total_count += count
            total_errors += errors
        else:
            print(f"Skipping {year} — file not found: {filepath.name}")

    cursor.close()
    conn.close()
    print(f"\nComplete — {total_count} sites loaded across all years, {total_errors} errors")


if __name__ == "__main__":
    load_all_registers()