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