"""
features.py - Per-candidate feature extraction for the v3 classifier (P1-6).
============================================================================
Computes a small per-site feature set at pipeline time, attached to each
candidate dict so store_candidate_sites persists it (migration 004).

Architecture note: this module implements fork (A) from Notebook 07's
architecture decision — features describe CANDIDATES emitted by the
BSI/NDVI threshold gate, supporting a model that re-ranks bare-land leads
(and the "does a model beat a simple persistence rule?" comparison from
the prediction-feasibility review). It does not implement fork (B)
gate-replacing detection; that would be pixel/patch-level sampling and a
different module.

The feature set is deliberately small — eight columns here plus the
pixel_count and bsi_value already stored — because the post-FND sample
maths (~18 positives per image) puts a hard ceiling on how many features
a first model can support.

Features:
- std_bsi, mean_ndvi, std_ndvi: spectral spread and vegetation state
  over the site's true (FND-1) member pixels
- mean_b04, mean_b08, mean_b11: red / NIR / SWIR reflectance means —
  the bands driving BSI/NDVI, exposed raw so the model can weight them
- compactness: 4*pi*area / perimeter^2 of the footprint geometry
  (1.0 = circle; long thin infrastructure scores low)
- prior_date_count: number of OTHER stored image dates with a candidate
  within 50m — the persistence signal (0 until multi-date runs exist)
"""

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

FEATURE_COLUMNS = [
    "std_bsi",
    "mean_ndvi",
    "std_ndvi",
    "mean_b04",
    "mean_b08",
    "mean_b11",
    "compactness",
    "prior_date_count",
]

# Model inputs = stored features + the two columns candidate_sites already
# carried. Used by model_train to assemble X consistently.
MODEL_INPUT_COLUMNS = ["pixel_count", "bsi_value"] + FEATURE_COLUMNS


def _ring_perimeter(ring: list) -> float:
    total = 0.0
    for i in range(len(ring) - 1):
        dx = ring[i + 1][0] - ring[i][0]
        dy = ring[i + 1][1] - ring[i][1]
        total += math.hypot(dx, dy)
    return total


def _ring_area(ring: list) -> float:
    """Shoelace area (positive regardless of winding)."""
    area = 0.0
    for i in range(len(ring) - 1):
        area += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(area) / 2.0


def compactness_from_geometry(geometry: dict | None) -> float | None:
    """
    Polsby-Popper compactness 4*pi*A / P^2 for a GeoJSON Polygon or
    MultiPolygon in projected (metre) coordinates. Exterior rings add
    area, interior rings (holes) subtract it; every ring contributes
    perimeter. Returns None for missing/empty geometry.
    """
    if not geometry:
        return None
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        return None

    area = 0.0
    perimeter = 0.0
    for rings in polygons:
        for i, ring in enumerate(rings):
            ring_area = _ring_area(ring)
            area += ring_area if i == 0 else -ring_area
            perimeter += _ring_perimeter(ring)

    if perimeter <= 0 or area <= 0:
        return None
    return min(4.0 * math.pi * area / (perimeter**2), 1.0)


def count_prior_dates(
    utm_x: float,
    utm_y: float,
    gss_code: str,
    image_date: str,
    connection,
    distance_m: float = 50.0,
) -> int:
    """
    Counts distinct OTHER image dates on which a stored candidate exists
    within distance_m of this location — the temporal persistence feature
    (P1-4 signal as a model input). 0 until multi-date runs (#92) populate
    the table; the column becomes informative as seasonal runs land.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(DISTINCT image_date)
        FROM candidate_sites
        WHERE gss_code = %s
          AND image_date <> %s
          AND ST_DWithin(
                ST_SetSRID(ST_MakePoint(utm_x, utm_y), 32630),
                ST_SetSRID(ST_MakePoint(%s, %s), 32630),
                %s
              )
        """,
        (gss_code, image_date, utm_x, utm_y, distance_m),
    )
    count = cursor.fetchone()[0]
    cursor.close()
    return int(count)


def compute_candidate_features(
    candidate_groups: dict,
    normalised_array: np.ndarray,
    bsi_array: np.ndarray,
    ndvi_array: np.ndarray,
    bands_20m: list,
    bands_10m: list,
) -> dict:
    """
    Computes the spectral features for every candidate group from the
    pipeline's in-memory arrays (the raster is deleted after each run, so
    features must be captured here, not post-hoc from the database).

    Args:
        candidate_groups (dict): site_id -> list of valid-pixel indices,
                                 from group_pixels_for_candidate_sites.
                                 Indices are true FND-1 member pixels.
        normalised_array (np.ndarray): (valid_pixels, 10) reflectance from
                                       preprocess.normalise_band_array.
        bsi_array, ndvi_array (np.ndarray): (valid_pixels,) index values.
        bands_20m, bands_10m (list): band-name lists from
                                     data_loading_satellite — column order
                                     of normalised_array is bands_20m +
                                     bands_10m, matching preprocess.

    Returns:
        dict: site_id -> {std_bsi, mean_ndvi, std_ndvi, mean_b04,
                          mean_b08, mean_b11} (floats).
    """
    bands_list = bands_20m + bands_10m
    b04 = bands_list.index("B04")
    b08 = bands_list.index("B08")
    b11 = bands_list.index("B11")

    features = {}
    for site_id, pixel_indices in candidate_groups.items():
        idx = np.asarray(pixel_indices, dtype=int)
        features[site_id] = {
            "std_bsi": float(bsi_array[idx].std()),
            "mean_ndvi": float(ndvi_array[idx].mean()),
            "std_ndvi": float(ndvi_array[idx].std()),
            "mean_b04": float(normalised_array[idx, b04].mean()),
            "mean_b08": float(normalised_array[idx, b08].mean()),
            "mean_b11": float(normalised_array[idx, b11].mean()),
        }
    return features


def attach_features(
    site_properties: list,
    spectral_features: dict,
    gss_code: str,
    image_date: str,
    connection,
) -> None:
    """
    Merges spectral features, geometry compactness and the persistence
    count onto each site dict in place, so store_candidate_sites persists
    them (migration 004 columns). Sites missing from spectral_features
    receive None values rather than raising — store handles NULLs.
    """
    for site in site_properties:
        spec = spectral_features.get(site["site_id"], {})
        for key in (
            "std_bsi",
            "mean_ndvi",
            "std_ndvi",
            "mean_b04",
            "mean_b08",
            "mean_b11",
        ):
            site[key] = spec.get(key)
        site["compactness"] = compactness_from_geometry(site.get("geometry"))
        site["prior_date_count"] = count_prior_dates(
            site["centroid_utm_x"],
            site["centroid_utm_y"],
            gss_code,
            image_date,
            connection,
        )
