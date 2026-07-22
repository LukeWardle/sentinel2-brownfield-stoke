# Notebook corrections — 22 July 2026

The four corrected `.md` files in this folder are the notebook *exports*
with the fixes applied. The `.ipynb` sources need the same edits mirrored
in — every change is prose-only (markdown cells; no code cells touched),
so each is a copy-paste into the matching cell in Jupyter. This list is
the complete change set.

## All four notebooks (04, 05, 06, 07)
- **Status banner** inserted directly under the title: pre-FND figures
  (218 / 39 / 17.9%) are void; post-FND provisional figures are 90 / 18 /
  60 at uncalibrated min_pixels=5 (#89).

## 04 — BSI/NDVI calibration
- Finding, second implication: "PCA validated as primary detection
  method" corrected — Notebook 05 abandoned PCA clustering, the pipeline
  shipped thresholds-only, and PCA feeds only the false-colour map
  (P0-7). The finding's warning is noted as having materialised as the
  low register recall.

## 05 — Clustering calibration
- Section 3 table commentary: the 218=218 register-count coincidence is
  marked as a dilation-bug artifact (true counts 25 at min=10, 90 at
  min=5); the thresholds it helped select are void pending #89.
- Final Finding: the 218-site line carries the same annotation; the
  82%-vegetated limitation is restated with post-FND provisional numbers.
- Version 3 implication: corrected — a classifier trained on
  threshold-gated candidates cannot recover vegetated register sites;
  recovering them requires a gate-REPLACING architecture (fork recorded
  in Notebook 07).

## 06 — Pipeline results validation
- Section 5 bullet and Conclusions item 4: "unregistered candidates are
  spectrally indistinguishable from register sites, confirming they are
  genuine findings" — **retracted** (struck through, kept visible). The
  inference is circular (both sets passed the same gate) and the 19/19
  false-positive labelling pilot refuted it.
- Section 5 recall paragraph: 70% recall target marked NOT achievable
  under the Notebook 07 candidate-classifying design; requires the
  gate-replacing architecture.
- "Recover the 179 vegetated registered sites" bullet: qualified with the
  same architecture condition.

## 07 — Classifier design
- Section 1: void figures flagged; **ARCHITECTURE NOTE** added — the open
  fork gating Notebook 08: (A) re-rank bare-land leads (this design,
  ceiling ~gate recall, aligned with the persistently-bare product) vs
  (B) full brownfield detection (model replaces the gate; needed for 70%).
- Section 5: sample-size maths corrected for post-FND counts (~360
  candidates / ~72 positives over four seasons ≈ 4 positives per feature
  — below the marginal line; mitigations noted).
- Section 8: primary metric restated per-architecture.
- Section 10: migration renamed 002 → **004** (002/003 are taken).
