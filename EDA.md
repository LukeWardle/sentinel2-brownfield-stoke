# Exploratory Data Analysis
## Sentinel-2 Brownfield Detection — Stoke-on-Trent

## 1. Data Source
- **Source:** Copernicus Data Space Ecosystem
- **URL:** https://dataspace.copernicus.eu
- **Mission:** Sentinel-2C
- **Instrument:** MSI (Multispectral Instrument)
- **Product type:** L2A (atmospherically corrected, bottom of atmosphere reflectance)
- **Sensing date:** 2026-05-25
- **Sensing time:** 11:06:21 UTC
- **Tile:** T30UWD
- **Cloud cover:** 10%
- **Product size:** 900MB
- **Filename:** S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE

## 2. Band Inventory
| File | Band | Wavelength | Resolution | What it Measures | Relevance to Project |
|---|---|---|---|---|---|
| B01 | Aerosol | 443nm | 20m | For aerosol detection | Not selected — measures atmospheric aerosol not land surface |
| B01 | Aerosol | 443nm | 60m | For aerosol detection | Not selected — measures atmospheric aerosol not land surface |
| B02 | Blue | 490nm | 10m | Soil and vegetation discrimination | Urban fabric identification | Selected — urban fabric and soil discrimination |
| B02 | Blue | 490nm | 20m | Soil and vegetation discrimination | Urban fabric identification | Selected — urban fabric and soil discrimination |
| B02 | Blue | 490nm | 60m | Soil and vegetation discrimination | Urban fabric identification | Selected — urban fabric and soil discrimination |
| B03 | Green | 560nm | 10m | Contrast between clear and turbid water | Not selected — water contrast not relevant to brownfield detection |
| B03 | Green | 560nm | 20m | Contrast between clear and turbid water | Not selected — water contrast not relevant to brownfield detection |
| B03 | Green | 560nm | 60m | Contrast between clear and turbid water | Not selected — water contrast not relevant to brownfield detection |
| B04 | Red | 665nm | 10m | Identifying landscape types| Selected — identifies urban areas and bare soil |
| B04 | Red | 665nm | 20m | Identifying landscape types| Selected — identifies urban areas and bare soil |
| B04 | Red | 665nm | 60m | Identifying landscape types| Selected — identifies urban areas and bare soil |
| B05 | Red edge | 705nm | 20m | Classifying vegetation | Selected — vegetation classification |
| B05 | Red edge | 705nm | 60m | Classifying vegetation | Selected — vegetation classification |
| B06 | No standard colour name | 740nm | 20m | Classifying vegetation | Selected — vegetation classification |
| B06 | No standard colour name | 740nm | 60m | Classifying vegetation | Selected — vegetation classification |
| B07 | No standard colour name | 783nm | 20m | Classifying vegetation | Selected — vegetation classification |
| B07 | No standard colour name | 783nm | 60m | Classifying vegetation | Selected — vegetation classification |
| B08 | NIR | 842nm | 10m | Biomass content, detecting and analysing vegetation | Selected — vegetation detection, separates green space from brownfield |
| B8A | No standard colour name | 865nm | 20m | Classifying vegetation | Selected — vegetation classification |
| B8A | No standard colour name | 865nm | 60m | Classifying vegetation | Selected — vegetation classification |
| B09 | No standard colour name | 945nm | 60m | Detecting water vapour | Not selected — water vapour, atmospheric measurement only |
| B11 | SWIR 1 | 1610nm | 20m | Measures the moisture content of soil and vegetation | Selected — soil moisture, key brownfield indicator |
| B11 | SWIR 1 | 1610nm | 60m | Measures the moisture content of soil and vegetation | Selected — soil moisture, key brownfield indicator |
| B12 | SWIR 2 | 2190nm | 20m | Measures the moisture content of soil and vegetation | Selected — soil moisture, key brownfield indicator |
| B12 | SWIR 2 | 2190nm | 60m | Measures the moisture content of soil and vegetation | Selected — soil moisture, key brownfield indicator |

## 3. Derived Products
| File | Resolution | What it is | Potential Use |
|---|---|---|---|
| AOT_10m | 10m | Aerosol Optical Thickness Map | Atmospheric quality check |
| AOT_20m | 20m | Aerosol Optical Thickness Map | Atmospheric quality check |
| AOT_60m | 60m | Aerosol Optical Thickness Map | Atmospheric quality check |
| SCL_20m | 20m | Scene Classification Map | Quality control - validate cloud pixels, validate PCA results |
| SCL_60m | 60m | Scene Classification Map | Quality control - validate cloud pixels, validate PCA results |
| TCI_10m | 10m | True Colour Image - Full resolution version | Visual reference |
| TCI_20m | 20m | True Colour Image - lower resolution version | Visual reference |
| TCI_60m | 60m | True Colour Image - lower resolution version | Visual reference |
| WVP_10m | 10m | Water Vapour Map | Atmospheric quality check |
| WVP_20m | 20m | Water Vapour Map | Atmospheric quality check |
| WVP_60m | 60m | Water Vapour Map | Atmospheric quality check | 

## 4. Image Dimensions and Pixel Statistics
- All R10m files: 10,980 x 10,980 pixels at 10m resolution
- All R20m files: 5,490 x 5,490 pixels at 20m resolution  
- All R60m files: 1,830 x 1,830 pixels at 60m resolution
- Coordinate system: EPSG:32630 (UTM Zone 30N)
- Data type: uint16 for spectral bands, uint8 for TCI and SCL

## 5. Pixel Statistics
- Spectral bands range 0 to ~20,000 at 10m, ~20,000 at 20m, ~9,300 at 60m
- Lower max values at 60m due to spatial averaging
- All bands have min value 0 — nodata pixels present outside tile boundary
- B08/B8A NIR bands have significantly higher mean (~3,500) than visible bands (~1,000-1,250)

## 6. Data Quality
- Cloud cover: less than 0.01% of valid pixels — excellent quality image
- Nodata pixels: 29.58% of tile outside valid boundary
- SCL classes present: vegetation (60.82%), bare soil (9.31%), water (0.17%)

## 7. Key Design Decisions
- Bands selected: B02, B03, B04, B05, B06, B07, B08, B8A, B11, B12
- Resolution: 20m — 10m bands will be downsampled
- Nodata pixels must be masked before PCA
- Brownfield signal confirmed — 2.8 million bare soil pixels present