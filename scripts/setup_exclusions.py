"""
setup_exclusions.py - One-time load of OSM exclusion zones for a council
========================================================================
Populates the exclusion_zones table for a given council by fetching land-use
polygons from OpenStreetMap (P1-5). Run once per council; the masking step
then reads the stored polygons on every pipeline run.

Usage:
    python scripts/setup_exclusions.py E06000021
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_query import get_db_connection
from src.exclusion_loader import load_exclusions_for_council


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/setup_exclusions.py <GSS_CODE>")
        sys.exit(1)
    gss_code = sys.argv[1]
    connection = get_db_connection()
    try:
        counts = load_exclusions_for_council(gss_code, connection)
        total = sum(counts.values())
        print(f"Loaded {total} exclusion polygons for {gss_code}:")
        for exclusion_class, count in counts.items():
            print(f"  {exclusion_class}: {count}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
