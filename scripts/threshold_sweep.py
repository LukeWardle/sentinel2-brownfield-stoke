"""
threshold_sweep.py - Data-driven threshold selection (P1-8, subsumes #89).
==========================================================================
Sweeps bsi_threshold x min_pixels over a real image and reports, for every
combination: candidate count, register matches, register recall, and lead
volume — the frontier from which thresholds are CHOSEN rather than hand-
picked. Run from the repo root:

    python scripts/threshold_sweep.py --gss_code E06000021 --safe_path raw_data/S2C_....SAFE
    python scripts/threshold_sweep.py --gss_code E06000021 --date 2026-05-25   # downloads

Output: outputs/threshold_sweep_<gss>_<ts>.csv plus a printed summary.

How to read it honestly:
- Register recall here is proximity-matched (100m centroid) against the
  most recent register year — the sanity floor, NOT the product metric.
- Precision cannot come from this sweep: it needs labels (P1-1) or
  multi-date persistence (#92). What the sweep CAN pin down today is the
  recall/volume frontier: the smallest lead volume that keeps register
  recall from collapsing.
- The arrays are computed ONCE; each combination re-runs only clustering
  and matching, so a 5x6 grid takes minutes, not hours.
- Log the chosen thresholds and the frontier reasoning in DESIGN.md — the
  acceptance criterion is the documented decision, and this CSV is its
  evidence.

Matching uses an in-memory KD-tree over register points (one DB read)
rather than per-candidate SQL — same 100m criterion as
match_candidate_to_register, dramatically faster for a sweep.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.aoi_clipping import clip_to_council_boundary
from src.api_copernicus import authenticate, download_safe, search_products
from src.clustering import calculate_site_properties, group_pixels_for_candidate_sites
from src.data_loading_satellite import bands_10m, bands_20m, load_bands, load_scl
from src.database_query import get_db_connection
from src.main import get_tile_metadata
from src.preprocess import compute_bsi, compute_ndvi, normalise_band_array
from src.scl_filtering import mask_nodata

MATCH_DISTANCE_M = 100.0

BSI_GRID = [0.05, 0.075, 0.10, 0.125, 0.15]
MIN_PIXELS_GRID = [3, 5, 8, 10, 15, 20]


def load_register_points(gss_code: str, connection) -> np.ndarray:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT utm_x, utm_y FROM brownfield_sites
        WHERE gss_code = %s
          AND year = (SELECT MAX(year) FROM brownfield_sites WHERE gss_code = %s)
        """,
        (gss_code, gss_code),
    )
    points = np.array(cursor.fetchall(), dtype=float)
    cursor.close()
    if len(points) == 0:
        raise ValueError(f"No register sites loaded for {gss_code}")
    return points


def prepare_arrays(gss_code: str, safe_path: str, connection):
    """One-off heavy lifting: load, clip, mask, normalise, index."""
    print("Loading and preparing arrays (once)...")
    band_array = load_bands(safe_path)
    scl_array = load_scl(safe_path)
    tile_metadata = get_tile_metadata(safe_path)
    band_array, scl_array = clip_to_council_boundary(
        band_array, scl_array, tile_metadata, gss_code, connection
    )
    masked_array, mask, original_shape = mask_nodata(band_array, scl_array)
    normalised = normalise_band_array(masked_array)
    bsi = compute_bsi(normalised, bands_20m, bands_10m)
    ndvi = compute_ndvi(normalised, bands_20m, bands_10m)
    return mask, original_shape, bsi, ndvi, tile_metadata


def sweep(gss_code, mask, original_shape, bsi, ndvi, tile_metadata, register_points):
    tree = cKDTree(register_points)
    n_register = len(register_points)
    results = []
    for bsi_threshold in BSI_GRID:
        for min_pixels in MIN_PIXELS_GRID:
            groups = group_pixels_for_candidate_sites(
                mask,
                original_shape,
                bsi,
                ndvi,
                bsi_threshold=bsi_threshold,
                ndvi_threshold=0.2,
                min_pixels=min_pixels,
                max_pixels=2500,
            )
            props = calculate_site_properties(
                groups, bsi, mask, original_shape, tile_metadata
            )
            if props:
                centroids = np.array(
                    [[p["centroid_utm_x"], p["centroid_utm_y"]] for p in props]
                )
                dists, idx = tree.query(centroids)
                matched_mask = dists <= MATCH_DISTANCE_M
                matched_candidates = int(matched_mask.sum())
                distinct_register_hit = len(set(idx[matched_mask].tolist()))
            else:
                matched_candidates = 0
                distinct_register_hit = 0

            results.append(
                {
                    "bsi_threshold": bsi_threshold,
                    "min_pixels": min_pixels,
                    "min_hectares": round(min_pixels * 0.04, 2),
                    "candidates": len(props),
                    "matched_candidates": matched_candidates,
                    "register_sites_hit": distinct_register_hit,
                    "register_recall": round(distinct_register_hit / n_register, 4),
                    "unmatched_leads": len(props) - matched_candidates,
                }
            )
            print(
                f"bsi>{bsi_threshold:<6} min_px={min_pixels:<3} -> "
                f"{len(props):>4} candidates, recall "
                f"{distinct_register_hit}/{n_register}, "
                f"{len(props) - matched_candidates} leads"
            )
    return results


def main():
    parser = argparse.ArgumentParser(description="P1-8 threshold sweep")
    parser.add_argument("--gss_code", type=str, default="E06000021")
    parser.add_argument("--safe_path", type=str, default=None)
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--out_dir", type=str, default="outputs")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        safe_path = args.safe_path
        if safe_path is None:
            if args.date is None:
                raise SystemExit("Provide --safe_path or --date")
            auth = authenticate()
            products = search_products(
                args.gss_code, args.date, auth["access_token"], conn
            )
            safe_path = download_safe(
                products[0]["product_id"],
                products[0]["product_name"],
                auth,
                str(Path(__file__).parent.parent / "raw_data"),
            )

        mask, shape, bsi, ndvi, tile_meta = prepare_arrays(
            args.gss_code, safe_path, conn
        )
        register_points = load_register_points(args.gss_code, conn)
        results = sweep(
            args.gss_code, mask, shape, bsi, ndvi, tile_meta, register_points
        )

        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = out / f"threshold_sweep_{args.gss_code}_{stamp}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSweep written to {csv_path}")
        print(
            "Next: pick the smallest lead volume that holds register recall, "
            "and log the choice + this CSV in DESIGN.md (that IS the P1-8 "
            "acceptance criterion). Note the SAFE path used and re-run after "
            "multi-date persistence lands — persistence changes the frontier."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
