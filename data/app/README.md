# App data exports

Everything the Streamlit app in [`app/`](../../app) reads. Committed on purpose:
Streamlit Community Cloud cannot reach the local Postgres instance the pipeline
writes to, so the app reads files or it reads nothing.

Regenerate with a database connection and, for the two gate-sample files, the
May 2026 SAFE scene under `raw_data/`:

```bash
python scripts/export_app_data.py                 # everything
python scripts/export_app_data.py --skip-imagery  # database only
```

| File | Rows | Source | Used by |
|---|---|---|---|
| `seasons.csv` | 4 | `candidate_sites` grouped by `image_date` | Pipeline |
| `candidates.csv` | 554 | `candidate_sites`, centroids in WGS84 | Pipeline, Map |
| `persistent_candidates.geojson` | 20 | `candidate_sites` footprints joined to `data/groundtruth/persistent_labels.csv` | Map |
| `register_sites.csv` | 352 | `brownfield_sites`, 2026 register | Map, Finding |
| `boundary.geojson` | 1 | `council_boundaries`, simplified to 0.0002° | Map |
| `register_gate_samples.csv` | 352 | May 2026 scene sampled at each register location | Finding |
| `background_samples.csv` | 5,000 | random valid pixels from the same scene, seed 42 | Finding |
| `metrics.json` | — | headline figures computed at export time | all three |

## Notes

**Geometry is EPSG:4326.** Transformed in SQL at export time, so the app needs
no geospatial libraries — no GDAL, no geopandas, no PostGIS client.

**`site_reference` is text, not a number.** 44 of the 352 register references
are zero-padded, and 27 rows are a second entry for a site that also appears
unpadded — `0137` and `137` are the same place. Parsed as integers the pairs
collide and 27 rows vanish. Read this column with `dtype={'site_reference': str}`.

**Persistence follows notebook 08, not `prior_date_count`.** A candidate is
persistent where a candidate from every other date lies within 50 m of it, with
the winter scene as the anchor. The stored `prior_date_count` column counts only
dates already in the table when the row was written, so it reflects the order the
runs happened to be executed in.

**The gate samples are the finding.** BSI and NDVI measured at every register
location irrespective of whether the detector emitted anything there — the
measurement that exists nowhere in the database, because the pipeline stores only
what the gate lets through. Reproduces notebook 09 section 6 exactly: 0 of 352
pass, maximum BSI 0.0843, mean NDVI 0.234. The background sample is redrawn at
export time with a fixed seed, so it is statistically but not pixel-for-pixel
identical to the one in `docs/images/register_vs_gate.png`.

Checked by `tests/test_app_data.py`, which needs no database.
