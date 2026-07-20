"""
exclusion_loader.py - Fetch OSM land-use polygons and populate exclusion_zones
==============================================================================
Populates the exclusion_zones table with land-use polygons that are masked
out of the candidate search before clustering (P1-5). A July 2026 labelling
pilot found the raw BSI/NDVI detector fires on any bare or hard man-made
surface with no land-use awareness — active industrial units, retail car
parks, operational infrastructure and school hardstanding all appeared as
false positives. This module fetches the polygons for those classes from
OpenStreetMap via the Overpass API, tags each with its exclusion_class and
source, and stores them for the masking step to use.

This is a setup-time loader, run once per council (like setup_boundaries.py),
not a per-pipeline-run step. Fetched polygons are cached in the database so
Overpass is queried only once per council per class.

The class-to-tag mapping lives in EXCLUSION_CLASSES below. It is the single
place that defines what each exclusion class means in OSM terms, and it is
what keeps the data source swappable: an OS OpenData loader would implement
the same classes from different tags without changing the schema or the
masking step. See P4-8 for the OSM/ODbL licensing review.
"""

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_HEADERS = {
    "User-Agent": "SiteSignal/1.0 (brownfield detection; contact l.wardle@live.co.uk)"
}

# Class-to-OSM-tag mapping. Each class lists Overpass tag filters; a polygon
# matching any filter for a class is fetched under that class. Kept in code
# because it is detection logic, not data — the masking step and any future
# OS OpenData loader implement the same class names from different sources.
EXCLUSION_CLASSES = {
    "building": [
        '["building"]',
    ],
    "car_park": [
        '["amenity"="parking"]',
    ],
    "amenity_leisure": [
        '["leisure"]',
        '["amenity"="school"]',
        '["amenity"="college"]',
        '["landuse"="recreation_ground"]',
    ],
    "infrastructure": [
        '["man_made"="wastewater_plant"]',
        '["man_made"="water_works"]',
        '["power"="substation"]',
        '["landuse"="industrial"]',
    ],
    "quarry": [
        '["landuse"="quarry"]',
        '["landuse"="landfill"]',
    ],
    "agriculture": [
        '["landuse"="farmland"]',
        '["landuse"="meadow"]',
    ],
}


def build_overpass_query(bbox: dict, exclusion_class: str) -> str:
    """
    Builds an Overpass QL query string for one exclusion class within a
    bounding box. Pure string building — no network call — so the class-to-tag
    mapping can be unit tested without hitting Overpass.

    Args:
        bbox (dict): Bounding box with west, east, south, north keys in
                     EPSG:4326, as returned by api_copernicus.get_bounding_box.
        exclusion_class (str): One of the keys in EXCLUSION_CLASSES.

    Returns:
        query (str): Overpass QL query returning ways and relations matching
                     any tag filter for the class, with full geometry, as JSON.

    Raises:
        ValueError: If exclusion_class is not a known class.
    """
    if exclusion_class not in EXCLUSION_CLASSES:
        raise ValueError(f"Unknown exclusion_class: {exclusion_class}")

    # Overpass expects bbox as (south, west, north, east)
    bbox_str = f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"

    statements = []
    for tag_filter in EXCLUSION_CLASSES[exclusion_class]:
        statements.append(f"  way{tag_filter}({bbox_str});")
        statements.append(f"  relation{tag_filter}({bbox_str});")
    body = "\n".join(statements)

    return f"[out:json][timeout:60];\n(\n{body}\n);\nout geom;"


def _ring_from_points(points: list) -> list:
    """
    Converts an Overpass geometry point list into a closed GeoJSON ring.
    Returns None if the ring has too few points to form a polygon.

    Args:
        points (list): List of {lat, lon} dicts from Overpass 'out geom' output.

    Returns:
        ring (list) or None: Closed list of [lon, lat] pairs, or None if invalid.
    """
    ring = [[point["lon"], point["lat"]] for point in points]
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    if len(ring) < 4:
        return None
    return ring


def parse_osm_element(element: dict) -> dict:
    """
    Parses a single Overpass element into a GeoJSON geometry. Handles both
    simple ways (flat geometry -> Polygon) and relations (outer/inner members
    -> Polygon with holes, or MultiPolygon when a relation has several outer
    rings). Relations are why big industrial estates, parks and infrastructure
    sites — which are frequently multipolygons rather than single ways — are
    captured rather than skipped.

    Args:
        element (dict): One element from an Overpass 'out geom' response.

    Returns:
        parsed (dict) or None: Dict with source_ref and a GeoJSON geometry
                               (Polygon or MultiPolygon), or None if the element
                               has no usable geometry.
    """
    element_type = element.get("type")
    source_ref = f"{element.get('type')}/{element.get('id')}"

    if element_type == "way":
        ring = _ring_from_points(element.get("geometry") or [])
        if ring is None:
            return None
        return {
            "source_ref": source_ref,
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }

    if element_type == "relation":
        outers = []
        inners = []
        for member in element.get("members", []):
            if member.get("type") != "way" or not member.get("geometry"):
                continue
            ring = _ring_from_points(member["geometry"])
            if ring is None:
                continue
            if member.get("role") == "inner":
                inners.append(ring)
            else:
                outers.append(ring)
        if not outers:
            return None
        if len(outers) == 1:
            # Single outer ring -> Polygon, any inners become holes
            return {
                "source_ref": source_ref,
                "geometry": {"type": "Polygon", "coordinates": [outers[0]] + inners},
            }
        # Multiple outer rings -> MultiPolygon. Inner holes are attached to the
        # first outer as a pragmatic simplification; exact hole-to-outer
        # assignment is not needed for masking, which only tests containment.
        polygons = [[outer] for outer in outers]
        if inners:
            polygons[0].extend(inners)
        return {
            "source_ref": source_ref,
            "geometry": {"type": "MultiPolygon", "coordinates": polygons},
        }

    return None


def fetch_osm_polygons(bbox: dict, exclusion_class: str) -> list:
    """
    Queries the Overpass API for all polygons of one exclusion class within a
    bounding box and returns them as source_ref/geometry dicts. This is the
    single network-bound function — tests mock the requests.post call here.
    Parsing of each element is delegated to parse_osm_element so ways and
    relation multipolygons are both handled and can be tested independently.

    Args:
        bbox (dict): Bounding box with west, east, south, north keys (EPSG:4326).
        exclusion_class (str): One of the keys in EXCLUSION_CLASSES.

    Returns:
        polygons (list): List of dicts each containing source_ref (str, e.g.
                         'way/12345' or 'relation/678') and geometry (dict, a
                         GeoJSON Polygon or MultiPolygon in EPSG:4326).

    Raises:
        ValueError: If the Overpass request fails.
    """
    query = build_overpass_query(bbox, exclusion_class)
    response = None
    for attempt in range(4):
        response = requests.post(
            OVERPASS_URL, data=query.encode("utf-8"), headers=OVERPASS_HEADERS
        )
        if response.status_code == 200:
            break
        if response.status_code == 429:
            # Overpass rate limit — wait and retry with linear backoff
            time.sleep(10 * (attempt + 1))
            continue
        raise ValueError(
            f"Overpass request failed for {exclusion_class} — "
            f"status code {response.status_code}"
        )
    if response is None or response.status_code != 200:
        raise ValueError(
            f"Overpass request failed for {exclusion_class} after retries — "
            f"status code {response.status_code if response else 'no response'}"
        )

    elements = response.json().get("elements", [])
    polygons = []
    for element in elements:
        parsed = parse_osm_element(element)
        if parsed is not None:
            polygons.append(parsed)
    return polygons


def store_exclusion_zones(
    polygons: list, gss_code: str, exclusion_class: str, source: str, connection
) -> None:
    """
    Stores exclusion-zone polygons in the exclusion_zones table. Deletes any
    existing rows for the same (gss_code, exclusion_class, source) first so
    re-running the loader for a council replaces rather than duplicates.
    Geometry is written in EPSG:4326 via ST_GeomFromGeoJSON to match
    council_boundaries.

    Args:
        polygons (list): List of dicts each with source_ref and geometry, as
                         returned by fetch_osm_polygons.
        gss_code (str): GSS code for the council these polygons belong to.
        exclusion_class (str): The class label for these polygons.
        source (str): Data provenance — e.g. 'osm'.
        connection: Active psycopg2 connection.

    Returns:
        None — writes to exclusion_zones.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM exclusion_zones
        WHERE gss_code = %s AND exclusion_class = %s AND source = %s
        """,
        (gss_code, exclusion_class, source),
    )
    for polygon in polygons:
        cursor.execute(
            """
            INSERT INTO exclusion_zones
                (gss_code, exclusion_class, source, source_ref, geom)
            VALUES (%s, %s, %s, %s, ST_GeomFromGeoJSON(%s))
            """,
            (
                gss_code,
                exclusion_class,
                source,
                polygon["source_ref"],
                json.dumps(polygon["geometry"]),
            ),
        )
    connection.commit()
    cursor.close()


def load_exclusions_for_council(
    gss_code: str, connection, classes: list = None
) -> dict:
    """
    Orchestrates the full load for one council: retrieves the council boundary,
    derives its bounding box, then fetches and stores every requested exclusion
    class from OSM. Returns a per-class count of stored polygons.

    Args:
        gss_code (str): GSS code for the council to load exclusions for.
        connection: Active psycopg2 connection.
        classes (list): Optional list of class names to load. Defaults to all
                        keys in EXCLUSION_CLASSES.

    Returns:
        counts (dict): Mapping of exclusion_class to number of polygons stored.

    Raises:
        ValueError: If no boundary is found for the given GSS code.
    """
    from src.api_copernicus import get_bounding_box

    cursor = connection.cursor()
    cursor.execute(
        "SELECT ST_AsGeoJSON(boundary) FROM council_boundaries WHERE gss_code = %s",
        (gss_code,),
    )
    result = cursor.fetchone()
    cursor.close()
    if result is None or result[0] is None:
        raise ValueError(f"No boundary found for GSS code: {gss_code}")

    boundary = json.loads(result[0])
    # get_bounding_box expects a single ring; MultiPolygon boundaries expose
    # coordinates[0][0], Polygon coordinates[0]. Normalise to a ring of points.
    if boundary["type"] == "MultiPolygon":
        ring = boundary["coordinates"][0][0]
    else:
        ring = boundary["coordinates"][0]
    bbox = get_bounding_box({"coordinates": [ring]})

    if classes is None:
        classes = list(EXCLUSION_CLASSES.keys())

    counts = {}
    for exclusion_class in classes:
        polygons = fetch_osm_polygons(bbox, exclusion_class)
        store_exclusion_zones(polygons, gss_code, exclusion_class, "osm", connection)
        counts[exclusion_class] = len(polygons)
        time.sleep(2)  # courtesy pause between Overpass queries
    return counts
