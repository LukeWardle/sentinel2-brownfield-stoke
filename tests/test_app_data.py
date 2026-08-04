"""
test_app_data.py — the committed data the Streamlit app ships with (P3-1, #58).
===============================================================================
The app reads data/app/ and nothing else. These tests check that those files
are present, internally consistent, and still say what the notebooks and the
README say they say. They need no database: that is the point of them.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "app"

EXPECTED_FILES = [
    "seasons.csv",
    "candidates.csv",
    "persistent_candidates.geojson",
    "register_sites.csv",
    "boundary.geojson",
    "register_gate_samples.csv",
    "background_samples.csv",
    "metrics.json",
]

# Stoke-on-Trent, roughly. Everything the app maps must land inside this.
STOKE_BOUNDS = {"lon": (-2.32, -2.02), "lat": (52.94, 53.13)}


@pytest.fixture(scope="module")
def metrics() -> dict:
    return json.loads((DATA_DIR / "metrics.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", EXPECTED_FILES)
def test_expected_file_is_committed(name):
    assert (DATA_DIR / name).is_file(), (
        f"data/app/{name} is missing — regenerate with "
        f"python scripts/export_app_data.py"
    )


def test_no_database_url_is_embedded_in_the_exports():
    """A committed export must never carry a connection string."""
    for name in EXPECTED_FILES:
        text = (DATA_DIR / name).read_text(encoding="utf-8")
        assert "postgresql://" not in text
        assert "postgres:" not in text


def test_four_seasonal_scenes_with_the_published_counts():
    seasons = pd.read_csv(DATA_DIR / "seasons.csv")
    assert list(seasons.season) == ["Summer", "Autumn", "Winter", "Spring"]
    assert dict(zip(seasons.season, seasons.candidates)) == {
        "Summer": 251,
        "Autumn": 153,
        "Winter": 72,
        "Spring": 78,
    }
    # The seasonal gradient the Pipeline page describes: bare-soil signal peaks
    # in midsummer and falls away through autumn into winter.
    shares = dict(zip(seasons.season, seasons.pixel_share_pct))
    assert shares["Summer"] > shares["Autumn"] > shares["Winter"] > shares["Spring"]


def test_candidates_cover_every_scene_and_sit_inside_stoke():
    candidates = pd.read_csv(DATA_DIR / "candidates.csv")
    seasons = pd.read_csv(DATA_DIR / "seasons.csv")

    assert len(candidates) == seasons.candidates.sum()
    assert set(candidates.season) == set(seasons.season)
    assert candidates.lon.between(*STOKE_BOUNDS["lon"]).all()
    assert candidates.lat.between(*STOKE_BOUNDS["lat"]).all()


def test_persistent_set_is_twenty_sites_nineteen_of_them_labelled():
    geojson = json.loads(
        (DATA_DIR / "persistent_candidates.geojson").read_text(encoding="utf-8")
    )
    features = geojson["features"]
    assert len(features) == 20

    properties = pd.DataFrame([f["properties"] for f in features])
    assert properties.registered.sum() == 1, "one site coincides with the register"

    unregistered = properties[~properties.registered]
    assert len(unregistered) == 19
    assert unregistered.site_name.map(bool).all(), "every one was inspected"
    assert (unregistered.label == "sellable").sum() == 0, "none was a lead"

    # Every footprint is a real polygon, not a point standing in for one.
    assert all(
        f["geometry"] and f["geometry"]["type"] in ("Polygon", "MultiPolygon")
        for f in features
    )


def test_persistent_labels_match_the_committed_ground_truth():
    """The map's colours come from the same file notebook 08 analysed."""
    geojson = json.loads(
        (DATA_DIR / "persistent_candidates.geojson").read_text(encoding="utf-8")
    )
    properties = pd.DataFrame([f["properties"] for f in geojson["features"]])
    labels = pd.read_csv(
        ROOT / "data" / "groundtruth" / "persistent_labels.csv", encoding="utf-8-sig"
    )

    exported = properties[~properties.registered].set_index("candidate_id").label
    ground_truth = labels.set_index("candidate_id").label
    assert exported.sort_index().equals(ground_truth.sort_index())


def test_register_is_the_2026_publication(metrics):
    register = pd.read_csv(
        DATA_DIR / "register_sites.csv", dtype={"site_reference": str}
    )
    assert len(register) == metrics["register"]["sites"] == 352
    assert register.site_reference.is_unique
    assert register.lon.between(*STOKE_BOUNDS["lon"]).all()
    assert register.lat.between(*STOKE_BOUNDS["lat"]).all()


def test_register_references_must_be_read_as_text():
    """
    27 of the 352 rows are the same site entered twice, once with a
    zero-padded reference and once without — '0137' and '137'. Read as
    numbers the pairs collide and the register silently loses 27 rows, so
    every loader reads this column as text.
    """
    as_text = pd.read_csv(
        DATA_DIR / "register_sites.csv", dtype={"site_reference": str}
    )
    assert as_text.site_reference.str.startswith("0").sum() == 44, "padding survives"
    assert as_text.site_reference.nunique() == 352

    unpadded = as_text.site_reference.str.lstrip("0")
    assert unpadded.nunique() == 325, "27 rows are a second entry for the same site"

    # Each of those pairs is the same place: same location, same area.
    for reference in unpadded[unpadded.duplicated()]:
        pair = as_text[unpadded == reference]
        assert len(pair) == 2
        assert pair.lon.nunique() == 1 and pair.lat.nunique() == 1
        assert pair.hectares.nunique() <= 2  # one pair disagrees on area


def test_no_register_site_passes_the_detection_gate(metrics):
    """The finding itself, checked against the sampled values rather than a note."""
    samples = pd.read_csv(
        DATA_DIR / "register_gate_samples.csv", dtype={"site_reference": str}
    )
    gate = metrics["gate"]

    assert len(samples) == 352
    # Zero either way — against the row count and against the distinct sites.
    assert samples.site_reference.str.lstrip("0").nunique() == 325
    passes_bsi = samples.bsi > gate["bsi_above"]
    passes_ndvi = samples.ndvi < gate["ndvi_below"]

    assert passes_bsi.sum() == 0, "no register site is bare enough"
    assert (passes_bsi & passes_ndvi).sum() == 0, "and so none passes the gate"
    assert samples.bsi.max() == pytest.approx(0.0843, abs=5e-4)
    assert samples.ndvi.mean() == pytest.approx(0.234, abs=5e-3)


def test_recall_collapses_as_the_matching_radius_tightens(metrics):
    """The 100 m match is coincidence, not detection — the app says so."""
    recall = metrics["matching"]["recall_by_radius"]
    assert recall["100"] > recall["50"] > recall["25"] > recall["10"]
    assert recall["100"] == 105
    assert recall["25"] == 16
    assert metrics["matching"]["nearest_candidate_m"]["median"] > 150


def test_metrics_agree_with_the_files_they_summarise(metrics):
    candidates = pd.read_csv(DATA_DIR / "candidates.csv")
    background = pd.read_csv(DATA_DIR / "background_samples.csv")

    assert metrics["pipeline"]["candidates_total"] == len(candidates)
    assert metrics["gate_samples"]["background_sample_size"] == len(background)
    assert metrics["gate_samples"]["passing_gate"] == 0
    assert metrics["persistence"]["sellable"] == 0
    assert sum(metrics["persistence"]["labels"].values()) == 19


def test_boundary_is_a_single_wgs84_polygon():
    boundary = json.loads((DATA_DIR / "boundary.geojson").read_text(encoding="utf-8"))
    assert len(boundary["features"]) == 1
    feature = boundary["features"][0]
    assert feature["properties"]["gss_code"] == "E06000021"
    assert feature["geometry"]["type"] in ("Polygon", "MultiPolygon")

    def coordinates(geometry):
        rings = (
            geometry["coordinates"]
            if geometry["type"] == "Polygon"
            else [ring for polygon in geometry["coordinates"] for ring in polygon]
        )
        return [point for ring in rings for point in ring]

    for lon, lat in coordinates(feature["geometry"]):
        assert STOKE_BOUNDS["lon"][0] <= lon <= STOKE_BOUNDS["lon"][1]
        assert STOKE_BOUNDS["lat"][0] <= lat <= STOKE_BOUNDS["lat"][1]
