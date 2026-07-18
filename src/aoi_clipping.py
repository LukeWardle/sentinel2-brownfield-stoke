"""
aoi_clipping.py - Clips satellite image to council boundary
============================================================
Clips the raw Sentinel-2 grid to only include pixels that fall within
the council boundary retrieved from the PostGIS database by GSS code.
Runs before SCL filtering so that mask_nodata only processes pixels
already inside the boundary — for Stoke that's ~233,000 pixels rather
than the full ~21 million in the tile.

Uses matplotlib.path.Path for vectorised point-in-polygon checking
across every pixel in the tile. Handles MultiPolygon boundaries by
checking each polygon separately and combining the results with a
logical OR. Pixels outside the boundary have their band values zeroed
and their SCL class set to 0 (nodata) so that mask_nodata will drop
them alongside genuinely defective pixels.
"""

import json

import numpy as np
from matplotlib.path import Path as MplPath


def clip_to_council_boundary(
    band_array_2d: np.ndarray,
    scl_array_2d: np.ndarray,
    tile_metadata: dict,
    gss_code: str,
    connection,
) -> tuple:
    """
    Clips the raw satellite arrays to the council boundary retrieved
    from PostGIS by GSS code. Runs before SCL filtering, so takes the
    raw 3D band grid and 2D SCL grid directly from data_loading_satellite.

    Retrieves the council boundary polygon in EPSG:32630 (UTM Zone 30N),
    builds UTM coordinates for every pixel in the tile using tile_metadata,
    applies a bounding-box pre-filter per polygon exterior ring, then runs
    matplotlib.path.Path.contains_points on the pre-filtered subset. Handles
    both Polygon and MultiPolygon geometries.

    Pixels outside the boundary are zeroed in the band array and set to
    SCL class 0 (nodata) in the SCL array. This preserves the grid
    dimensions so tile_metadata remains valid and lets mask_nodata drop
    out-of-boundary pixels naturally alongside genuine nodata pixels.

    Args:
        band_array_2d (np.ndarray): Shape (height, width, 10) — raw
                                     Sentinel-2 bands from load_bands.
        scl_array_2d (np.ndarray): Shape (height, width) — raw Scene
                                    Classification Layer from load_scl.
        tile_metadata (dict): Contains left, top and resolution from the
                              satellite image for pixel-to-UTM conversion.
        gss_code (str): GSS code for the council area to clip to —
                        e.g. 'E06000021' for Stoke-on-Trent.
        connection: Active psycopg2 database connection from
                    database_query.get_db_connection.

    Returns:
        tuple:
            np.ndarray: Shape (height, width, 10) — band array with
                        out-of-boundary pixels zeroed across all bands.
            np.ndarray: Shape (height, width) — SCL array with
                        out-of-boundary pixels set to class 0 (nodata).

    Raises:
        ValueError: If no boundary is found for the given GSS code, or
                    the geometry type is not Polygon or MultiPolygon.
    """
    # Retrieve council boundary in EPSG:32630 (UTM) from database
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT ST_AsGeoJSON(ST_Transform(boundary, 32630))
        FROM council_boundaries
        WHERE gss_code = %s
    """,
        (gss_code,),
    )
    result = cursor.fetchone()
    cursor.close()

    if result is None or result[0] is None:
        raise ValueError(f"No boundary found for GSS code: {gss_code}")

    boundary = json.loads(result[0])

    # Build UTM coordinates for every pixel in the tile.
    # xs_2d[row, col] holds the UTM x for that pixel, ys_2d[row, col] the UTM y.
    height, width = scl_array_2d.shape
    left = tile_metadata["left"]
    top = tile_metadata["top"]
    resolution = tile_metadata["resolution"]

    utm_x_per_col = left + np.arange(width) * resolution
    utm_y_per_row = top - np.arange(height) * resolution
    xs_2d, ys_2d = np.meshgrid(utm_x_per_col, utm_y_per_row)
    pixel_utm_coords = np.column_stack([xs_2d.ravel(), ys_2d.ravel()])

    # Check which pixels fall within the council boundary.
    # Handles both Polygon and MultiPolygon geometry types.
    geometry_type = boundary["type"]
    inside = np.zeros(len(pixel_utm_coords), dtype=bool)

    if geometry_type == "Polygon":
        polygons = [boundary["coordinates"]]
    elif geometry_type == "MultiPolygon":
        polygons = boundary["coordinates"]
    else:
        raise ValueError(f"Unsupported geometry type: {geometry_type}")

    for polygon in polygons:
        # Use exterior ring only (index 0) — holes ignored for simplicity
        exterior_coords = np.array(polygon[0])

        # Bounding box pre-filter — eliminates the majority of tile pixels
        # instantly before running the expensive point-in-polygon check.
        bbox_mask = (
            (pixel_utm_coords[:, 0] >= exterior_coords[:, 0].min())
            & (pixel_utm_coords[:, 0] <= exterior_coords[:, 0].max())
            & (pixel_utm_coords[:, 1] >= exterior_coords[:, 1].min())
            & (pixel_utm_coords[:, 1] <= exterior_coords[:, 1].max())
        )

        # Only run precise point-in-polygon check on pixels inside the bbox
        if bbox_mask.any():
            path = MplPath(exterior_coords)
            inside[bbox_mask] = inside[bbox_mask] | path.contains_points(
                pixel_utm_coords[bbox_mask]
            )

    # Reshape the boolean mask back onto the 2D grid
    inside_2d = inside.reshape(height, width)

    # Zero band values outside the boundary. Boolean indexing with a 2D
    # mask on a 3D array assigns across the band axis at masked positions.
    clipped_bands = band_array_2d.copy()
    clipped_bands[~inside_2d] = 0

    # Set SCL class to 0 (nodata) outside the boundary — mask_nodata will
    # drop these alongside genuine nodata pixels.
    clipped_scl = scl_array_2d.copy()
    clipped_scl[~inside_2d] = 0

    return clipped_bands, clipped_scl
