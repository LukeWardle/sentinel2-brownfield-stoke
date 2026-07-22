"""
evaluation.py - Register-recall and labelled-precision evaluation (P1-1/P1-2).
==============================================================================
Measures detection quality against the two ground-truth sources available:

1. The brownfield register (recall): what fraction of register sites for the
   most recent loaded year have at least one matched candidate in the latest
   pipeline run. This answers "does the detector find known brownfield when
   it is bare?" — the definitional ceiling documented in EDA 04 (most
   register sites are vegetated) means this number is expected to be low
   for a bare-soil detector and must be read alongside it.

2. A human-labelled CSV (precision): what fraction of labelled unregistered
   candidates a human marked as genuine/sellable. Produced by labelling the
   sheet exported with scripts/export_labelling_sheet.py.

P1-2 report artifact: metrics_report() computes register recall, register
precision, their F1, labelled precision where a labels CSV exists, and a
precision-recall curve over candidate mean-BSI scores, then writes a JSON
metrics file and a PR-curve PNG into an output directory. Honest caveats,
also embedded in the JSON:
- Register precision counts a candidate as a true positive only if it
  matched a register site. Unregistered candidates are NOT necessarily
  false positives — finding them is the product — so register precision is
  a floor, not the product metric. The product precision is the labelled
  precision from P1-1.
- The PR curve ranks candidates by mean BSI (the only stored per-site
  score) against register-match labels. It shows whether bareness intensity
  ranks register sites above other candidates — EDA 07 found it barely
  does, which is itself a finding worth recording as the baseline.

Usage:
    python -m src.evaluation --gss_code E06000021
    python -m src.evaluation --gss_code E06000021 --labels labels.csv
    python -m src.evaluation --gss_code E06000021 --report --out_dir outputs
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_query import get_db_connection


def register_recall(
    gss_code: str,
    connection,
    run_timestamp: str | None = None,
    distance_m: float = 100.0,
) -> dict:
    """
    Computes recall of a pipeline run against the most recent register year
    loaded for the council: the fraction of register sites that have at
    least one candidate within distance_m. Matching is computed live via
    ST_DWithin against the candidate centroids, so it does not depend on
    candidate_sites.matched_site_reference having been populated.

    Args:
        gss_code (str): GSS code for the council area.
        connection: Active psycopg2 connection.
        run_timestamp (str | None): The run to evaluate. When None, the
            latest stored run for the GSS code is used.
        distance_m (float): Match radius in metres. Default 100.

    Returns:
        dict: register_year, register_sites, detected (register sites with
              >=1 candidate within distance_m), recall (0.0-1.0), and the
              run_timestamp evaluated.

    Raises:
        ValueError: If no register data or no candidate runs exist for the
                    GSS code.
    """
    cursor = connection.cursor()

    cursor.execute(
        "SELECT MAX(year) FROM brownfield_sites WHERE gss_code = %s", (gss_code,)
    )
    row = cursor.fetchone()
    if row is None or row[0] is None:
        cursor.close()
        raise ValueError(f"No register data loaded for GSS code {gss_code}")
    register_year = row[0]

    if run_timestamp is None:
        cursor.execute(
            "SELECT MAX(run_timestamp) FROM candidate_sites WHERE gss_code = %s",
            (gss_code,),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            cursor.close()
            raise ValueError(f"No candidate runs stored for GSS code {gss_code}")
        run_timestamp = row[0]

    cursor.execute(
        "SELECT COUNT(*) FROM brownfield_sites WHERE gss_code = %s AND year = %s",
        (gss_code, register_year),
    )
    register_sites = cursor.fetchone()[0]

    # A register site is "detected" if any candidate from this run lies
    # within distance_m of it — computed live, independent of the stored
    # matched_site_reference column.
    cursor.execute(
        """
        SELECT COUNT(*) FROM brownfield_sites r
        WHERE r.gss_code = %s AND r.year = %s
          AND EXISTS (
            SELECT 1 FROM candidate_sites c
            WHERE c.gss_code = %s
              AND c.run_timestamp = %s
              AND ST_DWithin(
                    ST_SetSRID(ST_MakePoint(c.utm_x, c.utm_y), 32630),
                    ST_SetSRID(ST_MakePoint(r.utm_x, r.utm_y), 32630),
                    %s
                  )
          )
        """,
        (gss_code, register_year, gss_code, run_timestamp, distance_m),
    )
    detected = cursor.fetchone()[0]
    cursor.close()

    recall = detected / register_sites if register_sites else 0.0
    return {
        "register_year": register_year,
        "register_sites": register_sites,
        "detected": detected,
        "recall": recall,
        "run_timestamp": str(run_timestamp),
    }


def precision_from_labels(labels_csv: str) -> dict:
    """
    Computes precision of unregistered candidates from a human-labelled CSV
    produced by labelling the export from scripts/export_labelling_sheet.py.
    The sheet's 'label' column holds the labeller's decision per
    docs/labelling_protocol.md: 'sellable' marks a genuine sellable lead
    (a positive); any other non-empty value is a false-positive class
    (car_park, active-industrial, agriculture, ...). Blank rows are
    unlabelled and excluded from the denominator.

    Precision is therefore positives / all-labelled-rows — the fraction of
    labelled candidates that are genuine sellable leads. This is the
    product precision metric (P1-1), distinct from register precision.

    Args:
        labels_csv (str): Path to the labelled CSV file.

    Returns:
        dict: labelled (non-blank rows), positives (sellable, case-
              insensitive), precision (positives / labelled).

    Raises:
        ValueError: If the file has no 'label' column, or no labelled rows.
    """
    labelled = 0
    positives = 0

    with open(labels_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "label" not in reader.fieldnames:
            raise ValueError(f"{labels_csv} has no 'label' column")
        for row in reader:
            label = (row.get("label") or "").strip().lower()
            if label == "":
                continue
            labelled += 1
            if label == "sellable":
                positives += 1

    if labelled == 0:
        raise ValueError(f"No labelled rows in {labels_csv}")

    return {
        "labelled": labelled,
        "positives": positives,
        "precision": positives / labelled,
    }


def _pr_curve_from_scores(scores: list, labels: list) -> dict:
    """
    Computes precision-recall pairs by sweeping a threshold over candidate
    scores (descending). labels are 1 for register-matched, 0 otherwise.
    Pure-python/numpy-free so it stays dependency-light and exact for the
    small candidate counts involved.

    Returns:
        dict: thresholds, precision, recall (parallel lists) and pr_auc
              (trapezoidal area over recall).
    """
    paired = sorted(zip(scores, labels), key=lambda t: t[0], reverse=True)
    total_pos = sum(labels)
    precisions, recalls, thresholds = [], [], []
    tp = 0
    fp = 0
    for score, label in paired:
        if label == 1:
            tp += 1
        else:
            fp += 1
        thresholds.append(score)
        precisions.append(tp / (tp + fp))
        recalls.append(tp / total_pos if total_pos else 0.0)

    # Trapezoidal PR-AUC over recall. Seed with a (recall=0, precision of
    # the first point) anchor so the area from the origin to the first
    # threshold is counted — without it a perfect ranking scores 0.5, not 1.
    auc = 0.0
    prev_recall = 0.0
    prev_precision = precisions[0] if precisions else 0.0
    for i in range(len(recalls)):
        auc += (recalls[i] - prev_recall) * (precisions[i] + prev_precision) / 2
        prev_recall = recalls[i]
        prev_precision = precisions[i]

    return {
        "thresholds": thresholds,
        "precision": precisions,
        "recall": recalls,
        "pr_auc": auc,
    }


def metrics_report(
    gss_code: str, connection, labels_csv: str | None = None, out_dir: str = "outputs"
) -> dict:
    """
    P1-2 report artifact. Computes the full metric set for the latest run
    and writes two files into out_dir:
    - metrics_{gss}_{timestamp}.json — all metrics plus caveats
    - pr_curve_{gss}_{timestamp}.png — PR curve of mean-BSI score vs
      register-match label (skipped, with a note, when the run has no
      matched candidates or no unmatched candidates, since a curve needs
      both classes)

    Register-referenced metrics:
    - register_recall: distinct register sites matched / register sites
    - register_precision: matched candidates / total candidates
    - register_f1: harmonic mean of the two (both reference the register,
      so the combination is coherent — but see the caveat: unregistered
      candidates are the product, not automatically false positives)

    Labelled metric (when labels_csv given): labelled precision via
    precision_from_labels.

    Args:
        gss_code (str): GSS code for the council area.
        connection: Active psycopg2 connection.
        labels_csv (str | None): Optional labelled CSV for P1-1 precision.
        out_dir (str): Directory to write the JSON and PNG artifacts into.

    Returns:
        dict: The full metrics payload that was written to JSON, with an
              added 'json_path' and 'plot_path' (plot_path None when the
              curve was skipped).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    recall_stats = register_recall(gss_code, connection)

    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT bsi_value, (matched_site_reference IS NOT NULL)::int
        FROM candidate_sites
        WHERE gss_code = %s AND run_timestamp = %s
        ORDER BY id
        """,
        (gss_code, recall_stats["run_timestamp"]),
    )
    rows = cursor.fetchall()
    cursor.close()

    scores = [float(r[0]) for r in rows]
    match_flags = [int(r[1]) for r in rows]
    total_candidates = len(rows)
    matched_candidates = sum(match_flags)

    register_precision = (
        matched_candidates / total_candidates if total_candidates else 0.0
    )
    r = recall_stats["recall"]
    p = register_precision
    register_f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

    payload = {
        "gss_code": gss_code,
        "generated": stamp,
        "run_timestamp": recall_stats["run_timestamp"],
        "register_year": recall_stats["register_year"],
        "total_candidates": total_candidates,
        "matched_candidates": matched_candidates,
        "unmatched_candidates": total_candidates - matched_candidates,
        "register_recall": recall_stats["recall"],
        "register_precision": register_precision,
        "register_f1": register_f1,
        "caveats": [
            "Register precision treats unregistered candidates as non-matches, "
            "not as false positives — unregistered finds are the product. The "
            "product precision metric is labelled_precision (P1-1).",
            "The detector finds currently-bare land only; most register sites "
            "are vegetated (EDA 04), so register recall has a definitional "
            "ceiling and is a sanity floor, not a target.",
            "PR curve scores candidates by mean BSI, the only stored per-site "
            "score. EDA 07 found near-zero separation between matched and "
            "unmatched candidates on this feature; a flat curve is the "
            "expected baseline, recorded as the number to beat.",
            "Counts are provisional pending min_pixels calibration (#89) and "
            "multi-date persistence (#92).",
        ],
    }

    if labels_csv:
        payload["labelled"] = precision_from_labels(labels_csv)

    plot_path = None
    if 0 < matched_candidates < total_candidates:
        curve = _pr_curve_from_scores(scores, match_flags)
        payload["pr_auc_bsi_score"] = curve["pr_auc"]

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(curve["recall"], curve["precision"], marker=".", color="#2980b9")
        ax.axhline(
            register_precision,
            linestyle="--",
            color="grey",
            label=f"Prevalence baseline ({register_precision:.2f})",
        )
        ax.set_xlabel("Recall (register-matched candidates)")
        ax.set_ylabel("Precision")
        ax.set_title(
            f"PR curve — mean-BSI score vs register match\n"
            f"{gss_code}, run {payload['run_timestamp']}, "
            f"AUC {curve['pr_auc']:.3f}"
        )
        ax.set_xlim(0, 1.02)
        ax.set_ylim(0, 1.02)
        ax.legend()
        fig.tight_layout()
        plot_path = str(out / f"pr_curve_{gss_code}_{stamp}.png")
        fig.savefig(plot_path, dpi=150)
        plt.close(fig)
    else:
        payload["pr_curve_skipped"] = (
            "PR curve needs both matched and unmatched candidates in the run; "
            f"this run has {matched_candidates} matched of {total_candidates}."
        )

    json_path = str(out / f"metrics_{gss_code}_{stamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    payload["json_path"] = json_path
    payload["plot_path"] = plot_path
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate detection against register and labelled ground truth"
    )
    parser.add_argument("--gss_code", type=str, default="E06000021")
    parser.add_argument(
        "--labels",
        type=str,
        default=None,
        help="Path to a labelled CSV (from scripts/export_labelling_sheet.py)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="P1-2: write metrics JSON + PR-curve PNG artifacts to --out_dir",
    )
    parser.add_argument("--out_dir", type=str, default="outputs")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.report:
            result = metrics_report(args.gss_code, conn, args.labels, args.out_dir)
            print(f"Register recall:    {result['register_recall']:.1%}")
            print(f"Register precision: {result['register_precision']:.1%}")
            print(f"Register F1:        {result['register_f1']:.3f}")
            if "labelled" in result:
                print(f"Labelled precision: {result['labelled']['precision']:.1%}")
            if result.get("plot_path"):
                print(f"PR curve:           {result['plot_path']}")
            print(f"Metrics JSON:       {result['json_path']}")
        else:
            stats = register_recall(args.gss_code, conn)
            print(
                f"Register recall ({stats['register_year']}): "
                f"{stats['detected']}/{stats['register_sites']} "
                f"= {stats['recall']:.1%}  (run {stats['run_timestamp']})"
            )
            if args.labels:
                lab = precision_from_labels(args.labels)
                print(
                    f"Labelled precision: {lab['positives']}/{lab['labelled']} "
                    f"= {lab['precision']:.1%}"
                )
    finally:
        conn.close()
