"""
aoi_clipping.py - Clips satellite image to council boundary
============================================================
Clips the satellite band array to only include pixels that fall within
the council boundary retrieved from the PostgreSQL database by GSS code.
Uses matplotlib.path.Path for vectorised point-in-polygon checking across
all valid pixels. Handles MultiPolygon boundaries by checking each polygon
separately and combining results.
"""
import os
import sys
import json
import numpy as np
from pathlib import Path
from matplotlib.path import Path as MplPath

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_query import get_db_connection

def clip_to_council_boundary(band_array: np.ndarray,
                              mask: np.ndarray,
                              original_shape: tuple,
                              tile_metadata: dict,
                              gss_code: str,
                              connection) -> tuple:
    """
    Clips the satellite band array to only include pixels that fall within
    the council boundary retrieved from the database by GSS code. Uses
    matplotlib.path.Path for vectorised point-in-polygon checking across
    all valid pixels. Handles MultiPolygon boundaries by checking each
    polygon separately and combining results.

    Args:
        band_array (np.ndarray): Shape (pixels, 10) — masked band array from
                                 scl_filtering.mask_nodata.
        mask (np.ndarray): Shape (pixels,) — boolean mask from
                           scl_filtering.mask_nodata marking valid pixels.
        original_shape (tuple): (height, width) — original 2D dimensions of
                                the satellite image before flattening.
        tile_metadata (dict): Contains left, top and resolution from the
                              satellite image for pixel-to-UTM conversion.
        gss_code (str): GSS code for the council area to clip to —
                        e.g. 'E06000021' for Stoke-on-Trent.
        connection: Active psycopg2 database connection from
                    database_query.get_db_connection.

    Returns:
        tuple:
            np.ndarray: Shape (clipped_pixels, 10) — band array containing
                        only pixels within the council boundary.
            np.ndarray: Shape (pixels,) — updated boolean mask with pixels
                        outside the council boundary set to False.

    Raises:
        ValueError: If no boundary is found for the given GSS code.
    """
    # Retrieve council boundary in EPSG:32630 (UTM) from database
    cursor = connection.cursor()
    cursor.execute("""
        SELECT ST_AsGeoJSON(ST_Transform(boundary, 32630))
        FROM council_boundaries
        WHERE gss_code = %s
    """, (gss_code,))
    result = cursor.fetchone()
    cursor.close()

    if result is None or result[0] is None:
        raise ValueError(f"No boundary found for GSS code: {gss_code}")

    boundary = json.loads(result[0])

    # Reconstruct 2D pixel grid from flat mask
    mask_2d = mask.reshape(original_shape)
    valid_positions = np.argwhere(mask_2d)

    # Convert pixel positions to UTM coordinates
    left = tile_metadata['left']
    top = tile_metadata['top']
    resolution = tile_metadata['resolution']

    utm_x = left + valid_positions[:, 1] * resolution
    utm_y = top - valid_positions[:, 0] * resolution
    pixel_utm_coords = np.column_stack([utm_x, utm_y])

    # Check which pixels fall within the council boundary
    # Handle both Polygon and MultiPolygon geometry types
    geometry_type = boundary['type']
    inside = np.zeros(len(pixel_utm_coords), dtype=bool)

    if geometry_type == 'Polygon':
        polygons = [boundary['coordinates']]
    elif geometry_type == 'MultiPolygon':
        polygons = boundary['coordinates']
    else:
        raise ValueError(f"Unsupported geometry type: {geometry_type}")

    for polygon in polygons:
        # Use exterior ring only (index 0) — ignore holes for simplicity
        exterior_coords = np.array(polygon[0])

        # Bounding box pre-filter — eliminates majority of pixels instantly
        bbox_mask = (
            (pixel_utm_coords[:, 0] >= exterior_coords[:, 0].min()) &
            (pixel_utm_coords[:, 0] <= exterior_coords[:, 0].max()) &
            (pixel_utm_coords[:, 1] >= exterior_coords[:, 1].min()) &
            (pixel_utm_coords[:, 1] <= exterior_coords[:, 1].max())
        )

        # Only run precise point-in-polygon check on pixels within bounding box
        if bbox_mask.any():
            path = MplPath(exterior_coords)
            inside[bbox_mask] = inside[bbox_mask] | path.contains_points(
                pixel_utm_coords[bbox_mask]
            )

    # Build updated mask — set pixels outside boundary to False
    clipped_mask = mask.copy()
    valid_indices = np.where(mask)[0]
    clipped_mask[valid_indices[~inside]] = False

    # Apply clipped mask to band array
    clipped_array = band_array[inside]

    return clipped_array, clipped_mask