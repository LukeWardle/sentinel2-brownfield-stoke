"""
scl_filtering.py - Removes pixels based on SCL class
====================================================
Removes nodata (SCL class 0) and defective (SCL class 1) pixels from
the raw satellite grid and flattens the result into the (valid_pixels,
n_bands) form used by preprocess, PCA and clustering.

Runs after aoi_clipping in the pipeline: any pixel outside the council
boundary has already had its SCL class set to 0, so those pixels are
dropped here alongside genuine nodata and defective pixels in a single
pass. This module is the transition point between the 3D spatial grid
maintained upstream and the flat pixel table used downstream.

Scene Classification Layers:
      0 = No data, 4 = Vegetation, 5 = Bare soil, 6 = Water,
      8, 9, 10 = Cloud, 11 = Snow
"""
import numpy as np

def mask_nodata(band_array_2d: np.ndarray, scl_array_2d: np.ndarray) -> tuple:
    """
    Drops nodata (SCL=0) and defective (SCL=1) pixels from the raw
    Sentinel-2 grid and flattens the surviving pixels into a 2D table
    ready for spectral analysis. Also returns the flat boolean mask
    and the original grid shape so visualise can reconstruct the 2D
    image later.

    Args:
        band_array_2d (np.ndarray): Shape (height, width, n_bands) —
                                     raw bands with out-of-boundary
                                     pixels already zeroed by aoi_clipping.
        scl_array_2d (np.ndarray): Shape (height, width) — SCL grid
                                    with out-of-boundary pixels already
                                    set to class 0 by aoi_clipping.

    Returns:
        tuple:
            np.ndarray: Shape (valid_pixels, n_bands) — surviving pixel
                        readings after nodata and defective pixels are
                        dropped.
            np.ndarray: Shape (height * width,) — flat boolean mask, True
                        at positions kept in the flattened grid. Used to
                        place valid pixels back onto the 2D grid for the
                        false colour map.
            tuple: (height, width) — original grid shape needed to
                   reconstruct spatial relationships downstream.
    """
    scl_flat = scl_array_2d.flatten()
    mask = (scl_flat != 0) & (scl_flat != 1)
    band_flat = band_array_2d.reshape(-1, band_array_2d.shape[-1])
    masked_array = band_flat[mask]
    return masked_array, mask, scl_array_2d.shape