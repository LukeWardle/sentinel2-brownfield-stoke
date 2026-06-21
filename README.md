# sentinel2-brownfield-stoke

Satellite spectral analysis pipeline for brownfield site detection in Stoke-on-Trent.
Built for Stoke City Council planning officials to identify candidate unregistered brownfield sites using free Sentinel-2 satellite imagery.

---

## The Problem

Stoke-on-Trent has one of the highest concentrations of brownfield land in England — a legacy of the pottery, mining and steelworks industries. The council's published brownfield register is incomplete. Manual site surveys are expensive and slow. This tool uses satellite spectral analysis to identify candidate sites that may not yet appear on the register, giving planning officers a faster way to find land suitable for housing development.

---

## What This Tool Does

- Loads Sentinel-2 L2A satellite imagery covering Stoke-on-Trent
- Runs PCA spectral decomposition across 10 spectral bands
- Produces a false colour map highlighting candidate brownfield sites
- Generates a plain English results report for planning officials

---

## Results

Running the pipeline on the Sentinel-2 image captured 2026-05-25 (during a UK heatwave with near-zero cloud cover) produced the following:

![False colour map of Stoke-on-Trent](docs/images/false_colour_map.png)

**PCA Variance Breakdown:**

| Component | Variance Explained | Interpretation |
|---|---|---|
| PC1 | 82.08% | Overall brightness — dominant pattern |
| PC2 | 13.73% | Vegetation vs non-vegetation contrast |
| PC3 | 1.80% | Subtle spectral differences — likely brownfield signal |

Only 2 components were needed to reach the 95% variance threshold, meaning the 10 spectral bands are highly correlated across this landscape. The false colour map always renders the top 3 components regardless of k, so PC3 — where the brownfield signal most likely resides — is visible but subtle, sitting beneath the much stronger brightness and vegetation patterns.

This is an important finding, not a limitation to hide: it confirms that unsupervised PCA alone gives only a partial view of brownfield land in Stoke-on-Trent, and is the direct justification for Version 2's Bare Soil Index pre-filtering — isolating bare soil pixels before running PCA, so the dominant spectral pattern becomes brownfield-relevant rather than brightness-driven.

This is a candidate identification tool. All outputs require physical verification before any planning decision is made.

---

## Project Status

Version 1 — Complete

| Version | Status | Description |
|---|---|---|
| v1 | ✅ Complete | PCA spectral analysis pipeline — candidate site identification |
| v2 | 🔄 Planned | Bare Soil Index preprocessing, brownfield register validation, change detection |
| v3 | Planned | Supervised classification, Streamlit web interface, contamination filtering |
| v4 | Planned | Multi-city expansion |

---

## Data Sources

| Dataset | Source | Licence |
|---|---|---|
| Sentinel-2 L2A satellite imagery | Copernicus Data Space Ecosystem | Free — Copernicus licence |
| Stoke-on-Trent Brownfield Register 2019-2024 | data.gov.uk | Open Government Licence |
| Contaminated Land Special Sites | Environment Agency | Environment Agency copyright |
| UK Local Authority Boundaries | ONS Open Geography Portal | Open Government Licence |

See [raw_data/README.md](raw_data/README.md) for download instructions.

---

## Setup

```bash
# Clone the repository
git clone https://github.com/LukeWardle/sentinel2-brownfield-stoke.git
cd sentinel2-brownfield-stoke

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Download satellite data
# Follow instructions in raw_data/README.md
```

---

## Running the Pipeline

Once dependencies are installed and the SAFE folder is downloaded:

```bash
python src/main.py
```

This runs the full pipeline end to end and saves two timestamped files to outputs/:

- `false_colour_map_YYYYMMDD_HHMMSS.png` — the PCA false colour map
- `results_report_YYYYMMDD_HHMMSS.md` — plain English summary of variance explained per component

To run the pipeline on a different SAFE folder or save to a different location, edit the `SAFE_PATH` and `OUTPUT_DIR` variables at the bottom of `src/main.py`.

---

## Documentation

| Document | Description |
|---|---|
| [EDA.md](EDA.md) | Exploratory data analysis — band inventory, pixel statistics, data quality |
| [DESIGN.md](DESIGN.md) | System design — architecture, functions, risks, success criteria |
| [data/README.md](data/README.md) | Reference dataset documentation |
| [raw_data/README.md](raw_data/README.md) | Satellite data download instructions |

---

## Licence

MIT