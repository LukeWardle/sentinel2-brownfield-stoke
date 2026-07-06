"""
clustering.py - Groups spectrally similar pixels into candidate sites.
======================================================================
Provides three functions for grouping spectrally similar neighbouring pixels
into discrete candidate brownfield sites. group_pixels_for_candidate_sites
uses connected-component analysis to group pixels by spatial adjacency and
spectral similarity. calculate_site_properties computes pixel count, mean BSI
value and centroid UTM coordinates for each group. generate_boundary_polygons
traces the outline of each group and converts pixel positions to UTM coordinates
for database storage and Folium map display.
"""
import numpy as np
import scipy.ndimage

def group_pixels_for_candidate_sites(X_reduced: np.ndarray, 
                                     mask: np.ndarray, 
                                     original_shape: tuple, 
                                     similarity_threshold: float=0.1) -> dict:
    """
    Groups neighbouring pixels with similar spectral signatures into discrete 
    candidate sites using connected-component approach. Pixels join the same site 
    if spatially adjacent and spectrally similar within similarity_threshold. 
    Uses mask and original_shape to reconstruct spatial relationships lost when 
    image was flattened.

    Args:
        X_reduced (np.ndarray): Shape (pixels, k) — PCA-reduced spectral values
                                for each valid pixel, output of pca.project.
        mask (np.ndarray): Shape (pixels,) — boolean mask from scl_filtering.mask_nodata,
                           marking which pixels in the original flattened array are valid.
        original_shape (tuple): (height, width) — original 2D dimensions of the satellite
                                image before flattening, needed to reconstruct spatial
                                relationships between pixels.
        similarity_threshold (float): Maximum spectral distance between two pixels for
                                      them to be considered part of the same candidate site.
                                      Default 0.1 — may require calibration per council.

    Returns:
        candidate_groups (dict): Keys are integer site IDs, values are lists of pixel
                                 indices (positions in the flattened masked array) belonging
                                 to that site.
    """
    # Reconstruct 2D spatial grid from flat mask
    mask_2d = mask.reshape(original_shape)

    # Label all spatially connected groups of valid pixels
    labelled_array, num_features = scipy.ndimage.label(mask_2d)

    # Build flat index lookup — maps 2D position back to masked array index
    # This lets us find X_reduced values for any pixel by its 2D position
    flat_indices = np.full(original_shape, -1, dtype=int)
    valid_positions = np.argwhere(mask_2d)
    for i, (row, col) in enumerate(valid_positions):
        flat_indices[row, col] = i

    candidate_groups = {}
    site_id = 0

    for label in range(1, num_features + 1):
        # Find all pixel positions belonging to this connected group
        positions = np.argwhere(labelled_array == label)

        if len(positions) < 5:
            continue

        # Get masked array indices for these positions
        pixel_indices = [flat_indices[row, col] for row, col in positions
                        if flat_indices[row, col] != -1]

        if not pixel_indices:
            continue

        # Calculate mean spectral signature for this group
        group_spectral = X_reduced[pixel_indices]
        group_mean = group_spectral.mean(axis=0)

        # Check spectral similarity — keep group only if pixels are
        # spectrally similar enough to the group mean
        distances = np.linalg.norm(group_spectral - group_mean, axis=1)
        similar_mask = distances < similarity_threshold

        similar_indices = [pixel_indices[i] for i in range(len(pixel_indices))
                          if similar_mask[i]]

        if len(similar_indices) >= 5:
            candidate_groups[site_id] = similar_indices
            site_id += 1

    return candidate_groups

def calculate_site_properties(candidate_groups: dict, 
                              bsi_array: np.ndarray,
                              mask: np.ndarray,
                              original_shape: tuple,
                              tile_metadata: dict) -> list:
    """
    Calculates properties for each candidate site — pixel count, 
    mean BSI value across all site pixels, and centroid UTM coordinates converted 
    using tile_metadata. Results are used for database storage and register 
    matching.

    Args:
        candidate_groups (dict): Keys are site IDs, values are lists of pixel indices —
                                 output of group_pixels_for_candidate_sites.
        bsi_array (np.ndarray): Shape (pixels,) — BSI value for each valid pixel,
                                output of preprocess.compute_bsi.
        mask (np.ndarray): Shape (pixels,) — boolean mask from scl_filtering.mask_nodata.
        original_shape (tuple): (height, width) — original 2D dimensions of the satellite
                                image before flattening.
        tile_metadata (dict): Contains left, top and resolution from the satellite image,
                              used to convert pixel positions to UTM coordinates.

    Returns:
        site_properties (list): List of dicts, one per site, each containing site_id,
                                pixel_count, mean_bsi, centroid_utm_x, centroid_utm_y.
    """
    left = tile_metadata['left']
    top = tile_metadata['top']
    resolution = tile_metadata['resolution']

    # Build 2D position lookup for valid pixels
    mask_2d = mask.reshape(original_shape)
    valid_positions = np.argwhere(mask_2d)

    site_properties = []

    for site_id, pixel_indices in candidate_groups.items():
        # Pixel count
        pixel_count = len(pixel_indices)

        # Mean BSI value across all pixels in this site
        mean_bsi = float(bsi_array[pixel_indices].mean())

        # Centroid pixel position — mean row and column
        positions = valid_positions[pixel_indices]
        centroid_row = positions[:, 0].mean()
        centroid_col = positions[:, 1].mean()

        # Convert centroid pixel position to UTM coordinates
        centroid_utm_x = left + (centroid_col * resolution)
        centroid_utm_y = top - (centroid_row * resolution)

        site_properties.append({
            'site_id': site_id,
            'pixel_count': pixel_count,
            'mean_bsi': mean_bsi,
            'centroid_utm_x': float(centroid_utm_x),
            'centroid_utm_y': float(centroid_utm_y)
        })

    return site_properties

def generate_boundary_polygons(candidate_groups: dict,
                               mask: np.ndarray,
                               original_shape: tuple,
                               tile_metadata: dict) -> list:
    """
    Generates boundary polygon for each candidate site by tracing the outline 
    of grouped pixels in the 2D grid and converting pixel positions to UTM 
    coordinates using tile_metadata. Polygons are used for database storage and 
    Folium interactive map display.

    Args:
        candidate_groups (dict): Keys are site IDs, values are lists of pixel indices —
                                 output of group_pixels_for_candidate_sites.
        mask (np.ndarray): Shape (pixels,) — boolean mask from scl_filtering.mask_nodata.
        original_shape (tuple): (height, width) — original 2D dimensions of the satellite
                                image before flattening.
        tile_metadata (dict): Contains left, top and resolution from the satellite image,
                              used to convert pixel positions to UTM coordinates.

    Returns:
        site_polygons (list): List of dicts, one per site, each containing site_id and
                              boundary — a list of UTM coordinate pairs tracing the outline
                              of the grouped pixels, ready for Folium map display and
                              database storage.
    """
    from scipy.ndimage import binary_dilation, binary_erosion

    left = tile_metadata['left']
    top = tile_metadata['top']
    resolution = tile_metadata['resolution']

    mask_2d = mask.reshape(original_shape)
    valid_positions = np.argwhere(mask_2d)

    site_polygons = []

    for site_id, pixel_indices in candidate_groups.items():
        # Create a 2D boolean grid for just this site's pixels
        site_grid = np.zeros(original_shape, dtype=bool)
        positions = valid_positions[pixel_indices]
        for row, col in positions:
            site_grid[row, col] = True

        # Find boundary pixels — pixels that are in the site but adjacent to
        # pixels outside the site (erosion removes interior, leaving boundary)
        eroded = binary_erosion(site_grid)
        boundary_grid = site_grid & ~eroded

        # Get boundary pixel positions
        boundary_positions = np.argwhere(boundary_grid)

        # Convert boundary pixel positions to UTM coordinates
        boundary_utm = [
            [float(left + col * resolution),
             float(top - row * resolution)]
            for row, col in boundary_positions
        ]

        # Close the polygon by repeating the first point
        if boundary_utm:
            boundary_utm.append(boundary_utm[0])

        site_polygons.append({
            'site_id': site_id,
            'boundary': boundary_utm
        })

    return site_polygons

