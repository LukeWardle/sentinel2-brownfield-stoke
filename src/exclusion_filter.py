"""
exclusion_filter.py - Drop candidate sites in disjoint non-brownfield land use.
===============================================================================
The masking half of P1-5, rewritten under FND-4 as an indexed PostGIS
area-overlap test.

A July 2026 labelling pilot found the raw BSI/NDVI detector fires on any
bare or hard man-made surface with no land-use awareness. A first masking
attempt using all OSM classes then showed 114 of 352 registered brownfield
sites (32%) fall inside building/infrastructure polygons — because
registered brownfield IS previously-developed land, those classes overlap
the definition of the target and cannot be hard masks. Per the July 2026
math/algorithm audit:

- HARD EXCLUSION CLASSES are only those measured as disjoint from
  brownfield: car parks, quarries/landfill, agriculture, and
  amenity/leisure land. Building and infrastructure are NOT hard masks;
  they return as classifier features in P1-6.
- Overlap is computed as ST_Area(ST_Intersection(...)) / ST_Area(candidate)
  in PostGIS — true area overlap, not the size-biased vertex ratio of the
  superseded in-memory filter. The GIST index on exclusion_zones.geom
  pre-filters intersecting zones (the ST_Intersects test runs in the
  geometry's native 4326 so the index is used; areas are computed in 32630).
- The brownfield register is treated as a standing VALIDATION SET:
  report_register_recall measures how many register sites fall inside the
  hard exclusion classes on every run. It is a metric to watch, never a
  mask override — overriding would hide the error signal.
- Candidates are processed in deterministic (site_properties) order and
  ST_Union makes per-zone accumulation order-independent, so overlap
  fractions are stable run to run.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Classes measured as disjoint from registered brownfield (July 2026 audit:
# register hits car_park 13, amenity_leisure 10, quarry ~0, agriculture 0 —
# versus building 70 and infrastructure 32, which are therefore excluded from
# hard masking and reserved for classifier features).
HARD_EXCLUSION_CLASSES = ["car_park", "quarry", "agriculture", "amenity_leisure"]

# Fraction of a candidate's AREA inside hard exclusion zones above which the
# candidate is dropped. Strictly greater-than: a candidate exactly half on a
# car park survives.
OVERLAP_THRESHOLD = 0.5


def compute_exclusion_overlap(
    geometry: dict,
    gss_code: str,
    connection,
    classes: list = None,
    source: str = "osm",
) -> float:
    """
    Computes the fraction of a candidate geometry's area that falls inside
    the given exclusion classes for a council, entirely in PostGIS. The
    ST_Intersects pre-filter runs against exclusion_zones.geom in its native
    EPSG:4326 so the GIST index is used; the intersecting zones are unioned
    (order-independent) and the area ratio is computed in EPSG:32630.

    Args:
        geometry (dict): GeoJSON Polygon or MultiPolygon in EPSG:32630 —
                         a candidate footprint from generate_boundary_polygons.
        gss_code (str): GSS code for the council being processed.
        connection: Active psycopg2 connection.
        classes (list): Exclusion classes to test against. Defaults to
                        HARD_EXCLUSION_CLASSES.
        source (str): Data provenance to filter on — default 'osm'.

    Returns:
        overlap (float): Fraction of the candidate's area inside the given
                         exclusion classes, between 0.0 and 1.0. Returns 0.0
                         when no zones intersect or the geometry is None.
    """
    if geometry is None:
        return 0.0
    if classes is None:
        classes = HARD_EXCLUSION_CLASSES

    cursor = connection.cursor()
    cursor.execute(
        """
        WITH cand AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 32630) AS g
        )
        SELECT COALESCE(
            ST_Area(
                ST_Intersection(
                    c.g,
                    ST_Union(ST_Transform(ST_SetSRID(z.geom, 4326), 32630))
                )
            ) / NULLIF(ST_Area(c.g), 0),
            0
        )
        FROM cand c
        JOIN exclusion_zones z
          ON z.gss_code = %s
         AND z.source = %s
         AND z.exclusion_class = ANY(%s)
         AND ST_Intersects(z.geom, ST_Transform(c.g, 4326))
        GROUP BY c.g
        """,
        (json.dumps(geometry), gss_code, source, classes),
    )
    row = cursor.fetchone()
    cursor.close()
    if row is None or row[0] is None:
        return 0.0
    return float(min(max(row[0], 0.0), 1.0))


def filter_candidates_by_exclusion(
    site_properties: list,
    site_polygons: list,
    gss_code: str,
    connection,
    overlap_threshold: float = OVERLAP_THRESHOLD,
    classes: list = None,
    source: str = "osm",
) -> tuple:
    """
    Drops candidate sites whose footprint area is majority-inside the hard
    exclusion classes, computed per candidate in PostGIS. site_properties and
    site_polygons are matched by site_id. Candidates with no geometry are
    kept — there is nothing to test them against. Each surviving and dropped
    decision is based on true area overlap (FND-4), so the size/vertex bias
    of the superseded in-memory filter does not apply.

    Args:
        site_properties (list): Candidate property dicts from
                                calculate_site_properties, each with a site_id.
        site_polygons (list): Geometry dicts from generate_boundary_polygons,
                              each with site_id and geometry (GeoJSON, 32630).
        gss_code (str): GSS code for the council being processed.
        connection: Active psycopg2 connection.
        overlap_threshold (float): Area fraction above which a candidate is
                                   dropped. Default OVERLAP_THRESHOLD.
        classes (list): Exclusion classes applied as hard masks. Defaults to
                        HARD_EXCLUSION_CLASSES.
        source (str): Data provenance to filter on — default 'osm'.

    Returns:
        tuple:
            kept (list): The surviving site_properties dicts, in input order.
            dropped_count (int): Number of candidates removed.
    """
    geometry_by_id = {poly["site_id"]: poly.get("geometry") for poly in site_polygons}

    kept = []
    dropped_count = 0
    for site in site_properties:
        geometry = geometry_by_id.get(site["site_id"])
        if geometry is None:
            kept.append(site)
            continue
        overlap = compute_exclusion_overlap(
            geometry, gss_code, connection, classes=classes, source=source
        )
        if overlap > overlap_threshold:
            dropped_count += 1
        else:
            kept.append(site)
    return kept, dropped_count


def report_register_recall(
    gss_code: str,
    connection,
    classes: list = None,
    source: str = "osm",
) -> dict:
    """
    Standing recall metric (validation set, never a mask override): counts how
    many registered brownfield sites for the most recent register year fall
    inside the hard exclusion classes. A rising number signals the exclusion
    set has started eating genuine brownfield and needs retuning.

    Args:
        gss_code (str): GSS code for the council being processed.
        connection: Active psycopg2 connection.
        classes (list): Exclusion classes measured against. Defaults to
                        HARD_EXCLUSION_CLASSES.
        source (str): Data provenance to filter on — default 'osm'.

    Returns:
        dict: register_sites (int) — sites in the latest register year;
              inside_exclusions (int) — of those, how many fall inside the
              given exclusion classes.
    """
    if classes is None:
        classes = HARD_EXCLUSION_CLASSES

    cursor = connection.cursor()
    cursor.execute(
        "SELECT MAX(year) FROM brownfield_sites WHERE gss_code = %s", (gss_code,)
    )
    year_row = cursor.fetchone()
    if year_row is None or year_row[0] is None:
        cursor.close()
        return {"register_sites": 0, "inside_exclusions": 0}
    year = year_row[0]

    cursor.execute(
        "SELECT COUNT(*) FROM brownfield_sites WHERE gss_code = %s AND year = %s",
        (gss_code, year),
    )
    register_sites = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(DISTINCT b.site_reference)
        FROM brownfield_sites b
        JOIN exclusion_zones z
          ON z.gss_code = b.gss_code
         AND z.source = %s
         AND z.exclusion_class = ANY(%s)
         AND ST_Contains(
               ST_Transform(ST_SetSRID(z.geom, 4326), 32630),
               ST_SetSRID(ST_MakePoint(b.utm_x, b.utm_y), 32630)
             )
        WHERE b.gss_code = %s AND b.year = %s
        """,
        (source, classes, gss_code, year),
    )
    inside_exclusions = cursor.fetchone()[0]
    cursor.close()

    return {"register_sites": register_sites, "inside_exclusions": inside_exclusions}
