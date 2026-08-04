"""
finding.py — page 3. The negative result and its mechanism.
===========================================================
Zero of 352 registered brownfield sites satisfy the detector's gate. The page
shows the measurement, the committed figure from notebook 09, and the reason:
bare ground and previously developed land are near-disjoint populations in a
city.
"""

import altair as alt
import pandas as pd
import streamlit as st

from data_access import (
    AMBER,
    CRIMSON,
    GREY,
    IMAGES_DIR,
    NOTEBOOK_09_URL,
    README_FINDING_URL,
    TEAL,
    load_background,
    load_gate_samples,
    load_metrics,
    page_header,
)

metrics = load_metrics()
gate = metrics["gate"]
samples = load_gate_samples()
background = load_background()
gate_samples = metrics.get("gate_samples", {})
sites = metrics["register"]["sites"]

page_header(
    "It does not detect brownfield",
    "The pipeline runs, the imagery is sound and the sites it returns are real "
    "bare ground. It still does not find brownfield land, and the reason is not "
    "a tuning problem.",
)

st.divider()

# ---------------------------------------------------------------------------
# The measurement
# ---------------------------------------------------------------------------

headline = st.columns([2, 1, 1, 1])
headline[0].metric(
    "Registered brownfield sites passing the detector's gate",
    f"0 of {sites}",
)
headline[1].metric("Passing the bare-soil condition alone", "0")
headline[2].metric(
    "Highest bare-soil value in the whole register",
    f"{gate_samples.get('max_bsi', 0.0843)}",
    delta=f"gate needs above {gate['bsi_above']}",
    delta_color="inverse",
)
headline[3].metric(
    "Average vegetation index at register sites",
    f"{gate_samples.get('mean_ndvi', 0.2341):.3f}",
    delta=f"gate needs below {gate['ndvi_below']}",
    delta_color="inverse",
)

st.markdown(f"""
Every earlier check in this project examined what the detector *found*. This one
examines what it was meant to find. The council publishes {sites} brownfield
sites for Stoke-on-Trent. Each was located in the May 2026 satellite scene and
its bare-soil and vegetation values read straight off the imagery, over a window
sized to the site's recorded area — irrespective of whether the detector had
emitted anything there.

The gate requires a bare-soil index **above {gate['bsi_above']}** and a
vegetation index **below {gate['ndvi_below']}**, at the same time. Not one
registered site meets both. Not one meets the bare-soil condition on its own.
The highest bare-soil reading anywhere in the register is
{gate_samples.get('max_bsi', 0.0843)}, and the average is
{gate_samples.get('mean_bsi', -0.0028)}.

Those are the values of grassed ground. Registered brownfield in Stoke is
vegetated. It is former works, schools, hospitals and yards that closed years ago
and have since been colonised by grass and scrub. It is previously developed land
in the legal sense that defines the register, and it is not bare land in the
spectral sense the detector tests for. **The two definitions do not intersect.**
    """)

st.divider()

# ---------------------------------------------------------------------------
# The figure
# ---------------------------------------------------------------------------

st.subheader("The register against the gate")

# Fixed axis bounds, so the empty detection region keeps its size and position
# whatever the sample contains. Both are wider than the observed data: the
# highest bare-soil value anywhere in the scene sample is 0.17.
BSI_AXIS = alt.Scale(domain=[-0.45, 0.25], nice=False)
NDVI_AXIS = alt.Scale(domain=[-0.05, 0.78], nice=False)

detection_region = (
    alt.Chart(
        pd.DataFrame(
            {
                "x": [gate["bsi_above"]],
                "x2": [BSI_AXIS.domain[1]],
                "y": [gate["ndvi_below"]],
                "y2": [NDVI_AXIS.domain[0]],
            }
        )
    )
    .mark_rect(color=CRIMSON, opacity=0.07)
    .encode(
        x=alt.X("x:Q", scale=BSI_AXIS),
        x2="x2:Q",
        y=alt.Y("y:Q", scale=NDVI_AXIS),
        y2="y2:Q",
    )
)

background_layer = (
    alt.Chart(background[["bsi", "ndvi"]])
    .mark_circle(size=6, opacity=0.16, color=GREY)
    .encode(
        x=alt.X(
            "bsi:Q",
            title="Bare-soil index (BSI)  →  barer",
            scale=BSI_AXIS,
        ),
        y=alt.Y(
            "ndvi:Q",
            title="Vegetation index (NDVI)  →  greener",
            scale=NDVI_AXIS,
        ),
    )
)

register_layer = (
    alt.Chart(samples[["site_reference", "hectares", "bsi", "ndvi"]])
    .mark_circle(size=42, opacity=0.8, color=AMBER)
    .encode(
        x=alt.X("bsi:Q", scale=BSI_AXIS),
        y=alt.Y("ndvi:Q", scale=NDVI_AXIS),
        tooltip=[
            alt.Tooltip("site_reference:N", title="Register reference"),
            alt.Tooltip("hectares:Q", title="Area (ha)"),
            alt.Tooltip("bsi:Q", title="BSI", format=".4f"),
            alt.Tooltip("ndvi:Q", title="NDVI", format=".4f"),
        ],
    )
)

bsi_rule = (
    alt.Chart(pd.DataFrame({"x": [gate["bsi_above"]]}))
    .mark_rule(color=CRIMSON, strokeDash=[6, 4], size=2)
    .encode(x=alt.X("x:Q", scale=BSI_AXIS))
)
ndvi_rule = (
    alt.Chart(pd.DataFrame({"y": [gate["ndvi_below"]]}))
    .mark_rule(color=CRIMSON, strokeDash=[6, 4], size=2)
    .encode(y=alt.Y("y:Q", scale=NDVI_AXIS))
)

st.altair_chart(
    (detection_region + background_layer + register_layer + bsi_rule + ndvi_rule)
    .properties(height=460)
    .configure_view(strokeWidth=0),
    width="stretch",
)

legend = st.columns([1, 1, 2])
legend[0].markdown(
    f"<span style='color:{AMBER};'>●</span> the {sites} registered sites",
    unsafe_allow_html=True,
)
legend[1].markdown(
    f"<span style='color:{GREY};'>●</span> 5,000 random points in the city",
    unsafe_allow_html=True,
)
legend[2].markdown(
    f"<span style='color:{CRIMSON};'>▨</span> the shaded box is everything the "
    f"detector will accept — bottom right of both dashed lines",
    unsafe_allow_html=True,
)

st.markdown("""
The shaded box is empty of orange. That is the whole result, and it is a
structural fact about the two populations rather than a threshold that needs
nudging: the register cloud runs diagonally down the inverse relationship between
the two indices and stops short of the bare-soil line, reaching 0.084 at its
furthest.

Two further things are visible. The grey background is bimodal, as an urban area
should be — one cloud of vegetated surfaces at top left, one of built and
impervious surfaces at bottom right. The register overlaps the second almost
entirely, being neither fully green nor bare, which is what partially colonised
previously developed land looks like. And the two distributions are superimposed
rather than merely overlapping. There is no band of bare-soil values within which
a location is more likely to be registered brownfield than to be something else.
No threshold isolates the register, so no amount of retuning — and no classifier
trained on these two features — would either.
    """)

st.caption(f"""
One caveat on the denominator, since this page turns on being straight about
measurement. The 2026 register holds {sites} rows for Stoke-on-Trent, which is
the figure quoted throughout this project, but only
{samples.site_reference.str.lstrip("0").nunique()} of them are distinct sites:
{sites - samples.site_reference.str.lstrip("0").nunique()} appear twice, once
under a zero-padded reference and once without. Both copies carry the same
location and area, so both were sampled and both fail the gate. The result is
unaffected either way — it is zero against the row count and zero against the
distinct sites — but the register is smaller than the headline number suggests.
    """)

with st.expander("The same figure as published in notebook 09"):
    st.image(
        str(IMAGES_DIR / "register_vs_gate.png"),
        caption="Register sites against the detection gate. Left and centre: each "
        "index on its own, register sites against the city background. Right: both "
        "together, with the detection region at lower right.",
        width="stretch",
    )

st.divider()

# ---------------------------------------------------------------------------
# Mechanism
# ---------------------------------------------------------------------------

st.subheader("Why")

mechanism = st.columns(2, gap="large")

with mechanism[0]:
    st.markdown("""
##### Bare ground and brownfield are different things

Derelict land does not stay bare. Grass and scrub take it within a season or two
of abandonment, so by the time a site is worth finding it reads as vegetation.

What *does* stay reliably bare in a city is hardstanding kept in that condition
because something is using it: a lorry yard, a loading apron, a hospital service
road, a factory roof. The detector finds those, correctly and repeatedly. They
are what persistently bare ground in an urban area actually is.

So the system is not failing at its task. It is succeeding at a different task
from the one that was wanted. Bare ground and previously developed land are close
to disjoint populations in a city, and the project was built on the assumption
that they coincide.
        """)

with mechanism[1]:
    st.markdown(f"""
##### The earlier figures were an artefact

Recall of 17.9%, and later 15.3–23.1%, was reported earlier in this project.
Those figures are void. A register site counted as detected whenever any
candidate fell within 100 metres of it, which in a dense city catches candidates
that have nothing to do with the site.

Tightening the radius collapses the match count, which is the signature of
coincidence rather than detection — a candidate that genuinely identifies a site
sits *on* it, and does not stop doing so when the tolerance halves. The median
distance from a register site to the nearest candidate on any date is
{metrics['matching']['nearest_candidate_m']['median']:.0f} metres.
        """)

    radii = pd.DataFrame(
        [
            {"radius": f"{radius} m", "matched": matched, "order": int(radius)}
            for radius, matched in metrics["matching"]["recall_by_radius"].items()
        ]
    ).sort_values("order", ascending=False)

    st.altair_chart(
        alt.Chart(radii)
        .mark_bar(size=26, cornerRadiusEnd=3, color=TEAL)
        .encode(
            y=alt.Y("radius:N", sort=None, title="matching radius"),
            x=alt.X("matched:Q", title=f"register sites 'detected' (of {sites})"),
            tooltip=[
                alt.Tooltip("radius:N", title="Radius"),
                alt.Tooltip("matched:Q", title="Sites matched"),
            ],
        )
        .properties(height=190),
        width="stretch",
    )
    st.caption(
        "Recall against the register is not low. Measured by whether a register "
        "site passes the gate at all, it is zero."
    )

st.divider()

# ---------------------------------------------------------------------------
# Consequences
# ---------------------------------------------------------------------------

st.subheader("What would be needed instead")

st.markdown("""
The literature suggests this is a known unsolved problem rather than a botched
implementation. Work across 63 German districts abandoned image classification for
rule-based data fusion and still reported brownfield as the difficult case; other
work states plainly that separating vacant from operational industrial land cannot
be done from image features alone, and solves it by adding land surface
temperature and population density. Three directions follow, none of which is a
modification of this pipeline.
    """)

directions = st.columns(3, gap="large")
directions[0].markdown("""
**Non-image occupancy data**

UK business rates identify occupied premises, and empty-property relief works as a
vacancy register. That is the active-versus-abandoned signal imagery cannot
supply, and it is the distinction the whole problem turns on.
    """)
directions[1].markdown("""
**Multi-year phenology**

Land in use shows a cyclical annual greenness curve; abandoned land shows a rising
trend as succession takes hold. Detecting that needs years of imagery at 30 m,
which is coarse against a median register site of 0.28 ha.
    """)
directions[2].markdown("""
**A different target**

Monitoring *known* sites for build-out is what satellites are reliably good at,
has free ground truth in planning records, and reuses the ingest, clipping,
masking, storage and matching layers of this pipeline unchanged.
    """)

st.divider()

st.markdown(f"""
##### Read further

- [Notebook 09 — register characterisation]({NOTEBOOK_09_URL}) — the full
  analysis this page summarises, including the size-floor constraint and the
  feature-separation test.
- [The finding, in the project README]({README_FINDING_URL}) — the same result in
  the repository's own terms, with the evidence trail.

The measurement was available from the outset. Notebook 04 recorded a mean
bare-soil index of 0.005 at register sites, three paragraphs from the section that
set the gate threshold at 0.1. The two numbers were never compared, and three
notebooks proceeded on the assumption that the detector partially reached the
register and could be improved. That is the part of this worth keeping.
    """)
