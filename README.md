# Sentinel-2 Brownfield Site Detection
### Stoke-on-Trent Planning Intelligence Tool

A satellite-based system for identifying potential brownfield land in Stoke-on-Trent using free Sentinel-2 imagery from the Copernicus Data Space Ecosystem. The system automatically downloads satellite images, applies spectral analysis and machine learning to identify candidate brownfield sites, cross-references them against the council's brownfield register, and produces an interactive map for planning officials.

No commercial tool currently identifies *unregistered* brownfield land from satellite imagery. This system fills that gap.

---

## What It Does

1. **Downloads satellite imagery automatically** — authenticates with the Copernicus API and downloads Sentinel-2 L2A SAFE files for any UK council by GSS code and date
2. **Computes spectral indices** — calculates Bare Soil Index (BSI) and Normalised Difference Vegetation Index (NDVI) across all valid pixels after normalising raw digital numbers to surface reflectance
3. **Applies PCA spectral decomposition** — reduces 10 spectral bands to the most significant components, capturing 95%+ of spectral variance
4. **Clusters candidate sites** — groups spectrally similar neighbouring pixels into discrete candidate brownfield sites using connected-component analysis
5. **Cross-references the brownfield register** — compares candidate sites against Stoke-on-Trent's annual brownfield register stored in PostgreSQL, identifying matched and unregistered sites
6. **Produces an interactive map** — overlays candidate sites onto OpenStreetMap using Folium, with green markers for register-matched sites and red markers for potential unregistered brownfield
7. **Stores results in a database** — candidate sites and pipeline run metadata are stored in PostgreSQL for historical comparison and change detection

---

## Results

### Version 1 — PCA Spectral Analysis (Complete)

Running the Version 1 pipeline on the May 2026 Stoke-on-Trent image:
- **21,223,650** valid pixels after SCL masking
- **PC1** — 82.08% variance (brightness)
- **PC2** — 13.73% variance (vegetation contrast)
- **PC3** — 1.80% variance (likely brownfield signal)
- **k=2** components retained at 95% variance threshold

![False Colour Map](docs/images/false_colour_map.png)

### Version 2 — BSI/NDVI Calibration Finding

BSI and NDVI were computed across all valid pixels and extracted at the 217 valid brownfield register site locations. A critical finding emerged:

- **BSI at register sites:** range -0.26 to 0.17, mean 0.005
- **NDVI at register sites:** range 0.02 to 0.64, mean 0.21

Registered brownfield sites do not exhibit simple spectral threshold signatures — they are predominantly vegetated at the time of the May 2026 image. This confirmed that multi-band PCA is the correct primary detection approach rather than index-based thresholding. BSI and NDVI are retained as additional spectral features rather than standalone detectors.

---

## Project Status

| Version | Status | Description |
|---|---|---|
| v1 | ✅ Complete | PCA spectral analysis, false colour map, results report |
| v2 | 🔄 In Progress | Database, Copernicus API, BSI/NDVI, clustering, interactive map |
| v3 | Planned | Streamlit web interface, supervised Random Forest classifier, Supabase migration |
| v4 | Planned | UK-wide multi-council expansion, automated scheduling |

---

## Competitive Context

This system addresses a gap not covered by any existing commercial tool. Nimbus Maps, LandTech/LandInsight and SearchLand all overlay the existing brownfield register on a map — they show what is already known. This system identifies brownfield land that does not appear on any register, using satellite spectral analysis validated by the Alan Turing Institute's DemoLand research project.

---

## Data Sources

| Dataset | Source | Notes |
|---|---|---|
| Sentinel-2 L2A imagery | Copernicus Data Space Ecosystem | Free, downloaded automatically via API |
| Brownfield register | DLUHC / data.gov.uk | Annual publication, 218 sites for Stoke-on-Trent |
| UK council boundaries | ONS Open Geography Portal | 361 local authorities, stored in PostgreSQL |

---

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16 with PostGIS 3.5 (install via Chocolatey on Windows: `choco install postgresql16`)
- A Copernicus Data Space Ecosystem account (free at https://dataspace.copernicus.eu)

### Installation

```bash
git clone https://github.com/LukeWardle/sentinel2-brownfield-stoke
cd sentinel2-brownfield-stoke
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root (never commit this file):

COPERNICUS_USERNAME=your_email@example.com

COPERNICUS_PASSWORD=yourpassword

DB_NAME=sentinel2_brownfield

DB_HOST=127.0.0.1

DB_PORT=5432

DB_USER=postgres

DB_PASSWORD=yourpassword

### Database Setup

Create the database and enable PostGIS:

```sql
CREATE DATABASE sentinel2_brownfield;
\c sentinel2_brownfield
CREATE EXTENSION postgis;
```

Load reference data (one-time setup):

```bash
python scripts/setup_boundaries.py
python scripts/setup_brownfield.py
```

---

## Running the Pipeline

```bash
python src/main.py
```

The pipeline accepts a GSS code and date as inputs, downloads the relevant Sentinel-2 image automatically, and produces outputs in the `outputs/` folder.

---

## Outputs

Each pipeline run produces three timestamped files in `outputs/`:

- `false_colour_map_YYYYMMDD_HHMMSS.png` — PCA false colour map
- `results_report_YYYYMMDD_HHMMSS.md` — Plain English results report
- `interactive_map_GSSODE_YYYYMMDD_HHMMSS.html` — Interactive Folium map of candidate sites

---

## Running Tests

```bash
python -m pytest tests/ -v
```

139 tests passing across 12 modules.

---

## Documentation

- [DESIGN.md](DESIGN.md) — Full architecture, module design and Version 2 roadmap
- [DATABASE.md](DATABASE.md) — PostgreSQL/PostGIS schema design and migration path
- [EDA.md](EDA.md) — Exploratory data analysis findings
- [data/README.md](data/README.md) — Data source download instructions

---

## Licence

MIT Licence — see LICENSE file for details.