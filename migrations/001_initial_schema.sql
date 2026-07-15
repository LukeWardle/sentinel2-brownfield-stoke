-- migrations/001_initial_schema.sql
-- SiteSignal — initial schema for PostgreSQL + PostGIS.
--
-- Run against an empty PostgreSQL database. Creates the PostGIS extension,
-- five tables (council_boundaries, brownfield_sites, candidate_sites,
-- pipeline_runs, council_models), one spatial index for register matching,
-- the brownfield_sites unique constraint used for register upserts, and
-- foreign keys on every gss_code column referencing council_boundaries.
--
-- Supabase:  paste this file into the SQL Editor and Run.
-- Local:     psql -d sentinel2_brownfield -f migrations/001_initial_schema.sql
--
-- Assumes an empty database — no IF NOT EXISTS or DROP guards on tables.
-- Rerunning against a populated database will fail on the first CREATE TABLE
-- and no data will be lost.

-- Extension (Supabase also enables this via the dashboard; IF NOT EXISTS
-- keeps this file idempotent for the extension line itself)
CREATE EXTENSION IF NOT EXISTS postgis;

-- council_boundaries: one row per UK council, boundary polygon in WGS84 (EPSG:4326).
-- Referenced by every other table via gss_code for referential integrity.
CREATE TABLE public.council_boundaries (
    gss_code VARCHAR(9) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    boundary geometry(Geometry, 4326)
);

-- brownfield_sites: registered brownfield sites per council, per year.
-- start_date and end_date come from planning.data.gov.uk and enable
-- change detection across register years via detect_register_changes.
CREATE TABLE public.brownfield_sites (
    id SERIAL PRIMARY KEY,
    site_reference VARCHAR(50),
    gss_code VARCHAR(9) REFERENCES public.council_boundaries(gss_code),
    year INTEGER NOT NULL,
    name_address TEXT,
    utm_x DOUBLE PRECISION,
    utm_y DOUBLE PRECISION,
    hectares DOUBLE PRECISION,
    planning_status VARCHAR(100),
    location geometry(Point, 32630),
    start_date DATE,
    end_date DATE,
    CONSTRAINT brownfield_sites_unique UNIQUE (site_reference, gss_code, year)
);

-- Spatial index on brownfield_sites.location — used by match_candidate_to_register
-- via ST_DWithin. Called once per candidate site per pipeline run (218 times for
-- Stoke), so avoiding full table scans matters even at ~2000-row scale.
CREATE INDEX brownfield_sites_location_idx
    ON public.brownfield_sites
    USING GIST (location);

-- candidate_sites: pipeline outputs, one row per detected candidate per run.
-- Column names differ from the pipeline dict keys (centroid_utm_x → utm_x,
-- mean_bsi → bsi_value) — the translation happens in store_candidate_sites.
CREATE TABLE public.candidate_sites (
    id SERIAL PRIMARY KEY,
    gss_code VARCHAR(9) REFERENCES public.council_boundaries(gss_code),
    image_date DATE NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    utm_x DOUBLE PRECISION,
    utm_y DOUBLE PRECISION,
    pixel_count INTEGER,
    bsi_value DOUBLE PRECISION,
    matched_site_reference VARCHAR(50)
);

-- pipeline_runs: metadata per pipeline execution — success/failure status and counts
CREATE TABLE public.pipeline_runs (
    id SERIAL PRIMARY KEY,
    gss_code VARCHAR(9) REFERENCES public.council_boundaries(gss_code),
    image_date DATE NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    status VARCHAR(20),
    candidate_sites_found INTEGER,
    matched_to_register INTEGER,
    unmatched INTEGER
);

-- council_models: per-council trained Random Forest models (Version 3 feature).
-- model_binary holds a pickle-serialised sklearn estimator.
CREATE TABLE public.council_models (
    id SERIAL PRIMARY KEY,
    gss_code VARCHAR(9) REFERENCES public.council_boundaries(gss_code),
    trained_date DATE NOT NULL,
    training_sites INTEGER,
    accuracy DOUBLE PRECISION,
    precision_score DOUBLE PRECISION,
    recall_score DOUBLE PRECISION,
    image_date DATE,
    model_binary BYTEA
);