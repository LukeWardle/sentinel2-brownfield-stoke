"""
data_access.py — the app's only data layer (P3-1, issue #58).
=============================================================
Every figure in the app comes from a committed file under data/app/,
written by scripts/export_app_data.py. Nothing here opens a database
connection: Streamlit Cloud cannot reach the local Postgres instance the
pipeline writes to, and the app must be readable by someone who has never
run the pipeline at all.

Loaders are cached for the session, so the files are read once.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "app"
IMAGES_DIR = ROOT / "docs" / "images"

REPO_URL = "https://github.com/LukeWardle/sentinel2-brownfield-stoke"
NOTEBOOK_09_URL = f"{REPO_URL}/blob/main/notebooks/09_register_characterisation.ipynb"
NOTEBOOK_08_URL = f"{REPO_URL}/blob/main/notebooks/08_persistence_validation.ipynb"
README_FINDING_URL = f"{REPO_URL}#the-finding"
LABELS_CSV_URL = f"{REPO_URL}/blob/main/data/groundtruth/persistent_labels.csv"

# Season order used on every axis in the app. The four scenes span fourteen
# months, so plotting them by date reads as an arbitrary ordering; by season
# the gradient the pipeline actually produces is visible.
SEASON_ORDER = ["Summer", "Autumn", "Winter", "Spring"]

# One colour per manual label, chosen to stay legible over satellite imagery.
# register_matched is the single persistent candidate that coincides with a
# register site; it carries no manual label because the labelling exercise
# covered the nineteen unregistered candidates.
LABEL_COLOURS = {
    "active_industrial": "#e2601a",
    "active_institutional": "#3b7dd8",
    "active_retail": "#c93bb0",
    "car_park": "#f2c230",
    "construction": "#22b3a0",
    "heritage_constrained": "#8a5cf0",
    "register_matched": "#f5f5f5",
    "sellable": "#2ecc71",
}

LABEL_TITLES = {
    "active_industrial": "Active industrial",
    "active_institutional": "Active institutional",
    "active_retail": "Active retail",
    "car_park": "Car park",
    "construction": "Under construction",
    "heritage_constrained": "Heritage constrained",
    "register_matched": "Matched to the register",
    "sellable": "Sellable lead",
}

# What each label means in the terms a visitor cares about — why the site is
# not a lead, rather than what class it was filed under.
LABEL_MEANINGS = {
    "active_industrial": "A working factory, depot or trade estate. The detected "
    "shape is its roofs and service yards.",
    "active_institutional": "A hospital or school. The detected shape is its "
    "hardstanding and parking.",
    "active_retail": "A working retail site. The detected shape is its stock and "
    "service yards.",
    "car_park": "Surface parking in use. Car parks are already an exclusion class; "
    "this one is missing from the land-use data.",
    "construction": "A site already being developed, so not an undiscovered "
    "opportunity.",
    "heritage_constrained": "Genuinely derelict, and correctly detected, but a "
    "scheduled monument that cannot be cleared and built on.",
    "register_matched": "Coincides with a site already on the council's brownfield "
    "register, so not an unregistered find.",
    "sellable": "A discrete parcel with no active use that a developer could "
    "plausibly acquire. None were found.",
}

# The project's notebook palette, reused so the app and the committed figures
# read as one piece of work.
TEAL = "#4a90a4"
AMBER = "#d99a4e"
GREEN = "#2f4f43"
GREY = "#8a9ba3"
CRIMSON = "#dc143c"


def _path(name: str) -> Path:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path.relative_to(ROOT)} is missing. Regenerate the app's data with "
            f"`python scripts/export_app_data.py` (needs a database connection)."
        )
    return path


@st.cache_data
def load_metrics() -> dict:
    """Headline figures, computed against the database at export time."""
    return json.loads(_path("metrics.json").read_text(encoding="utf-8"))


@st.cache_data
def load_seasons() -> pd.DataFrame:
    """One row per seasonal scene."""
    seasons = pd.read_csv(_path("seasons.csv"))
    seasons["season"] = pd.Categorical(
        seasons.season, categories=SEASON_ORDER, ordered=True
    )
    return seasons.sort_values("season")


@st.cache_data
def load_candidates() -> pd.DataFrame:
    """Every candidate the detector emitted, on all four scenes."""
    candidates = pd.read_csv(_path("candidates.csv"))
    candidates["season"] = pd.Categorical(
        candidates.season, categories=SEASON_ORDER, ordered=True
    )
    return candidates


@st.cache_data
def load_persistent() -> tuple[dict, pd.DataFrame]:
    """
    The candidates bare across all four seasons, as GeoJSON and as a table.

    The GeoJSON carries the footprint the detector traced, which is what the
    map draws; the table is the same properties flattened for display.
    """
    geojson = json.loads(_path("persistent_candidates.geojson").read_text("utf-8"))
    table = pd.DataFrame([f["properties"] for f in geojson["features"]])
    table["label_title"] = table.label.map(LABEL_TITLES).fillna(table.label)
    return geojson, table


# Register references are strings, and some are zero-padded: '0137' and '137'
# are two separate rows describing the same site. Parsed as numbers they
# collide, which silently merges 27 of the 352 rows.
REFERENCE_AS_TEXT = {"site_reference": str}


@st.cache_data
def load_register() -> pd.DataFrame:
    """The council's published brownfield register — the target."""
    return pd.read_csv(_path("register_sites.csv"), dtype=REFERENCE_AS_TEXT)


@st.cache_data
def load_boundary() -> dict:
    """Stoke-on-Trent council boundary."""
    return json.loads(_path("boundary.geojson").read_text(encoding="utf-8"))


@st.cache_data
def load_gate_samples() -> pd.DataFrame:
    """
    BSI and NDVI measured at every register site, from the May 2026 scene.

    Sampled directly at the register locations rather than read back from
    detector output, which is the distinction the whole finding rests on.
    """
    return pd.read_csv(_path("register_gate_samples.csv"), dtype=REFERENCE_AS_TEXT)


@st.cache_data
def load_background() -> pd.DataFrame:
    """A random sample of pixels from the same scene, for comparison."""
    return pd.read_csv(_path("background_samples.csv"))


def page_header(title: str, standfirst: str) -> None:
    """Consistent title block across the three pages."""
    st.title(title)
    st.markdown(
        f"<p style='font-size:1.12rem; line-height:1.6; color:#6d7a80; "
        f"margin-top:-0.5rem;'>{standfirst}</p>",
        unsafe_allow_html=True,
    )
