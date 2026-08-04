"""
streamlit_app.py — entry point for the SiteSignal app (P3-1, issue #58).
========================================================================
Three pages presenting a satellite brownfield detector built for
Stoke-on-Trent and the investigation that established it does not work.

The app reads committed files under data/app/ only. It never opens a
database connection, so it runs anywhere the repository is checked out,
including Streamlit Community Cloud.

Run locally:
    streamlit run app/streamlit_app.py
"""

import streamlit as st

from data_access import NOTEBOOK_09_URL, REPO_URL, load_metrics

st.set_page_config(
    page_title="Detecting brownfield from space — and why it fails",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Emoji rather than :material/…: icons — the Material Symbols font is fetched
# from Google, and the page must still read correctly where it is not reachable.
pipeline = st.Page("views/pipeline.py", title="Pipeline", icon="🛰️", default=True)
site_map = st.Page("views/site_map.py", title="Map", icon="🗺️")
finding = st.Page("views/finding.py", title="Finding", icon="🔎")

# st.navigation claims the sidebar, and must be called before anything else
# writes to it — otherwise the sidebar, navigation included, does not render.
navigation = st.navigation([pipeline, site_map, finding])

with st.sidebar:
    metrics = load_metrics()
    st.divider()
    st.caption("Stoke-on-Trent · Sentinel-2 · a negative result")
    st.metric(
        "Register sites passing the detector's gate",
        f"0 of {metrics['register']['sites']}",
    )
    st.caption(
        "Sampled directly at every registered brownfield site in the city, "
        "rather than inferred from what the detector found."
    )
    st.divider()
    st.markdown(
        f"[Full analysis — notebook 09]({NOTEBOOK_09_URL})  \n"
        f"[Source and README]({REPO_URL})"
    )

navigation.run()
