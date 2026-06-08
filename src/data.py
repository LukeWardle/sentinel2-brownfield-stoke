"""
data.py — Load and prepare band data
=====================================
Loads the 10 selected Sentinel-2 spectral bands from the SAFE folder.
R10m bands (B02, B03, B04, B08) are downsampled to 20m to match R20m bands.
All 10 bands are stacked into a single array of shape (pixels, 10).

Native resolutions:
  R20m — B05, B06, B07, B8A, B11, B12
  R10m — B02, B03, B04, B08 (downsampled to 20m)
"""

import rasterio
import numpy as np
import os


def load_bands(safe_path: str) -> np.ndarray:
    """
    load_bands -> Loads 10 selected bands at 20m, downsamples 10m bands

    Args:
      safe_path (str): Path to the Sentinel-2 SAFE folder

    Returns:
      np.ndarray: Shape (pixels, 10) - stacked array of 10 bands at 20m resolution.

    Raises:
      FileNotFoundError: If safe_path does not exist
      ValueError: If expected band files are missing
    """
    granule_path = os.path.join(safe_path, "GRANULE")
    granule_name = os.listdir(granule_path)[0]
    img_data_path = os.path.join(granule_path, granule_name, "IMG_DATA")
    r20m_path = os.path.join(img_data_path, "R20m")
    r10m_path = os.path.join(img_data_path, "R10m")
    bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
    bands_10m = ["B02", "B03", "B04", "B08"]
    loaded_bands = []
    # Load R20m band files
    for band in bands_20m:
        band_file = [f for f in os.listdir(r20m_path) if f"_{band}_" in f][0]
        band_path = os.path.join(r20m_path, band_file)
        with rasterio.open(band_path) as src:
            data = src.read(1)
            loaded_bands.append(data)
    # Load R10m band files
    for band in bands_10m:
        band_file = [f for f in os.listdir(r10m_path) if f"_{band}_" in f][0]
        band_path = os.path.join(r10m_path, band_file)
        with rasterio.open(band_path) as src:
            # Downsample R10m bands to match R20m bands
            data = src.read(
                1, out_shape=(5490, 5490), resampling=rasterio.enums.Resampling.bilinear
            )
            loaded_bands.append(data)

    band_stack = np.array(loaded_bands)
    pixels = band_stack.shape[1] * band_stack.shape[2]
    band_array = band_stack.reshape(pixels, 10)
    return band_array


def load_scl(safe_path: str) -> np.ndarray:
    """
    load_scl -> Loads the SCL_20m.jp2 containing Scene Classification Layers data
    used for nodata masking.

    Scene Classification Layers:
      0 = No data, 4 = Vegetation, 5 = Bare soil, 6 = Water, 8,9,10 = Cloud, 11 = Snow

    Args:
      safe_path (str): Path to the Sentinel-2 SAFE folder.

    Returns:
      np.ndarray: Shape (5490, 5490) - array of values for Scene Classification Layers.

    Raises:
      FileNotFoundError: If safe_path does not exist
      ValueError: If expected band files are missing

    """
    granule_path = os.path.join(safe_path, "GRANULE")
    granule_name = os.listdir(granule_path)[0]
    img_data_path = os.path.join(granule_path, granule_name, "IMG_DATA")
    r20m_path = os.path.join(img_data_path, "R20m")
    scl_file = [f for f in os.listdir(r20m_path) if f"_SCL_" in f][0]
    scl_path = os.path.join(r20m_path, scl_file)
    with rasterio.open(scl_path) as src:
        scl_array = src.read(1)
    return scl_array


def mask_nodata(band_array: np.ndarray, scl_array: np.ndarray = None) -> np.ndarray:
    """
    mask_nodata - Uses the scl_array to remove the no data pixels (marked as 0) from the band_array.

    Args:
      band_array (np.ndarray): shape (pixels, 10) - Stacked array of 10 bands.
      scl_array (np.ndarray, optional): Shape (5490, 5490) - Scene Classification
                                        Layers. If None masking is skipped.

    Returns:
      np.ndarray: Shape (valid_pixels, 10) - Removes pixels where the SCL class = 0,
                                             if scl_array is None then masking is skipped.

    """
    if scl_array is None:
        return band_array
    scl_flat = scl_array.flatten()
    mask = scl_flat != 0
    return band_array[mask]
