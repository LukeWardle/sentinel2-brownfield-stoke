# Brownfield Register EDA — Stoke-on-Trent 2024

This notebook investigates the structure, columns and data quality of brownfield_register_2024.csv, in preparation for Version 2's register validation feature — cross-referencing PCA candidate pixels from the satellite pipeline against known registered brownfield sites.

## Objectives
- Confirm the file loads correctly and check its size (rows, columns).
- Identify whether the register contains coordinates for each site, and in what format.
- Check the coordinate format is compatible with — or convertible to — the satellite image's coordinate system (EPSG:32630, confirmed in 01_data_inspection.ipynb).
- Identify any data quality issues (missing values, duplicates, inconsistent formatting).


```python
import os
from pathlib import Path

import pandas as pd
from pyproj import Transformer
```

## File Structure Investigation


```python
PROJECT_ROOT = Path(__file__).parent.parent if '__file__'in dir() else Path(os.getcwd()).parent
csv_path = str(PROJECT_ROOT / "data" / "brownfield_register_2024.csv")
print(csv_path)

df = pd.read_excel(csv_path)
print(df.shape)
print(df.columns)
```

    C:\Users\lward\workspace\sentinel2-brownfield-stoke\data\brownfield_register_2024.csv
    (218, 20)
    Index(['OrganisationURI', 'SiteReference', 'SiteNameAddress', 'SiteplanURL',
           'GeoY', 'GeoX', 'Hectares', 'OwnershipStatus', 'PlanningStatus',
           'PermissionType', 'PermissionDate', 'PlanningHistory', 'Deliverable',
           'NetDwellingsRangeFrom', 'NewDwellingsRangeTo', 'HazardousSubstances',
           'Notes', 'FirstAddedDate', 'LastUpdatedDate', 'EndDate'],
          dtype='str')
    

## Finding - File Structure
File type is a .xlsx despite the .csv extension. This was confirmed via raw byte inspection. The data contains 218 registered brownfield sites with 20 columns of data characteristics, including coordinate columns 'GeoX' and 'GeoY'.


```python
print(df[['SiteReference', 'GeoX', 'GeoY']].head())
```

       SiteReference       GeoX       GeoY
    0          64519  388309.18  344107.34
    1          63067  392955.67  343560.26
    2          62728  391321.18  342545.40
    3          63168  389547.02  341008.78
    4          63095  388914.14  344819.72
    

## Finding - Coordinate Reference System (Inferred)

According to gov.uk, the specific data standard for GeoX and GeoY should be WGS84 or ETRS89. These are degree-based latitude and longitude systems, where values typically fall in the range -180 to 180. However, the values in this dataset (e.g. GeoX = 388309.18, GeoY = 344107.34) are far larger than that range, suggesting they are not in degrees at all.

This value range is consistent with the British National Grid (EPSG:27700), a metres-based coordinate system used widely across England — but it is a **different** coordinate system from the Sentinel-2 satellite image's UTM Zone 30N (EPSG:32630), which uses a different numeric range entirely (eastings roughly 499,980 to 609,780).

No "Coordinate Reference System" column is present in this file to confirm which system was actually used, so this conclusion is inferred from the numeric range rather than confirmed by metadata. This uncertainty should be flagged as a Version 2 risk — if the assumption proves incorrect, any coordinate transformation built on it would place sites in the wrong location.



```python
transformer = Transformer.from_crs("EPSG:27700", "EPSG:32630")
demo = transformer.transform(388309.18, 344107.34)
print(demo)
```

    (555331.1865177682, 5871939.229711984)
    

## Finding — Coordinate System Confirmation Test
Tested the hypothesis that the Brownfield register data is using the British National Grid (EPSG:27700) data standard. Using one real site coordinates (SiteReference 64519, GeoX=388309.18, GeoY=344107.34) coverted to EPSG:32630 used by the Sentinel-2 images. Using pyproj.Transformer to convert 27700 -> EPSG:32630 with the result output (555331.19, 5871939.23).

The converted coordinates falls within the Sentinel-2 UTM tile bounds (easting 499980 - 609780, northing 5790240 - 5900040) 
which was confirmed in 01_data_inspection.ipynb. The result supports, but does not definitively prove, that the Brownfield Register coordinates is in British National Grid standard.


```python
converted_sites = []
for idx, row in df.iterrows():
    converted_sites.append(transformer.transform(row['GeoX'], row['GeoY']))
    
utm_x, utm_y = zip(*converted_sites)
df['UTM_X'] = utm_x
df['UTM_Y'] = utm_y
print(df[['SiteReference', 'GeoX', 'GeoY', 'UTM_X', 'UTM_Y']].head())

    
    
```

       SiteReference       GeoX       GeoY          UTM_X         UTM_Y
    0          64519  388309.18  344107.34  555331.186518  5.871939e+06
    1          63067  392955.67  343560.26  559984.898997  5.871457e+06
    2          62728  391321.18  342545.40  558364.694036  5.870419e+06
    3          63168  389547.02  341008.78  556612.105629  5.868858e+06
    4          63095  388914.14  344819.72  555926.159883  5.872660e+06
    

## Finding — Full Dataset Coordinate Conversion

Converted 218 sites from the Brownfield Register from EPSG:27700 to match the Sentinel-2 UTM EPSG:32630. The Brownfield Register has been updated with two new columns (UTM_X and UTM_Y) which stored the converted values. This allows Version 2 to plot registered sites directly against satellite pixel coordinates.


```python
threshold = (df['UTM_X'] > 499980) & (df['UTM_X'] < 609780) & (df['UTM_Y'] > 5790240) & (df['UTM_Y'] < 5900040)
print(threshold.sum())

print(df[threshold == False])
```

    217
                                           OrganisationURI  SiteReference  \
    214  http://opendatacommunities.org/id/unitary-auth...          68349   
    
                                           SiteNameAddress  \
    214  Land at Old Hall Street, Charles Street, Birch...   
    
                                               SiteplanURL      GeoY      GeoX  \
    214  https://webmaplayers.stoke.gov.uk/webmaplayers...  388338.0  347655.0   
    
         Hectares  OwnershipStatus PlanningStatus                PermissionType  \
    214      2.76  mixed ownership  permissioned   outline planning permission    
    
         ... Deliverable  NetDwellingsRangeFrom NewDwellingsRangeTo  \
    214  ...         Yes                    292                 292   
    
         HazardousSubstances  Notes  FirstAddedDate LastUpdatedDate EndDate  \
    214                  NaN    NaN      2024-04-01      2024-04-01     NaT   
    
               UTM_X         UTM_Y  
    214  514063.8853  5.915596e+06  
    
    [1 rows x 22 columns]
    

## Finding — Coordinate Outlier (Likely Source Data Error)

Checked to see if all 218 sites sit within the Sentinel-2 tile boundary (easting 499980 - 609780, northing 5790240 - 5900040).
Only 1 site fell outside these parameters (SiteReference: 68349, Old Hall Street, Charles Street), the discrepancy UTM_Y = 5915596 which is roughly 15.5km north of the boundary tile limit. A google lookup at the location shows it is located in Hanley well within the boundary area. 

Due to only one site not falling within the boundary, and a manual check confirming the site is actually within the boundary this would point to a likely data entry error rather than a flaw in the coordinate conversion.

This should be flagged as a Version 2 risk — converted coordinates should always be sanity-checked against expected tile bounds, since the source register itself may contain data entry errors that a coordinate transformation alone cannot catch.


```python
df.isnull().sum()
```




    OrganisationURI            0
    SiteReference              0
    SiteNameAddress            0
    SiteplanURL                0
    GeoY                       0
    GeoX                       0
    Hectares                   0
    OwnershipStatus            0
    PlanningStatus             0
    PermissionType            79
    PermissionDate            80
    PlanningHistory          218
    Deliverable               70
    NetDwellingsRangeFrom      0
    NewDwellingsRangeTo        0
    HazardousSubstances      218
    Notes                     66
    FirstAddedDate             0
    LastUpdatedDate            0
    EndDate                  152
    UTM_X                      0
    UTM_Y                      0
    dtype: int64



## Finding — Missing Value Check

Checked all 218 rows and 20 columns for missing values using df.isnull().sum(). Two columns are entirely empty across all 218 sites — PlanningHistory and HazardousSubstances. These columns contain no usable information for Version 2 and can be excluded from any register validation logic.

EndDate is missing for 152 of 218 sites (70%). Checking the gov.uk data standard confirms this is expected rather than a data quality error — EndDate is only populated once a site has been developed and is no longer classified as brownfield. A missing EndDate simply means the site is still active brownfield land.

PermissionType (79 missing), PermissionDate (80 missing), Deliverable (70 missing) and Notes (66 missing) all show partial gaps, likely reflecting sites at earlier stages of the planning process where this information genuinely does not yet exist, consistent with the same pattern seen in EndDate. No further action is needed on these gaps for Version 2, as they reflect the natural lifecycle of a brownfield site rather than corrupted or incomplete data entry.


```python

```
