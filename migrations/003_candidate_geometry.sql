-- migrations/003_candidate_geometry.sql
-- SiteSignal — persist candidate site footprints (FND-3).
--
-- Candidate footprints were previously computed by generate_boundary_polygons
-- and discarded; candidate_sites stored only a centroid. Persisting the valid
-- geometry produced under FND-2 is the prerequisite for indexed, exact
-- exclusion overlap (FND-4), enables temporal-persistence checks across runs
-- (P1-4), and turns a lead from a dot into a viewable parcel (interactive
-- map, classifier shape features, lead packs).
--
-- Stored in EPSG:32630 to match candidate UTM coordinates and the
-- brownfield_sites.location column, so overlap and proximity queries run
-- without per-row transforms on the candidate side.
--
-- Local:  psql -U postgres -d sentinel2_brownfield -f migrations/003_candidate_geometry.sql

ALTER TABLE public.candidate_sites
    ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 32630);

-- Spatial index — used by FND-4 exclusion overlap, P1-4 persistence checks
-- and P1-2 register-recall evaluation.
CREATE INDEX IF NOT EXISTS candidate_sites_geom_idx
    ON public.candidate_sites
    USING GIST (geom);
