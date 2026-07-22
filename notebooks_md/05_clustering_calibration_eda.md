# Notebook 05 — Clustering Calibration EDA
## Sentinel-2 Brownfield Site Detection — SiteSignal Ltd

> **STATUS NOTE — 22 July 2026.** The figures in this notebook predate the
> Detection Correctness Foundation (PR #90, merged 21 July 2026). FND-1 removed
> dilation-border pixels from candidate membership, which voided the headline
> counts used throughout: **218 candidate sites / 39 register matches / 17.9%
> recall were measured under dilation-inflated counts and no longer hold.**
> Post-FND provisional figures at min_pixels=5 (uncalibrated, see issue #89):
> 90 candidate sites, 18 register matches, 60 unregistered candidates after
> hard-class exclusion. Analysis and reasoning below remain valid; treat all
> absolute numbers as historical.


This notebook documents the calibration process for the candidate site clustering module. It covers the failure of the original spectral similarity approach, the redesign to a BSI/NDVI threshold-based connected-component approach, the performance optimisations required to make it run on 21 million pixels, and the threshold combinations tested to arrive at the final pipeline settings.

The findings in this notebook directly informed the Version 2 pipeline configuration and provide the analytical justification for the supervised Random Forest classifier planned for Version 3.


```python
%matplotlib inline
import os
import sys

import matplotlib

matplotlib.use('Agg')
from pathlib import Path

import matplotlib.pyplot as plt

PROJECT_ROOT = Path(os.getcwd()).parent
sys.path.insert(0, str(PROJECT_ROOT))

import scipy.ndimage

from src.aoi_clipping import clip_to_council_boundary
from src.clustering import calculate_site_properties, group_pixels_for_candidate_sites
from src.data_loading_satellite import bands_10m, bands_20m, load_bands, load_scl
from src.database_query import get_db_connection
from src.pca import (
    cumulative_variance_for_k,
    project,
    sort_variance,
    spectral_decomposition,
)
from src.preprocess import (
    centre_data,
    compute_bsi,
    compute_covariance,
    compute_ndvi,
    normalise_band_array,
)
from src.scl_filtering import mask_nodata

safe_path = str(PROJECT_ROOT / "raw_data" / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE" / "S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE")
tile_metadata = {'left': 499980.0, 'top': 5900040.0, 'resolution': 20}
gss_code = 'E06000021'

print(f"Project root: {PROJECT_ROOT}")
print(f"Safe path: {safe_path}")
```

    Project root: C:\Users\lward\workspace\sentinel2-brownfield-stoke
    Safe path: C:\Users\lward\workspace\sentinel2-brownfield-stoke\raw_data\S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE\S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE
    

## Section 1 — Data Loading and Initial PCA

The first approach to candidate site detection used PCA-reduced spectral values as the basis for clustering. The hypothesis was that spectrally distinct pixels — those with unusual combinations of reflectance across the 10 Sentinel-2 bands — would cluster together and form candidate brownfield sites.

The full 110km × 110km Sentinel-2 tile was loaded, SCL masking applied to remove clouds and defective pixels, and PCA run on all 21,223,650 valid pixels.


```python
print("Loading data...")
band_array = load_bands(safe_path)
scl_array = load_scl(safe_path)
masked_array, mask, original_shape = mask_nodata(band_array, scl_array)
print(f"Valid pixels after SCL masking: {mask.sum():,}")
print(f"Original shape: {original_shape}")

print("\nNormalising and running PCA...")
normalised = normalise_band_array(masked_array)
centred = centre_data(normalised)
cov = compute_covariance(centred)
eigenvalues, eigenvectors = spectral_decomposition(cov)
sorted_eigenvalues, sorted_eigenvectors = sort_variance(eigenvalues, eigenvectors)

total_variance = sorted_eigenvalues.sum()
print("\nVariance explained per component:")
for i, val in enumerate(sorted_eigenvalues):
    print(f"  PC{i+1}: {val/total_variance*100:.2f}%")

k_95 = cumulative_variance_for_k(sorted_eigenvalues, variance_threshold=0.95)
k_80 = cumulative_variance_for_k(sorted_eigenvalues, variance_threshold=0.80)
print(f"\nk at 95% variance threshold: {k_95}")
print(f"k at 80% variance threshold: {k_80}")
```

    Loading data...
    Valid pixels after SCL masking: 21,223,650
    Original shape: (5490, 5490)
    
    Normalising and running PCA...
    
    Variance explained per component:
      PC1: 82.08%
      PC2: 13.73%
      PC3: 1.80%
      PC4: 1.18%
      PC5: 0.57%
      PC6: 0.31%
      PC7: 0.16%
      PC8: 0.08%
      PC9: 0.07%
      PC10: 0.02%
    
    k at 95% variance threshold: 2
    k at 80% variance threshold: 1
    

## Finding — PCA Variance Distribution

PC1 explains 82.08% and PC2 explains 13.73% of spectral variance — together accounting for 95.81% with just two components. This is expected for a satellite image of a predominantly urban area: PC1 captures overall brightness and PC2 captures vegetation versus non-vegetation contrast. These two patterns dominate the spectral variation so completely that the 95% variance threshold gives k=2.

The problem for clustering is that with only 2 PCA components, all urban pixels — brownfield, rooftops, roads, car parks — appear spectrally similar relative to the dominant brightness and vegetation patterns. The variance threshold was lowered to 80% and a minimum of k=3 enforced, but as shown in the next section, this was still insufficient.

Note that the 80% threshold actually gives k=1 — this is because PC1 alone explains 82.08%, already exceeding 80%. The `max(k, 3)` minimum enforced in the pipeline ensures at least 3 components are always used.


```python
# Test original spectral similarity approach with k=3
k = max(cumulative_variance_for_k(sorted_eigenvalues, variance_threshold=0.80), 3)
X_reduced = project(centred, sorted_eigenvectors, k)

print(f"k used: {k}")
print(f"X_reduced shape: {X_reduced.shape}")
print(f"X_reduced min: {X_reduced.min():.4f}, max: {X_reduced.max():.4f}")
print(f"X_reduced std: {X_reduced.std():.4f}")

print("\nTesting original spectral similarity clustering at different thresholds:")
print("(Full tile, 21 million pixels, no AOI clipping)")
for threshold in [0.1, 0.5, 1.0, 2.0, 5.0]:
    # Simulate original approach — connected components on all valid pixels
    mask_2d = mask.reshape(original_shape)
    labelled_array, num_features = scipy.ndimage.label(mask_2d)
    print(f"  Threshold {threshold}: {num_features} connected components on full mask")
    break  # Only need to show once — result is always 1 massive component
```

    k used: 3
    X_reduced shape: (21223650, 3)
    X_reduced min: -3.8668, max: 1.0303
    X_reduced std: 0.1335
    
    Testing original spectral similarity clustering at different thresholds:
    (Full tile, 21 million pixels, no AOI clipping)
      Threshold 0.1: 1 connected components on full mask
    

## Finding — Original Spectral Similarity Approach Failed

The original clustering approach used `scipy.ndimage.label` on the full SCL-masked pixel array to find connected components, then applied a spectral similarity threshold to group pixels by their PCA-reduced values.

With 21,223,650 valid pixels across the full 110km × 110km tile, `scipy.ndimage.label` found exactly **1 connected component** — the entire valid pixel area forms one spatially connected region. This means the connected-component step produced nothing useful before spectral similarity was even applied.

The spectral similarity check then compared each pixel to its group mean. With k=3 and a standard deviation of only 0.1335 across the PCA-reduced values, almost all pixels fell within any reasonable threshold of the group mean — confirming that at full tile scale, the spectral variation is too dominated by brightness and vegetation contrast to distinguish brownfield from other urban land cover.

**This approach was abandoned.** The fundamental insight is that PCA on the full tile captures spectral variation *across the entire tile* — urban, rural, agricultural, water — not the fine-grained variation within urban land cover types that would distinguish brownfield from rooftops or roads.

The replacement approach uses BSI and NDVI spectral indices to identify bare soil candidate pixels before any spatial grouping takes place.


```python
print("Computing BSI and NDVI on full tile...")
bsi_array = compute_bsi(normalised, bands_20m, bands_10m)
ndvi_array = compute_ndvi(normalised, bands_20m, bands_10m)

print(f"BSI range: {bsi_array.min():.4f} to {bsi_array.max():.4f}, mean: {bsi_array.mean():.4f}")
print(f"NDVI range: {ndvi_array.min():.4f} to {ndvi_array.max():.4f}, mean: {ndvi_array.mean():.4f}")

print("\nBSI/NDVI threshold combinations on full tile (21,223,650 pixels):")
for bsi_thresh in [0.05, 0.10, 0.15]:
    for ndvi_thresh in [0.2, 0.1]:
        candidate_mask = (bsi_array > bsi_thresh) & (ndvi_array < ndvi_thresh)
        print(f"  BSI>{bsi_thresh}, NDVI<{ndvi_thresh}: {candidate_mask.sum():,} pixels ({candidate_mask.sum()/len(bsi_array)*100:.1f}%)")
```

    Computing BSI and NDVI on full tile...
    BSI range: -0.7404 to 1.0000, mean: -0.1553
    NDVI range: -1.0000 to 1.0000, mean: 0.4923
    
    BSI/NDVI threshold combinations on full tile (21,223,650 pixels):
      BSI>0.05, NDVI<0.2: 1,418,659 pixels (6.7%)
      BSI>0.05, NDVI<0.1: 437,388 pixels (2.1%)
      BSI>0.1, NDVI<0.2: 482,245 pixels (2.3%)
      BSI>0.1, NDVI<0.1: 163,243 pixels (0.8%)
      BSI>0.15, NDVI<0.2: 16,163 pixels (0.1%)
      BSI>0.15, NDVI<0.1: 8,136 pixels (0.0%)
    

## Section 2 — The AOI Clipping Discovery

Running BSI/NDVI threshold combinations on the full 110km × 110km tile revealed a critical issue. At BSI>0.05, NDVI<0.2, 1,418,659 pixels (6.7% of the tile) were identified as candidates. Initial clustering on this full tile produced tens of thousands of connected components but after size filtering only 1 site survived — a massive component of 676,286 pixels (~27,000 hectares) that dominated everything.

The root cause: the tile covers a large area of agricultural land, moorland and rural areas outside Stoke where bare soil is common. These are not brownfield sites — they are fields, tracks, and bare earth that happen to meet the BSI/NDVI criteria.

The fix was to apply AOI clipping to the Stoke-on-Trent council boundary **before** running BSI/NDVI analysis. This reduces the valid pixel set from 21,223,650 to 233,603 — only 1.1% of the full tile — and constrains all subsequent analysis to the actual area of interest.

This confirmed that AOI clipping should ideally occur earlier in the pipeline, before spectral index computation. This refactor is deferred to Version 3 for performance optimisation.


```python
print("Applying AOI clipping to Stoke-on-Trent boundary...")
conn = get_db_connection()
clipped_array, clipped_mask = clip_to_council_boundary(
    masked_array, mask, original_shape, tile_metadata, gss_code, conn
)
conn.close()

print(f"Valid pixels before AOI clipping: {mask.sum():,}")
print(f"Valid pixels after AOI clipping:  {clipped_mask.sum():,}")
print(f"Reduction: {(1 - clipped_mask.sum()/mask.sum())*100:.1f}% of tile removed")

print("\nRecomputing BSI and NDVI on Stoke pixels only...")
clipped_normalised = normalise_band_array(clipped_array)
bsi_stoke = compute_bsi(clipped_normalised, bands_20m, bands_10m)
ndvi_stoke = compute_ndvi(clipped_normalised, bands_20m, bands_10m)

print(f"BSI range: {bsi_stoke.min():.4f} to {bsi_stoke.max():.4f}, mean: {bsi_stoke.mean():.4f}")
print(f"NDVI range: {ndvi_stoke.min():.4f} to {ndvi_stoke.max():.4f}, mean: {ndvi_stoke.mean():.4f}")

print("\nBSI/NDVI threshold combinations on Stoke pixels only (233,603 pixels):")
for bsi_thresh in [0.05, 0.10, 0.15]:
    for ndvi_thresh in [0.2, 0.1]:
        candidate_mask = (bsi_stoke > bsi_thresh) & (ndvi_stoke < ndvi_thresh)
        print(f"  BSI>{bsi_thresh}, NDVI<{ndvi_thresh}: {candidate_mask.sum():,} pixels ({candidate_mask.sum()/len(bsi_stoke)*100:.1f}%)")
```

    Applying AOI clipping to Stoke-on-Trent boundary...
    Valid pixels before AOI clipping: 21,223,650
    Valid pixels after AOI clipping:  233,603
    Reduction: 98.9% of tile removed
    
    Recomputing BSI and NDVI on Stoke pixels only...
    BSI range: -0.5375 to 0.6578, mean: -0.0747
    NDVI range: -0.2350 to 0.7139, mean: 0.3660
    
    BSI/NDVI threshold combinations on Stoke pixels only (233,603 pixels):
      BSI>0.05, NDVI<0.2: 26,307 pixels (11.3%)
      BSI>0.05, NDVI<0.1: 10,685 pixels (4.6%)
      BSI>0.1, NDVI<0.2: 1,951 pixels (0.8%)
      BSI>0.1, NDVI<0.1: 858 pixels (0.4%)
      BSI>0.15, NDVI<0.2: 152 pixels (0.1%)
      BSI>0.15, NDVI<0.1: 75 pixels (0.0%)
    

## Finding — AOI Clipping Transforms the Analysis

AOI clipping to the Stoke-on-Trent boundary removes 98.9% of the satellite tile, reducing valid pixels from 21,223,650 to 233,603. This has two important effects:

**1. BSI and NDVI ranges change significantly:**
- Full tile BSI mean: -0.1553 (dominated by vegetation and water)
- Stoke-only BSI mean: -0.0747 (more urban, less rural vegetation)
- Full tile NDVI mean: 0.4923 (high — rural vegetation dominant)
- Stoke-only NDVI mean: 0.3660 (lower — more urban impervious surfaces)

**2. Candidate pixel counts become meaningful:**
At BSI>0.1, NDVI<0.2, the full tile returns 482,245 pixels (2.3%) — dominated by agricultural bare soil outside Stoke. After AOI clipping, the same threshold returns only 1,951 pixels (0.8% of Stoke) — a much more targeted set of candidates concentrated within the urban area.

This confirms that all threshold calibration must be performed on AOI-clipped data, not the full tile. Full tile analysis produces misleading results regardless of the threshold combination chosen.


```python
print("Section 3 — Threshold Calibration on Stoke-Clipped Data")
print("="*60)

print("\nRunning PCA on Stoke-clipped data...")
centred_stoke = centre_data(clipped_normalised)
cov_stoke = compute_covariance(centred_stoke)
eigenvalues_stoke, eigenvectors_stoke = spectral_decomposition(cov_stoke)
sorted_eigenvalues_stoke, sorted_eigenvectors_stoke = sort_variance(eigenvalues_stoke, eigenvectors_stoke)
k_stoke = max(cumulative_variance_for_k(sorted_eigenvalues_stoke, variance_threshold=0.80), 3)
X_reduced_stoke = project(centred_stoke, sorted_eigenvectors_stoke, k_stoke)
print(f"k: {k_stoke}")

print("\nTesting threshold combinations and clustering:")
results = []
tile_metadata_stoke = {'left': 499980.0, 'top': 5900040.0, 'resolution': 20}

for bsi_thresh, ndvi_thresh, min_pix, max_pix in [
    (0.05, 0.2, 10, 2500),
    (0.05, 0.2, 25, 500),
    (0.10, 0.2, 10, 2500),
    (0.10, 0.1, 10, 2500),
    (0.15, 0.2, 10, 2500),
]:
    groups = group_pixels_for_candidate_sites(
        X_reduced_stoke, clipped_mask, original_shape,
        bsi_stoke, ndvi_stoke,
        bsi_threshold=bsi_thresh,
        ndvi_threshold=ndvi_thresh,
        min_pixels=min_pix,
        max_pixels=max_pix
    )
    if groups:
        props = calculate_site_properties(groups, bsi_stoke, clipped_mask, original_shape, tile_metadata_stoke)
        sizes = [p['hectares'] for p in props]
        mean_size = sum(sizes) / len(sizes)
        max_size = max(sizes)
        min_size = min(sizes)
    else:
        mean_size = max_size = min_size = 0

    results.append({
        'bsi': bsi_thresh,
        'ndvi': ndvi_thresh,
        'min': min_pix,
        'max': max_pix,
        'sites': len(groups),
        'mean_ha': mean_size,
        'min_ha': min_size,
        'max_ha': max_size
    })
    print(f"  BSI>{bsi_thresh}, NDVI<{ndvi_thresh}, min={min_pix}, max={max_pix}: "
          f"{len(groups)} sites, mean {mean_size:.2f}ha, max {max_size:.2f}ha")
```

    Section 3 — Threshold Calibration on Stoke-Clipped Data
    ============================================================
    
    Running PCA on Stoke-clipped data...
    k: 3
    
    Testing threshold combinations and clustering:
    Brownfield candidate pixels: 26,307 (11.3% of valid pixels)
    Connected components found: 1901
    Candidate sites after size filter: 801
      BSI>0.05, NDVI<0.2, min=10, max=2500: 801 sites, mean 1.97ha, max 98.28ha
    Brownfield candidate pixels: 26,307 (11.3% of valid pixels)
    Connected components found: 1901
    Candidate sites after size filter: 291
      BSI>0.05, NDVI<0.2, min=25, max=500: 291 sites, mean 3.08ha, max 18.52ha
    Brownfield candidate pixels: 1,951 (0.8% of valid pixels)
    Connected components found: 819
    Candidate sites after size filter: 218
      BSI>0.1, NDVI<0.2, min=10, max=2500: 218 sites, mean 0.76ha, max 6.80ha
    Brownfield candidate pixels: 858 (0.4% of valid pixels)
    Connected components found: 483
    Candidate sites after size filter: 89
      BSI>0.1, NDVI<0.1, min=10, max=2500: 89 sites, mean 0.68ha, max 3.16ha
    Brownfield candidate pixels: 152 (0.1% of valid pixels)
    Connected components found: 77
    Candidate sites after size filter: 14
      BSI>0.15, NDVI<0.2, min=10, max=2500: 14 sites, mean 0.71ha, max 1.92ha
    

## Section 3 — Threshold Calibration Results

Five threshold combinations were tested on the Stoke-clipped data (233,603 pixels). Results are summarised below:

| BSI threshold | NDVI threshold | min pixels | max pixels | Sites | Mean size | Max size |
|---|---|---|---|---|---|---|
| 0.05 | 0.2 | 10 | 2500 | 801 | 1.97ha | 98.28ha |
| 0.05 | 0.2 | 25 | 500 | 291 | 3.08ha | 18.52ha |
| **0.10** | **0.2** | **10** | **2500** | **218** | **0.76ha** | **6.80ha** |
| 0.10 | 0.1 | 10 | 2500 | 89 | 0.68ha | 3.16ha |
| 0.15 | 0.2 | 10 | 2500 | 14 | 0.71ha | 1.92ha |

**Key observations:**

- BSI>0.05 produces 801 sites at min=10 — too many for a useful planning tool, and the 98.28ha maximum site suggests some large non-brownfield areas are being captured
- BSI>0.05 with a tighter size filter (min=25, max=500) gives 291 sites with more realistic sizes — a plausible set of candidates
- BSI>0.1, NDVI<0.2, min=10, max=2500 produced exactly **218 sites** — the same number as the Stoke-on-Trent brownfield register. **Correction (July 2026):** this count was an artifact of the dilation-contamination bug fixed by FND-1; sites were being measured at dilation-inflated pixel counts. At true counts the same thresholds yield 25 sites at min=10 and 90 at min=5. The 218=218 coincidence therefore carried no meaning, and the size thresholds it helped select are void pending recalibration against true counts (issue #89 / FND-7)
- BSI>0.15 produces only 14 sites — too restrictive, likely missing genuine brownfield

**Selected for pipeline testing:** BSI>0.1, NDVI<0.2, min=10, max=2500 — to test whether the 218 detected sites correspond to register locations.


```python
print("Section 4 — Visualising Threshold Comparison")
print("="*60)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Plot 1 — number of sites per threshold combination
labels = [
    'BSI>0.05\nNDVI<0.2\nmin=10',
    'BSI>0.05\nNDVI<0.2\nmin=25',
    'BSI>0.1\nNDVI<0.2\nmin=10',
    'BSI>0.1\nNDVI<0.1\nmin=10',
    'BSI>0.15\nNDVI<0.2\nmin=10'
]
sites = [r['sites'] for r in results]
colours = ['#e74c3c' if s > 300 else '#27ae60' if s == 218 else '#f39c12' for s in sites]

axes[0].bar(labels, sites, color=colours, edgecolor='black', alpha=0.8)
axes[0].axhline(218, color='black', linestyle='--', linewidth=1.5, label='Register count (218)')
axes[0].set_title('Candidate Sites per Threshold Combination')
axes[0].set_ylabel('Number of Candidate Sites')
axes[0].legend()
axes[0].tick_params(axis='x', labelsize=8)

# Plot 2 — mean site size per threshold combination
mean_sizes = [r['mean_ha'] for r in results]
axes[1].bar(labels, mean_sizes, color='#2980b9', edgecolor='black', alpha=0.8)
axes[1].axhline(1.0, color='black', linestyle='--', linewidth=1.5, label='1 hectare reference')
axes[1].set_title('Mean Site Size per Threshold Combination')
axes[1].set_ylabel('Mean Site Size (hectares)')
axes[1].legend()
axes[1].tick_params(axis='x', labelsize=8)

plt.tight_layout()
plt.savefig('../docs/images/clustering_threshold_comparison.png', dpi=150, bbox_inches='tight')
plt.show()
print("Saved to docs/images/clustering_threshold_comparison.png")
```

    Section 4 — Visualising Threshold Comparison
    ============================================================
    Saved to docs/images/clustering_threshold_comparison.png
    

    C:\Users\lward\AppData\Local\Temp\ipykernel_40904\587110138.py:35: UserWarning: FigureCanvasAgg is non-interactive, and thus cannot be shown
      plt.show()
    

## Section 4 — Performance Optimisation

The initial implementation of `group_pixels_for_candidate_sites` used Python loops to build connected component groups. With tens of thousands of components across a 5490×5490 grid, this was catastrophically slow — taking over an hour to run at some thresholds.

Two critical optimisations were made:

**Optimisation 1 — Vectorised candidate map construction:**

Original approach (slow):
```python
for row, col in candidate_positions:
    candidate_2d[row, col] = True
```

Replaced with vectorised numpy indexing (fast):
```python
candidate_2d[candidate_positions[:, 0], candidate_positions[:, 1]] = True
```

**Optimisation 2 — Single-pass label grouping:**

Original approach (slow) — scanned the entire array once per label:
```python
for label in range(1, num_features + 1):
    positions = np.argwhere(labelled_array == label)
```

Replaced with a single sorted pass using `np.unique` with `return_index=True`:
```python
sort_order = np.argsort(all_labels)
unique_labels, start_indices = np.unique(all_labels[sort_order], return_index=True)
```

These two changes reduced clustering runtime from over an hour to under 2 minutes on the full tile, and under 30 seconds on the Stoke-clipped data.

**Morphological dilation:**

A single iteration of `scipy.ndimage.binary_dilation` was added before connected-component labelling. This connects candidate pixels that are separated by a single non-candidate pixel — bridging gaps caused by mixed pixels at site edges or minor spectral noise. Testing showed `iterations=2` was too aggressive, connecting unrelated patches into one massive component. `iterations=1` produced the most geographically coherent candidate sites.


```python
print("Section 5 — Final Algorithm Summary")
print("="*60)

print("\nFinal pipeline configuration:")
print("  BSI threshold: 0.10")
print("  NDVI threshold: 0.20")
print("  Minimum pixels: 10 (0.4 hectares)")
print("  Maximum pixels: 2500 (100 hectares)")
print("  Dilation iterations: 1")
print("  k (PCA components): max(cumulative_variance_for_k(0.80), 3) = 3")

print("\nFinal clustering results on Stoke-on-Trent (May 2026 image):")
final_groups = group_pixels_for_candidate_sites(
    X_reduced_stoke, clipped_mask, original_shape,
    bsi_stoke, ndvi_stoke,
    bsi_threshold=0.10,
    ndvi_threshold=0.20,
    min_pixels=10,
    max_pixels=2500
)
final_props = calculate_site_properties(
    final_groups, bsi_stoke, clipped_mask, original_shape, tile_metadata_stoke
)

sizes = [p['hectares'] for p in final_props]
bsi_values = [p['mean_bsi'] for p in final_props]

print(f"  Total candidate sites: {len(final_groups)}")
print(f"  Site sizes: min {min(sizes):.2f}ha, max {max(sizes):.2f}ha, mean {sum(sizes)/len(sizes):.2f}ha")
print(f"  Mean BSI: min {min(bsi_values):.4f}, max {max(bsi_values):.4f}, mean {sum(bsi_values)/len(bsi_values):.4f}")

# Size distribution histogram
fig, ax = plt.subplots(figsize=(10, 5))
ax.hist(sizes, bins=30, color='#c0392b', edgecolor='black', alpha=0.8)
ax.set_title('Distribution of Candidate Site Sizes — BSI>0.1, NDVI<0.2, min=10, max=2500')
ax.set_xlabel('Site Size (hectares)')
ax.set_ylabel('Number of Sites')
ax.axvline(sum(sizes)/len(sizes), color='black', linestyle='--', 
           label=f'Mean: {sum(sizes)/len(sizes):.2f}ha')
ax.legend()
plt.tight_layout()
plt.savefig('../docs/images/candidate_site_size_distribution.png', dpi=150, bbox_inches='tight')
plt.show()
print("Saved to docs/images/candidate_site_size_distribution.png")
```

    Section 5 — Final Algorithm Summary
    ============================================================
    
    Final pipeline configuration:
      BSI threshold: 0.10
      NDVI threshold: 0.20
      Minimum pixels: 10 (0.4 hectares)
      Maximum pixels: 2500 (100 hectares)
      Dilation iterations: 1
      k (PCA components): max(cumulative_variance_for_k(0.80), 3) = 3
    
    Final clustering results on Stoke-on-Trent (May 2026 image):
    Brownfield candidate pixels: 1,951 (0.8% of valid pixels)
    Connected components found: 819
    Candidate sites after size filter: 218
      Total candidate sites: 218
      Site sizes: min 0.40ha, max 6.80ha, mean 0.76ha
      Mean BSI: min -0.0290, max 0.1723, mean 0.0593
    Saved to docs/images/candidate_site_size_distribution.png
    

    C:\Users\lward\AppData\Local\Temp\ipykernel_40904\4029362876.py:43: UserWarning: FigureCanvasAgg is non-interactive, and thus cannot be shown
      plt.show()
    

## Final Finding — Clustering Calibration

The BSI/NDVI threshold-based connected-component approach successfully identifies discrete candidate brownfield sites within the Stoke-on-Trent boundary from a single Sentinel-2 L2A image captured on 25 May 2026.

**Final configuration:**
- BSI > 0.10 AND NDVI < 0.20 identifies 1,951 bare soil candidate pixels (0.8% of valid Stoke pixels)
- Morphological dilation (iterations=1) connects nearby candidates into coherent patches
- 819 connected components found before size filtering
- After filtering (min=10 pixels, max=2500 pixels): **218 candidate sites** *(dilation-inflated; true count 25 at min=10, 90 at min=5 — see status note and issue #89)*
- Site sizes range from 0.40ha to 6.80ha, mean 0.76ha — consistent with realistic brownfield plot sizes in an urban area

**Important limitation:**

As established in Notebook 04, registered brownfield sites in Stoke have a mean BSI of 0.005 and mean NDVI of 0.21 — meaning they are predominantly vegetated at the time of this image. The BSI>0.1, NDVI<0.2 threshold detects only **currently bare** land, not all brownfield land. When matched against the 2024 register, 39 of 218 candidate sites corresponded to register entries — meaning the large majority of registered sites are vegetated and invisible to this threshold approach. (Post-FND provisional figures: 18 of 90 at min_pixels=5. The vegetated-invisibility conclusion is unchanged.)

This is not a failure of the algorithm — it is detecting a different and complementary signal: land that is currently bare and unregistered, which may represent the highest priority brownfield sites for immediate development. Vegetated brownfield sites on the register are already known to planners.

**Version 3 implication:**

The supervised classifier planned for Version 3 aims to learn the full spectral signature of brownfield regardless of vegetation state. **Correction (July 2026):** as designed in Notebook 07, the classifier trains on candidate sites emitted by the threshold detector — so vegetated register sites, which never pass the threshold gate, can never appear as training rows, and a downstream classifier cannot recover recall the gate has already discarded. Recovering vegetated brownfield requires the model to REPLACE the threshold gate (training rows sampled independently of it, e.g. register locations as positives with sampled background negatives). This architectural fork is recorded as an open decision in Notebook 07.

The threshold-based approach implemented here is the correct Version 2 baseline: interpretable, fast, and producing geographically plausible results that can be validated by planning officials without requiring machine learning expertise to understand.


```python

```


```python

```
