# Data Directory

This folder contains reference datasets used for validation and future versions of the pipeline.
All datasets are committed to GitHub as they are small enough to version control.

## Files

### Brownfield Land Register — Stoke-on-Trent
Source: data.gov.uk — Stoke-on-Trent City Council
URL: https://www.data.gov.uk/dataset/1368fc6f-3975-4bf1-b234-1f5d6055b7dd/stoke-on-trent-brownfield-register
Licence: Open Government Licence

| File | Year | Format | Purpose |
|---|---|---|---|
| brownfield_register_2024.csv | 2024 | CSV | Primary validation dataset — cross-reference PCA candidate sites against current register |
| brownfield_register_2023.csv | 2023 | CSV | Historical comparison — identify sites added or removed between years |
| brownfield_register_2022.xlsx | 2022 | XLSX | Historical comparison — note different format, requires pandas.read_excel() |
| brownfield_register_2021.csv | 2021 | CSV | Historical comparison |
| brownfield_register_2020.csv | 2020 | CSV | Temporal analysis baseline — sites active at time of earliest Sentinel-2 imagery |
| brownfield_register_2019.csv | 2019 | CSV | Temporal analysis baseline |

### Contaminated Land Register — Stoke-on-Trent
Source: Stoke-on-Trent City Council
URL: https://www.stoke.gov.uk/downloads/download/626/
Licence: Open Government Licence

| File | Format | Purpose |
|---|---|---|
| contaminated_land_register.pdf | PDF | Reference only — not machine readable. Cross-reference candidate sites to identify known contaminated land. Manual inspection required. |

### Contaminated Land Special Sites — England
Source: Environment Agency
URL: https://www.data.gov.uk/dataset/e3770885-fc05-4813-9e60-42b03ec411cf/contaminated-land-special-sites
Licence: Environment Agency copyright and database right 2016

| File | Format | Purpose |
|---|---|---|
| contaminated_land_special_sites.csv | CSV | National register of special contaminated sites — filter by Stoke-on-Trent for Version 2 contamination filtering |

### UK Local Authority Boundaries
Source: ONS Open Geography Portal
URL: https://geoportal.statistics.gov.uk/datasets/ons::local-authority-districts-may-2024-boundaries-uk-bfe-2/about
Licence: Open Government Licence

| File | Format | Purpose |
|---|---|---|
| uk_local_authority_boundaries.geojson | GeoJSON | Full UK local authority boundaries — filter on GSS code E06000021 to extract Stoke-on-Trent boundary for Version 2 AOI clipping |

## Notes

- brownfield_register_2022.xlsx is in XLSX format unlike the other years which are CSV — use pandas.read_excel() not pandas.read_csv() when loading
- contaminated_land_register.pdf is not machine readable — data must be extracted manually or the Environment Agency special sites CSV used as an alternative
- uk_local_authority_boundaries.geojson covers the whole UK — filter on property LAD24CD == E06000021 to extract Stoke-on-Trent only