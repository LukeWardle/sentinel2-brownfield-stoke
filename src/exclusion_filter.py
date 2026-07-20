"""
exclusion_filter.py - Drop candidate sites that fall in non-brownfield land use
===============================================================================
The masking half of P1-5. A July 2026 labelling pilot found the raw BSI/NDVI
detector fires on any bare or hard man-made surface with no land-use awareness
(19 of 19 sampled candidates were false positives — industrial units, car
parks, sewage works, school hardstanding). This module removes candidate sites
that sit inside the land-use polygons loaded into exclusion_zones by
exclusion_loader.py, before the survivors are matched and stored.

Runs after clustering: it takes the candidate site properties and their
boundary polygons (both keyed by site_id) and drops any candidate whose
outline is majority-inside the council's exclusion zones. Point-in-polygon
testing uses matplotlib.path.Path — the same vectorised approach as
aoi_clipping — so no new geometry dependency is introduced.

The drop rule is proportional, not a centroid coin-flip: a candidate is removed
only when more than half of its boundary vertices fall inside exclusion zones,
so a site that merely clips a building edge survives and is eroded in spirit
rather than binned outright. When candidate footprints are later persisted to
the database (see the candidate-geometry follow-on), this vertex-ratio
approximation can be replaced by exact PostGIS ST_Area(ST_Intersection(...)).
"""

import json
import sys
from pathlib import Path as FilePath

import numpy as np
from matplotlib.path import Path as MplPath

sys.path.insert(0, str(FilePath(__file__).parent.parent))

# Fraction of a candidate's boundary vertices that must fall inside exclusion
# zones for the candidate to be dropped.
OVERLAP_THRESHOLD = 0.5


def retrieve_exclusion_zones(gss_code: str, connection, source: str = "osm") -> list:
    """
    Retrieves the council's exclusion-zone polygons from the exclusion_zones
    table, transformed to EPSG:32630 to match candidate boundary coordinates.
    Mirrors retrieve_council_boundary_gss. Returns a flat list of exterior
    rings — one per polygon, with MultiPolygon geometries expanded to their
    component polygons — ready for matplotlib.path containment testing.

    Args:
        gss_code (str): GSS code for the council to retrieve exclusions for.
        connection: Active psycopg2 connection.
        source (str): Data provenance to filter on — default 'osm'.

    Returns:
        rings (list): List of np.ndarray, each an (N, 2) array of UTM exterior
                      ring coordinates. Empty list if the council has no
                      exclusion zones loaded.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT ST_AsGeoJSON(ST_Transform(ST_SetSRID(geom, 4326), 32630))
        FROM exclusion_zones
        WHERE gss_code = %s AND source = %s
        """,
        (gss_code, source),
    )
    results = cursor.fetchall()
    cursor.close()

    rings = []
    for row in results:
        if row[0] is None:
            continue
        geometry = json.loads(row[0])
        geom_type = geometry["type"]
        if geom_type == "Polygon":
            polygons = [geometry["coordinates"]]
        elif geom_type == "MultiPolygon":
            polygons = geometry["coordinates"]
        else:
            continue
        for polygon in polygons:
            # Exterior ring only (index 0); holes are ignored for masking —
            # a candidate over a hole is a rare edge case not worth the cost.
            rings.append(np.array(polygon[0]))
    return rings


def _fraction_inside(boundary: list, exclusion_paths: list) -> float:
    """
    Returns the fraction of a candidate's boundary vertices that fall inside any
    exclusion polygon.

    Args:
        boundary (list): List of [utm_x, utm_y] coordinate pairs for one candidate.
        exclusion_paths (list): List of matplotlib.path.Path exclusion polygons.

    Returns:
        fraction (float): Proportion of boundary vertices inside any exclusion
                          zone, between 0.0 and 1.0.
    """
    vertices = np.array(boundary)
    if len(vertices) == 0:
        return 0.0
    inside = np.zeros(len(vertices), dtype=bool)
    for path in exclusion_paths:
        inside |= path.contains_points(vertices)
    return float(inside.sum()) / len(vertices)


def filter_candidates_by_exclusion(
    site_properties: list,
    site_polygons: list,
    exclusion_rings: list,
    overlap_threshold: float = OVERLAP_THRESHOLD,
) -> tuple:
    """
    Drops candidate sites whose boundary is majority-inside the council's
    exclusion zones. site_properties and site_polygons are matched by site_id.
    Candidates with no matching polygon (no boundary traced) are kept, since
    there is no geometry to test them against.

    Args:
        site_properties (list): Candidate property dicts from
                                calculate_site_properties, each with a site_id.
        site_polygons (list): Boundary dicts from generate_boundary_polygons,
                              each with site_id and boundary (UTM coordinate pairs).
        exclusion_rings (list): Exclusion ring arrays from retrieve_exclusion_zones.
        overlap_threshold (float): Fraction of boundary vertices inside exclusion
                                   zones above which a candidate is dropped.

    Returns:
        tuple:
            kept (list): The surviving site_properties dicts.
            dropped_count (int): Number of candidates removed.
    """
    if not exclusion_rings:
        return site_properties, 0

    exclusion_paths = [MplPath(ring) for ring in exclusion_rings]
    boundary_by_id = {poly["site_id"]: poly["boundary"] for poly in site_polygons}

    kept = []
    dropped_count = 0
    for site in site_properties:
        boundary = boundary_by_id.get(site["site_id"])
        if boundary is None:
            kept.append(site)
            continue
        if _fraction_inside(boundary, exclusion_paths) > overlap_threshold:
            dropped_count += 1
        else:
            kept.append(site)
    return kept, dropped_count
