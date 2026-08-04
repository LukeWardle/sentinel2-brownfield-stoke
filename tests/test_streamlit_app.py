"""
test_streamlit_app.py — the app renders without a database (P3-1, #58).
=======================================================================
Issue #58 requires the app to deploy to Streamlit Cloud, which cannot reach
the Postgres instance the pipeline writes to. Every test here runs with
DATABASE_URL removed from the environment, so a page that acquired a
connection would fail rather than pass quietly on a developer machine where
one happens to be available.

Streamlit's own AppTest harness runs the pages in-process, without a browser.
"""

import ast
import sys
from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit", reason="app dependencies not installed")
pytest.importorskip("streamlit_folium", reason="app dependencies not installed")

from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "streamlit_app.py"
PAGES = ["views/pipeline.py", "views/site_map.py", "views/finding.py"]

# Rendering the map builds several hundred markers, which is slower than the
# harness's three-second default.
TIMEOUT = 60


@pytest.fixture(autouse=True)
def without_a_database(monkeypatch):
    """No connection string, and no way to reach one."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # The app's modules live beside its entrypoint; Streamlit puts that
    # directory on the path at runtime, and the harness does not.
    monkeypatch.syspath_prepend(str(APP.parent))


def run(page: str | None = None) -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=TIMEOUT)
    if page:
        app.switch_page(page)
    return app.run()


@pytest.mark.parametrize("page", [None, *PAGES])
def test_page_renders_without_a_database_connection(page):
    app = run(page)
    assert not app.exception, [e.value for e in app.exception]


def test_navigation_offers_exactly_the_three_pages():
    """
    Issue #58 specifies three pages. The navigation itself is assembled in the
    browser, so the entrypoint's st.Page calls are read from its source.
    """
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    declared = [
        (
            node.args[0].value,
            next(k.value.value for k in node.keywords if k.arg == "title"),
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Page"
    ]

    assert declared == [
        ("views/pipeline.py", "Pipeline"),
        ("views/site_map.py", "Map"),
        ("views/finding.py", "Finding"),
    ]
    assert [page for page, _ in declared] == PAGES


def test_pipeline_page_reports_the_seasonal_counts():
    app = run("views/pipeline.py")
    text = " ".join(element.value for element in app.markdown)

    assert "26 sites are bare in winter alone" in text
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Candidate sites found across four scenes"] == "554"
    assert metrics["Still bare in every season"] == "20"
    assert metrics["Of those, sites a developer could buy"] == "0"


def test_finding_page_leads_with_zero_of_352():
    app = run("views/finding.py")
    metrics = {metric.label: metric.value for metric in app.metric}

    assert metrics["Registered brownfield sites passing the detector's gate"] == (
        "0 of 352"
    )
    assert metrics["Passing the bare-soil condition alone"] == "0"

    text = " ".join(element.value for element in app.markdown)
    assert "0.0843" in text, "the highest bare-soil value in the register"
    assert "do not intersect" in text, "the mechanism, stated plainly"


def test_finding_page_links_back_to_notebook_09_and_the_readme():
    app = run("views/finding.py")
    text = " ".join(element.value for element in app.markdown)
    assert "notebooks/09_register_characterisation.ipynb" in text
    assert "#the-finding" in text


def test_map_page_selecting_a_site_shows_its_detail():
    app = run("views/site_map.py")
    assert "What the twenty sites turned out to be" in " ".join(
        element.value for element in app.markdown
    )

    # Chatterley Whitfield: derelict, correctly detected, and undevelopable.
    app.selectbox("site_choice").select(1319).run()

    text = " ".join(element.value for element in app.markdown)
    assert "Chatterley Whitfield" in text
    assert "scheduled monument" in text
    assert {metric.label for metric in app.metric} >= {"Area", "Compactness"}


def test_map_page_offers_every_persistent_site():
    app = run("views/site_map.py")
    options = app.selectbox("site_choice").options
    assert len(options) == 21, "twenty sites plus the city-wide view"


def test_app_imports_no_database_driver():
    """A stray import of psycopg2 would break the deployed app, not the tests."""
    run()
    app_modules = {
        name: module
        for name, module in sys.modules.items()
        if getattr(module, "__file__", None)
        and str(APP.parent) in str(Path(module.__file__).resolve().parent)
    }
    assert app_modules, "the app's own modules were imported"

    for name, module in app_modules.items():
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "psycopg2" not in source, f"{name} reaches for a database"
        assert "database_query" not in source, f"{name} reaches for a database"
