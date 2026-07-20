"""
export_labelling_sheet.py - Export a run's unregistered candidates for labelling.
=================================================================================
P1-1 tooling. Exports the unregistered candidates (no register match) from a
pipeline run to a CSV with one row per candidate: database id, UTM and
lat/lon coordinates, size, mean BSI and a Google Maps link — plus empty
label / fp_class / notes columns for the human labeller to fill per
docs/labelling_protocol.md. The labelled sheet feeds
src/evaluation.py precision_from_labels (P1-2).

The labelling itself is manual by design: the protocol requires aerial and
street-level inspection that only a human can do defensibly.

Usage:
    python scripts/export_labelling_sheet.py E06000021
    python scripts/export_labelling_sheet.py E06000021 "2026-07-20 02:29:12"
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pyproj import Transformer

from src.database_query import get_db_connection

# EPSG:32630 -> WGS84 for map links. always_xy so output is (lon, lat).
TRANSFORMER_UTM_TO_WGS84 = Transformer.from_crs(
    "EPSG:32630", "EPSG:4326", always_xy=True
)

LABEL_COLUMNS = ["label", "fp_class", "notes"]


def export_labelling_sheet(gss_code: str, run_timestamp: str = None) -> str:
    """
    Writes the labelling sheet CSV for a run's unregistered candidates and
    returns its path. Defaults to the council's most recent run.
    """
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        if run_timestamp is None:
            cursor.execute(
                "SELECT MAX(run_timestamp) FROM candidate_sites WHERE gss_code = %s",
                (gss_code,),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise ValueError(f"No candidate runs stored for GSS code: {gss_code}")
            run_timestamp = row[0]

        cursor.execute(
            """
            SELECT id, utm_x, utm_y, pixel_count, bsi_value
            FROM candidate_sites
            WHERE gss_code = %s
              AND run_timestamp = %s
              AND matched_site_reference IS NULL
            ORDER BY id
            """,
            (gss_code, run_timestamp),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    if not rows:
        raise ValueError(
            f"No unregistered candidates for {gss_code} in run {run_timestamp}"
        )

    output_dir = Path(__file__).parent.parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"labelling_sheet_{gss_code}_{stamp}.csv"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "candidate_id",
                "utm_x",
                "utm_y",
                "latitude",
                "longitude",
                "hectares",
                "mean_bsi",
                "google_maps",
            ]
            + LABEL_COLUMNS
        )
        for cand_id, utm_x, utm_y, pixel_count, bsi_value in rows:
            lon, lat = TRANSFORMER_UTM_TO_WGS84.transform(utm_x, utm_y)
            writer.writerow(
                [
                    cand_id,
                    round(utm_x, 2),
                    round(utm_y, 2),
                    round(lat, 6),
                    round(lon, 6),
                    round((pixel_count or 0) * 0.04, 2),
                    round(bsi_value, 4) if bsi_value is not None else "",
                    f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}",
                    "",
                    "",
                    "",
                ]
            )

    print(f"Wrote {len(rows)} unregistered candidates to {out_path}")
    print(
        "Label each row per docs/labelling_protocol.md (label column: "
        "sellable / non-sellable class), then evaluate with:"
    )
    print(f"  python -m src.evaluation --gss_code {gss_code} --labels {out_path}")
    return str(out_path)


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/export_labelling_sheet.py <GSS_CODE> [run_timestamp]"
        )
        sys.exit(1)
    gss_code = sys.argv[1]
    run_timestamp = sys.argv[2] if len(sys.argv) > 2 else None
    export_labelling_sheet(gss_code, run_timestamp)


if __name__ == "__main__":
    main()
