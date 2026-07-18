"""
clustering.py - Groups spectrally similar pixels into candidate sites.
======================================================================
Provides three functions for grouping candidate brownfield pixels into
discrete candidate sites. group_pixels_for_candidate_sites applies BSI
and NDVI thresholds to identify bare soil candidate pixels then uses
connected-component analysis to group spatially adjacent candidates into
discrete sites. calculate_site_properties computes pixel count, hectares,
mean BSI value and centroid UTM coordinates for each group.
generate_boundary_polygons traces the outline of each group and converts
pixel positions to UTM coordinates for database storage and Folium map display.
"""

import numpy as np
import scipy.ndimage


def group_pixels_for_candidate_sites(
    X_reduced: np.ndarray,
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

    Args:
        X_reduced (np.ndarray): Shape (pixels, k) — PCA-reduced spectral values
                                for each valid pixel, output of pca.project.
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
        min_pixels (int): Minimum number of pixels for a group to be retained
                          as a candidate site. Default 5 (0.2 hectares at 20m).
        max_pixels (int): Maximum number of pixels for a group to be retained
                          as a candidate site. Default 2500 (100 hectares at 20m).
                          Larger groups are likely noise or non-brownfield land.

    Returns:
        candidate_groups (dict): Keys are integer site IDs, values are lists of
                                 pixel indices (positions in the flattened masked
                                 array) belonging to that site.
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

    # Step 3 — dilate to connect nearby pixels into patches
    candidate_2d = scipy.ndimage.binary_dilation(candidate_2d, iterations=1)

    # Step 4 — connected component labelling
    labelled_array, num_features = scipy.ndimage.label(candidate_2d)
    print(f"Connected components found: {num_features}")

    # Step 5 — build flat index lookup
    flat_indices = np.full(original_shape, -1, dtype=int)
    flat_indices[valid_positions[:, 0], valid_positions[:, 1]] = np.arange(
        len(valid_positions)
    )

    # Step 6 — build candidate groups in one vectorised pass
    candidate_groups = {}
    site_id = 0
    all_positions = np.argwhere(labelled_array > 0)
    all_labels = labelled_array[all_positions[:, 0], all_positions[:, 1]]
    all_flat_indices = flat_indices[all_positions[:, 0], all_positions[:, 1]]
    sort_order = np.argsort(all_labels)
    all_labels = all_labels[sort_order]
    all_flat_indices = all_flat_indices[sort_order]
    unique_labels, start_indices = np.unique(all_labels, return_index=True)
    end_indices = np.append(start_indices[1:], len(all_labels))

    for label, start, end in zip(unique_labels, start_indices, end_indices):
        count = end - start
        if count < min_pixels or count > max_pixels:
            continue
        pixel_indices = all_flat_indices[start:end]
        pixel_indices = pixel_indices[pixel_indices != -1].tolist()
        if min_pixels <= len(pixel_indices) <= max_pixels:
            candidate_groups[site_id] = pixel_indices
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
    using tile_metadata. Results are used for database storage and register
    matching.

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
    Generates boundary polygon for each candidate site by tracing the outline
    of grouped pixels in the 2D grid and converting pixel positions to UTM
    coordinates using tile_metadata. Polygons are used for database storage and
    Folium interactive map display.

    Args:
        candidate_groups (dict): Keys are site IDs, values are lists of pixel
                                 indices — output of group_pixels_for_candidate_sites.
        mask (np.ndarray): Shape (pixels,) — boolean mask from scl_filtering.mask_nodata.
        original_shape (tuple): (height, width) — original 2D dimensions of the
                                satellite image before flattening.
        tile_metadata (dict): Contains left, top and resolution from the satellite
                              image, used to convert pixel positions to UTM coordinates.

    Returns:
        site_polygons (list): List of dicts, one per site, each containing site_id
                              and boundary — a list of UTM coordinate pairs tracing
                              the outline of the grouped pixels, ready for Folium
                              map display and database storage.
    """
    left = tile_metadata["left"]
    top = tile_metadata["top"]
    resolution = tile_metadata["resolution"]
    mask_2d = mask.reshape(original_shape)
    valid_positions = np.argwhere(mask_2d)
    site_polygons = []

    for site_id, pixel_indices in candidate_groups.items():
        site_grid = np.zeros(original_shape, dtype=bool)
        positions = valid_positions[pixel_indices]
        site_grid[positions[:, 0], positions[:, 1]] = True

        eroded = scipy.ndimage.binary_erosion(site_grid)
        boundary_grid = site_grid & ~eroded
        boundary_positions = np.argwhere(boundary_grid)

        boundary_utm = [
            [float(left + col * resolution), float(top - row * resolution)]
            for row, col in boundary_positions
        ]

        if boundary_utm:
            boundary_utm.append(boundary_utm[0])

        site_polygons.append({"site_id": site_id, "boundary": boundary_utm})

    return site_polygons
