-- 004_classifier_features.sql
-- P1-6 / P1-7: per-candidate classifier features and calibrated confidence.
--
-- Columns are written by the pipeline at insert time (src/features.py via
-- store_candidate_sites) except confidence, which is written after model
-- scoring (src/model_train.py --score). Feature set is deliberately small
-- — the post-FND sample-size correction in Notebook 07 (~4 positives per
-- feature at 17 features) is the reason. pixel_count and bsi_value already
-- exist on the table and complete the model input set.
--
-- Numbered 004: 002 = exclusion_zones, 003 = candidate geometry.
-- ADD COLUMN IF NOT EXISTS makes reruns safe.

ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS std_bsi          DOUBLE PRECISION;
ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS mean_ndvi        DOUBLE PRECISION;
ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS std_ndvi         DOUBLE PRECISION;
ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS mean_b04         DOUBLE PRECISION;
ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS mean_b08         DOUBLE PRECISION;
ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS mean_b11         DOUBLE PRECISION;
ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS compactness      DOUBLE PRECISION;
ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS prior_date_count INTEGER;

-- P1-7: calibrated probability that the candidate is a genuine lead,
-- written by model scoring — NULL until a model has scored the run.
ALTER TABLE public.candidate_sites ADD COLUMN IF NOT EXISTS confidence       DOUBLE PRECISION;
