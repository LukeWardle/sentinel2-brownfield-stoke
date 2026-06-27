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

def _arrange_band_array(loaded_bands: list) -> np.ndarray:
    """
    Arranges a list of 2D band arrays into a single (pixels, n_bands) array.
    
    Each band is a 2D array of shape (height, width). This function stacks
    them into a 3D array, transposes so bands are last, then reshapes to
    (pixels, n_bands).
    
    Args:
        loaded_bands (list): List of 2D numpy arrays, one per band.
    
    Returns:
        np.ndarray: Shape (pixels, n_bands) — each row is one pixel's band readings.
    """
    band_stack = np.array(loaded_bands)        # (n_bands, height, width)
    band_stack = band_stack.transpose(1, 2, 0) # (height, width, n_bands)
    pixels = band_stack.shape[0] * band_stack.shape[1]
    return band_stack.reshape(pixels, band_stack.shape[2])


def load_bands(safe_path: str) -> np.ndarray:
    """
    load_bands -> Loads 10 selected bands at 20m, downsamples 10m bands

    Args:
      safe_path (str): Path to the Sentinel-2 SAFE folder

    Returns:
      np.ndarray: Shape (pixels, 10) - stacked array of 10 bands at 20m resolution.

    Raises:
      ValueError: If safe_path does not exist
      ValueError: If expected band files are missing (R20m bands)
      ValueError: If expected band files are missing (R10m bands)
      ValueError: if band shapes are inconsistent after downsampling
    """
    granule_path = os.path.join(safe_path, "GRANULE")
    granule_contents = os.listdir(granule_path)
    if not granule_contents:
        raise ValueError(f"GRANULE folder is empty - no granule found in {granule_path}")
    granule_name = granule_contents[0]
    img_data_path = os.path.join(granule_path, granule_name, "IMG_DATA")
    r20m_path = os.path.join(img_data_path, "R20m")
    r10m_path = os.path.join(img_data_path, "R10m")
    bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
    bands_10m = ["B02", "B03", "B04", "B08"]
    loaded_bands = []

    # Check all R20m bands exist before loading
    missing_bands = []
    for band in bands_20m:
        matches = [f for f in os.listdir(r20m_path) if f"_{band}_" in f]
        if not matches:
            missing_bands.append(band)
    if missing_bands:
        raise ValueError(f"Missing R20m band files: {missing_bands}")
    
    # Load R20m band files
    for band in bands_20m:
        band_file = [f for f in os.listdir(r20m_path) if f"_{band}_" in f][0]
        band_path = os.path.join(r20m_path, band_file)
        with rasterio.open(band_path) as src:
            data = src.read(1)
            loaded_bands.append(data)
    
    # Check all R10m bands exist before loading
    missing_bands = []
    for band in bands_10m:
        matches = [f for f in os.listdir(r10m_path) if f"_{band}_" in f]
        if not matches:
            missing_bands.append(band)
    if missing_bands:
        raise ValueError(f"Missing R10m band files: {missing_bands}")
    
    # Load R10m band files
    for band in bands_10m:
        band_file = [f for f in os.listdir(r10m_path) if f"_{band}_" in f][0]
        band_path = os.path.join(r10m_path, band_file)
        with rasterio.open(band_path) as src:
            data = src.read(
                1, out_shape=(5490, 5490), resampling=rasterio.enums.Resampling.bilinear
            )
            loaded_bands.append(data)

    shapes = [b.shape for b in loaded_bands]
    if len(set(shapes)) > 1:
        raise ValueError(f"Band shape mismatch after loading - shapes found: {set(shapes)}")
    return _arrange_band_array(loaded_bands) 


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
    granule_contents = os.listdir(granule_path)
    if not granule_contents:
        raise ValueError(f"GRANULE folder is empty - no granule found in {granule_path}")
    granule_name = granule_contents[0]
    img_data_path = os.path.join(granule_path, granule_name, "IMG_DATA")
    r20m_path = os.path.join(img_data_path, "R20m")
    scl_matches = [f for f in os.listdir(r20m_path) if "_SCL_" in f]
    if not scl_matches:
        raise ValueError(f"SCL file not found in {r20m_path}")
    scl_file = scl_matches[0]
    scl_path = os.path.join(r20m_path, scl_file)
    with rasterio.open(scl_path) as src:
        scl_array = src.read(1)
    return scl_array

