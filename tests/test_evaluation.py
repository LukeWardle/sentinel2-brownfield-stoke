"""
test_evaluation.py - Unit tests for the P1-2 evaluation harness.
================================================================
register_recall is tested against the real DB with rollback, using inserted
register and candidate rows in a far-future year so real data is never the
max-year and nothing persists. precision_from_labels is tested with
temporary CSVs.
"""

import csv

import pytest

from src.database_query import get_db_connection
from src.evaluation import precision_from_labels, register_recall

GSS = "E06000021"
TEST_YEAR = 2099
RUN_TS = "2099-06-01 12:00:00"
BASE_X, BASE_Y = 562000.0, 5872000.0


@pytest.fixture
def connection():
    conn = get_db_connection()
    yield conn
    conn.rollback()
    conn.close()


def _insert_register_site(connection, ref, utm_x, utm_y):
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO brownfield_sites
        (site_reference, gss_code, year, utm_x, utm_y, location)
        VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 32630))
        """,
        (ref, GSS, TEST_YEAR, utm_x, utm_y, utm_x, utm_y),
    )
    cursor.close()


def _insert_candidate(connection, utm_x, utm_y):
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO candidate_sites
        (gss_code, image_date, run_timestamp, utm_x, utm_y, pixel_count, bsi_value)
        VALUES (%s, '2099-06-01', %s, %s, %s, 10, 0.2)
        """,
        (GSS, RUN_TS, utm_x, utm_y),
    )
    cursor.close()


# --- register_recall ---
def test_register_recall_detects_nearby_candidate(connection):
    _insert_register_site(connection, "EVAL-1", BASE_X, BASE_Y)
    _insert_register_site(connection, "EVAL-2", BASE_X + 5000, BASE_Y)
    _insert_candidate(connection, BASE_X + 20, BASE_Y)  # within 100m of EVAL-1 only
    result = register_recall(GSS, connection, run_timestamp=RUN_TS)
    assert result["register_year"] == TEST_YEAR
    assert result["register_sites"] == 2
    assert result["detected"] == 1
    assert result["recall"] == 0.5


def test_register_recall_unknown_council_raises(connection):
    with pytest.raises(ValueError):
        register_recall("E99999999", connection)


# --- precision_from_labels ---
def _write_labels(tmp_path, rows):
    path = tmp_path / "labels.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "label", "fp_class", "notes"])
        writer.writerows(rows)
    return str(path)


def test_precision_counts_positive_labels(tmp_path):
    path = _write_labels(
        tmp_path,
        [
            [1, "sellable", "", ""],
            [2, "car-park", "car_park", ""],
            [3, "Sellable", "", "case-insensitive"],
            [4, "active-industrial", "industrial", ""],
        ],
    )
    result = precision_from_labels(path)
    assert result["labelled"] == 4
    assert result["positives"] == 2
    assert result["precision"] == 0.5


def test_precision_skips_unlabelled_rows(tmp_path):
    path = _write_labels(tmp_path, [[1, "sellable", "", ""], [2, "", "", ""]])
    result = precision_from_labels(path)
    assert result["labelled"] == 1
    assert result["precision"] == 1.0


def test_precision_all_unlabelled_raises(tmp_path):
    path = _write_labels(tmp_path, [[1, "", "", ""]])
    with pytest.raises(ValueError):
        precision_from_labels(path)


def test_precision_missing_label_column_raises(tmp_path):
    path = tmp_path / "bad.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["candidate_id", "notes"])
    with pytest.raises(ValueError):
        precision_from_labels(str(path))


def test_precision_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        precision_from_labels("does/not/exist.csv")
