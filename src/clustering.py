"""
clustering.py - Groups spectrally similar pixels into candidate sites.
======================================================================
Provides three functions for grouping candidate brownfield pixels into
discrete candidate sites. group_pixels_for_candidate_sites applies BSI
and NDVI thresholds to identify bare soil candidate pixels then uses
connected-component analysis to group spatially adjacent candidates into
discrete sites. calculate_site_properties computes pixel count, hectares,
mean BSI value and centroid UTM coordinates for each group.
generate_boundary_polygons converts each group's pixel footprint into a
valid GeoJSON Polygon or MultiPolygon in UTM coordinates for database
storage, exclusion overlap testing and Folium map display.

P0-7: detection is driven purely by the BSI/NDVI thresholds. The PCA
projection previously accepted as a parameter was never used in this
module and has been removed; PCA now exists solely for the false-colour
visualisation in main.py.

FND-1: morphological dilation is used only as a connectivity scaffold for
labelling. Group membership is the intersection of each labelled blob with
the original (pre-dilation) candidate map, so dilation-border pixels that
never passed the BSI/NDVI thresholds cannot contaminate mean_bsi,
pixel_count or hectares.

FND-2: boundary polygons are produced by rasterio.features.shapes on each
site's pixel grid, which emits valid, correctly ordered rings (with holes
where present) rather than raster-ordered boundary pixels. The exact pixel
footprint is preserved, so polygon area equals pixel_count x 400 m^2.
"""

import numpy as np
import scipy.ndimage
from rasterio import features as rio_features
from rasterio.transform import from_origin


def group_pixels_for_candidate_sites(
    mask: np.ndarray,
    original_shape: tuple,
    bsi_array: np.ndarray,
    ndvi_array: np.ndarray,
    bsi_threshold: float = 0.05,
    ndvi_threshold: float = 0.2,
    min_pixels: int = 5,
    max_pixels: int = 2500,
) -> dict:
    """
    Identifies candidate brownfield pixels using BSI and NDVI thresholds
    then groups spatially adjacent candidates into discrete sites using
    connected-component analysis. Only pixels with BSI above bsi_threshold
    AND NDVI below ndvi_threshold are considered brownfield candidates.
    Groups smaller than min_pixels or larger than max_pixels are filtered out.

    Dilation is applied to the candidate map purely so that labelling
    connects near-adjacent patches; the dilated pixels themselves are never
    admitted to a group (FND-1). Every pixel index returned passed the
    BSI/NDVI thresholds.

    Args:
        mask (np.ndarray): Shape (original_height * original_width,) — boolean
                           mask from scl_filtering.mask_nodata marking which
                           pixels in the original flattened array are valid.
        original_shape (tuple): (height, width) — original 2D dimensions of the
                                satellite image before flattening.
        bsi_array (np.ndarray): Shape (pixels,) — BSI values for each valid pixel
                                from preprocess.compute_bsi.
        ndvi_array (np.ndarray): Shape (pixels,) — NDVI values for each valid
                                 pixel from preprocess.compute_ndvi.
        bsi_threshold (float): Minimum BSI value for a pixel to be considered
                               a brownfield candidate. Default 0.05.
        ndvi_threshold (float): Maximum NDVI value for a pixel to be considered
                                a brownfield candidate. Default 0.2.
        min_pixels (int): Minimum number of true candidate pixels for a group
                          to be retained. Default 5 (0.2 hectares at 20m).
        max_pixels (int): Maximum number of true candidate pixels for a group
                          to be retained. Default 2500 (100 hectares at 20m).

    Returns:
        candidate_groups (dict): Keys are integer site IDs, values are lists of
                                 pixel indices (positions in the flattened masked
                                 array) belonging to that site. Every index is a
                                 true threshold-passing candidate pixel.
    """
    # Step 1 — identify brownfield candidate pixels using BSI and NDVI thresholds
    brownfield_candidates = (bsi_array > bsi_threshold) & (ndvi_array < ndvi_threshold)
    if len(bsi_array) > 0:
        print(
            f"Brownfield candidate pixels: {brownfield_candidates.sum():,} "
            f"({brownfield_candidates.sum() / len(bsi_array) * 100:.1f}% of valid pixels)"
        )
    else:
        print("Brownfield candidate pixels: 0 (empty array)")

    if brownfield_candidates.sum() == 0:
        print(
            "No brownfield candidates found — try lowering bsi_threshold or raising ndvi_threshold"
        )
        return {}

    # Step 2 — reconstruct 2D candidate map
    mask_2d = mask.reshape(original_shape)
    candidate_2d = np.zeros(original_shape, dtype=bool)
    valid_positions = np.argwhere(mask_2d)
    candidate_positions = valid_positions[brownfield_candidates]
    candidate_2d[candidate_positions[:, 0], candidate_positions[:, 1]] = True

    # Step 3 — dilate a COPY to connect nearby pixels for labelling only.
    # The original candidate_2d is retained: dilation is a connectivity
    # scaffold, not a membership grant (FND-1).
    dilated_2d = scipy.ndimage.binary_dilation(candidate_2d, iterations=1)

    # Step 4 — connected component labelling on the dilated map
    labelled_array, num_features = scipy.ndimage.label(dilated_2d)
    print(f"Connected components found: {num_features}")

    # Step 5 — build flat index lookup for valid pixels
    flat_indices = np.full(original_shape, -1, dtype=int)
    flat_indices[valid_positions[:, 0], valid_positions[:, 1]] = np.arange(
        len(valid_positions)
    )

    # Step 6 — build candidate groups from TRUE candidate pixels only (FND-1):
    # membership = labelled blob INTERSECTED with the pre-dilation candidate map.
    membership_2d = (labelled_array > 0) & candidate_2d
    member_positions = np.argwhere(membership_2d)
    member_labels = labelled_array[member_positions[:, 0], member_positions[:, 1]]
    member_flat_indices = flat_indices[member_positions[:, 0], member_positions[:, 1]]

    sort_order = np.argsort(member_labels, kind="stable")
    member_labels = member_labels[sort_order]
    member_flat_indices = member_flat_indices[sort_order]
    unique_labels, start_indices = np.unique(member_labels, return_index=True)
    end_indices = np.append(start_indices[1:], len(member_labels))

    candidate_groups = {}
    site_id = 0
    for _label, start, end in zip(unique_labels, start_indices, end_indices):
        pixel_indices = member_flat_indices[start:end]
        pixel_indices = pixel_indices[pixel_indices != -1]
        count = len(pixel_indices)
        if count < min_pixels or count > max_pixels:
            continue
        candidate_groups[site_id] = pixel_indices.tolist()
        site_id += 1

    print(f"Candidate sites after size filter: {len(candidate_groups)}")
    return candidate_groups


def calculate_site_properties(
    candidate_groups: dict,
    bsi_array: np.ndarray,
    mask: np.ndarray,
    original_shape: tuple,
    tile_metadata: dict,
) -> list:
    """
    Calculates properties for each candidate site — pixel count, hectares,
    mean BSI value across all site pixels, and centroid UTM coordinates converted
    using tile_metadata. Because group membership contains only true
    threshold-passing candidate pixels (FND-1), mean_bsi and hectares reflect
    the actual bare-soil footprint rather than a dilation-inflated one.

    Args:
        candidate_groups (dict): Keys are site IDs, values are lists of pixel
                                 indices — output of group_pixels_for_candidate_sites.
        bsi_array (np.ndarray): Shape (pixels,) — BSI value for each valid pixel,
                                output of preprocess.compute_bsi.
        mask (np.ndarray): Shape (pixels,) — boolean mask from scl_filtering.mask_nodata.
        original_shape (tuple): (height, width) — original 2D dimensions of the
                                satellite image before flattening.
        tile_metadata (dict): Contains left, top and resolution from the satellite
                              image, used to convert pixel positions to UTM coordinates.

    Returns:
        site_properties (list): List of dicts, one per site, each containing
                                site_id, pixel_count, hectares, mean_bsi,
                                centroid_utm_x, centroid_utm_y.
    """
    left = tile_metadata["left"]
    top = tile_metadata["top"]
    resolution = tile_metadata["resolution"]
    mask_2d = mask.reshape(original_shape)
    valid_positions = np.argwhere(mask_2d)
    site_properties = []

    for site_id, pixel_indices in candidate_groups.items():
        pixel_count = len(pixel_indices)
        mean_bsi = float(bsi_array[pixel_indices].mean())
        positions = valid_positions[pixel_indices]
        centroid_row = positions[:, 0].mean()
        centroid_col = positions[:, 1].mean()
        centroid_utm_x = left + (centroid_col * resolution)
        centroid_utm_y = top - (centroid_row * resolution)
        site_properties.append(
            {
                "site_id": site_id,
                "pixel_count": pixel_count,
                "hectares": round(pixel_count * 0.04, 2),
                "mean_bsi": mean_bsi,
                "centroid_utm_x": float(centroid_utm_x),
                "centroid_utm_y": float(centroid_utm_y),
            }
        )
    return site_properties


def generate_boundary_polygons(
    candidate_groups: dict, mask: np.ndarray, original_shape: tuple, tile_metadata: dict
) -> list:
    """
    Converts each candidate site's pixel footprint into a valid GeoJSON
    geometry in UTM (EPSG:32630) coordinates using rasterio.features.shapes
    (FND-2). Rings are correctly ordered and closed, holes are preserved, and
    a site whose pixels form several disconnected parts becomes a
    MultiPolygon. The polygon traces exact pixel edges, so its area equals
    pixel_count x resolution^2 — suitable for ST_GeomFromGeoJSON storage
    (FND-3) and PostGIS area-overlap exclusion testing (FND-4).

    Args:
        candidate_groups (dict): Keys are site IDs, values are lists of pixel
                                 indices — output of group_pixels_for_candidate_sites.
        mask (np.ndarray): Shape (pixels,) — boolean mask from scl_filtering.mask_nodata.
        original_shape (tuple): (height, width) — original 2D dimensions of the
                                satellite image before flattening.
        tile_metadata (dict): Contains left, top and resolution from the satellite
                              image, used to place pixel footprints in UTM space.

    Returns:
        site_polygons (list): List of dicts, one per site, each containing
                              site_id and geometry — a GeoJSON Polygon or
                              MultiPolygon dict in EPSG:32630 coordinates, or
                              None when a site has no pixels.
    """
    left = tile_metadata["left"]
    top = tile_metadata["top"]
    resolution = tile_metadata["resolution"]
    transform = from_origin(left, top, resolution, resolution)
    mask_2d = mask.reshape(original_shape)
    valid_positions = np.argwhere(mask_2d)
    site_polygons = []

    for site_id, pixel_indices in candidate_groups.items():
        site_grid = np.zeros(original_shape, dtype=np.uint8)
        positions = valid_positions[pixel_indices]
        site_grid[positions[:, 0], positions[:, 1]] = 1

        rings = [
            geom["coordinates"]
            for geom, value in rio_features.shapes(
                site_grid, mask=site_grid.astype(bool), transform=transform
            )
            if value == 1
        ]

        if not rings:
            geometry = None
        elif len(rings) == 1:
            geometry = {"type": "Polygon", "coordinates": rings[0]}
        else:
            geometry = {"type": "MultiPolygon", "coordinates": rings}

        site_polygons.append({"site_id": site_id, "geometry": geometry})

    return site_polygons
