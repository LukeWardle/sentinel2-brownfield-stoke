"""
main.py - Orchestrates the full pipeline.
=========================================
Runs the full Sentinel-2 brownfield detection pipeline end to end — from
loading a raw SAFE folder through to saving a false colour map and results
report in outputs/. Calls every function from data_loading_satellite.py,
validation_satellite.py,
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data_loading_satellite import load_bands, load_scl
from src.scl_filtering import mask_nodata
from src.validation_satellite import validate_path, validate_bands, validate_quality
from src.preprocess import centre_data, compute_covariance
from src.pca import spectral_decomposition, sort_variance, cumulative_variance_for_k, project
from src.visualise import convert_k_to_rgb, false_map_creation, report_creation

def run_pipeline(safe_path: str, output_dir: str):
    """
    Orchestrates the full Sentinel-2 brownfield detection pipeline — from
    loading raw satellite data through to saving a false colour map and
    results report. Calls validate_path, load_bands, load_scl, mask_nodata,
    validate_bands, validate_quality, centre_data, compute_covariance,
    spectral_decomposition, sort_variance, cumulative_variance_for_k, project
    (twice — once for k components, once for 3 components), convert_k_to_rgb,
    false_map_creation and report_creation in sequence.

    Args:
        safe_path (str): Path to the Sentinel-2 SAFE folder.
        output_dir (str): Path to the folder where the false colour map and
                          results report will be saved.

    Returns:
        None — saves false_colour_map_YYYYMMDD_HHMMSS.png and
              results_report_YYYYMMDD_HHMMSS.md to output_dir.

    Raises:
        FileNotFoundError: If safe_path does not exist or is not a .SAFE folder.
        ValueError: If band files are missing, image quality is insufficient,
                   or data is corrupt at any validation stage.
    """
    os.makedirs(output_dir, exist_ok=True)

    validate_path(safe_path)
    band_array = load_bands(safe_path)
    scl_array = load_scl(safe_path)
    masked_array, mask, original_shape = mask_nodata(band_array, scl_array)
    validate_bands(masked_array)
    validate_quality(scl_array)

    centred_array = centre_data(masked_array)
    covariance_matrix = compute_covariance(centred_array)
    eigenvalues, eigenvectors = spectral_decomposition(covariance_matrix)
    sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)
    k = cumulative_variance_for_k(sorted_eigenvalues)

    X_reduced = project(centred_array, sorted_eigenvectors, k)
    X_for_map = project(centred_array, sorted_eigenvectors, 3)
    rgb_array = convert_k_to_rgb(X_for_map)

    false_map_creation(rgb_array, output_dir, mask, original_shape)
    # report_creation(k, sorted_eigenvalues, output_dir)


if __name__ == "__main__":
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).parent.parent
    SAFE_PATH = str(PROJECT_ROOT / "raw_data" / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE" / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE")
    OUTPUT_DIR = str(PROJECT_ROOT / "outputs")
    run_pipeline(SAFE_PATH, OUTPUT_DIR)