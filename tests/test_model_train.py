"""
test_model_train.py - Tests for P1-6/P1-7 training, calibration and
persistence. Training tests use synthetic separable data (no P1-1 labels
needed to prove the machinery); DB tests use the established rollback /
sentinel-cleanup pattern against the real database.
"""

import numpy as np
import pytest

from src.database_query import get_db_connection
from src.features import MODEL_INPUT_COLUMNS
from src.model_train import (
    MIN_POSITIVES,
    fit_calibrated_rf,
    load_latest_model,
    store_model,
)

GSS = "E06000021"


def _separable_data(n=120, seed=0):
    """Synthetic features where positives sit at higher mean_b11 —
    linearly separable enough for a sanity-checkable model."""
    rng = np.random.default_rng(seed)
    n_pos = n // 2
    X_pos = rng.normal(0.7, 0.05, size=(n_pos, len(MODEL_INPUT_COLUMNS)))
    X_neg = rng.normal(0.3, 0.05, size=(n - n_pos, len(MODEL_INPUT_COLUMNS)))
    X = np.vstack([X_pos, X_neg])
    y = np.array([1] * n_pos + [0] * (n - n_pos))
    return X, y


def test_fit_calibrated_rf_metrics_keys_and_ranges():
    X, y = _separable_data()
    model, metrics = fit_calibrated_rf(X, y, seed=42)
    for key in (
        "precision",
        "recall",
        "accuracy",
        "train_rows",
        "test_rows",
        "calibration_method",
    ):
        assert key in metrics
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
    # Separable data: the model must comfortably beat coin-flipping
    assert metrics["precision"] > 0.8
    assert metrics["recall"] > 0.8


def test_fit_calibrated_rf_probabilities_are_calibrated_range():
    X, y = _separable_data()
    model, _ = fit_calibrated_rf(X, y, seed=42)
    proba = model.predict_proba(X)[:, 1]
    assert proba.min() >= 0.0
    assert proba.max() <= 1.0
    # Positives should receive systematically higher probabilities
    assert proba[y == 1].mean() > proba[y == 0].mean() + 0.3


def test_fit_calibrated_rf_reproducible_with_seed():
    X, y = _separable_data()
    m1, met1 = fit_calibrated_rf(X, y, seed=42)
    m2, met2 = fit_calibrated_rf(X, y, seed=42)
    assert met1["precision"] == met2["precision"]
    assert np.allclose(m1.predict_proba(X), m2.predict_proba(X))


def test_fit_calibrated_rf_isotonic_over_100_rows_sigmoid_under():
    X, y = _separable_data(n=160)
    _, metrics_big = fit_calibrated_rf(X, y, seed=42)
    assert metrics_big["calibration_method"] == "isotonic"

    X_small, y_small = _separable_data(n=40)
    _, metrics_small = fit_calibrated_rf(X_small, y_small, seed=42)
    assert metrics_small["calibration_method"] == "sigmoid"


def test_fit_calibrated_rf_refuses_too_few_positives():
    X, y = _separable_data(n=60)
    y[:] = 0
    y[: MIN_POSITIVES - 1] = 1  # one short of the floor
    with pytest.raises(ValueError, match="positive"):
        fit_calibrated_rf(X, y, seed=42)


# --- council_models persistence round-trip (real DB) ---
@pytest.fixture
def connection():
    conn = get_db_connection()
    yield conn
    # store_model commits, so clean up explicitly rather than rolling back
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM council_models WHERE gss_code = %s AND training_sites = -999",
        (GSS,),
    )
    conn.commit()
    cursor.close()
    conn.close()


def test_store_and_load_model_roundtrip(connection):
    X, y = _separable_data(n=60)
    model, metrics = fit_calibrated_rf(X, y, seed=42)
    metrics = dict(metrics)
    metrics["train_rows"] = -999  # sentinel for cleanup: training_sites = -999
    metrics["test_rows"] = 0

    model_id = store_model(model, metrics, GSS, None, connection)
    assert isinstance(model_id, int)

    loaded = load_latest_model(GSS, connection)
    assert np.allclose(loaded.predict_proba(X), model.predict_proba(X))


def test_load_latest_model_raises_when_absent(connection):
    with pytest.raises(ValueError, match="No trained model"):
        load_latest_model("E00000000", connection)
