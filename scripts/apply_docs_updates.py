"""
apply_docs_updates.py - Appends the P0-batch documentation to DESIGN.md
and README.md. Run from the repo root:

    python scripts/apply_docs_updates.py

Append-only by design: no anchors to break. Fold the content into the
existing sections whenever you next do a doc pass.
"""

from pathlib import Path

DESIGN_ADDENDUM = """

## P0 batch — 22 July 2026 (settings, containerisation, API robustness)

**[DECISION] Centralised settings layer (P0-3).** All configuration is read
through `src/settings.py` (pydantic-settings): `DATABASE_URL`,
`COPERNICUS_USERNAME`, `COPERNICUS_PASSWORD`, sourced from the environment
then `.env`. `database_query.get_db_connection` and
`api_copernicus.authenticate` consume it; no module calls
`os.getenv`/`load_dotenv` for these values any more. DATABASE_URL is the
sole DB contract — discrete DB_* variables are dead.

**[DECISION] PCA is visualisation-only (P0-7).** EDA 07 confirmed the PCA
projection passed into clustering was never used; detection is BSI/NDVI
thresholds plus connected components. The dead parameter is removed:
`group_pixels_for_candidate_sites(mask, original_shape, bsi_array,
ndvi_array, ...)`. main.py computes PCA solely for the false-colour map
and the report's variance summary. Any future spectral model enters via
the classifier workstream (Notebook 07/08 architecture decision), not by
resurrecting this parameter.

**[DECISION] Copernicus auth is a refreshable bundle (P0-10).**
`authenticate()` returns `{access_token, refresh_token, expires_at}`;
`ensure_fresh()` refreshes via the refresh-token grant (password fallback)
inside a 60s expiry margin. `download_safe` accepts the bundle, refreshes
before every attempt and treats a mid-stream 401 as forced-refresh-and-
retry, so 600MB+ SAFE downloads survive the ~10-minute token lifetime.
A bare token string is still accepted for back-compatibility (no refresh).

**[DECISION] search_products uses the shared connection (P0-8).** The
pipeline's single `get_db_connection()` connection is passed in; the
module no longer opens (or closes) its own, honouring the one-connection
design and removing the api->database import.

**[CHANGE] Register year is dynamic (P0-9).** `detect_register_changes`
derives the register vintage as `MAX(year)` for the GSS code — the
hardcoded 2026 is gone, matching the behaviour already used by
`match_candidate_to_register`.

**[CHANGE] Dependencies split and pinned (P0-4).** `requirements.txt` is
runtime-only (including the previously undeclared `pyproj` and the new
`pydantic-settings`); dev/notebook tooling moved to `requirements-dev.txt`;
CI installs `requirements-ci.txt`.

**[CHANGE] Containerised local stack (P0-5).** `Dockerfile` (python:3.11-slim;
rasterio/pyproj wheels bundle GDAL/PROJ), `docker-compose.yml` (PostGIS
16-3.5 with `migrations/` auto-applied on first init) and a `Makefile`
with `db` / `run` / `test` / `psql` targets.

**[CHANGE] Evaluation report artifact (P1-2).**
`python -m src.evaluation --gss_code E06000021 --report` writes
`metrics_<gss>_<ts>.json` (register recall/precision/F1, labelled
precision when a labels CSV is supplied, caveats embedded) and a PR-curve
PNG ranking candidates by mean BSI against register-match labels. The
mean-BSI curve is the recorded baseline to beat — EDA 07 predicts it is
near-flat.
"""

README_ADDENDUM = """

## Docker quickstart (P0-5)

```bash
docker compose up -d db        # PostGIS 16-3.5, migrations auto-applied on first init
docker compose run pipeline python -m src.main --gss_code E06000021 --date 2026-05-25
```

`docker compose down -v` resets the database (drops the volume, so
migrations re-run on next start). Credentials come from `.env` — see
`.env.example`; they are never baked into the image.

## Dependency layout (P0-4)

- `requirements.txt` — runtime only (install for running the pipeline)
- `requirements-dev.txt` — dev environment: pytest, pre-commit, Jupyter,
  scikit-learn (installs runtime via `-r`)
- `requirements-ci.txt` — what CI installs

## Evaluation metrics report (P1-2)

```bash
python -m src.evaluation --gss_code E06000021 --report
python -m src.evaluation --gss_code E06000021 --report --labels labels.csv
```

Writes `outputs/metrics_<gss>_<timestamp>.json` and a PR-curve PNG. The
JSON embeds the caveats that make the numbers honest: register precision
is a floor (unregistered finds are the product, not false positives), and
register recall carries the vegetated-brownfield definitional ceiling.
"""

for path, addendum, marker in (
    ("DESIGN.md", DESIGN_ADDENDUM, "P0 batch — 22 July 2026"),
    ("README.md", README_ADDENDUM, "Docker quickstart (P0-5)"),
):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if marker in text:
        print(f"{path}: addendum already present — skipped")
        continue
    p.write_text(text.rstrip() + "\n" + addendum, encoding="utf-8")
    print(f"{path}: addendum appended")

print("Docs updated.")
