"""
scl_filtering.py - Removes pixels based on SCL class
====================================================
Removes the pixels from scl_array based on Scene Classification type.

Scene Classification Layers:
      0 = No data, 4 = Vegetation, 5 = Bare soil, 6 = Water, 8,9,10 = Cloud, 11 = Snow
"""
import numpy as np

def mask_nodata(band_array: np.ndarray, scl_array: np.ndarray = None) -> tuple:
    """
    mask_nodata - Uses the scl_array to remove the no data and defective pixels
    from the band_array. Also returns the mask and original 2D shape so that
    valid pixels can be correctly placed back into a 2D grid later for visualisation.

    Args:
      band_array (np.ndarray): shape (pixels, 10) - Stacked array of 10 bands.
      scl_array (np.ndarray, optional): Shape (5490, 5490) - Scene Classification
                                        Layers. If None masking is skipped.

    Returns:
      tuple:
        np.ndarray: Shape (valid_pixels, 10) - band_array with pixels removed where
                    SCL class = 0 (nodata) or SCL class = 1 (defective/saturated).
                    If scl_array is None, band_array is returned unchanged.
        np.ndarray or None: Shape (pixels,) - boolean mask marking which pixels were
                    kept (True) or removed (False). None if scl_array is None.
        tuple or None: Original 2D shape (height, width) of scl_array before flattening,
                    needed to reconstruct a 2D image later. None if scl_array is None.
    """
    if scl_array is None:
        return band_array, None, None
    scl_flat = scl_array.flatten()
    mask = (scl_flat != 0) & (scl_flat != 1)
    return band_array[mask], mask, scl_array.shape
