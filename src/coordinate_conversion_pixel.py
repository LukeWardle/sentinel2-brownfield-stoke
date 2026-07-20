"""
coordinate_conversion_pixel.py - Converts external coordinates to UTM and pixel positions.
=========================================================================================
Provides two functions for locating external coordinates within the Sentinel-2 satellite
image pixel grid. convert_bng_to_utm converts British National Grid coordinates (EPSG:27700)
into UTM Zone 30N (EPSG:32630) using pyproj, matching the satellite image's coordinate system.
utm_coordinate_to_pixel then converts those UTM coordinates into pixel row and column positions
using the satellite image's tile metadata (left, top, resolution). Used by register validation
and AOI clipping to locate external datasets within the satellite image's pixel grid.

FND-5: the transformer is built with always_xy=True so axis order is explicitly
(easting, northing) / (x, y) regardless of each CRS's native axis definition.
Without it the code relied on both projected CRS happening to agree on axis
order — a silent-swap landmine if a geographic CRS or a pyproj default ever
enters the chain.

FND-6: the transformer is constructed once at module level and reused.
pyproj Transformer construction is expensive, and convert_bng_to_utm is called
once per register site during setup — previously rebuilding it on every call.
"""

from pyproj import Transformer

# Built once at import (FND-6), with explicit axis order (FND-5).
TRANSFORMER_BNG_TO_UTM = Transformer.from_crs(
    "EPSG:27700", "EPSG:32630", always_xy=True
)


def convert_bng_to_utm(x: float, y: float) -> dict:
    """
    Converts a coordinate from EPSG:27700 (British National Grid)
    to EPSG:32630 (UTM Zone 30N) using the module-level pyproj Transformer.

    Args:
        x (float): easting from EPSG:27700.
        y (float): northing from EPSG:27700.

    Returns:
        utm_position (dict): Converted x and y coordinates in EPSG:32630.
    """
    utm_x, utm_y = TRANSFORMER_BNG_TO_UTM.transform(x, y)
    utm_positions = {"x": utm_x, "y": utm_y}
    return utm_positions


def utm_coordinate_to_pixel(x: float, y: float, tile_metadata: dict) -> dict:
    """
    Converts a UTM coordinate into a pixel position. tile_metadata top, left and resolution
    from the satellite image.
    column = int((x - left) / resolution)
    row = int((top - y) / resolution)

    Args:
        x (float): x coordinates from EPSG:32630.
        y (float): y coordinates from EPSG:32630.
        tile_metadata (dict): Containing the metadata values for left, top, resolution.

    Returns:
        pixel_position (dict): Column and row values returned from formulation.
    """
    left = tile_metadata["left"]
    top = tile_metadata["top"]
    resolution = tile_metadata["resolution"]
    column = int((x - left) / resolution)
    row = int((top - y) / resolution)
    pixel_position = {"column": column, "row": row}
    return pixel_position
