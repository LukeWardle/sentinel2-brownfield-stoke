"""
pipeline.py — page 1. What the system does, and what it produced.
=================================================================
The engineering, the four seasonal scenes, the candidate counts and the
seasonal gradient. This page describes a working pipeline. Whether what it
finds is the thing it was built to find is the Finding page's subject.
"""

import altair as alt
import streamlit as st

from data_access import (
    AMBER,
    GREY,
    NOTEBOOK_08_URL,
    SEASON_ORDER,
    TEAL,
    load_metrics,
    load_seasons,
    page_header,
)

metrics = load_metrics()
seasons = load_seasons()
pipeline = metrics["pipeline"]
persistence = metrics["persistence"]

page_header(
    "A brownfield detector for Stoke-on-Trent",
    "Brownfield land is previously developed land — old works, yards, schools and "
    "hospitals that have closed. Councils publish a register of the sites they know "
    "about. This system was built to find the ones nobody has registered, by looking "
    "for bare ground in free satellite imagery.",
)

st.divider()

# ---------------------------------------------------------------------------
# What the system does
# ---------------------------------------------------------------------------

st.subheader("What it does")

left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown("""
Every few days the European Space Agency's Sentinel-2 satellites photograph the
whole of the UK, free to anyone. Each image records ten bands of light,
including infrared the eye cannot see. Vegetation and bare earth reflect
infrared very differently, so a bare patch of ground can be picked out from a
grassed one without ever visiting it.

1. **Download** a cloud-free scene over the council from the Copernicus archive.
2. **Clip** it to the council boundary, discarding 99% of the tile.
3. **Mask** cloud, shadow and missing data.
4. **Compute** two indices per pixel — a bare-soil index (BSI) and a vegetation
   index (NDVI).
5. **Gate** each pixel: keep it only where BSI is above 0.1 *and* NDVI is below
   0.2. This is the definition of "bare" the whole system rests on.
6. **Cluster** surviving pixels into contiguous sites and trace their outlines.
7. **Filter** out land uses that cannot be brownfield — car parks, quarries,
   farmland, playing fields — using OpenStreetMap polygons.
8. **Require persistence**, optionally: a site must still be bare on earlier
   dates, so that a freshly ploughed field does not count.
9. **Store** every site with its outline, so runs can be compared over time.

The engineering works and is tested. Steps 1 to 9 do what they say.
        """)

with right:
    st.markdown("###### From a satellite tile to a shortlist")
    st.metric(
        "Usable pixels in the satellite tile",
        f"{pipeline['tile_valid_pixels'] / 1_000_000:.1f}M",
    )
    st.metric(
        "Left after clipping to Stoke-on-Trent",
        f"{pipeline['aoi_pixels']:,}",
        delta="1.1% of the tile",
        delta_color="off",
    )
    st.metric(
        "Candidate sites found across four scenes",
        f"{pipeline['candidates_total']}",
    )
    st.metric(
        "Still bare in every season",
        f"{persistence['persistent_sites']}",
    )
    st.metric(
        "Of those, sites a developer could buy",
        f"{persistence['sellable']}",
        delta=f"0 of {persistence['labelled']} inspected",
        delta_color="inverse",
    )
    st.caption(
        f"Counts are after the land-use filter. Where both figures were "
        f"recorded, on the May 2026 scene, it removed 90 raw clusters to "
        f"{int(seasons.set_index('season').loc['Spring', 'candidates'])}. "
        f"{pipeline['exclusion_polygons']:,} exclusion polygons were loaded for "
        f"the city."
    )

st.divider()

# ---------------------------------------------------------------------------
# The four seasonal scenes
# ---------------------------------------------------------------------------

st.subheader("Four seasons")

st.markdown("""
A single date cannot tell derelict land from a field that happened to be
ploughed that week. Four cloud-free scenes were processed, one per season,
spanning fourteen months. Cloud-free had to be judged by eye: the archive
reports cloud across the whole 110 km tile, which says nothing about the
weather over one city inside it.
    """)

display = seasons.assign(
    scene=seasons.image_date,
    gate_pixels=seasons.pixel_share_pct.map(lambda v: f"{v}%"),
    area=seasons.total_hectares.map(lambda v: f"{v:,.0f} ha"),
)[["season", "scene", "candidates", "gate_pixels", "area"]]

st.dataframe(
    display,
    hide_index=True,
    width="stretch",
    column_config={
        "season": st.column_config.TextColumn("Season"),
        "scene": st.column_config.TextColumn("Scene date"),
        "candidates": st.column_config.NumberColumn("Candidate sites"),
        "gate_pixels": st.column_config.TextColumn("Pixels passing the gate"),
        "area": st.column_config.TextColumn("Total area flagged"),
    },
)

chart_left, chart_right = st.columns(2, gap="large")

with chart_left:
    st.markdown("###### Candidate sites per scene")
    bars = (
        alt.Chart(seasons)
        .mark_bar(size=48, cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color=TEAL)
        .encode(
            x=alt.X("season:N", sort=SEASON_ORDER, title=None),
            y=alt.Y("candidates:Q", title="candidate sites"),
            tooltip=[
                alt.Tooltip("season:N", title="Season"),
                alt.Tooltip("image_date:N", title="Scene"),
                alt.Tooltip("candidates:Q", title="Candidates"),
            ],
        )
        .properties(height=280)
    )
    labels = bars.mark_text(dy=-9, color="#4a5257").encode(text="candidates:Q")
    st.altair_chart(bars + labels, width="stretch")

with chart_right:
    st.markdown("###### Share of city pixels passing the bare-ground gate")
    share = (
        alt.Chart(seasons)
        .mark_bar(size=48, cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color=AMBER)
        .encode(
            x=alt.X("season:N", sort=SEASON_ORDER, title=None),
            y=alt.Y("pixel_share_pct:Q", title="% of pixels"),
            tooltip=[
                alt.Tooltip("season:N", title="Season"),
                alt.Tooltip("pixel_share_pct:Q", title="% passing the gate"),
            ],
        )
        .properties(height=280)
    )
    share_labels = share.mark_text(dy=-9, color="#4a5257").encode(
        text=alt.Text("pixel_share_pct:Q", format=".1f")
    )
    st.altair_chart(share + share_labels, width="stretch")

st.markdown("""
The gradient is physically sensible, which is the first sign the measurement
itself is sound. Bare soil shows up most strongly in midsummer and fades through
autumn into winter as the light drops, the ground wets and vegetation dies back.
Summer exceeding spring was not expected — the likeliest explanation is that
drought-parched grass reads as bare, which would make the summer scene a weaker
discriminator rather than a stronger one.
    """)

st.divider()

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

st.subheader("Sites that stay bare")

by_dates = persistence["by_dates_present"]
persistence_frame = alt.Data(
    values=[
        {
            "dates": f"{k} of 4",
            "sites": v,
            "kept": k == "4",
        }
        for k, v in sorted(by_dates.items())
    ]
)

narrow, wide = st.columns([2, 3], gap="large")

with narrow:
    st.altair_chart(
        alt.Chart(persistence_frame)
        .mark_bar(size=36, cornerRadiusEnd=3)
        .encode(
            y=alt.Y("dates:N", title="seasons the site was bare in"),
            x=alt.X("sites:Q", title="winter candidate sites"),
            color=alt.condition(alt.datum.kept, alt.value(TEAL), alt.value(GREY)),
            tooltip=[
                alt.Tooltip("dates:N", title="Bare in"),
                alt.Tooltip("sites:Q", title="Sites"),
            ],
        )
        .properties(height=230),
        width="stretch",
    )

with wide:
    st.markdown(f"""
The winter scene is the strictest of the four, producing only
{persistence['winter_candidates']} candidates against summer's
{pipeline['candidates_by_season']['Summer']}. Taking it as the anchor and asking
which of its sites also appear in the other three seasons — within
{persistence['match_radius_m']} metres — gives the breakdown on the left.

{by_dates['1']} sites are bare in winter alone. That is transient bare ground:
wet ground, temporary works, a single ploughing. Discarding them is exactly what
the filter was built to do. **{persistence['persistent_sites']} sites are bare in
all four seasons.** That set is what the product definition describes, and it is
what the Map page shows.

All {persistence['labelled']} of the unregistered sites in it were then inspected
individually against aerial photography. None was a lead.
        """)
    st.page_link(
        "views/site_map.py", label="See the persistent sites on the map", icon="🗺️"
    )

st.info(f"""
**Why requiring persistence made things worse.** Persistence selects for
permanence of *use*, not absence of it. A depot yard or a warehouse roof is bare
in every season precisely because it is maintained in that condition by being in
continuous use. Derelict land does the opposite: it greens over within a season
or two of abandonment, reads as vegetated on at least one date, and is thrown
out. The filter selects against the target. Full working in
[notebook 08]({NOTEBOOK_08_URL}).
    """)
