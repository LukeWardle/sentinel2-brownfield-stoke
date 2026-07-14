# Sentinel-2 Brownfield Site Detection — Database Design
Version 2.0 | Stoke-on-Trent Planning Intelligence Tool

## 1. Database Technology Decision

The program uses a database system. This was chosen as it solves a number of issues that a file-based system would have had originally. Firstly, the program would have experienced longer loading times if it had needed to perform all the conversions required for the mapping process every time it started. A database can instead store all of the processed mapping information once the initial conversion has been completed, significantly reducing loading times.

SQLite was first considered because of its simplicity. However, while SQLite can support spatial data through the SpatiaLite extension, it does not provide the same level of geospatial functionality or integration as PostGIS. PostgreSQL, when used with the PostGIS extension, is the industry standard for geospatial databases and provides native support for geographic data types and spatial operations such as point-in-polygon queries. This also removes the need for many of the geometry conversions previously performed using Shapely and provides a more scalable solution for the web interface introduced in Version 3.

The database was introduced in Version 2 so that council boundaries and the current Stoke-on-Trent brownfield data could be stored centrally. PostgreSQL 16 and PostGIS 3.5 were installed locally using Chocolatey, with a development database named sentinel2_brownfield. This provides a single location for storing all spatial datasets and allows additional data sources to be integrated more easily in future versions of the application.

## 2. Local Development Setup

The local development database is named sentinel2_brownfield. PostgreSQL is hosted locally using the default address of 127.0.0.1 on port 5432. The default PostgreSQL user account, postgres, is used to connect to the database during development.

A development password is configured for the local installation. This password is only intended for development purposes and should never be committed to Git or included within the source code. Instead, database credentials should be stored using environment variables or a .env configuration file that is excluded from version control via .gitignore.

The database can be accessed through the PostgreSQL command line tool using the following command:

psql -h 127.0.0.1 -p 5432 -U postgres -d sentinel2_brownfield

When the project is migrated to a hosted environment in Version 3, the database credentials, host address and connection details will differ from the local development configuration. These values will be provided by the hosting provider and configured separately for the production environment.

## 3. Table Structure

### 3.1 council_boundaries

Stores the boundary polygon for every UK local authority. Populated once by scripts/setup_boundaries.py using the UK Local Authority Boundaries GeoJSON file. All other tables reference this table via gss_code as a foreign key, ensuring every dataset is linked to a specific council area. Supports both Polygon and MultiPolygon geometry types to handle councils with detached areas or islands.

```sql
CREATE TABLE council_boundaries (
    gss_code VARCHAR(9) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    boundary GEOMETRY(GEOMETRY, 4326)
);
```

### 3.2 brownfield_sites

Stores all available years of the brownfield register for any UK council. Populated annually by scripts/setup_brownfield.py for manual register files, or scripts/download_brownfield_registers.py for automated download from planning.data.gov.uk (85% UK council coverage). Coordinates are stored in both their original BNG form (via UTM conversion) and as a PostGIS POINT geometry for spatial queries. The year column allows change detection queries across annual registers without requiring separate tables. The start_date and end_date columns are sourced from planning.data.gov.uk and drive detect_register_changes across register years. A unique constraint on (site_reference, gss_code, year) prevents duplicate entries when running setup or download scripts multiple times. A GIST spatial index on the location column accelerates the ST_DWithin proximity query used by match_candidate_to_register during pipeline runs.

```sql
CREATE TABLE brownfield_sites (
    id SERIAL PRIMARY KEY,
    site_reference VARCHAR(50),
    gss_code VARCHAR(9) REFERENCES council_boundaries(gss_code),
    year INTEGER NOT NULL,
    name_address TEXT,
    utm_x DOUBLE PRECISION,
    utm_y DOUBLE PRECISION,
    hectares DOUBLE PRECISION,
    planning_status VARCHAR(100),
    location GEOMETRY(POINT, 32630),
    start_date DATE,
    end_date DATE,
    CONSTRAINT brownfield_sites_unique UNIQUE (site_reference, gss_code, year)
);

CREATE INDEX brownfield_sites_location_idx
    ON brownfield_sites USING GIST (location);
```

### 3.3 candidate_sites

Stores candidate brownfield sites identified by the clustering module during each pipeline run. Each row represents one candidate site identified from the satellite imagery. The matched_site_reference column links confirmed matches back to the brownfield register using 100m proximity matching, leaving unmatched sites as NULL for further investigation by planning officials.

```sql
CREATE TABLE candidate_sites (
    id SERIAL PRIMARY KEY,
    gss_code VARCHAR(9) REFERENCES council_boundaries(gss_code),
    image_date DATE NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    utm_x DOUBLE PRECISION,
    utm_y DOUBLE PRECISION,
    pixel_count INTEGER,
    bsi_value DOUBLE PRECISION,
    matched_site_reference VARCHAR(50)
);
```

### 3.4 pipeline_runs

Records metadata for every pipeline execution. Provides a history of all analyses performed, including which council was processed, which image was used, when the run occurred, and summary counts of candidate sites found and matched. Used by the Version 3 web interface to display run history to planning officials.

```sql
CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    gss_code VARCHAR(9) REFERENCES council_boundaries(gss_code),
    image_date DATE NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    status VARCHAR(20),
    candidate_sites_found INTEGER,
    matched_to_register INTEGER,
    unmatched INTEGER
);
```

### 3.5 council_models

Stores trained Random Forest classifier models for each council area. One row per council per training run, with the serialised model binary stored directly in the database as BYTEA to avoid filesystem dependencies when deployed to Supabase in Version 3. Accuracy, precision and recall metrics are stored alongside the model to track performance over time and across councils.

```sql
CREATE TABLE council_models (
    id SERIAL PRIMARY KEY,
    gss_code VARCHAR(9) REFERENCES council_boundaries(gss_code),
    trained_date DATE NOT NULL,
    training_sites INTEGER,
    accuracy DOUBLE PRECISION,
    precision_score DOUBLE PRECISION,
    recall_score DOUBLE PRECISION,
    image_date DATE,
    model_binary BYTEA
);
```

## 4. Table Relationships

The diagram below shows the relationships between the five tables. All four data tables (brownfield_sites, candidate_sites, pipeline_runs, council_models) reference council_boundaries via gss_code as a foreign key, ensuring all data is linked to a specific council area.

![Database ERD](docs/images/database_erd.png)

## 5. Version Roadmap

In Version 2, the database is the core component of the system and is now fully operational. PostgreSQL with PostGIS replaces the previous file-based workflow and provides a centralised structure for all spatial data. The database stores 361 UK council boundary datasets and brownfield register data for Stoke-on-Trent across six years (2019-2024, 1,308 sites) plus 352 sites from planning.data.gov.uk. The Version 2 pipeline runs end-to-end, detecting 218 candidate brownfield sites for Stoke-on-Trent from the May 2026 Sentinel-2 image, matching 39 to the register and identifying 179 potential unregistered sites. Candidate sites and pipeline run metadata are stored in the database after each run. Change detection across register years is implemented and driven by the start_date and end_date columns sourced from planning.data.gov.uk, reporting 66 removed and 119 added sites for Stoke 2019-2024.

In Version 3, the database is extended to support a full web-based application. An API layer is introduced between the database and the frontend, allowing spatial queries to be handled dynamically through PostGIS. Council boundary data becomes automatically downloaded and updated rather than manually imported. Where available, brownfield datasets are also automatically refreshed to ensure the system remains up to date. The council_models table is populated with trained Random Forest classifier models, with model binaries stored as BYTEA directly in the database to avoid filesystem dependencies in the hosted environment. At this stage, the system is migrated from a local PostgreSQL instance to a hosted production database on Supabase, improving scalability and allowing multi-user access.

In Version 4, the system is expanded beyond a single local authority. The database structure is updated to support multiple cities and council areas within the same system. Users are able to select different regions, with each dataset stored and managed centrally within the same PostgreSQL/PostGIS environment. The processing pipeline is extended to handle multiple council boundaries and imagery sources, allowing automated analysis across different geographic areas. This version moves the system from a single-city tool into a scalable national framework with a more flexible data model and improved performance through optimised spatial indexing.

## 6. Migration Path — Local to Hosted

The current system runs on a local PostgreSQL instance installed on the development machine. This setup is used during Version 2 development and allows full control over schema design, PostGIS functionality, and spatial querying without reliance on external services.

The migration to a hosted database occurs in Version 3, at the point where the Streamlit-based web interface is introduced. At this stage, the system transitions from a single-user local environment to a web-accessible application requiring a persistent cloud-hosted database.

The chosen hosting platform for this migration is Supabase, which provides a managed PostgreSQL service with PostGIS support built in. It is selected specifically because it offers a free tier suitable for development and testing, while still supporting the full geospatial functionality required by the application. Model binaries stored as BYTEA in the council_models table will remain in the database rather than being moved to object storage, keeping the architecture simple and avoiding additional service dependencies within the free tier limits.

During migration, the only required change is the database connection string. The underlying schema, spatial structure, and all SQL queries remain unchanged, meaning no modifications are required to the Python database interaction code.

All existing database logic continues to function as normal because Supabase is fully PostgreSQL-compatible. This ensures that spatial queries, indexing, and PostGIS operations behave identically to the local environment.

The primary advantage of Supabase in this context is that it is designed for exactly this type of application: geospatial data processing combined with a web front end. It removes the need to manage infrastructure manually while still providing full PostGIS capability and production-ready scalability.