# Ground-truth labels

Labels produced against `docs/labelling_protocol.md` (Dec 2024 NPPF PDL definition).

## stoke_pilot_19.csv
Manual pilot, 2026-07-19, single rater (LW). 19 unregistered candidates from the
2026-07-14 Stoke run, sampled by cluster from the interactive map. Result: 19/19
not sellable leads - infrastructure-utility (4), active-industrial (6), car-park
(7), recreation-education (1), construction (1, real but already developing).

Purpose: (a) evidence the raw threshold detector has no land-use/temporal awareness;
(b) regression fixture for P1-5 (exclusion mask) and P1-4 (persistence) - after those
filters, these sites should mostly drop out.

TODO: back-fill utm_x/utm_y per row from the candidate_sites table (matched by
location) to make the regression check coordinate-precise.
