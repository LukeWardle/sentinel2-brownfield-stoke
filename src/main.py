"""
main.py - Orchestrates the full Version 2 pipeline.
====================================================
Runs the full Sentinel-2 brownfield detection pipeline end to end — from
automatic SAFE file download via the Copernicus API through to saving a
false colour map, PDF report and interactive map in outputs/. Accepts a
GSS code and image date as inputs rather than a manual SAFE path.

All Version 2 modules are called in sequence:
api_copernicus → data_loading_satellite → aoi_clipping → scl_filtering
→ validation_satellite → preprocess → pca → clustering → exclusion_filter
→ (persistence_filter) → database_query → visualise

Detection-quality steps (FND / P1 workstream):
- Candidate footprints are captured as valid GeoJSON geometry (FND-2) and
  stored alongside each site (FND-3, migration 003).
- The exclusion filter drops candidates majority-inside hard exclusion
  classes via indexed PostGIS area-overlap (FND-4); building and
  infrastructure are not hard masks. The register recall guardrail is
  printed every run — a validation metric, never a mask override.
- Optional temporal persistence (P1-4, --min_persistence) requires
  candidates to recur near the same location on prior image dates.
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import rasterio

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.aoi_clipping import clip_to_council_boundary
from src.api_copernicus import download_safe, get_access_token, search_products
from src.clustering import (
    calculate_site_properties,
    generate_boundary_polygons,
    group_pixels_for_candidate_sites,
)
from src.data_loading_satellite import bands_10m, bands_20m, load_bands, load_scl
from src.database_query import (
    detect_register_changes,
    get_db_connection,
    match_candidate_to_register,
    store_candidate_sites,
    store_pipeline_metadata,
)
from src.exclusion_filter import (
    filter_candidates_by_exclusion,
    report_register_recall,
)
from src.pca import (
    cumulative_variance_for_k,
    project,
    sort_variance,
    spectral_decomposition,
)
from src.persistence_filter import filter_candidates_by_persistence
from src.preprocess import (
    centre_data,
    compute_bsi,
    compute_covariance,
    compute_ndvi,
    normalise_band_array,
)
from src.scl_filtering import mask_nodata
from src.validation_database import (
    store_candidate_sites_validation,
    store_pipeline_metadata_validation,
    validate_council_boundary_gss,
)
from src.validation_satellite import validate_bands, validate_path, validate_quality
from src.visualise import (
    convert_k_to_rgb,
    create_interactive_map,
    false_map_creation,
    report_creation,
)


def get_tile_metadata(safe_path: str) -> dict:
    """
    Extracts tile metadata from a Sentinel-2 SAFE folder. Reads the left
    edge, top edge and pixel resolution from a 20m band file using rasterio.
    Used to convert pixel positions to UTM coordinates throughout the pipeline.

    Args:
        safe_path (str): Full path to the extracted SAFE folder.

    Returns:
        dict: Containing left, top and resolution values for coordinate conversion.

    Raises:
        FileNotFoundError: If the GRANULE directory or B05 band file is missing.
    """
    granule_dir = os.path.join(safe_path, "GRANULE")
    granule_name = os.listdir(granule_dir)[0]
    r20m_path = os.path.join(granule_dir, granule_name, "IMG_DATA", "R20m")
    sample_band = [f for f in os.listdir(r20m_path) if "_B05_" in f][0]
    with rasterio.open(os.path.join(r20m_path, sample_band)) as src:
        bounds = src.bounds
        return {"left": bounds.left, "top": bounds.top, "resolution": 20}


def run_pipeline(
    gss_code: str, image_date: str, output_dir: str, min_persistence: int = 0
) -> None:
    """
    Orchestrates the full Sentinel-2 brownfield detection pipeline.
    Downloads the SAFE file automatically via the Copernicus API, processes
    the satellite imagery, identifies candidate brownfield sites, filters
    non-brownfield land use, cross-references against the most recent
    available brownfield register, and produces a false colour map, PDF
    report and interactive map.

    Args:
        gss_code (str): GSS code for the council area to process —
                        e.g. 'E06000021' for Stoke-on-Trent.
        image_date (str): Date of the Sentinel-2 image to download and process
                          in YYYY-MM-DD format.
        output_dir (str): Path to the folder where outputs will be saved.
        min_persistence (int): P1-4 — minimum number of OTHER stored image
                               dates on which each candidate must recur.
                               0 (default) disables the persistence filter.

    Returns:
        None — saves false_colour_map, results_report PDF and interactive_map
               to output_dir. Stores candidate sites (with footprint geometry)
               and pipeline run metadata in the PostgreSQL database.

    Raises:
        ValueError: If GSS code is invalid, no products found for the given date,
                    database validation fails, or data is corrupt at any stage.
        FileNotFoundError: If downloaded SAFE folder is missing expected structure.
    """
    os.makedirs(output_dir, exist_ok=True)
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_path = None
    status = "failure"
    site_properties = []

    conn = get_db_connection()

    try:
        # --- Step 1: Validate database inputs ---
        print(f"Validating GSS code: {gss_code}")
        validate_council_boundary_gss(gss_code, conn)

        # --- Step 2: Download SAFE file via Copernicus API ---
        print("Authenticating with Copernicus API...")
        token = get_access_token()

        print(f"Searching for Sentinel-2 image for {gss_code} on {image_date}...")
        products = search_products(gss_code, image_date, token)
        best_product = products[0]
        print(
            f"Found: {best_product['product_name']} — cloud cover: {best_product['cloud_cover']}"
        )

        raw_data_dir = str(Path(__file__).parent.parent / "raw_data")
        print("Downloading SAFE file...")
        safe_path = download_safe(
            best_product["product_id"],
            best_product["product_name"],
            token,
            raw_data_dir,
        )
        print(f"Downloaded to: {safe_path}")

        # --- Step 3: Load satellite data ---
        print("Loading satellite bands...")
        validate_path(safe_path)
        band_array = load_bands(safe_path)  # (height, width, 10)
        scl_array = load_scl(safe_path)  # (height, width)

        # --- Step 4: Get tile metadata ---
        tile_metadata = get_tile_metadata(safe_path)

        # --- Step 5: AOI clipping on the raw grid ---
        # Runs before SCL masking so downstream processing only sees pixels
        # inside the council boundary — for Stoke ~233,000 rather than ~21M.
        print(f"Clipping to council boundary for {gss_code}...")
        band_array, scl_array = clip_to_council_boundary(
            band_array, scl_array, tile_metadata, gss_code, conn
        )

        # --- Step 6: SCL filtering ---
        # Drops nodata (SCL=0) and defective (SCL=1) pixels. Out-of-boundary
        # pixels already carry SCL=0 from Step 5, so they are removed here in
        # the same pass. The 3D grid is flattened to the (valid_pixels, 10)
        # form used by preprocess, PCA and clustering.
        print("Applying SCL masking...")
        masked_array, mask, original_shape = mask_nodata(band_array, scl_array)

        # --- Step 7: Validate satellite data ---
        # validate_quality now measures cloud coverage within the council
        # boundary rather than across the full tile, since out-of-boundary
        # SCL pixels have been zeroed.
        validate_bands(masked_array)
        validate_quality(scl_array)

        # --- Step 8: Normalise band array ---
        print("Normalising band array to surface reflectance...")
        normalised_array = normalise_band_array(masked_array)

        # --- Step 9: Compute spectral indices ---
        print("Computing BSI and NDVI...")
        bsi_array = compute_bsi(normalised_array, bands_20m, bands_10m)
        ndvi_array = compute_ndvi(normalised_array, bands_20m, bands_10m)

        # --- Step 10: PCA ---
        print("Running PCA spectral decomposition...")
        centred_array = centre_data(normalised_array)
        covariance_matrix = compute_covariance(centred_array)
        eigenvalues, eigenvectors = spectral_decomposition(covariance_matrix)
        sorted_eigenvalues, sorted_eigenvectors = sort_variance(
            eigenvalues, eigenvectors
        )
        k = cumulative_variance_for_k(sorted_eigenvalues)
        k = max(k, 3)
        X_reduced = project(centred_array, sorted_eigenvectors, k)
        X_for_map = project(centred_array, sorted_eigenvectors, 3)

        # --- Step 11: Clustering ---
        print("Grouping pixels into candidate sites...")
        candidate_groups = group_pixels_for_candidate_sites(
            X_reduced,
            mask,
            original_shape,
            bsi_array,
            ndvi_array,
            bsi_threshold=0.1,
            ndvi_threshold=0.2,
            min_pixels=10,
            max_pixels=2500,
        )
        print(f"Found {len(candidate_groups)} candidate groups")

        site_properties = calculate_site_properties(
            candidate_groups, bsi_array, mask, original_shape, tile_metadata
        )

        # FND-2/FND-3: valid footprint geometry, captured and attached so it
        # is stored with each site.
        site_polygons = generate_boundary_polygons(
            candidate_groups, mask, original_shape, tile_metadata
        )
        geometry_by_id = {p["site_id"]: p.get("geometry") for p in site_polygons}
        for site in site_properties:
            site["geometry"] = geometry_by_id.get(site["site_id"])

        # --- Step 11b: Exclusion filtering (P1-5 / FND-4) ---
        # Drop candidates majority-inside the HARD exclusion classes
        # (car parks, quarries, agriculture, amenity/leisure) via indexed
        # PostGIS area-overlap. Building and infrastructure are NOT hard
        # masks — they overlap the definition of brownfield and return as
        # classifier features in P1-6.
        print("Applying non-brownfield exclusion filter...")
        site_properties, excluded_count = filter_candidates_by_exclusion(
            site_properties, site_polygons, gss_code, conn
        )
        print(
            f"Excluded {excluded_count} candidates in non-brownfield land use; "
            f"{len(site_properties)} remain"
        )

        # Register recall guardrail — validation metric, never a mask override.
        recall_guard = report_register_recall(gss_code, conn)
        print(
            f"Register recall guardrail: {recall_guard['inside_exclusions']} of "
            f"{recall_guard['register_sites']} register sites fall inside the "
            f"hard exclusion classes"
        )

        # --- Step 11c: Temporal persistence (P1-4, optional) ---
        if min_persistence > 0:
            print(
                f"Applying persistence filter (>= {min_persistence} prior date(s))..."
            )
            site_properties, persistence_dropped = filter_candidates_by_persistence(
                site_properties,
                gss_code,
                image_date,
                conn,
                min_prior_dates=min_persistence,
            )
            print(
                f"Dropped {persistence_dropped} non-persistent candidates; "
                f"{len(site_properties)} remain"
            )

        # --- Step 12: Register matching ---
        print("Matching candidate sites against brownfield register...")
        for site in site_properties:
            site["matched_site_reference"] = match_candidate_to_register(
                site["centroid_utm_x"], site["centroid_utm_y"], gss_code, conn
            )

        matched = sum(1 for s in site_properties if s.get("matched_site_reference"))
        unmatched = len(site_properties) - matched
        print(f"Matched: {matched}, Unregistered candidates: {unmatched}")

        # --- Step 13: Store candidate sites (with geometry, FND-3) ---
        if site_properties:
            store_candidate_sites_validation(site_properties)
            store_candidate_sites(
                site_properties, gss_code, image_date, run_timestamp, conn
            )

        # --- Step 14: Change detection ---
        print("Running change detection across register years...")
        try:
            change_detection = detect_register_changes(gss_code, 2019, 2024, conn)
            print(
                f"Change detection — added: {len(change_detection['added'])}, "
                f"removed: {len(change_detection['removed'])}"
            )
        except ValueError:
            change_detection = {"added": [], "removed": []}
            print("Insufficient register data for change detection")

        # --- Step 15: Generate outputs ---
        print("Generating false colour map...")
        rgb_array = convert_k_to_rgb(X_for_map)
        false_map_creation(rgb_array, output_dir, mask, original_shape)

        print("Generating PDF report...")
        report_creation(
            k,
            sorted_eigenvalues,
            output_dir,
            gss_code,
            image_date,
            site_properties,
            change_detection,
        )

        print("Generating interactive map...")
        create_interactive_map(site_properties, output_dir, gss_code)

        status = "success"
        print(f"Pipeline complete — status: {status}")

    except Exception as e:
        print(f"Pipeline failed: {e}")
        status = "failure"
        raise

    finally:
        # --- Step 16: Store pipeline metadata ---
        try:
            matched_count = sum(
                1 for s in site_properties if s.get("matched_site_reference")
            )
            unmatched_count = len(site_properties) - matched_count

            store_pipeline_metadata_validation(
                gss_code,
                image_date,
                status,
                len(site_properties),
                matched_count,
                unmatched_count,
            )
            store_pipeline_metadata(
                gss_code,
                image_date,
                run_timestamp,
                status,
                len(site_properties),
                matched_count,
                unmatched_count,
                conn,
            )
        except Exception:
            pass

        # --- Step 17: Delete SAFE file ---
        if safe_path and os.path.exists(safe_path):
            outer_safe = str(Path(safe_path).parent)
            if os.path.exists(outer_safe) and outer_safe.endswith(".SAFE"):
                shutil.rmtree(outer_safe, ignore_errors=True)
            elif os.path.exists(safe_path) and safe_path.endswith(".SAFE"):
                shutil.rmtree(safe_path, ignore_errors=True)

        # --- Step 18: Close database connection ---
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Brownfield Detection Pipeline")
    parser.add_argument(
        "--gss_code",
        type=str,
        default="E06000021",
        help="GSS code for the council area (default: E06000021 — Stoke-on-Trent)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default="2026-05-25",
        help="Image date in YYYY-MM-DD format (default: 2026-05-25)",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(Path(__file__).parent.parent / "outputs"),
        help="Output directory (default: outputs/)",
    )
    parser.add_argument(
        "--min_persistence",
        type=int,
        default=0,
        help="P1-4: minimum prior image dates each candidate must recur on "
        "(default 0 = persistence filter off)",
    )
    args = parser.parse_args()

    run_pipeline(args.gss_code, args.date, args.output_dir, args.min_persistence)
