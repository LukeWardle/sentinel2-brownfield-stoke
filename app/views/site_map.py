"""
site_map.py — page 2. The persistent candidates, on the ground.
===============================================================
The twenty sites that stayed bare across all four seasons, drawn as the
footprints the detector actually traced, over aerial imagery. Colour is the
label a human gave the site after inspecting it. The point of the page is
that the imagery and the label agree: these are working premises.
"""

import folium
import streamlit as st
from folium.plugins import Fullscreen
from streamlit_folium import st_folium

from data_access import (
    GREY,
    LABEL_COLOURS,
    LABEL_MEANINGS,
    LABEL_TITLES,
    LABELS_CSV_URL,
    NOTEBOOK_08_URL,
    load_boundary,
    load_candidates,
    load_metrics,
    load_persistent,
    load_register,
    page_header,
)

CITY_CENTRE = (53.0235, -2.1780)
CITY_ZOOM = 11
SITE_ZOOM = 17
ALL_SITES = 0  # sentinel for the "no site selected" option

metrics = load_metrics()
geojson, persistent = load_persistent()
boundary = load_boundary()

page_header(
    "What the detector found",
    "Twenty sites in Stoke-on-Trent were bare in summer, autumn, winter and "
    "spring alike. By the product's own definition these were the leads. Every "
    "one of them was then looked at by eye against aerial photography.",
)

labelled = persistent[~persistent.registered]
counts = labelled.label.value_counts()

top = st.columns(4)
top[0].metric("Sites bare in all four seasons", len(persistent))
top[1].metric("Not already on the register", len(labelled))
top[2].metric("Inspected individually", len(labelled))
top[3].metric("Sellable leads", 0, delta="none found", delta_color="inverse")

st.divider()

# ---------------------------------------------------------------------------
# Site selection — shared by the dropdown and by clicking the map
# ---------------------------------------------------------------------------

options = [ALL_SITES] + list(persistent.candidate_id)
names = {
    int(row.candidate_id): (
        f"{row.site_name or 'Register-matched site'} — {row.label_title}"
    )
    for row in persistent.itertuples()
}


def option_label(candidate_id: int) -> str:
    if candidate_id == ALL_SITES:
        return "All twenty sites — city view"
    return names[candidate_id]


chooser, layers = st.columns([3, 2], gap="large")

with chooser:
    selected_id = st.selectbox(
        "Zoom to a site",
        options,
        format_func=option_label,
        key="site_choice",
    )

with layers:
    context = st.multiselect(
        "Add context",
        ["Registered brownfield sites", "All candidates, all four scenes"],
        default=["Registered brownfield sites"],
        help="The register is the target the detector was built to find. Compare "
        "where it sits against where the candidates sit.",
    )

selected = (
    persistent[persistent.candidate_id == selected_id].iloc[0]
    if selected_id != ALL_SITES
    else None
)

# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

centre = (selected.lat, selected.lon) if selected is not None else CITY_CENTRE
zoom = SITE_ZOOM if selected is not None else CITY_ZOOM

site_map = folium.Map(location=centre, zoom_start=zoom, tiles=None, control_scale=True)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
    "MapServer/tile/{z}/{y}/{x}",
    attr="Esri, Maxar, Earthstar Geographics",
    name="Aerial imagery",
    max_zoom=19,
).add_to(site_map)
folium.TileLayer("cartodbpositron", name="Map", max_zoom=19).add_to(site_map)

folium.GeoJson(
    boundary,
    name="Council boundary",
    style_function=lambda _: {
        "color": "#ffffff",
        "weight": 2,
        "opacity": 0.7,
        "fillOpacity": 0,
        "dashArray": "6 6",
    },
    interactive=False,
).add_to(site_map)

if "Registered brownfield sites" in context:
    register_group = folium.FeatureGroup(name="Registered brownfield", show=True)
    for site in load_register().itertuples():
        folium.CircleMarker(
            location=(site.lat, site.lon),
            radius=3,
            color="#2ecc71",
            weight=1,
            fill=True,
            fill_opacity=0.55,
            tooltip=folium.Tooltip(
                f"<b>On the register</b><br>{site.name_address}<br>"
                f"{site.hectares} ha · {site.planning_status}"
            ),
        ).add_to(register_group)
    register_group.add_to(site_map)

if "All candidates, all four scenes" in context:
    candidate_group = folium.FeatureGroup(name="All candidates", show=True)
    for candidate in load_candidates().itertuples():
        folium.CircleMarker(
            location=(candidate.lat, candidate.lon),
            radius=2,
            color=GREY,
            weight=1,
            fill=True,
            fill_opacity=0.5,
            tooltip=folium.Tooltip(
                f"Candidate {candidate.id} · {candidate.season}<br>"
                f"{candidate.hectares} ha"
            ),
        ).add_to(candidate_group)
    candidate_group.add_to(site_map)


def style(feature: dict) -> dict:
    label = feature["properties"]["label"]
    is_selected = feature["properties"]["candidate_id"] == selected_id
    return {
        "fillColor": LABEL_COLOURS.get(label, GREY),
        "color": "#ffffff" if is_selected else LABEL_COLOURS.get(label, GREY),
        "weight": 3 if is_selected else 2,
        "fillOpacity": 0.55,
    }


folium.GeoJson(
    geojson,
    name="Persistent candidates",
    style_function=style,
    highlight_function=lambda _: {"weight": 4, "fillOpacity": 0.75},
    tooltip=folium.GeoJsonTooltip(
        fields=["site_name", "label", "hectares"],
        aliases=["Site", "Turned out to be", "Area (ha)"],
        sticky=True,
    ),
).add_to(site_map)

Fullscreen().add_to(site_map)
folium.LayerControl(collapsed=True).add_to(site_map)

map_column, detail_column = st.columns([3, 2], gap="large")

with map_column:
    state = st_folium(
        site_map,
        use_container_width=True,
        height=560,
        returned_objects=["last_active_drawing"],
        key="persistent_map",
    )

# Clicking a footprint selects it, the same as choosing it from the dropdown.
clicked = (state or {}).get("last_active_drawing")
if clicked:
    clicked_id = (clicked.get("properties") or {}).get("candidate_id")
    if clicked_id and clicked_id != selected_id:
        st.session_state.site_choice = clicked_id
        st.rerun()

# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------

with detail_column:
    if selected is not None:
        colour = LABEL_COLOURS.get(selected.label, GREY)
        st.markdown(
            f"<span style='display:inline-block; width:12px; height:12px; "
            f"border-radius:3px; background:{colour}; margin-right:8px;'></span>"
            f"<strong>{selected.label_title}</strong>",
            unsafe_allow_html=True,
        )
        st.markdown(f"### {selected.site_name or 'Matched to the register'}")
        st.write(LABEL_MEANINGS.get(selected.label, ""))
        if selected.notes:
            st.caption(selected.notes)

        figures = st.columns(2)
        figures[0].metric("Area", f"{selected.hectares} ha")
        figures[1].metric("Compactness", f"{selected.compactness}")
        st.caption(
            "Compactness scores 1.0 for a circle and 0.785 for a square. Every "
            "site in this set scores below 0.33, meaning long and thin — the "
            "shape of a yard, verge or roof rather than a developable plot."
        )
        if selected.maps_url:
            st.link_button(
                "Open in Google Maps aerial view",
                selected.maps_url,
                width="stretch",
            )
    else:
        st.markdown("#### What the twenty sites turned out to be")
        for label, count in counts.items():
            colour = LABEL_COLOURS.get(label, GREY)
            st.markdown(
                f"<div style='display:flex; align-items:flex-start; gap:10px; "
                f"margin-bottom:10px;'>"
                f"<span style='flex:none; width:12px; height:12px; margin-top:5px; "
                f"border-radius:3px; background:{colour};'></span>"
                f"<span><strong>{LABEL_TITLES.get(label, label)} — {count}</strong>"
                f"<br><span style='color:#6d7a80; font-size:0.88rem;'>"
                f"{LABEL_MEANINGS.get(label, '')}</span></span></div>",
                unsafe_allow_html=True,
            )
        st.caption(
            "Plus one site already on the council's register, which is therefore "
            "not an unregistered find. Select a site above, or click a footprint "
            "on the map, for detail."
        )

st.divider()

st.subheader("All twenty, in full")

table = persistent.assign(
    site=persistent.site_name.where(
        persistent.site_name.astype(bool), "Matched to the register"
    )
)[["site", "label_title", "hectares", "compactness", "bsi", "maps_url"]]

st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    column_config={
        "site": st.column_config.TextColumn("Site", width="large"),
        "label_title": st.column_config.TextColumn("Turned out to be"),
        "hectares": st.column_config.NumberColumn("Area (ha)", format="%.2f"),
        "compactness": st.column_config.NumberColumn("Compactness", format="%.3f"),
        "bsi": st.column_config.NumberColumn("Bare-soil index", format="%.4f"),
        "maps_url": st.column_config.LinkColumn("Aerial view", display_text="Open"),
    },
)

st.caption(
    f"Labels were assigned by a single rater against aerial imagery, using the "
    f"controlled vocabulary in the project's labelling protocol. The raw file is "
    f"[persistent_labels.csv]({LABELS_CSV_URL}); the working is in "
    f"[notebook 08]({NOTEBOOK_08_URL}). Aerial imagery may postdate the satellite "
    f"scenes, and in one case — the Haywood Hospital construction site — that "
    f"discrepancy could not be resolved."
)

st.warning(
    "**Every detected footprint is roofs and hardstanding, not land.** Warehouse "
    "roofs, bus and lorry yards, hospital service areas, surface parking. Two "
    "signatures recur: the north-light sawtooth factory roof characteristic of "
    "the Potteries, and the loading apron between distribution units, which is "
    "kept clear because vehicles manoeuvre across it. The second matters for any "
    "attempted fix — it is not a building, so masking building outlines would "
    "not remove it."
)
