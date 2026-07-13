"""
data_loading_satellite.py — Load and prepare Sentinel-2 band data
==================================================================
Loads the 10 selected Sentinel-2 spectral bands from the SAFE folder.
R10m bands (B02, B03, B04, B08) are bilinearly resampled to 20m so all
bands share a common (5490, 5490) grid. The bands are stacked into a
single array of shape (height, width, 10).

The 3D grid layout is preserved so that AOI clipping can operate on
the raw spatial arrays before mask_nodata flattens them to the
(valid_pixels, 10) form used by preprocess, PCA and clustering. This
means SCL filtering only ever sees pixels inside the council boundary
— roughly 233,000 for Stoke rather than the full 21 million.

Native resolutions:
  R20m — B05, B06, B07, B8A, B11, B12
  R10m — B02, B03, B04, B08 (bilinearly resampled to 20m)
"""
import os
import numpy as np
import rasterio

bands_20m = ["B05", "B06", "B07", "B8A", "B11", "B12"]
bands_10m = ["B02", "B03", "B04", "B08"]

def _arrange_band_array(loaded_bands: list) -> np.ndarray:
    """
    Stacks a list of 2D band arrays into a single 3D array of shape
    (height, width, n_bands). Each pixel position (row, col) then holds
    all band readings for that pixel at [row, col, :].

    Args:
        loaded_bands (list): List of 2D numpy arrays, each of shape
                             (height, width), one per band, in the
                             order bands_20m followed by bands_10m.

    Returns:
        np.ndarray: Shape (height, width, n_bands) — band values indexed
                    by pixel row, pixel column, then band.
    """
    return np.stack(loaded_bands, axis=-1)

def load_bands(safe_path: str) -> np.ndarray:
    """
    Loads the 10 selected Sentinel-2 bands from the SAFE folder. R20m
    bands are read at native resolution. R10m bands are bilinearly
    resampled to the (5490, 5490) 20m grid so every band shares the
    same shape before stacking.

    Args:
        safe_path (str): Path to the Sentinel-2 SAFE folder.

    Returns:
        np.ndarray: Shape (height, width, 10) — stacked band array on
                    the 20m grid. Bands are ordered bands_20m followed
                    by bands_10m.

    Raises:
        FileNotFoundError: If safe_path does not exist.
        ValueError: If the GRANULE folder is empty, if any expected
                    R20m or R10m band file is missing, or if band
                    shapes are inconsistent after resampling.
    """
    granule_path = os.path.join(safe_path, "GRANULE")
    granule_contents = os.listdir(granule_path)
    if not granule_contents:
        raise ValueError(f"GRANULE folder is empty - no granule found in {granule_path}")
    granule_name = granule_contents[0]
    img_data_path = os.path.join(granule_path, granule_name, "IMG_DATA")
    r20m_path = os.path.join(img_data_path, "R20m")
    r10m_path = os.path.join(img_data_path, "R10m")
    loaded_bands = []

    # Check all R20m bands exist before loading
    missing_bands = []
    for band in bands_20m:
        matches = [f for f in os.listdir(r20m_path) if f"_{band}_" in f]
        if not matches:
            missing_bands.append(band)
    if missing_bands:
        raise ValueError(f"Missing R20m band files: {missing_bands}")

    # Load R20m band files at native resolution
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

    # Load R10m band files and bilinearly resample to 20m grid
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
    Loads the Scene Classification Layer at 20m resolution from the
    SAFE folder. Used by mask_nodata to remove nodata and defective
    pixels and by validate_quality to check cloud coverage.

    Scene Classification Layers:
      0 = No data, 4 = Vegetation, 5 = Bare soil, 6 = Water,
      8, 9, 10 = Cloud, 11 = Snow

    Args:
        safe_path (str): Path to the Sentinel-2 SAFE folder.

    Returns:
        np.ndarray: Shape (5490, 5490) — Scene Classification Layer
                    at 20m resolution.

    Raises:
        FileNotFoundError: If safe_path does not exist.
        ValueError: If the GRANULE folder is empty or the SCL file
                    is missing.
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