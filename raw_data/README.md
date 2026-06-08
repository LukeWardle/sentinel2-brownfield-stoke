# Raw Data

## Data Source
Sentinel-2 L2A imagery downloaded from the Copernicus Data Space Ecosystem.

**URL:** https://dataspace.copernicus.eu

## How to Download

### 1. Register
Create a free account at https://dataspace.copernicus.eu

### 2. Open Copernicus Browser
Click Browser after logging in.

### 3. Define Area of Interest
Search for Stoke-on-Trent in the search box. Draw a bounding box over the 
Five Towns urban area — Tunstall, Burslem, Hanley, Fenton, Longton. 
Approximately 154 km².

### 4. Set Filters
- Data source: Sentinel-2 L2A
- Cloud cover: maximum 10%

### 5. Select Image
- Date: 2026-05-25
- Product: S2C_MSIL2A_20260525T110621_N0512_R137_T30UWD_20260525T144513.SAFE
- This date was chosen as it falls during the May 2026 UK heatwave — 
  minimal cloud cover over the Midlands

### 6. Download and Extract
Download the product as a zip file. Extract using 7-Zip — 
Windows has a 260 character path limit that prevents standard extraction.

**Important:** After extraction the SAFE folder will be nested inside 
itself. The actual data is in the inner SAFE folder:
raw_data/S2C_MSIL2A_...SAFE/S2C_MSIL2A_...SAFE/

### 7. File Location
Place the extracted SAFE folder inside the raw_data/ directory.
The raw_data/ folder is excluded from GitHub — you must download the data yourself.

## Band Files

### R20m — Native 20m resolution
| File | Band | Wavelength | What it Measures |
|---|---|---|---|
| B05_20m.jp2 | Band 5 — Red edge | 705nm | Classifying vegetation |
| B06_20m.jp2 | Band 6 — Red edge | 740nm | Classifying vegetation |
| B07_20m.jp2 | Band 7 — Red edge | 783nm | Classifying vegetation |
| B8A_20m.jp2 | Band 8A | 865nm | Classifying vegetation |
| B11_20m.jp2 | Band 11 — SWIR 1 | 1610nm | Soil moisture — key brownfield indicator |
| B12_20m.jp2 | Band 12 — SWIR 2 | 2190nm | Soil moisture — key brownfield indicator |

### R10m — Native 10m resolution (downsampled to 20m in pipeline)
| File | Band | Wavelength | What it Measures |
|---|---|---|---|
| B02_10m.jp2 | Band 2 — Blue | 490nm | Soil and vegetation discrimination |
| B03_10m.jp2 | Band 3 — Green | 560nm | Vegetation contrast |
| B04_10m.jp2 | Band 4 — Red | 665nm | Identifying landscape types |
| B08_10m.jp2 | Band 8 — NIR | 842nm | Vegetation detection |

## Scene Classification Layer (SCL)

The SCL_20m.jp2 file classifies every pixel in the image. Used by mask_nodata() to remove invalid pixels before analysis.

| Value | Class |
|---|---|
| 0 | No data — outside tile boundary |
| 1 | Saturated or defective |
| 2 | Dark area pixels |
| 3 | Cloud shadow |
| 4 | Vegetation |
| 5 | Bare soil — primary brownfield indicator |
| 6 | Water |
| 7 | Unclassified |
| 8 | Cloud medium probability |
| 9 | Cloud high probability |
| 10 | Thin cirrus |
| 11 | Snow or ice |