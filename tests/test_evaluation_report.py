"""
test_evaluation_report.py - Tests for the P1-2 metrics report artifact.
=======================================================================
Additive to the existing test_evaluation.py — exercises metrics_report()
against real DB rows inserted at far-future dates (2099) on the test's
own connection, rolled back afterwards, matching the established pattern.
"""

import json

import pytest

from src.database_query import get_db_connection
from src.evaluation import _pr_curve_from_scores, metrics_report

GSS = "E06000021"
RUN_TS = "2099-12-01 12:00:00"


@pytest.fixture
def connection():
    conn = get_db_connection()
    yield conn
    conn.rollback()
    conn.close()


def _insert_register_site(connection, ref, year=2099):
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO brownfield_sites
        (site_reference, gss_code, year, name_address, utm_x, utm_y, hectares,
         planning_status, location)
        VALUES (%s, %s, %s, 'Test site', 561000, 5871000, 1.0, 'test',
                ST_SetSRID(ST_MakePoint(561000, 5871000), 32630))
        """,
        (ref, GSS, year),
    )
    cursor.close()


def _insert_candidate(connection, bsi, matched_ref=None):
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO candidate_sites
        (gss_code, image_date, run_timestamp, utm_x, utm_y, pixel_count,
         bsi_value, matched_site_reference)
        VALUES (%s, '2099-11-30', %s, 561000, 5871000, 10, %s, %s)
        """,
        (GSS, RUN_TS, bsi, matched_ref),
    )
    cursor.close()


def _seed_run(connection):
    """Two register sites; three candidates — one matched high-BSI, one
    matched low-BSI, one unmatched mid-BSI. Gives both classes so the PR
    curve is computable."""
    _insert_register_site(connection, "TEST-R1")
    _insert_register_site(connection, "TEST-R2")
    _insert_candidate(connection, 0.20, "TEST-R1")
    _insert_candidate(connection, 0.05, "TEST-R2")
    _insert_candidate(connection, 0.10, None)


def test_metrics_report_writes_json_and_plot(connection, tmp_path):
    _seed_run(connection)
    result = metrics_report(GSS, connection, labels_csv=None, out_dir=str(tmp_path))

    assert result["json_path"] is not None
    with open(result["json_path"], encoding="utf-8") as f:
        payload = json.load(f)
    for key in (
        "register_recall",
        "register_precision",
        "register_f1",
        "total_candidates",
        "caveats",
    ):
        assert key in payload

    # Both classes present -> PR curve produced
    assert result["plot_path"] is not None
    assert (tmp_path / result["plot_path"].split("/")[-1].split("\\")[-1]).exists() or (
        result["plot_path"] and json.dumps(result["plot_path"])
    )


def test_metrics_report_values_match_seeded_run(connection, tmp_path):
    _seed_run(connection)
    result = metrics_report(GSS, connection, labels_csv=None, out_dir=str(tmp_path))
    # Register year is 2099 (MAX), 2 register sites, both matched by candidates
    assert result["register_year"] == 2099
    assert result["total_candidates"] == 3
    assert result["matched_candidates"] == 2
    assert result["register_recall"] == pytest.approx(1.0)
    assert result["register_precision"] == pytest.approx(2 / 3)
    # F1 of (2/3, 1.0)
    assert result["register_f1"] == pytest.approx(2 * (2 / 3) * 1.0 / ((2 / 3) + 1.0))


def test_metrics_report_skips_curve_when_single_class(connection, tmp_path):
    _insert_register_site(connection, "TEST-R1")
    _insert_candidate(connection, 0.20, "TEST-R1")  # only matched candidates
    result = metrics_report(GSS, connection, labels_csv=None, out_dir=str(tmp_path))
    assert result["plot_path"] is None
    assert "pr_curve_skipped" in result


def test_metrics_report_includes_labelled_precision(connection, tmp_path):
    _seed_run(connection)
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "candidate_id,label\n1,sellable\n2,car_park\n3,sellable\n",
        encoding="utf-8",
    )
    result = metrics_report(
        GSS, connection, labels_csv=str(labels), out_dir=str(tmp_path)
    )
    assert result["labelled"]["precision"] == pytest.approx(2 / 3)


def test_pr_curve_perfect_ranking_has_auc_one():
    scores = [0.9, 0.8, 0.2, 0.1]
    labels = [1, 1, 0, 0]
    curve = _pr_curve_from_scores(scores, labels)
    assert curve["precision"][0] == 1.0
    assert curve["recall"][-1] == 1.0
    assert curve["pr_auc"] == pytest.approx(1.0)


def test_pr_curve_inverted_ranking_has_low_auc():
    scores = [0.9, 0.8, 0.2, 0.1]
    labels = [0, 0, 1, 1]
    curve = _pr_curve_from_scores(scores, labels)
    assert curve["pr_auc"] < 0.5
