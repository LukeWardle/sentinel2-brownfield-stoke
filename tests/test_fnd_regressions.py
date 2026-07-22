"""
test_fnd_regressions.py - Regression tests for the July 2026 audit findings.
============================================================================
FND-1: dilation must not contaminate group membership.
FND-2: boundary polygons must be valid geometry with exact pixel-footprint area.
FND-5: coordinate transforms must use explicit axis order.
FND-6: the pyproj transformer must be module-level, not rebuilt per call.
No database or network required — pure-function tests.
"""

import numpy as np

import src.coordinate_conversion_pixel as ccp
from src.clustering import (
    calculate_site_properties,
    generate_boundary_polygons,
    group_pixels_for_candidate_sites,
)

TILE = {"left": 500000.0, "top": 5900000.0, "resolution": 20}


def _synthetic_scene():
    """
    A 16x16 fully-valid scene with two separated 2x2 candidate blocks.
    Blocks at rows 2-3 cols 2-3 and rows 2-3 cols 8-9: the 4-column gap is
    wide enough that a single dilation cannot bridge them, so they remain two
    distinct components of exactly 4 true pixels each. The dilation ring
    around each block still sweeps in non-candidate pixels — the FND-1 trap —
    so membership equalling the true 4-pixel set proves the fix.
    Returns (mask, original_shape, bsi, ndvi, candidate_flat_indices).
    """
    original_shape = (16, 16)
    n_pixels = 16 * 16
    mask = np.ones(n_pixels, dtype=bool)

    bsi = np.full(n_pixels, -0.5)  # everything non-candidate by default
    ndvi = np.full(n_pixels, 0.9)

    candidate_rc = [
        (2, 2),
        (2, 3),
        (3, 2),
        (3, 3),
        (2, 8),
        (2, 9),
        (3, 8),
        (3, 9),
    ]
    candidate_flat = [r * 16 + c for r, c in candidate_rc]
    for idx in candidate_flat:
        bsi[idx] = 0.5  # passes bsi > threshold
        ndvi[idx] = 0.0  # passes ndvi < threshold
    return mask, original_shape, bsi, ndvi, set(candidate_flat)


# --- FND-1: group membership excludes dilation-added pixels ---
def test_fnd1_membership_contains_only_true_candidates():
    """Every pixel index in every group must have passed the thresholds."""
    mask, shape, bsi, ndvi, true_candidates = _synthetic_scene()
    groups = group_pixels_for_candidate_sites(
        mask, shape, bsi, ndvi, bsi_threshold=0.1, ndvi_threshold=0.2, min_pixels=2
    )
    assert groups, "expected candidate groups from the synthetic scene"
    all_members = {idx for indices in groups.values() for idx in indices}
    assert all_members == true_candidates, (
        "group membership must equal the true candidate set — dilation-border "
        "pixels leaked in"
        if all_members - true_candidates
        else "true candidate pixels were lost from membership"
    )


def test_fnd1_two_separate_sites_each_four_pixels():
    """The scene yields two distinct sites, each of exactly 4 true pixels —
    proving dilation connects for labelling without merging or inflating."""
    mask, shape, bsi, ndvi, _ = _synthetic_scene()
    groups = group_pixels_for_candidate_sites(
        mask, shape, bsi, ndvi, bsi_threshold=0.1, ndvi_threshold=0.2, min_pixels=2
    )
    assert len(groups) == 2
    props = calculate_site_properties(groups, bsi, mask, shape, TILE)
    for site in props:
        assert site["pixel_count"] == 4  # each block is exactly 2x2
        assert site["mean_bsi"] == 0.5  # dilution would pull this below 0.5


def test_fnd1_size_filter_applies_to_true_count():
    """min_pixels gates the TRUE candidate count, not the dilated blob size.
    Each block has 4 true candidates; the dilated blobs are far larger, so
    min_pixels=5 must filter both sites out."""
    mask, shape, bsi, ndvi, _ = _synthetic_scene()
    groups = group_pixels_for_candidate_sites(
        mask, shape, bsi, ndvi, bsi_threshold=0.1, ndvi_threshold=0.2, min_pixels=5
    )
    assert groups == {}, "4-pixel sites must be filtered when min_pixels=5"


# --- FND-2: boundary polygons are valid with exact footprint area ---
def _shoelace_area(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    area = 0.0
    for i in range(len(ring) - 1):
        area += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
    return abs(area) / 2.0


def test_fnd2_polygons_are_valid_geojson():
    """Each site geometry is a Polygon/MultiPolygon with closed rings."""
    mask, shape, bsi, ndvi, _ = _synthetic_scene()
    groups = group_pixels_for_candidate_sites(
        mask, shape, bsi, ndvi, bsi_threshold=0.1, ndvi_threshold=0.2, min_pixels=2
    )
    polygons = generate_boundary_polygons(groups, mask, shape, TILE)
    assert len(polygons) == len(groups)
    for entry in polygons:
        geometry = entry["geometry"]
        assert geometry is not None
        assert geometry["type"] in ("Polygon", "MultiPolygon")
        rings = (
            geometry["coordinates"]
            if geometry["type"] == "Polygon"
            else [r for poly in geometry["coordinates"] for r in poly]
        )
        for ring in rings:
            assert len(ring) >= 4
            assert ring[0] == ring[-1], "ring must be closed"


def test_fnd2_polygon_area_equals_pixel_footprint():
    """Each separated 2x2 block at 20m resolution traces to exactly 1600 m^2.
    Blocks are spaced so each site is a single solid Polygon with no holes."""
    mask, shape, bsi, ndvi, _ = _synthetic_scene()
    groups = group_pixels_for_candidate_sites(
        mask, shape, bsi, ndvi, bsi_threshold=0.1, ndvi_threshold=0.2, min_pixels=2
    )
    polygons = generate_boundary_polygons(groups, mask, shape, TILE)
    for entry in polygons:
        geometry = entry["geometry"]
        assert geometry["type"] == "Polygon"  # solid 2x2 block, no holes
        exterior = geometry["coordinates"][0]
        assert _shoelace_area(exterior) == 1600.0


# --- FND-5 / FND-6: coordinate transform axis order and reuse ---
def test_fnd5_bng_to_utm_stoke_sanity():
    """A Stoke BNG coordinate lands in the correct UTM 30N range — a silent
    axis swap would put it wildly outside these bounds."""
    result = ccp.convert_bng_to_utm(388000.0, 347000.0)
    assert 500000 < result["x"] < 620000
    assert 5800000 < result["y"] < 5950000


def test_fnd6_transformer_is_module_level_and_reused():
    """The transformer exists as a module constant and calls reuse it."""
    first = ccp.TRANSFORMER_BNG_TO_UTM
    ccp.convert_bng_to_utm(388000.0, 347000.0)
    ccp.convert_bng_to_utm(390000.0, 349000.0)
    assert ccp.TRANSFORMER_BNG_TO_UTM is first
