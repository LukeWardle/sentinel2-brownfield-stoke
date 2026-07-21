-- migrations/002_exclusion_zones.sql
-- SiteSignal — exclusion zones for P1-5 non-brownfield land-use filtering.
--
-- Stores land-use polygons that are masked OUT of the candidate search before
-- clustering (buildings, car parks, schools, infrastructure, etc.). A 2026-07
-- manual pilot found the raw detector fires on any bare/hard man-made surface
-- with no land-use awareness; this table drives the fix.
--
-- Polygons stored in WGS84 (4326) to match council_boundaries; transformed to
-- 32630 at mask time, mirroring clip_to_council_boundary.
--
-- The `source` column keeps the data provenance swappable per class: OSM (ODbL,
-- rich land-use tags) is used now; OS OpenData (OGL, licence-clean) can replace
-- individual classes later without a schema change. See P4-8 (licensing review).
--
-- Local:  psql -d sentinel2_brownfield -f migrations/002_exclusion_zones.sql

CREATE TABLE public.exclusion_zones (
    id SERIAL PRIMARY KEY,
    gss_code VARCHAR(9) REFERENCES public.council_boundaries(gss_code),
    exclusion_class VARCHAR(40) NOT NULL,   -- building | car_park | amenity_leisure | infrastructure | quarry | agriculture | permission
    source VARCHAR(20) NOT NULL,            -- osm | os_open — data provenance, swappable per class
    source_ref VARCHAR(80),                 -- upstream feature id (e.g. OSM way/relation id) for traceability
    geom geometry(Geometry, 4326) NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Spatial index — the mask query filters exclusion_zones by gss_code and tests
-- polygon containment; GIST keeps that fast as classes accumulate per council.
CREATE INDEX exclusion_zones_geom_idx
    ON public.exclusion_zones
    USING GIST (geom);

-- Lookup index for per-council, per-class retrieval and idempotent reloads.
CREATE INDEX exclusion_zones_gss_class_idx
    ON public.exclusion_zones (gss_code, exclusion_class, source);
