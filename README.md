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

This is a candidate identification tool. All outputs require physical verification before any planning decision is made.

---

## Project Status

Version 1 — In development

| Version | Status | Description |
|---|---|---|
| v1 | 🔄 In development | PCA spectral analysis pipeline — candidate site identification |
| v2 | Planned | Bare Soil Index preprocessing, brownfield register validation, change detection |
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

## Project Structure

See [DESIGN.md](DESIGN.md) for full architecture and function-level documentation.

See [EDA.md](EDA.md) for exploratory data analysis of the Sentinel-2 imagery.

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