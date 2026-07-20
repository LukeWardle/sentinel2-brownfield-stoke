"""
evaluation.py - Precision and recall evaluation harness (P1-2).
===============================================================
Two measurements, two sources of truth:

RECALL — the brownfield register is the standing validation set. For a
pipeline run, recall is the fraction of register sites (latest register
year) with at least one stored candidate within 100 m. This is the same
guardrail number the exclusion work is judged against, computed the same
way every run so changes are comparable over time.

PRECISION — the register cannot measure precision (unregistered candidates
are the product, and the register says nothing about them), so precision
comes from manual labels. scripts/export_labelling_sheet.py exports a run's
unregistered candidates to a CSV; a human labels each row per
docs/labelling_protocol.md; precision_from_labels reads the labelled CSV
back and computes the fraction labelled sellable.

Usage:
    python -m src.evaluation --gss_code E06000021
    python -m src.evaluation --gss_code E06000021 --labels outputs/labelling_sheet_E06000021.csv
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_query import get_db_connection

# Labels (lowercased) counted as a true positive when computing precision.
# "sellable" is the primary label from docs/labelling_protocol.md.
POSITIVE_LABELS = {"sellable", "brownfield", "tp", "true_positive", "yes"}


def register_recall(
    gss_code: str,
    connection,
    run_timestamp: str = None,
    distance_m: float = 100.0,
) -> dict:
    """
    Computes register recall for a pipeline run: the fraction of register
    sites (latest register year for the council) with at least one stored
    candidate from that run within distance_m.

    Args:
        gss_code (str): GSS code for the council.
        connection: Active psycopg2 connection.
        run_timestamp (str): Run to evaluate. Defaults to the council's most
                             recent run in candidate_sites.
        distance_m (float): Match radius in metres. Default 100 (matches
                            match_candidate_to_register).

    Returns:
        dict: run_timestamp, register_year, register_sites, detected, recall
              (0.0-1.0; 0.0 when the register is empty).

    Raises:
        ValueError: If no candidate runs exist for the council.
    """
    cursor = connection.cursor()

    if run_timestamp is None:
        cursor.execute(
            "SELECT MAX(run_timestamp) FROM candidate_sites WHERE gss_code = %s",
            (gss_code,),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            cursor.close()
            raise ValueError(f"No candidate runs stored for GSS code: {gss_code}")
        run_timestamp = row[0]

    cursor.execute(
        "SELECT MAX(year) FROM brownfield_sites WHERE gss_code = %s", (gss_code,)
    )
    year_row = cursor.fetchone()
    if year_row is None or year_row[0] is None:
        cursor.close()
        return {
            "run_timestamp": str(run_timestamp),
            "register_year": None,
            "register_sites": 0,
            "detected": 0,
            "recall": 0.0,
        }
    year = year_row[0]

    cursor.execute(
        "SELECT COUNT(*) FROM brownfield_sites WHERE gss_code = %s AND year = %s",
        (gss_code, year),
    )
    register_sites = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM brownfield_sites b
        WHERE b.gss_code = %s
          AND b.year = %s
          AND EXISTS (
              SELECT 1
              FROM candidate_sites c
              WHERE c.gss_code = b.gss_code
                AND c.run_timestamp = %s
                AND ST_DWithin(
                      b.location,
                      ST_SetSRID(ST_MakePoint(c.utm_x, c.utm_y), 32630),
                      %s
                    )
          )
        """,
        (gss_code, year, run_timestamp, distance_m),
    )
    detected = cursor.fetchone()[0]
    cursor.close()

    recall = (detected / register_sites) if register_sites else 0.0
    return {
        "run_timestamp": str(run_timestamp),
        "register_year": year,
        "register_sites": register_sites,
        "detected": detected,
        "recall": round(recall, 4),
    }


def precision_from_labels(labels_csv_path: str) -> dict:
    """
    Computes precision from a manually labelled candidate sheet. Reads the
    CSV produced by scripts/export_labelling_sheet.py after a human has
    filled the 'label' column per docs/labelling_protocol.md. Rows with an
    empty label are treated as unlabelled and excluded from the calculation.

    Args:
        labels_csv_path (str): Path to the labelled CSV. Must contain a
                               'label' column.

    Returns:
        dict: labelled (int), positives (int), precision (0.0-1.0).

    Raises:
        FileNotFoundError: If the CSV does not exist.
        ValueError: If the CSV has no 'label' column or no labelled rows.
    """
    path = Path(labels_csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Labels file not found: {labels_csv_path}")

    labelled = 0
    positives = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "label" not in reader.fieldnames:
            raise ValueError(
                f"No 'label' column in {labels_csv_path} — expected the sheet "
                f"produced by scripts/export_labelling_sheet.py"
            )
        for row in reader:
            label = (row.get("label") or "").strip().lower()
            if not label:
                continue
            labelled += 1
            if label in POSITIVE_LABELS:
                positives += 1

    if labelled == 0:
        raise ValueError(
            f"No labelled rows in {labels_csv_path} — fill the 'label' column "
            f"per docs/labelling_protocol.md before evaluating precision"
        )

    return {
        "labelled": labelled,
        "positives": positives,
        "precision": round(positives / labelled, 4),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="P1-2 evaluation harness")
    parser.add_argument("--gss_code", type=str, default="E06000021")
    parser.add_argument(
        "--run_timestamp",
        type=str,
        default=None,
        help="Run to evaluate (default: most recent run for the council)",
    )
    parser.add_argument(
        "--labels",
        type=str,
        default=None,
        help="Labelled CSV from scripts/export_labelling_sheet.py for precision",
    )
    args = parser.parse_args()

    connection = get_db_connection()
    try:
        rr = register_recall(
            args.gss_code, connection, run_timestamp=args.run_timestamp
        )
        print(f"Run: {rr['run_timestamp']}")
        print(
            f"Register recall: {rr['detected']} of {rr['register_sites']} "
            f"register sites ({rr['register_year']}) detected within 100m "
            f"= {rr['recall']:.1%}"
        )
        if args.labels:
            pr = precision_from_labels(args.labels)
            print(
                f"Labelled precision: {pr['positives']} of {pr['labelled']} "
                f"labelled candidates sellable = {pr['precision']:.1%}"
            )
        else:
            print(
                "Precision: no --labels supplied. Export a sheet with "
                "scripts/export_labelling_sheet.py, label it per "
                "docs/labelling_protocol.md, then re-run with --labels."
            )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
