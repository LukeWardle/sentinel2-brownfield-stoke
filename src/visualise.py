"""
visualise.py - Fale colour report and results map.
==================================================
Takes the top 3 principal components and converts them to RGB colour channels
for the false colour map. Renders the false colour map and saves it to outputs/.
Creates the results report and saves it to the outputs/ folder too.
"""
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime

def convert_k_to_rgb(X_reduced: np.ndarray) -> np.ndarray:
    """
    Normalises the top 3 k components to RGB colour channels (0-255).

    Args:
        X_reduced (np.ndarray): Shape (pixels, k) — projected data from PCA pipeline.
    
    Returns:
        rgb_array (np.ndarray): Shape (pixels, 3) - Top 3 components normalised
                                                    to 0-255 range.

    Raises:
        ValueError: If X_reduced has fewer than 3 components.
        ValueError: If X_reduced is empty.
        ValueError: If any of the top 3 components has zero variance.

    """
    if X_reduced.shape[0] == 0:
        raise ValueError("X_reduced is empty")
    if X_reduced.shape[1] < 3:
        raise ValueError(f"X_reduced must have at least 3 components, got {X_reduced.shape[1]}")
    top_3 = X_reduced[:, :3]
    rgb_array = np.zeros_like(top_3, dtype=np.uint8)
    for i in range(3):
        column = top_3[:, i]
        column_min = column.min()
        column_max = column.max()
        if column_max == column_min:
            raise ValueError(f"Component {i+1} has zero variance — cannot normalise to RGB")
        normalised = (column - column_min) / (column_max - column_min) * 255
        rgb_array[:, i] = normalised.astype(np.uint8)
    return rgb_array

def false_map_creation(rgb_array: np.ndarray, output_dir: str, mask: np.ndarray = None,
                       original_shape: tuple = None) -> None:
    """
    Renders RGB array as false colour map using matplotlib. Reconstructs the full
    2D image by placing valid pixels back into their original positions using mask
    and original_shape, with nodata/defective pixels rendered as black. Saves the
    map to outputs/ with a timestamp as filename.

    Args:
        rgb_array (np.ndarray): Shape (valid_pixels, 3) — RGB values normalised to 0-255.
        output_dir (str): Path to outputs/ folder where map will be saved.
        mask (np.ndarray, optional): Shape (total_pixels,) — boolean mask marking which
                           pixels were kept (True) or removed (False) by mask_nodata.
                           If None, rgb_array is assumed to contain every pixel.
        original_shape (tuple, optional): Original 2D shape (height, width) before
                           flattening. If None, falls back to assuming a square image.

    Returns:
        None — saves false_colour_map_YYYYMMDD_HHMMSS.png to output_dir.

    Raises:
        ValueError: If rgb_array does not have 3 columns.
        FileNotFoundError: If output_dir does not exist.
    
    """
    if rgb_array.shape[1] != 3:
        raise ValueError(f"rgb_array must have 3 columns, got {rgb_array.shape[1]}")
    if not os.path.exists(output_dir):
        raise FileNotFoundError(f"output_dir does not exist: {output_dir}")

    if mask is None or original_shape is None:
        side_length = int(np.sqrt(rgb_array.shape[0]))
        image_array = rgb_array.reshape(side_length, side_length, 3)
    else:
        total_pixels = original_shape[0] * original_shape[1]
        full_rgb = np.zeros((total_pixels, 3), dtype=np.uint8)
        full_rgb[mask] = rgb_array
        image_array = full_rgb.reshape(original_shape[0], original_shape[1], 3)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"false_colour_map_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)

    plt.figure(figsize=(10, 10))
    plt.imshow(image_array)
    plt.title("Stoke-on-Trent — PCA False Colour Map")
    plt.axis("off")
    plt.savefig(filepath, bbox_inches="tight", dpi=150)
    plt.close()
    
def report_creation(k: int, sorted_eigenvalues: np.ndarray, output_dir: str) -> None:
    """
    Generates a results report, saved to outputs/ with a timestamp filename.

    Args:
        k (int): Number of principal components retained.
        sorted_eigenvalues (np.ndarray): Shape (10,) — sorted eigenvalues for variance calculation.
        output_dir (str): Path to outputs/ folder where report will be saved.

    Returns:
        None — saves results_report_YYYYMMDD_HHMMSS.md to output_dir.

    Raises:
        FileNotFoundError: If output_dir does not exist.
        
    """
    if not os.path.exists(output_dir):
        raise FileNotFoundError(f"output_dir does not exist: {output_dir}")

    total_variance = np.sum(sorted_eigenvalues)
    variance_explained = sorted_eigenvalues[:k].sum() / total_variance

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results_report_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)

    report_lines = [
        "# Sentinel-2 Brownfield Detection — Results Report",
        f"\nGenerated: {timestamp}",
        f"\n## Summary",
        f"\nThe PCA analysis retained {k} principal components, explaining {variance_explained:.2%} of total spectral variance.",
        f"\n## Component Variance Breakdown",
        ""
    ]

    for i, val in enumerate(sorted_eigenvalues):
        pct = val / total_variance * 100
        report_lines.append(f"- PC{i+1}: {pct:.2f}%")

    report_lines.append(f"\n## Interpretation")
    report_lines.append(f"\nThe false colour map highlights areas of similar spectral signature using the top 3 principal components. The two largest patterns in the data — overall brightness (PC1, {sorted_eigenvalues[0]/total_variance*100:.1f}%) and vegetation contrast (PC2, {sorted_eigenvalues[1]/total_variance*100:.1f}%) — dominate the visible colours. Subtler spectral differences that may indicate brownfield land are present in lower-ranked components and are not always easily distinguished by eye in this map alone. All candidate sites require physical verification before any planning decision, and Version 2 of this tool will introduce bare soil pre-filtering to strengthen the brownfield signal before visualisation.")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))