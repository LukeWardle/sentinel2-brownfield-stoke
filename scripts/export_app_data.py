"""
export_app_data.py — export the data the Streamlit app reads (P3-1, issue #58).
==============================================================================
The app in app/ presents the investigation and its negative result, and must
run on Streamlit Cloud, which cannot reach a local Postgres instance. This
script is the only place a database connection is used: it writes everything
the app needs into data/app/ as CSV, GeoJSON and JSON, which are committed.

Two sources are read.

The database supplies the candidate sites for the four seasonal scenes, the
persistent set defined in Notebook 08, the 2026 brownfield register and the
council boundary. Geometry is transformed to EPSG:4326 in SQL so the app
needs no geospatial libraries.

The May 2026 SAFE scene, if present under raw_data/, supplies the register
gate samples reproduced from Notebook 09 section 6 — BSI and NDVI sampled at
every register location irrespective of whether the detector emitted anything
there. This is the measurement behind the 0 of 352 finding and it exists
nowhere in the database, because the pipeline only ever stored what the gate
let through. Without a scene on disk this step is skipped and the previously
committed CSVs are left untouched.

Usage:
    python scripts/export_app_data.py                 # database + imagery if present
    python scripts/export_app_data.py --skip-imagery  # database only
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.database_query import get_db_connection  # noqa: E402

GSS = "E06000021"
REGISTER_YEAR = 2026

# The four seasonal scenes analysed in Notebook 08. Winter anchors the
# persistence query for the reason given there: it is the strictest date.
SEASONS = {
    "2026-07-09": "Summer",
    "2025-09-22": "Autumn",
    "2025-12-26": "Winter",
    "2026-05-25": "Spring",
}
WINTER = "2025-12-26"
PERSISTENCE_MATCH_M = 50  # Notebook 08 cross-date centroid tolerance

# The detection gate. BSI above and NDVI below, simultaneously.
BSI_THRESHOLD = 0.1
NDVI_THRESHOLD = 0.2

# Gate-passing pixel share per scene. Recorded in the run logs rather than in
# the database, so carried here as a constant (README, Notebook 08 section 4).
PIXEL_SHARE_PCT = {
    "2026-07-09": 2.8,
    "2025-09-22": 1.7,
    "2025-12-26": 1.0,
    "2026-05-25": 0.8,
}

# Pixel area at 20 m resolution, in hectares — the conversion used throughout
# the notebooks to turn a cluster's pixel count into a site area.
HA_PER_PIXEL = 0.04

OUT_DIR = ROOT / "data" / "app"
LABELS_CSV = ROOT / "data" / "groundtruth" / "persistent_labels.csv"

# EPSG:32630 point built from the stored UTM columns. Both candidate_sites and
# brownfield_sites carry utm_x/utm_y, and the notebooks match on these rather
# than on the geometry columns, so the same construction is used here.
UTM_POINT = "ST_SetSRID(ST_MakePoint({t}.utm_x, {t}.utm_y), 32630)"


def _lonlat(table: str) -> str:
    """SQL selecting WGS84 longitude and latitude from a table's UTM columns."""
    point = UTM_POINT.format(t=table)
    return (
        f"ST_X(ST_Transform({point}, 4326)) AS lon, "
        f"ST_Y(ST_Transform({point}, 4326)) AS lat"
    )


def _read_sql(sql: str, conn, params: dict | None = None) -> pd.DataFrame:
    """pandas.read_sql over a psycopg2 connection without the SQLAlchemy warning."""
    with conn.cursor() as cursor:
        cursor.execute(sql, params or {})
        columns = [c.name for c in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=columns)


# ---------------------------------------------------------------------------
# Database exports
# ---------------------------------------------------------------------------


def export_seasons(conn) -> pd.DataFrame:
    """Per-scene candidate counts — the Pipeline page's seasonal gradient."""
    seasons = _read_sql(
        """
        SELECT image_date,
               COUNT(*)                         AS candidates,
               COUNT(matched_site_reference)    AS matched_100m,
               ROUND(AVG(bsi_value)::numeric, 4)              AS mean_bsi,
               ROUND(SUM(pixel_count * %(ha)s)::numeric, 1)   AS total_hectares
        FROM candidate_sites
        WHERE gss_code = %(gss)s
        GROUP BY image_date
        ORDER BY image_date
        """,
        conn,
        {"gss": GSS, "ha": HA_PER_PIXEL},
    )
    seasons["image_date"] = seasons.image_date.astype(str)
    seasons["season"] = seasons.image_date.map(SEASONS)
    seasons["pixel_share_pct"] = seasons.image_date.map(PIXEL_SHARE_PCT)
    # Present in season order rather than date order: the scenes span fourteen
    # months, so a chronological axis reads as an unrelated ordering.
    order = ["Summer", "Autumn", "Winter", "Spring"]
    seasons = seasons.set_index("season").loc[order].reset_index()
    seasons = seasons[
        [
            "season",
            "image_date",
            "candidates",
            "matched_100m",
            "pixel_share_pct",
            "mean_bsi",
            "total_hectares",
        ]
    ]
    seasons.to_csv(OUT_DIR / "seasons.csv", index=False)
    print(f"  seasons.csv                  {len(seasons)} rows")
    return seasons


def export_candidates(conn) -> pd.DataFrame:
    """Every candidate on every scene, as a point. 554 rows across four dates."""
    candidates = _read_sql(
        f"""
        SELECT c.id,
               c.image_date,
               c.pixel_count,
               ROUND((c.pixel_count * %(ha)s)::numeric, 2) AS hectares,
               ROUND(c.bsi_value::numeric, 4)   AS bsi,
               ROUND(c.mean_ndvi::numeric, 4)   AS mean_ndvi,
               ROUND(c.compactness::numeric, 3) AS compactness,
               c.matched_site_reference,
               {_lonlat("c")}
        FROM candidate_sites c
        WHERE c.gss_code = %(gss)s
        ORDER BY c.image_date, c.id
        """,
        conn,
        {"gss": GSS, "ha": HA_PER_PIXEL},
    )
    candidates["image_date"] = candidates.image_date.astype(str)
    candidates["season"] = candidates.image_date.map(SEASONS)
    candidates["registered"] = candidates.matched_site_reference.notna()
    candidates.to_csv(OUT_DIR / "candidates.csv", index=False)
    print(f"  candidates.csv               {len(candidates)} rows")
    return candidates


def export_persistent(conn) -> pd.DataFrame:
    """
    The persistent set with footprint geometry and manual labels.

    Persistence is Notebook 08's definition: a winter candidate with a
    candidate from every other date within 50 metres. The stored
    prior_date_count column is deliberately not used — it counts only dates
    already in the table when the row was written, so it reflects run order
    rather than cross-date persistence.
    """
    persistent = _read_sql(
        f"""
        SELECT w.id AS candidate_id,
               w.pixel_count,
               ROUND((w.pixel_count * %(ha)s)::numeric, 2) AS hectares,
               ROUND(w.bsi_value::numeric, 4)   AS bsi,
               ROUND(w.mean_ndvi::numeric, 4)   AS mean_ndvi,
               ROUND(w.compactness::numeric, 3) AS compactness,
               w.matched_site_reference,
               {_lonlat("w")},
               ST_AsGeoJSON(ST_Transform(w.geom, 4326)) AS geometry
        FROM candidate_sites w
        WHERE w.gss_code = %(gss)s
          AND w.image_date = %(winter)s
          AND (SELECT COUNT(DISTINCT o.image_date)
                 FROM candidate_sites o
                WHERE o.gss_code = w.gss_code
                  AND ST_DWithin(
                        ST_SetSRID(ST_MakePoint(o.utm_x, o.utm_y), 32630),
                        ST_SetSRID(ST_MakePoint(w.utm_x, w.utm_y), 32630),
                        %(m)s)) = 4
        ORDER BY w.pixel_count DESC
        """,
        conn,
        {"gss": GSS, "winter": WINTER, "m": PERSISTENCE_MATCH_M, "ha": HA_PER_PIXEL},
    )

    labels = pd.read_csv(LABELS_CSV, encoding="utf-8-sig")
    merged = persistent.merge(
        labels[["candidate_id", "label", "site_name", "notes", "maps_url"]],
        on="candidate_id",
        how="left",
    )

    # The one register-matched site carries no manual label: the labelling
    # exercise covered the nineteen unregistered candidates only.
    merged["registered"] = merged.matched_site_reference.notna()
    merged["label"] = merged.label.fillna("register_matched")
    merged["site_name"] = merged.site_name.fillna("")
    merged["notes"] = merged.notes.fillna("")
    merged["maps_url"] = merged.maps_url.fillna("")

    unlabelled = merged[(~merged.registered) & (merged.site_name == "")]
    if len(unlabelled):
        raise ValueError(
            f"unregistered persistent candidates without a label: "
            f"{sorted(unlabelled.candidate_id)}"
        )

    def scalar(value):
        """numpy and Decimal values into something json.dumps accepts."""
        if value is None or (
            not isinstance(value, (bool, np.bool_)) and pd.isna(value)
        ):
            return None
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, (int, np.integer)):
            return int(value)
        if isinstance(value, str):
            return value
        return float(value)

    features = []
    for row in merged.itertuples(index=False):
        properties = {
            key: scalar(value)
            for key, value in row._asdict().items()
            if key != "geometry"
        }
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(row.geometry) if row.geometry else None,
                "properties": properties,
            }
        )

    geojson = {
        "type": "FeatureCollection",
        "name": "persistent_candidates",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": features,
    }
    (OUT_DIR / "persistent_candidates.geojson").write_text(
        json.dumps(geojson, indent=1, default=float), encoding="utf-8"
    )
    print(
        f"  persistent_candidates.geojson {len(features)} features "
        f"({int(merged.registered.sum())} register-matched)"
    )
    return merged


def export_register(conn) -> pd.DataFrame:
    """The 2026 register — the target the detector was built to find."""
    register = _read_sql(
        f"""
        SELECT b.site_reference,
               b.name_address,
               b.hectares,
               b.planning_status,
               {_lonlat("b")}
        FROM brownfield_sites b
        WHERE b.gss_code = %(gss)s AND b.year = %(yr)s
        ORDER BY b.hectares DESC NULLS LAST
        """,
        conn,
        {"gss": GSS, "yr": REGISTER_YEAR},
    )
    register["hectares"] = register.hectares.astype(float)
    register.to_csv(OUT_DIR / "register_sites.csv", index=False)
    print(f"  register_sites.csv           {len(register)} rows")
    return register


def export_boundary(conn) -> None:
    """Council boundary for the map. Stored in 4326 with the SRID unset."""
    boundary = _read_sql(
        """
        SELECT name,
               ST_AsGeoJSON(
                   ST_SimplifyPreserveTopology(ST_SetSRID(boundary, 4326), 0.0002)
               ) AS geometry
        FROM council_boundaries
        WHERE gss_code = %(gss)s
        """,
        conn,
        {"gss": GSS},
    )
    if boundary.empty:
        raise ValueError(f"no council boundary stored for {GSS}")

    geojson = {
        "type": "FeatureCollection",
        "name": "council_boundary",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(boundary.geometry.iloc[0]),
                "properties": {"gss_code": GSS, "name": boundary.name.iloc[0]},
            }
        ],
    }
    path = OUT_DIR / "boundary.geojson"
    path.write_text(json.dumps(geojson), encoding="utf-8")
    print(f"  boundary.geojson             {path.stat().st_size // 1024} KB")


def collect_metrics(conn, seasons, candidates, persistent, register) -> dict:
    """
    The figures quoted on the Pipeline and Finding pages, computed here rather
    than hardcoded in the app so that they remain accountable to the database.
    """
    # Recall at three matching radii. The 100 m figure is what the pipeline
    # reports; the collapse as the radius tightens is the evidence that the
    # matches are coincidental proximity rather than detection.
    recall_by_radius = {}
    for radius in (100, 50, 25, 10):
        matched = _read_sql(
            """
            SELECT COUNT(DISTINCT b.site_reference) AS n
            FROM brownfield_sites b
            JOIN candidate_sites c
              ON c.gss_code = b.gss_code
             AND ST_DWithin(
                   ST_SetSRID(ST_MakePoint(c.utm_x, c.utm_y), 32630),
                   ST_SetSRID(ST_MakePoint(b.utm_x, b.utm_y), 32630),
                   %(r)s)
            WHERE b.gss_code = %(gss)s AND b.year = %(yr)s
            """,
            conn,
            {"gss": GSS, "yr": REGISTER_YEAR, "r": radius},
        )
        recall_by_radius[str(radius)] = int(matched.n.iloc[0])

    # Distance from each register site to the nearest candidate on any date.
    distances = _read_sql(
        """
        SELECT MIN(ST_Distance(
                 ST_SetSRID(ST_MakePoint(c.utm_x, c.utm_y), 32630),
                 ST_SetSRID(ST_MakePoint(b.utm_x, b.utm_y), 32630)
               )) AS nearest_m
        FROM brownfield_sites b
        LEFT JOIN candidate_sites c ON c.gss_code = b.gss_code
        WHERE b.gss_code = %(gss)s AND b.year = %(yr)s
        GROUP BY b.site_reference
        """,
        conn,
        {"gss": GSS, "yr": REGISTER_YEAR},
    )
    nearest = distances.nearest_m.astype(float)

    # How many winter candidates recur on how many dates.
    persistence_breakdown = _read_sql(
        """
        SELECT dates_present, COUNT(*) AS sites FROM (
          SELECT w.id,
            (SELECT COUNT(DISTINCT o.image_date)
               FROM candidate_sites o
              WHERE o.gss_code = w.gss_code
                AND ST_DWithin(
                      ST_SetSRID(ST_MakePoint(o.utm_x, o.utm_y), 32630),
                      ST_SetSRID(ST_MakePoint(w.utm_x, w.utm_y), 32630),
                      %(m)s)) AS dates_present
          FROM candidate_sites w
          WHERE w.gss_code = %(gss)s AND w.image_date = %(winter)s
        ) t
        GROUP BY dates_present
        ORDER BY dates_present
        """,
        conn,
        {"gss": GSS, "winter": WINTER, "m": PERSISTENCE_MATCH_M},
    )

    exclusions = _read_sql(
        "SELECT COUNT(*) AS n FROM exclusion_zones WHERE gss_code = %(gss)s",
        conn,
        {"gss": GSS},
    )

    labelled = persistent[~persistent.registered]

    metrics = {
        "gss_code": GSS,
        "council": "Stoke-on-Trent",
        "register_year": REGISTER_YEAR,
        "gate": {"bsi_above": BSI_THRESHOLD, "ndvi_below": NDVI_THRESHOLD},
        "pipeline": {
            "tile_valid_pixels": 21_223_650,
            "aoi_pixels": 233_603,
            "scenes": len(SEASONS),
            "candidates_total": int(len(candidates)),
            "candidates_by_season": {
                r.season: int(r.candidates) for r in seasons.itertuples()
            },
            "exclusion_polygons": int(exclusions.n.iloc[0]),
        },
        "register": {
            "sites": int(len(register)),
            "median_hectares": round(float(register.hectares.median()), 3),
            "below_detection_floor": int((register.hectares < 0.2).sum()),
            "detection_floor_ha": 0.2,
        },
        "matching": {
            "recall_by_radius": recall_by_radius,
            "nearest_candidate_m": {
                "median": round(float(nearest.median()), 1),
                "p25": round(float(nearest.quantile(0.25)), 1),
                "p75": round(float(nearest.quantile(0.75)), 1),
                "min": round(float(nearest.min()), 1),
            },
        },
        "persistence": {
            "match_radius_m": PERSISTENCE_MATCH_M,
            "anchor_date": WINTER,
            "winter_candidates": int(
                seasons.set_index("season").loc["Winter", "candidates"]
            ),
            "by_dates_present": {
                str(r.dates_present): int(r.sites)
                for r in persistence_breakdown.itertuples()
            },
            "persistent_sites": int(len(persistent)),
            "register_matched": int(persistent.registered.sum()),
            "labelled": int(len(labelled)),
            "sellable": int((labelled.label == "sellable").sum()),
            "labels": {
                str(k): int(v) for k, v in labelled.label.value_counts().items()
            },
        },
    }
    return metrics


# ---------------------------------------------------------------------------
# Imagery export — Notebook 09 section 6
# ---------------------------------------------------------------------------


def _find_scene(raw_data: Path) -> Path | None:
    """The extracted SAFE folder nests one level deep: X.SAFE/X.SAFE/."""
    scenes = sorted(raw_data.glob("*.SAFE")) if raw_data.exists() else []
    if not scenes:
        return None
    nested = scenes[0] / scenes[0].name
    return nested if nested.exists() else scenes[0]


def _read_band(safe_path: Path, band: str) -> np.ndarray:
    """
    One band on the common 20 m grid, as float32 reflectance.

    load_bands reads all ten bands and stacks them, which needs more memory
    than this machine reliably has. Only B02, B04, B08 and B11 enter BSI and
    NDVI, so they are read one at a time here, with the same bilinear
    resampling load_bands applies to the 10 m bands.
    """
    import rasterio

    granule = safe_path / "GRANULE"
    img_data = granule / next(iter(granule.iterdir())).name / "IMG_DATA"
    native = "R20m" if band in ("B05", "B06", "B07", "B8A", "B11", "B12") else "R10m"
    directory = img_data / native
    band_file = next(f for f in directory.iterdir() if f"_{band}_" in f.name)

    with rasterio.open(band_file) as src:
        if native == "R10m":
            data = src.read(
                1,
                out_shape=(5490, 5490),
                resampling=rasterio.enums.Resampling.bilinear,
            )
        else:
            data = src.read(1)
    return data.astype(np.float32) / 10_000  # raw DN to surface reflectance


def export_gate_samples(conn, raw_data: Path) -> dict:
    """
    BSI and NDVI at every register location and at a random background sample.

    This reproduces Notebook 09 section 6. The pipeline stores only what the
    gate emits, so the spectral values at undetected register sites — the
    substantial majority — exist only in the imagery. Each site is sampled
    over a square window sized to its recorded area, so a one hectare site is
    averaged over more pixels than a 0.1 hectare one.
    """
    from src.coordinate_conversion_pixel import utm_coordinate_to_pixel
    from src.main import get_tile_metadata

    scene = _find_scene(raw_data)
    if scene is None:
        print(f"  no SAFE scene under {raw_data} — skipping gate samples")
        print(
            "  to regenerate: python -m src.main --gss_code E06000021 "
            "--date 2026-05-25"
        )
        return {}

    print(f"  scene: {scene.name}")
    tile = get_tile_metadata(str(scene))
    resolution = tile["resolution"]
    height = width = 5490

    # Register sites carry UTM coordinates; convert each to a pixel window.
    utm = _read_sql(
        """
        SELECT site_reference, hectares, utm_x, utm_y
        FROM brownfield_sites
        WHERE gss_code = %(gss)s AND year = %(yr)s
        """,
        conn,
        {"gss": GSS, "yr": REGISTER_YEAR},
    )

    windows = []
    for site in utm.itertuples(index=False):
        if pd.isna(site.utm_x) or pd.isna(site.utm_y):
            continue
        pixel = utm_coordinate_to_pixel(site.utm_x, site.utm_y, tile)
        row, column = pixel["row"], pixel["column"]
        if not (0 <= row < height and 0 <= column < width):
            continue
        hectares = site.hectares if pd.notna(site.hectares) else 0.2
        side_m = np.sqrt(max(hectares, 0.04) * 10_000)
        half = max(int(side_m / resolution / 2), 1)
        rows = slice(max(row - half, 0), min(row + half + 1, height))
        columns = slice(max(column - half, 0), min(column + half + 1, width))
        windows.append((site.site_reference, site.hectares, rows, columns))

    # Pass one: the valid-data mask, accumulated a band at a time so that no
    # more than one full band is resident. Nodata reads as zero in every band.
    valid = np.ones((height, width), dtype=bool)
    bands = {}
    for band in ("B02", "B04", "B08", "B11"):
        array = _read_band(scene, band)
        valid &= array > 0
        # Keep only the pixels the sampling needs, then release the band.
        bands[band] = [array[rows, columns].copy() for _, _, rows, columns in windows]
        del array
        print(f"    read {band}")

    records = []
    for i, (reference, hectares, _, _) in enumerate(windows):
        b02, b04, b08, b11 = (bands[b][i] for b in ("B02", "B04", "B08", "B11"))
        bsi_num = (b11 + b04) - (b08 + b02)
        bsi_den = (b11 + b04) + (b08 + b02)
        bsi = np.where(bsi_den == 0, 0, bsi_num / np.where(bsi_den == 0, 1, bsi_den))
        ndvi_den = b08 + b04
        ndvi = np.where(
            ndvi_den == 0, 0, (b08 - b04) / np.where(ndvi_den == 0, 1, ndvi_den)
        )
        records.append(
            {
                "site_reference": reference,
                "hectares": hectares,
                "bsi": round(float(np.nanmean(bsi)), 5),
                "ndvi": round(float(np.nanmean(ndvi)), 5),
            }
        )

    samples = pd.DataFrame(records)
    samples["passes_bsi"] = samples.bsi > BSI_THRESHOLD
    samples["passes_ndvi"] = samples.ndvi < NDVI_THRESHOLD
    samples["passes_gate"] = samples.passes_bsi & samples.passes_ndvi
    samples.to_csv(OUT_DIR / "register_gate_samples.csv", index=False)
    print(f"  register_gate_samples.csv    {len(samples)} rows")

    # Pass two: a random background sample from the same scene, for the
    # comparison the Finding page plots the register against.
    rng = np.random.default_rng(42)
    rows, columns = np.where(valid)
    pick = rng.choice(len(rows), size=min(5000, len(rows)), replace=False)
    sample_rows, sample_columns = rows[pick], columns[pick]
    del rows, columns, valid

    values = {}
    for band in ("B02", "B04", "B08", "B11"):
        array = _read_band(scene, band)
        values[band] = array[sample_rows, sample_columns]
        del array

    b02, b04, b08, b11 = (values[b] for b in ("B02", "B04", "B08", "B11"))
    bsi_den = (b11 + b04) + (b08 + b02)
    ndvi_den = b08 + b04
    background = pd.DataFrame(
        {
            "bsi": np.where(
                bsi_den == 0,
                0,
                ((b11 + b04) - (b08 + b02)) / np.where(bsi_den == 0, 1, bsi_den),
            ).round(5),
            "ndvi": np.where(
                ndvi_den == 0,
                0,
                (b08 - b04) / np.where(ndvi_den == 0, 1, ndvi_den),
            ).round(5),
        }
    )
    background.to_csv(OUT_DIR / "background_samples.csv", index=False)
    print(f"  background_samples.csv       {len(background)} rows")

    return {
        "scene": scene.name,
        "sites_sampled": int(len(samples)),
        "passing_bsi": int(samples.passes_bsi.sum()),
        "passing_ndvi": int(samples.passes_ndvi.sum()),
        "passing_gate": int(samples.passes_gate.sum()),
        "max_bsi": round(float(samples.bsi.max()), 4),
        "mean_bsi": round(float(samples.bsi.mean()), 4),
        "mean_ndvi": round(float(samples.ndvi.mean()), 4),
        "background_sample_size": int(len(background)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-imagery",
        action="store_true",
        help="export from the database only, leaving the gate-sample CSVs as committed",
    )
    parser.add_argument(
        "--raw-data",
        type=Path,
        default=ROOT / "raw_data",
        help="directory holding the extracted SAFE scene (default: raw_data/)",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = OUT_DIR / "metrics.json"
    conn = get_db_connection()
    try:
        print("database:")
        seasons = export_seasons(conn)
        candidates = export_candidates(conn)
        persistent = export_persistent(conn)
        register = export_register(conn)
        export_boundary(conn)
        metrics = collect_metrics(conn, seasons, candidates, persistent, register)

        print("imagery:")
        if args.skip_imagery:
            print("  --skip-imagery set")
            gate = {}
            if metrics_path.exists():
                # Carry the previous run's figures forward rather than dropping
                # them, since the committed gate-sample CSVs are unchanged.
                gate = json.loads(metrics_path.read_text("utf-8")).get(
                    "gate_samples", {}
                )
        else:
            gate = export_gate_samples(conn, args.raw_data)
        if gate:
            metrics["gate_samples"] = gate
    finally:
        conn.close()

    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nwritten to {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
