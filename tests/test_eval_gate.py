"""
test_eval_gate.py - Detection-quality regression gate (P1-3).
=============================================================
The gate: when a frozen labelled sample exists at
tests/fixtures/frozen_labels.csv, CI computes labelled precision via the
P1-2 harness and FAILS if it drops below the floor in
tests/fixtures/eval_floor.json. Until the P1-1 labelling work produces
that frozen sample, the gate test SKIPS with an explicit message — the
mechanism is in place and arms itself the moment the fixture is
committed. No CI configuration changes are needed: this is an ordinary
pytest test, so tests.yml runs it already.

The mechanism self-tests below prove today that the gate goes red on a
deliberate regression (the P1-3 acceptance criterion), using temporary
label files rather than the not-yet-existing frozen sample.

To arm the gate once P1-1 labels exist:
1. Freeze a representative labelled subset as tests/fixtures/frozen_labels.csv
   (columns: candidate_id, label — sellable / a false-positive class).
2. Set the agreed floor in tests/fixtures/eval_floor.json.
3. Commit both. The skip disappears; the gate is live.
"""

import json
from pathlib import Path

import pytest

from src.evaluation import precision_from_labels

FIXTURES = Path(__file__).parent / "fixtures"
FROZEN_LABELS = FIXTURES / "frozen_labels.csv"
FLOOR_FILE = FIXTURES / "eval_floor.json"


def check_precision_gate(labels_csv: str, floor: float) -> dict:
    """The gate itself: raises AssertionError when labelled precision on
    the frozen sample falls below the floor."""
    stats = precision_from_labels(labels_csv)
    assert stats["precision"] >= floor, (
        f"DETECTION-QUALITY REGRESSION: labelled precision "
        f"{stats['precision']:.1%} is below the agreed floor {floor:.1%} "
        f"({stats['positives']}/{stats['labelled']} sellable). Investigate "
        f"before merging."
    )
    return stats


# --- The live gate ---
def test_precision_gate_on_frozen_sample():
    if not FROZEN_LABELS.exists():
        pytest.skip(
            "Gate not yet armed: tests/fixtures/frozen_labels.csv absent. "
            "It arms automatically once the P1-1 labelled sample is frozen "
            "and committed (see module docstring)."
        )
    floor = json.loads(FLOOR_FILE.read_text(encoding="utf-8"))["precision_floor"]
    check_precision_gate(str(FROZEN_LABELS), floor)


# --- Mechanism self-tests (run today, prove the gate can go red) ---
def _write_labels(path, sellable, false_positive):
    rows = ["candidate_id,label"]
    rows += [f"{i},sellable" for i in range(sellable)]
    rows += [f"{1000 + i},car_park" for i in range(false_positive)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_gate_fails_on_deliberate_regression(tmp_path):
    bad = tmp_path / "bad_labels.csv"
    _write_labels(bad, sellable=2, false_positive=8)  # 20% precision
    with pytest.raises(AssertionError, match="REGRESSION"):
        check_precision_gate(str(bad), floor=0.6)


def test_gate_passes_above_floor(tmp_path):
    good = tmp_path / "good_labels.csv"
    _write_labels(good, sellable=8, false_positive=2)  # 80% precision
    stats = check_precision_gate(str(good), floor=0.6)
    assert stats["precision"] == pytest.approx(0.8)


def test_gate_boundary_exactly_at_floor_passes(tmp_path):
    edge = tmp_path / "edge_labels.csv"
    _write_labels(edge, sellable=6, false_positive=4)  # exactly 60%
    check_precision_gate(str(edge), floor=0.6)


def test_floor_config_is_valid_json_with_expected_key():
    payload = json.loads(FLOOR_FILE.read_text(encoding="utf-8"))
    assert "precision_floor" in payload
    assert 0.0 < payload["precision_floor"] <= 1.0
