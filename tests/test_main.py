"""
test_main.py - Unit tests for module main.py
"""
import pytest
import os
from pathlib import Path
from src.main import run_pipeline

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def safe_path():
    safe_path = str(
        PROJECT_ROOT
        / "raw_data"
        / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE"
        / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE"
    )
    return safe_path


# --- run_pipeline tests ---
def test_run_pipeline_creates_output_files(safe_path, tmp_path):
    """
    Tests that run_pipeline completes successfully against real data and
    creates both the false colour map and results report in output_dir.
    """
    run_pipeline(safe_path, str(tmp_path))

    files = os.listdir(tmp_path)
    map_files = [f for f in files if f.startswith("false_colour_map_") and f.endswith(".png")]
    report_files = [f for f in files if f.startswith("results_report_") and f.endswith(".md")]

    assert len(map_files) == 1
    assert len(report_files) == 1


def test_run_pipeline_creates_output_dir_if_missing(safe_path, tmp_path):
    """
    Tests that run_pipeline creates output_dir automatically if it does
    not already exist, rather than raising an error.
    """
    new_output_dir = tmp_path / "does_not_exist_yet"
    assert not new_output_dir.exists()

    run_pipeline(safe_path, str(new_output_dir))

    assert new_output_dir.exists()
    files = os.listdir(new_output_dir)
    assert len(files) == 2


def test_run_pipeline_raises_filenotfounderror_for_invalid_safe_path(tmp_path):
    """
    Tests that run_pipeline raises FileNotFoundError when safe_path does
    not end with .SAFE or does not exist, propagated from validate_path.
    """
    with pytest.raises((FileNotFoundError, ValueError)):
        run_pipeline("/nonexistent/path/that/does/not/exist.SAFE", str(tmp_path))


def test_run_pipeline_raises_valueerror_for_non_safe_path(safe_path, tmp_path):
    """
    Tests that run_pipeline raises ValueError when safe_path does not
    end with .SAFE, propagated from validate_path.
    """
    bad_path = safe_path.replace(".SAFE", "")
    with pytest.raises(ValueError):
        run_pipeline(bad_path, str(tmp_path))