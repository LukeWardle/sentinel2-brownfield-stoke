"""
model_train.py - v3 Random Forest training, calibration and scoring
(P1-6, P1-7).
====================================================================
Trains a per-council classifier that re-ranks threshold-gated candidates
(fork A of the Notebook 07 architecture decision), persists it to
council_models, and writes a calibrated confidence per candidate.

WHAT THIS CANNOT DO YET — read before running:
- Training requires the P1-1 labelled ground truth (a CSV with
  candidate_id + label columns; 'sellable' marks a positive, any other
  joined to candidate rows that already carry the migration-004 feature
  non-empty value is a false-positive class. Until those labels exist,
  --train exits with a clear error;
  there is nothing to train on. The 19/19 all-false-positive pilot cannot
  train a model (single class).
- This is the fork-A re-ranker: its honest job is precision on bare-land
  leads, and it is the model half of the "does a model beat a simple
  persistence rule?" comparison. It cannot recover vegetated register
  sites and its register recall is capped by the threshold gate.

Training design:
- X = MODEL_INPUT_COLUMNS from src.features (10 columns; pixel_count and
  bsi_value plus the 8 stored features), y = 1 for 'sellable'.
- Stratified train/test split (25% test, fixed seed) BEFORE any fitting.
- RandomForest wrapped in CalibratedClassifierCV (P1-7): isotonic when
  the training set is large enough (>=100 rows), sigmoid/Platt otherwise
  — isotonic overfits badly on tiny samples.
- Test-set precision/recall/accuracy stored to council_models alongside
  the pickled calibrated model; a reliability (calibration) curve PNG is
  written for the documented calibration check.
- Small-sample guardrails: refuses to train with <10 positives; warns
  loudly under 30.

Scoring (--score): loads the newest council model, computes
predict_proba for the latest run's candidates from their stored feature
columns, and UPDATEs candidate_sites.confidence.

Usage:
    python -m src.model_train --train --gss_code E06000021 --labels labels.csv
    python -m src.model_train --score --gss_code E06000021
"""

import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_query import get_db_connection
from src.features import MODEL_INPUT_COLUMNS

TEST_FRACTION = 0.25
RANDOM_SEED = 42
MIN_POSITIVES = 10
WARN_POSITIVES = 30
ISOTONIC_MIN_ROWS = 100


def load_training_frame(gss_code: str, connection, labels_csv: str) -> tuple:
    """
    Joins the labelled CSV (candidate_id, label) to candidate_sites feature
    columns. 'unsure' rows are excluded. Rows with any NULL feature are
    dropped with a warning (prior_date_count NULL is imputed to 0 — it is
    genuinely zero before multi-date runs exist).

    Returns:
        (X, y, candidate_ids): np.ndarray (n, len(MODEL_INPUT_COLUMNS)),
        np.ndarray (n,) of 0/1, list of candidate ids kept.

    Raises:
        ValueError: If the CSV lacks required columns, no usable rows
                    remain, or only one class is present.
    """
    import csv

    labels = {}
    with open(labels_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or not {"candidate_id", "label"} <= set(
            reader.fieldnames
        ):
            raise ValueError(f"{labels_csv} must have candidate_id and label columns")
        for row in reader:
            label = (row.get("label") or "").strip().lower()
            if label == "":
                continue
            # Matches evaluation.precision_from_labels and the labelling
            # sheet: 'sellable' is the positive; any other non-empty value
            # is a false-positive class (car_park, active-industrial, ...).
            labels[int(row["candidate_id"])] = 1 if label == "sellable" else 0

    if not labels:
        raise ValueError(
            f"No labelled rows in {labels_csv} — P1-1 labelling has to happen "
            "before a model can be trained."
        )

    cursor = connection.cursor()
    cursor.execute(
        f"""
        SELECT id, {", ".join(MODEL_INPUT_COLUMNS)}
        FROM candidate_sites
        WHERE gss_code = %s AND id = ANY(%s)
        ORDER BY id
        """,
        (gss_code, list(labels.keys())),
    )
    rows = cursor.fetchall()
    cursor.close()

    X_rows, y_rows, kept_ids, dropped = [], [], [], 0
    prior_idx = MODEL_INPUT_COLUMNS.index("prior_date_count")
    for row in rows:
        cand_id, values = row[0], list(row[1:])
        if values[prior_idx] is None:
            values[prior_idx] = 0
        if any(v is None for v in values):
            dropped += 1
            continue
        X_rows.append([float(v) for v in values])
        y_rows.append(labels[cand_id])
        kept_ids.append(cand_id)

    if dropped:
        print(
            f"WARNING: dropped {dropped} labelled candidates with NULL features "
            "— were they stored before migration 004 / the features step? "
            "Re-run the pipeline to populate features for them."
        )
    if not X_rows:
        raise ValueError(
            "No labelled candidates with populated feature columns. Run the "
            "pipeline (with migration 004 applied) so features are stored, "
            "then label those candidates."
        )

    y = np.array(y_rows)
    if len(set(y_rows)) < 2:
        raise ValueError(
            "Labels contain a single class — a classifier cannot be trained. "
            "(The 19/19 false-positive pilot is exactly this case.)"
        )
    return np.array(X_rows), y, kept_ids


def fit_calibrated_rf(X: np.ndarray, y: np.ndarray, seed: int = RANDOM_SEED) -> tuple:
    """
    Splits, fits the calibrated Random Forest, and evaluates on the
    held-out test set. Pure function of (X, y, seed) for reproducibility.

    Returns:
        (model, metrics): the fitted CalibratedClassifierCV and a dict of
        test-set precision/recall/accuracy, split sizes, calibration
        method, and the calibration-curve points.
    """
    from sklearn.calibration import CalibratedClassifierCV, calibration_curve
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    from sklearn.model_selection import train_test_split

    positives = int(y.sum())
    if positives < MIN_POSITIVES:
        raise ValueError(
            f"Only {positives} positive labels — below the {MIN_POSITIVES} "
            "floor. Label more genuine sites (P1-1) before training."
        )
    if positives < WARN_POSITIVES:
        print(
            f"WARNING: {positives} positives is thin — metrics will be noisy. "
            "Treat this model as a smoke test, not the number to report."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_FRACTION, random_state=seed, stratify=y
    )

    method = "isotonic" if len(X_train) >= ISOTONIC_MIN_ROWS else "sigmoid"
    base = RandomForestClassifier(
        n_estimators=300, class_weight="balanced", random_state=seed
    )
    model = CalibratedClassifierCV(base, method=method, cv=3)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    proba_test = model.predict_proba(X_test)[:, 1]
    frac_pos, mean_pred = calibration_curve(
        y_test, proba_test, n_bins=min(5, max(2, len(y_test) // 4))
    )

    metrics = {
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "positives_total": positives,
        "calibration_method": method,
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "calibration_fraction_positive": [float(v) for v in frac_pos],
        "calibration_mean_predicted": [float(v) for v in mean_pred],
    }
    return model, metrics


def _save_calibration_plot(metrics: dict, gss_code: str, out_dir: str) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="grey", label="Perfect calibration")
    ax.plot(
        metrics["calibration_mean_predicted"],
        metrics["calibration_fraction_positive"],
        marker="o",
        color="#c0392b",
        label=f"Model ({metrics['calibration_method']})",
    )
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction actually genuine")
    ax.set_title(f"Calibration curve — {gss_code}")
    ax.legend()
    fig.tight_layout()
    path = str(out / f"calibration_curve_{gss_code}.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def store_model(
    model, metrics: dict, gss_code: str, image_date: str | None, connection
) -> int:
    """Persists the pickled calibrated model + test metrics to
    council_models (schema from migration 001). Returns the new row id."""
    import psycopg2

    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO council_models
        (gss_code, trained_date, training_sites, accuracy, precision_score,
         recall_score, image_date, model_binary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            gss_code,
            date.today(),
            metrics["train_rows"] + metrics["test_rows"],
            metrics["accuracy"],
            metrics["precision"],
            metrics["recall"],
            image_date,
            psycopg2.Binary(pickle.dumps(model)),
        ),
    )
    model_id = cursor.fetchone()[0]
    connection.commit()
    cursor.close()
    return model_id


def load_latest_model(gss_code: str, connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT model_binary FROM council_models
        WHERE gss_code = %s ORDER BY id DESC LIMIT 1
        """,
        (gss_code,),
    )
    row = cursor.fetchone()
    cursor.close()
    if row is None:
        raise ValueError(f"No trained model stored for {gss_code}")
    return pickle.loads(bytes(row[0]))


def score_latest_run(gss_code: str, connection) -> int:
    """
    P1-7: writes calibrated confidence for every candidate in the latest
    run that has populated feature columns. Returns the number scored.
    """
    model = load_latest_model(gss_code, connection)

    cursor = connection.cursor()
    cursor.execute(
        "SELECT MAX(run_timestamp) FROM candidate_sites WHERE gss_code = %s",
        (gss_code,),
    )
    latest_run = cursor.fetchone()[0]
    if latest_run is None:
        cursor.close()
        raise ValueError(f"No candidate runs stored for {gss_code}")

    cursor.execute(
        f"""
        SELECT id, {", ".join(MODEL_INPUT_COLUMNS)}
        FROM candidate_sites
        WHERE gss_code = %s AND run_timestamp = %s
        ORDER BY id
        """,
        (gss_code, latest_run),
    )
    rows = cursor.fetchall()

    prior_idx = MODEL_INPUT_COLUMNS.index("prior_date_count")
    ids, X_rows = [], []
    for row in rows:
        cand_id, values = row[0], list(row[1:])
        if values[prior_idx] is None:
            values[prior_idx] = 0
        if any(v is None for v in values):
            continue
        ids.append(cand_id)
        X_rows.append([float(v) for v in values])

    if not X_rows:
        cursor.close()
        raise ValueError(
            "Latest run has no candidates with populated features — was it "
            "run before migration 004 / the features step?"
        )

    proba = model.predict_proba(np.array(X_rows))[:, 1]

    for cand_id, p in zip(ids, proba):
        cursor.execute(
            "UPDATE candidate_sites SET confidence = %s WHERE id = %s",
            (float(p), cand_id),
        )
    connection.commit()
    cursor.close()
    print(f"Scored {len(ids)} candidates (run {latest_run})")
    return len(ids)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="v3 model training and scoring")
    parser.add_argument("--gss_code", type=str, default="E06000021")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--labels", type=str, default=None)
    parser.add_argument("--out_dir", type=str, default="outputs")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.train:
            if not args.labels:
                raise SystemExit(
                    "--train needs --labels <csv> from the P1-1 labelling work. "
                    "No labels, no model — that dependency is real."
                )
            X, y, _ = load_training_frame(args.gss_code, conn, args.labels)
            model, metrics = fit_calibrated_rf(X, y)
            plot = _save_calibration_plot(metrics, args.gss_code, args.out_dir)
            model_id = store_model(model, metrics, args.gss_code, None, conn)
            print(
                f"Model {model_id} stored — test precision "
                f"{metrics['precision']:.1%}, recall {metrics['recall']:.1%}, "
                f"calibration: {plot}"
            )
        if args.score:
            score_latest_run(args.gss_code, conn)
        if not args.train and not args.score:
            parser.print_help()
    finally:
        conn.close()
