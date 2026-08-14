# Project Review — citations and directions

Compiled 5 August 2026. Two independent parts.

> **Status note, added 14 August 2026.** This is a dated snapshot. Part 1 audits the
> repository as it stood on 5 August, and two of its findings have since been acted on:
> the Xu & Ehlers claim flagged as overstated in §1.2 and §1.5 was corrected, and a
> References section was added to `README.md`, including Preston et al. (2023), which §1.2
> notes was missing. Commit `47ce0e9`, 6 August 2026.
>
> The audit text is left unedited. Amending it to describe the repository as it is now
> would remove the record of what it found.

**Part 1** is an audit of every external source this repository refers to, with a canonical
link and a verification status for each. Anything that could not be confirmed is marked as
such rather than filled in from memory.

**Part 2** sets out what the published literature says about detecting derelict or vacant
previously developed land from satellite imagery, arranged as options. Each option states
what it involves, what data and resolution it needs, what accuracy has actually been
reported, and what would cause it to fail. No option is recommended and none is written up
as work to be done. Where the literature contradicts an approach, that is said plainly.

### How verification was done

Bibliographic details were checked against Crossref, OpenAlex and Semantic Scholar rather
than against search-engine summaries, because those summaries paraphrase and occasionally
attribute claims to the wrong paper. Abstracts quoted below come from the publisher record
via those APIs. Several publisher sites (MDPI, ScienceDirect, ResearchGate) refuse
automated requests, so where a claim needed the full text rather than the abstract, that
is flagged and the claim is not asserted.

Four domains could not be reached from this environment at all — the network path failed
rather than the pages 404ing. Those are marked *unreachable here*, which is not evidence
that the page is wrong or missing.

---

# Part 1 — Citation audit

## 1.1 What the repository actually cites

The search covered notebooks 04–09, `README.md`, `DESIGN.md`, `EDA.md`, `DATABASE.md`,
`docs/labelling_protocol.md` and the three `data/` READMEs.

The result worth stating first: **the repository contains two academic citations in total**,
both in `README.md`, both in the "What would be required instead" section. Notebooks 04–09
contain none. `DESIGN.md` contains none. Notebook 09 refers to "the literature reviewed
alongside this work" without naming a single source, and notebook 08 uses the
Polsby–Popper ratio by name without a reference.

For a project whose central conclusion is a claim about the state of the art, the evidence
base is carried almost entirely in two sentences of the README.

## 1.2 Academic references — verified

### Xu & Ehlers (2022)

> Xu, S. & Ehlers, M. (2022). Automatic detection of urban vacant land: An open-source
> approach for sustainable cities. *Computers, Environment and Urban Systems*, 91, 101729.
> DOI: [10.1016/j.compenvurbsys.2021.101729](https://doi.org/10.1016/j.compenvurbsys.2021.101729)

**Status: verified.** Authors, title, journal, volume, article number and DOI all confirmed
against Crossref and OpenAlex. Crossref gives the issue date as January 2022; OpenAlex
records the publication year as 2021 (online-first). Citing it as 2022 is correct.

**What the README claims, against what the abstract says.**

| README claim | Verdict |
|---|---|
| "abandoned image classification for rule-based data fusion" | **Verified.** Abstract: automatic detection "has been attempted using classification of remote sensing images. However … it remains difficult to achieve this goal." The paper then "describe[s] the rule-based data fusion method applied for site detection," combining "remote sensing images, GIS layers and citizen science data." |
| "across 63 German districts" | **Verified.** Abstract: "tested in 63 urban and rural districts in Germany." |
| "still reported brownfield specifically as difficult" | **Not verified — overstated.** The abstract reports difficulty for vacant land *as a class*, listing brownfield as one of four categories alongside transportation-associated land, unfavourable natural sites, and leftover spaces. It does not single brownfield out. Establishing whether brownfield performed worst would need the full text, which ScienceDirect would not serve. |

The abstract reports **no accuracy figure**. The paper describes identifying "a large number
of vacant sites"; it does not, in the abstract, quantify how many were correct. Any claim
about its accuracy would need the full text.

One sentence in that abstract is more useful to this project than the sentence the README
draws from it:

> "because the morphology of vacant land can cover such diverse aspects as derelict
> structures, bare soil, and vegetation or a mix thereof, **even when commercial
> high-resolution images are used**, it remains difficult to achieve this goal."

That is a direct statement that the problem does not dissolve at higher resolution.

### Sun et al. (2023)

> Sun, Y., Hu, H., Han, Y., Wang, Z. & Zheng, X. (2023). Large-Scale Automatic
> Identification of Industrial Vacant Land. *ISPRS International Journal of
> Geo-Information*, 12(10), 409.
> DOI: [10.3390/ijgi12100409](https://doi.org/10.3390/ijgi12100409)

**Status: verified.** The README cites this as "Sun et al. (2023)" with no further detail;
the full author list is Yihao Sun, Han Hu, Yawen Han, Ziyan Wang and Xiaodi Zheng.

**What the README claims, against what the abstract says.**

| README claim | Verdict |
|---|---|
| "separating vacant from operational industrial land cannot be done from image features alone" | **Verified almost verbatim.** Abstract: "it is difficult to distinguish industrial vacant land from operational industrial land based solely upon image features." Note "difficult," not "cannot" — the README hardens it slightly. |
| "solve it by adding land surface temperature and population density as non-image filters" | **Verified.** Abstract: the framework trains a semantic segmentation model "and further use[s] population density and surface temperature data to filter model predictions." |

**Accuracy, stated precisely.** The abstract reports "a model accuracy of 97.84%" for HRNet,
the best of the segmentation backbones tested. Three qualifications matter and none is in
the README:

1. It is a **segmentation model accuracy on the authors' own labelled tiles**, not an
   end-to-end measure of whether identified sites are genuinely vacant industrial land.
2. The study area is a **single case study, Tangshan City, Hebei Province, China**.
3. The abstract does not report precision, recall, F1 or IoU, and does not report accuracy
   after the population-density and temperature filters are applied.

## 1.3 Methods used without attribution

| Method | Where used | Canonical source | Status |
|---|---|---|---|
| Polsby–Popper compactness, 4πA/P² | Notebook 08 §5; `DESIGN.md` | Polsby, D. D. & Popper, R. (1991). The Third Criterion: Compactness as a Procedural Safeguard Against Partisan Gerrymandering. *Yale Law & Policy Review*, 9(2), 301. [Open copy](https://openyls.law.yale.edu/bitstream/20.500.13051/17448/2/18_9YaleL_PolyRev301_SpringSummer1991_.pdf) · [SSRN mirror](https://doi.org/10.2139/ssrn.2936284) | **Verified.** Named in the notebook, cited nowhere. |
| Bare Soil Index, `((B11+B04)-(B08+B02))/((B11+B04)+(B08+B02))` | `src/preprocess.py`; `DESIGN.md`; notebooks 04, 05 | **Could not establish.** Commonly attributed in the remote-sensing literature to Rikimaru, Roy & Miyatake (2002), *Tropical Ecology* 43(1), but that paper is indexed in neither Crossref nor OpenAlex and no publisher page was reachable. | **Unverified.** The formula is standard and the implementation is correct; the provenance is undocumented and I could not close it. |
| NDVI, `(B08-B04)/(B08+B04)` | `src/preprocess.py`; `DESIGN.md` | Conventionally Rouse et al. (1974), NASA/GSFC Type III Final Report. Not verified against a publisher record here. | **Unverified.** Universally known, so the omission is immaterial. |
| NDBSI | `src/preprocess.py` | No source identified in the repository, and the acronym is used inconsistently across the literature for more than one formulation. | **Unverified.** Worth noting because the index name alone does not identify the formula. |

## 1.4 Datasets and external sources

| Source | Used for | Canonical link | Status |
|---|---|---|---|
| Copernicus Data Space Ecosystem — Sentinel-2 L2A | All imagery | https://dataspace.copernicus.eu | **Live (HTTP 200).** |
| planning.data.gov.uk — Brownfield land | The 352-site register | https://www.planning.data.gov.uk/dataset/brownfield-land | **Verified.** Publisher: Ministry of Housing, Communities and Local Government. Licence: Open Government Licence v3.0. 37,485 sites from 354 providers. The page itself warns the data "may be incomplete and not yet cover all of England." |
| Town and Country Planning (Brownfield Land Register) Regulations 2017 | Why the register exists | https://www.gov.uk/guidance/brownfield-land-registers | **Live (HTTP 200).** Registers are in two parts; Part 1 is all brownfield suitable for residential development, Part 2 those granted permission in principle. |
| data.gov.uk — Stoke-on-Trent brownfield register | `data/brownfield_register_*.csv` | https://www.data.gov.uk/dataset/1368fc6f-3975-4bf1-b234-1f5d6055b7dd/stoke-on-trent-brownfield-register | **Live (HTTP 200).** |
| data.gov.uk — Contaminated land special sites | `data/contaminated_land_special_sites.csv` | https://www.data.gov.uk/dataset/e3770885-fc05-4813-9e60-42b03ec411cf/contaminated-land-special-sites | **Live (HTTP 200).** |
| Stoke-on-Trent City Council downloads | `data/` register files | https://www.stoke.gov.uk/downloads/download/626/ | **Live (HTTP 200).** |
| ONS Open Geography Portal — Local Authority Districts (May 2024) Boundaries UK BFE | `council_boundaries` | https://geoportal.statistics.gov.uk/datasets/ons::local-authority-districts-may-2024-boundaries-uk-bfe-2/about | **Partially verified.** Title confirmed; publisher, licence and CRS could not be read from the page. |
| OpenStreetMap Overpass API | `exclusion_zones` | https://wiki.openstreetmap.org/wiki/Overpass_API | **Unreachable here.** |
| Open Database Licence (ODbL) | OSM licence obligations in `DESIGN.md` | https://opendatacommons.org/licenses/odbl/ | **Unreachable here.** The licensing analysis in `DESIGN.md` §licensing is not assessed in this review. |
| Historic England — National Heritage List / Heritage at Risk | Named in notebook 08 as a future designation overlay | https://historicengland.org.uk/listing/the-list/ | **Unreachable here.** Not currently a dependency. |
| NPPF, December 2024 — Annex 2, "previously developed land" | The controlling definition in `docs/labelling_protocol.md` | Annex 2 of the National Planning Policy Framework, gov.uk | **Not independently verified.** The protocol's summary of the definition is detailed and internally consistent, including the December 2024 treatment of hardstanding, but I did not retrieve Annex 2 to check it clause by clause. |

## 1.5 Claims carrying no citation at all

These are assertions in `README.md` presented as established fact with nothing behind them.

| Claim | Assessment |
|---|---|
| "Abandonment detection by NDVI trajectory reaches the high 80s in the cropland literature" | **Supportable, but the nearest evidence weakens the inference.** Löw et al. (2018) report overall accuracy 0.879 for mapping abandoned cropland — matching "high 80s" almost exactly. But that result is from **MODIS at 250 m** over the Aral Sea Basin drylands, an agricultural setting with field-scale parcels. The README uses the figure to motivate a 30 m Landsat approach against a median register site of 0.28 ha. The number is real; the transfer to small urban parcels is not evidenced. Full citation in Part 2, Option C. |
| "non-abandoned land shows cyclical annual NDVI, abandoned land a rising trend under succession" | **Plausible and consistent with the abandonment literature, but uncited.** Goga et al. (2019) review 73 studies in this area and note the field's weak point is precisely the absence of comparable field validation. |
| "Nimbus Maps, LandTech/LandInsight and SearchLand … None are known to use satellite detection of unregistered land" | **Not verifiable.** A claim about the internals of commercial products. "None are known to" is honest phrasing, but it is an absence of evidence and cannot be checked. |
| "LandInsight additionally filters sites by state (in use, vacant, demolished) from business-rates data" | **Not verified.** A specific factual claim about a named commercial product, with no source. |
| "Xu & Ehlers (2022) … still reported brownfield specifically as difficult" | **Overstated**, as set out in §1.2. |

## 1.6 Summary of flags

| Flag | Count | Items |
|---|---|---|
| Fully verified | 2 papers, 1 method, 5 datasets | Xu & Ehlers 2022; Sun et al. 2023; Polsby–Popper 1991; Copernicus; planning.data.gov.uk; gov.uk registers guidance; both data.gov.uk datasets; stoke.gov.uk |
| Claim overstated relative to source | 2 | "brownfield specifically as difficult"; "cannot" vs "difficult" in Sun et al. |
| Verified but materially under-qualified | 1 | Sun et al. 97.84% quoted nowhere in the repo, but if it is ever quoted it needs its three caveats |
| Attribution missing | 4 | BSI, NDVI, NDBSI, Polsby–Popper |
| Uncited factual claim | 4 | NDVI-trajectory accuracy; succession signature; two commercial-product claims |
| Could not verify from this environment | 5 | Rikimaru et al. 2002; OSM wiki; ODbL; Historic England; NPPF Annex 2 |

---

# Part 2 — Options

Seven directions appear in the literature. They are set out as options, not as a ranking.
Each carries the accuracy actually reported — with the measurement conditions, because the
headline numbers in this field are rarely comparable — and an explicit account of what
would make it fail.

**One framing observation applies to all of them.** Not one published study located here
reports a validated accuracy for the specific task this project attempted: finding
*unregistered* derelict previously developed land, in a UK city, at parcel scale. The
closest work either maps vacant land as a broad class (Xu & Ehlers; Mao et al.; Hu &
Zhuang), maps industrial vacancy in a Chinese city with non-image filters (Sun et al.), or
characterises brownfield that is *already registered* (Preston et al.). The absence is
itself evidence about the difficulty of the task, and it means every accuracy figure below
is being read across from an adjacent problem.

## Option A — The null option: the target is not separable at this resolution

**What it involves.** Accepting that persistently bare ground and previously developed land
are near-disjoint populations in a UK city, that no threshold or classifier over optical
indices separates them, and that the project's finding is the result rather than a stage on
the way to one.

**Data and resolution.** None beyond what has already been collected.

**Evidence for.**

- **This project's own measurement.** Zero of 352 register sites satisfy BSI > 0.1 and
  NDVI < 0.2, sampled directly at the register locations. Highest BSI anywhere in the
  register: 0.0843, against a threshold of 0.1. Mean NDVI 0.234. Not a marginal failure.

- **Independent corroboration from a UK post-industrial city.** Preston et al. (2023)
  classified brownfield across Greater Manchester and found that **over half — 51% — of
  brownfield land is vegetated** (27% trees and shrubs, 24% grass and herbaceous). Sites
  "traditionally perceived as difficult to develop … are particularly highly vegetated."
  This is the same finding as notebook 09, reached independently, on a different city, by a
  different method, and published in a peer-reviewed journal. It is the single strongest
  external corroboration available to this project and the README does not cite it.

  > Preston, P. D., Dunk, R. M., Smith, G. R. & Cavan, G. (2023). Not all brownfields are
  > equal: A typological assessment reveals hidden green space in the city. *Landscape and
  > Urban Planning*, 229, 104590.
  > DOI: [10.1016/j.landurbplan.2022.104590](https://doi.org/10.1016/j.landurbplan.2022.104590)
  >
  > *Cite with care: the DOI suffix and several bibliographic indexes say 2022, but the
  > publisher record places it in the January 2023 issue, volume 229. Both years appear in
  > the wild.*

- **The resolution defence does not obviously hold.** Xu & Ehlers (2022) state that vacant
  land detection remains difficult "even when commercial high-resolution images are used."

- **The task is stated as unsolved on image features.** Sun et al. (2023): "it is difficult
  to distinguish industrial vacant land from operational industrial land based solely upon
  image features."

**What would make this option wrong.**

- It generalises from one council. Stoke's register is 352 sites with a median of 0.28 ha;
  a city with larger, more recently cleared sites might show a different BSI distribution.
  Preston et al. reduce this risk but do not eliminate it — Greater Manchester is also
  post-industrial and wet, and both are English Midlands/North-West.
- It generalises from one gate. Zero sites pass *this* threshold pair. Notebook 09 goes
  further and shows the register and background distributions are superimposed rather than
  merely offset, which is the stronger claim; but that was established on two indices from
  one May scene, not on the full feature space.
- It is a claim about optical indices, not about satellites. Options F and G below use
  satellite data for different questions and are untouched by it.

## Option B — Non-image occupancy data as the primary signal

**What it involves.** Treating the active-versus-abandoned distinction as an administrative
fact rather than a spectral one. In the UK the candidate sources are business rates
records, which identify occupied hereditaments, and empty-property relief, which functions
as a vacancy declaration.

**Data and resolution.** No imagery required for the core signal. Resolution is the
addressable property, not a pixel.

**Accuracy reported.** None found — no located study evaluates UK business-rates data for
this purpose. The nearest published support is indirect: Sun et al. (2023) resolve exactly
this distinction by importing non-image data (population density, surface temperature)
because image features would not do it. That validates the *shape* of the argument, not the
UK data source.

**What would make it fail.**

- **Coverage.** Business rates cover non-domestic hereditaments. Cleared sites with no
  rateable building may not appear at all — and cleared sites are precisely the
  brownfield of interest.
- **Geometry.** Rates records attach to an address, not a parcel boundary. Matching a
  hereditament to a developable site polygon is an unsolved join, and this project has
  already been burnt once by proximity matching standing in for correspondence.
- **Availability and licensing.** Whether the granular data is obtainable, at what cost,
  and under what terms, is unestablished here.
- **It answers a different question.** Occupancy is not developability. Chatterley
  Whitfield — correctly detected, genuinely derelict, and a scheduled monument — would pass
  an occupancy filter and still not be a lead.
- **The satellite becomes optional.** If occupancy data carries the signal, the imagery
  pipeline is not the product. That is a strategic consequence, not a technical failure.

## Option C — Multi-year phenology and succession trajectory

**What it involves.** Abandoning single-date bareness for the temporal shape of the
greenness curve: land in use shows a cyclical annual NDVI, land left alone shows a rising
trend as succession takes hold.

**Data and resolution.** Years of consistent imagery. The cropland literature runs on
Landsat at 30 m or MODIS at 250 m, because the method needs a long, dense, radiometrically
consistent archive more than it needs fine pixels.

**Accuracy reported.**

- Löw et al. (2018) mapped abandoned cropland in the Aral Sea Basin from a 2003–2016 MODIS
  NDVI time series, reporting **overall accuracy 0.879** with stratum-specific classifiers,
  against 0.811 for an unstratified global classifier.

  > Löw, F., Prishchepov, A. V., Waldner, F., Dubovyk, O., Akramkhanov, A., Biradar, C. &
  > Lamers, J. P. A. (2018). Mapping Cropland Abandonment in the Aral Sea Basin with MODIS
  > Time Series. *Remote Sensing*, 10(2), 159.
  > DOI: [10.3390/rs10020159](https://doi.org/10.3390/rs10020159)

- Goga et al. (2019) reviewed 73 studies from 1992–2019 on identifying abandoned
  agricultural land by remote sensing. They report the benefit of fusing optical and radar
  (Sentinel-1 with Sentinel-2), and identify as a field-wide weakness "the absence of
  similar field research, which serves not only for validation, but also for understanding
  the process."

  > Goga, T., Feranec, J., Bucha, T., Rusnák, M., Sačkov, I., Barka, I., Kopecká, M.,
  > Papčo, J., Oťaheľ, J., Szatmári, D., Pazúr, R., Sedliak, M., Pajtík, J. & Vladovič, J.
  > (2019). A Review of the Application of Remote Sensing Data for Abandoned Agricultural
  > Land Identification with Focus on Central and Eastern Europe. *Remote Sensing*, 11(23),
  > 2759. DOI: [10.3390/rs11232759](https://doi.org/10.3390/rs11232759)

**What would make it fail.**

- **Scale mismatch, and it is severe.** The 0.879 figure is from 250 m MODIS pixels over
  agricultural fields. A 250 m pixel is 6.25 ha. This project's median register site is
  0.28 ha. Even Landsat at 30 m gives roughly three pixels across a median site. The
  literature's accuracy was earned at a parcel-to-pixel ratio this target does not have.
- **The literature is agricultural, not urban.** Cropland abandonment has a clean signature
  because cropping is a strong, regular, human-imposed annual cycle. Urban brownfield has
  no equivalent baseline rhythm to depart from.
- **Vegetated-from-the-start sites have no transition to detect.** Preston et al. (2023)
  found 51% of brownfield already vegetated. A site abandoned in 1990 shows a flat mature
  curve, not a rising one. The method detects the *event* of abandonment, and much of the
  register's abandonment predates any usable archive.
- **Validation.** Goga et al. name the lack of field validation as the field's structural
  weakness. This project has 38 manually labelled sites and no positives — an insufficient
  base to validate a trajectory classifier.
- **Confusion with ordinary succession.** A rising NDVI trend also describes a hedgerow
  maturing, a park being left to grow, or a verge that stopped being mown.

## Option D — Very-high-resolution imagery with semantic segmentation

**What it involves.** Replacing index thresholds with a deep segmentation network trained
on labelled examples of vacant land, run on sub-metre or few-metre commercial imagery.

**Data and resolution.** High-resolution commercial or aerial imagery, plus a substantial
hand-labelled training set.

**Accuracy reported.**

- Mao et al. (2022) applied semantic segmentation to high-resolution imagery across **36
  major Chinese cities**, reporting framework accuracy "over 90 percent of professional
  auditors" and roughly 15× the throughput of manual identification, with city
  stratification improving robustness at scale.

  > Mao, L., Zheng, Z., Meng, X., Zhou, Y., Zhao, P., Yang, Z. & Long, Y. (2022).
  > Large-scale automatic identification of urban vacant land using semantic segmentation of
  > high-resolution remote sensing images. *Landscape and Urban Planning*, 222, 104384.
  > DOI: [10.1016/j.landurbplan.2022.104384](https://doi.org/10.1016/j.landurbplan.2022.104384)
  >
  > *Note: no abstract is indexed for this paper in Crossref, OpenAlex or Semantic Scholar,
  > and ScienceDirect refused automated access. The figures above come from search-result
  > summaries of the publisher page and were not read from the paper. Treat as indicative,
  > not verified.*

- Hu & Zhuang (2024) trained five segmentation networks on a purpose-built dataset (3,096
  training patches, 128 evaluation patches, five vacant-land categories) and applied
  Segformer across Hangzhou. The abstract reports "good identification performance" and
  releases the dataset, **but states no headline accuracy number**.

  > Hu, X. & Zhuang, S. (2024). Large-Scale Spatial–Temporal Identification of Urban Vacant
  > Land and Informal Green Spaces Using Semantic Segmentation. *Remote Sensing*, 16(2),
  > 216. DOI: [10.3390/rs16020216](https://doi.org/10.3390/rs16020216)

**What would make it fail.**

- **The direct contradiction.** Xu & Ehlers (2022) state that detection "remains difficult
  … even when commercial high-resolution images are used," and give the reason: vacant land
  has no consistent morphology, spanning "derelict structures, bare soil, and vegetation or
  a mix thereof." Resolution does not fix a class that has no visual definition.
- **"Vacant land" in the Chinese studies is not "unregistered brownfield" in the UK.** Mao
  et al. and Hu & Zhuang segment a visually distinguishable land-cover class in rapidly
  developing cities with large cleared plots. Stoke's target is small, often vegetated
  parcels indistinguishable from the scrub next door.
- **Mao et al.'s accuracy is expressed against human auditors, not ground truth.** If human
  auditors identify vacant land from the same imagery, the ceiling is agreement with human
  photo-interpretation — which is exactly what this project's own labelling exercise showed
  cannot resolve active from derelict from a top-down view. `docs/labelling_protocol.md`
  already encodes this: "When the top-down view shows a building you CANNOT tell occupied
  from abandoned."
- **Training data.** These studies build labelled datasets of thousands of patches. This
  project has 38 labels and zero positives. A segmentation model needs positive examples,
  and the register cannot supply footprints — it stores point locations.
- **Cost and licensing.** Sub-metre imagery is neither free nor openly licensed, which
  removes the property that made the current pipeline viable.

## Option E — Rule-based multi-source data fusion

**What it involves.** Xu & Ehlers's approach: abandon single-classifier image
classification, define a typology of vacant land, and build a separate rule-based
processing flow per category, fusing remote sensing with GIS layers and citizen-science
data (OpenStreetMap, Wikidata).

**Data and resolution.** Open imagery plus open GIS vector layers plus crowd-sourced data.
Explicitly designed to be low-cost — "information on vacant land is retrievable by local
administrations irrespective of their financial circumstances."

**Accuracy reported.** **None in the abstract.** The paper reports identifying "a large
number of vacant sites" across 63 German districts and does not, at abstract level,
quantify correctness. This is the option with the weakest published accuracy evidence, and
it is also the one the README leans on hardest.

**What would make it fail.**

- **It inherits its ground truth from the same vector data it fuses.** If OpenStreetMap
  does not know a site exists, the rules cannot find it. This project has already met that
  failure directly: the bet365 Stadium car park survived a hard `car_park` exclusion purely
  because it is absent from OSM.
- **Rules are per-category and hand-built.** Four categories in Germany became four separate
  processing flows. Transfer to UK data means rebuilding all of them, and the German flows
  depend on German cadastral and open-data availability.
- **Licensing.** OSM is ODbL. `DESIGN.md` already flags share-alike as a blocking item for
  any commercial product.
- **No accuracy to inherit.** Adopting a method whose published validation is qualitative
  means starting the validation problem from zero.

## Option F — Non-image filters over image predictions

**What it involves.** Sun et al.'s architecture: use imagery to propose candidates, then
filter those proposals with data that speaks to *occupancy* rather than appearance —
population density and land surface temperature. Thermal signal is a proxy for activity;
an operating works is warm, an abandoned one is not.

**Data and resolution.** Optical imagery for segmentation, plus thermal (Landsat 8/9 TIRS
at 100 m resampled to 30 m; Sentinel-2 carries no thermal band) and gridded population.

**Accuracy reported.** Sun et al. (2023) report HRNet **model accuracy 97.84%** — with the
three qualifications in §1.2: it is segmentation accuracy on the authors' labelled tiles,
in one Chinese city, and is not reported after the filters are applied. The paper does not
quantify how much the LST and population filters improved the result, which is the part
that matters for this option.

**What would make it fail.**

- **Sentinel-2 has no thermal band.** This is a different sensor programme. Landsat thermal
  at 100 m native resolution against a 0.28 ha median site is a scale mismatch of the same
  order as Option C's.
- **Thermal contrast in a UK climate.** The signal separating an active works from an idle
  one is weakest in a cool, cloudy, maritime climate, and the useful thermal contrast in
  Tangshan may not exist in Stoke. No located study tests this in the UK.
- **Population density does not discriminate industrial from derelict.** An active
  distribution depot has near-zero residential population, exactly like an abandoned one.
- **It is a filter, not a detector.** It removes false positives from a candidate pool. This
  project's finding is that the pool contains no true positives to begin with — filtering
  an empty set more precisely yields an empty set.

## Option G — Change detection on known geometries

**What it involves.** Inverting the problem. Rather than searching for unknown sites, monitor
*known* parcels — permitted sites, register entries — for physical change over time:
build-out, clearance, demolition.

**Data and resolution.** Sentinel-2 as already ingested, plus a source of known geometries.
Ground truth comes free from planning records.

**Accuracy reported.** No study located that measures this for UK brownfield build-out
monitoring. The adjacent building change-detection literature is mature and benchmark-driven
— for example S2Looking, 5,000 bitemporal image pairs and 65,920 annotated change instances
— but those benchmarks measure building change on curated datasets, not planning compliance.

> Shen, L., Lu, Y., Chen, H., Wei, H., Xie, D., Yue, J., Chen, R., Lv, S. & Jiang, B.
> (2021). S2Looking: A Satellite Side-Looking Dataset for Building Change Detection.
> *Remote Sensing*, 13(24), 5094.
> DOI: [10.3390/rs13245094](https://doi.org/10.3390/rs13245094)

**What would make it fail.**

- **It is a different product.** It monitors sites someone already knows about. The original
  proposition — finding land nobody has registered — is abandoned, not solved.
- **Scale is still the binding constraint.** Detecting whether a 0.28 ha parcel has been
  built on, from 10–20 m pixels, is the same pixel-count problem in a new guise. It is more
  tractable because the geometry is known and the question is binary, but it is not free of
  it.
- **The benchmarks do not transfer cleanly.** S2Looking is deliberately hard — off-nadir,
  large illumination variance — and its authors note deep-learning methods find it
  significantly more challenging than near-nadir datasets. Accuracy on curated benchmarks
  is not accuracy on a specific council's permitted sites.
- **Commercial value is unestablished.** Free ground truth in planning records is also
  freely available to everyone, including the councils themselves.

---

## Where the literature contradicts an approach

Stated plainly, as requested.

| Approach | What contradicts it |
|---|---|
| Higher-resolution imagery will fix detection | Xu & Ehlers (2022): difficult "even when commercial high-resolution images are used," because vacant land has no consistent morphology. |
| A classifier on spectral features will separate brownfield from background | Sun et al. (2023): the vacant/operational distinction cannot be made "based solely upon image features." Corroborated internally by notebook 09 §5, where no stored feature separates register-matched from unmatched candidates (largest Cohen's *d* = −0.372, both gate indices near zero). |
| Bare-ground indices are the right discriminant for brownfield | Preston et al. (2023): 51% of Greater Manchester brownfield is vegetated, and the hardest-to-develop sites are the most vegetated. A bare-ground detector selects against the target. |
| NDVI-trajectory methods will transfer from cropland to urban brownfield | Löw et al. (2018) achieve 0.879 at **250 m** on agricultural parcels. Goga et al. (2019) identify absent field validation as the field's structural weakness. Neither supports parcel-scale urban transfer. |
| Persistence filtering improves lead quality | This project's own result: persistence selects for permanence of *use*. Consistent with, though not proven by, Sun et al.'s need to import occupancy data. |

## What could not be established

- **No accuracy figure for Xu & Ehlers (2022).** The abstract reports none and the full text
  was not accessible.
- **No verified accuracy for Mao et al. (2022).** Figures above come from publisher-page
  summaries, not the paper.
- **No study, anywhere in this search, reporting validated accuracy for detecting
  unregistered derelict PDL at parcel scale in a UK city.** This may be a gap in the search
  rather than in the literature; the search covered OpenAlex, Crossref and Semantic Scholar
  by keyword and citation, not a systematic review protocol.
- **Whether Xu & Ehlers found brownfield harder than their other three categories** — the
  claim the README makes.
- **BSI provenance**, per §1.3.

---

## Reference list

All DOIs resolve. Verification status per §1.

1. Goga, T. et al. (2019). A Review of the Application of Remote Sensing Data for Abandoned
   Agricultural Land Identification with Focus on Central and Eastern Europe. *Remote
   Sensing*, 11(23), 2759. https://doi.org/10.3390/rs11232759
2. Hu, X. & Zhuang, S. (2024). Large-Scale Spatial–Temporal Identification of Urban Vacant
   Land and Informal Green Spaces Using Semantic Segmentation. *Remote Sensing*, 16(2), 216.
   https://doi.org/10.3390/rs16020216
3. Löw, F., Prishchepov, A. V., Waldner, F., Dubovyk, O., Akramkhanov, A., Biradar, C. &
   Lamers, J. P. A. (2018). Mapping Cropland Abandonment in the Aral Sea Basin with MODIS
   Time Series. *Remote Sensing*, 10(2), 159. https://doi.org/10.3390/rs10020159
4. Mao, L., Zheng, Z., Meng, X., Zhou, Y., Zhao, P., Yang, Z. & Long, Y. (2022).
   Large-scale automatic identification of urban vacant land using semantic segmentation of
   high-resolution remote sensing images. *Landscape and Urban Planning*, 222, 104384.
   https://doi.org/10.1016/j.landurbplan.2022.104384
5. Polsby, D. D. & Popper, R. (1991). The Third Criterion: Compactness as a Procedural
   Safeguard Against Partisan Gerrymandering. *Yale Law & Policy Review*, 9(2), 301.
   https://doi.org/10.2139/ssrn.2936284
6. Preston, P. D., Dunk, R. M., Smith, G. R. & Cavan, G. (2023). Not all brownfields are
   equal: A typological assessment reveals hidden green space in the city. *Landscape and
   Urban Planning*, 229, 104590. https://doi.org/10.1016/j.landurbplan.2022.104590
   *(indexed as 2022 by OpenAlex and Semantic Scholar; publisher record says vol 229,
   January 2023)*
7. Shen, L., Lu, Y., Chen, H., Wei, H., Xie, D., Yue, J., Chen, R., Lv, S. & Jiang, B.
   (2021). S2Looking: A Satellite Side-Looking Dataset for Building Change Detection.
   *Remote Sensing*, 13(24), 5094. https://doi.org/10.3390/rs13245094
8. Sun, Y., Hu, H., Han, Y., Wang, Z. & Zheng, X. (2023). Large-Scale Automatic
   Identification of Industrial Vacant Land. *ISPRS International Journal of
   Geo-Information*, 12(10), 409. https://doi.org/10.3390/ijgi12100409
9. Xu, S. & Ehlers, M. (2022). Automatic detection of urban vacant land: An open-source
   approach for sustainable cities. *Computers, Environment and Urban Systems*, 91, 101729.
   https://doi.org/10.1016/j.compenvurbsys.2021.101729

---

# Part 3 — Ten proposed approaches, tested against the two established constraints

Added 5 August 2026, extending Part 2. Ten approaches were nominated for assessment:
anomaly detection, self-supervised learning, multimodal foundation models, vision-language
models, graph neural networks, SAR (Sentinel-1), LiDAR, parcel-level temporal embeddings,
agentic data fusion, and multimodal transformers.

Each is asked two questions.

> **Q1. Does it introduce information not present in Sentinel-2 optical imagery, or is it a
> different way of processing the same information?**
>
> **Q2. Does it survive the two constraints this project already established?**
> **(a)** Sub-hectare sites at 10–20 m are a handful of pixels.
> **(b)** Preston et al. (2023) find ~half of brownfield is vegetated and visually
> indistinguishable from non-brownfield green space.

Nothing is called promising unless it does both. Most do not.

## 3.0 The arithmetic the scale constraint actually implies

Every judgement below rests on this table, so it is stated first. These are not literature
figures — they are division, from published sensor specifications and this project's own
register statistics (median 0.28 ha, lower quartile 0.10 ha, detection floor 0.20 ha, 38.5%
of the register below the floor).

**Resolution cells per site**

| Sensor | Cell | 0.28 ha (median) | 0.20 ha (floor) | 0.10 ha (Q1) |
|---|---|---|---|---|
| Sentinel-2, 10 m bands | 100 m² | 28 | 20 | 10 |
| **Sentinel-2, 20 m bands** (B11/B12 — what BSI uses) | 400 m² | **7** | **5** | **2.5** |
| Sentinel-1 IW GRD, ~20 × 22 m | ~440 m² | 6.4 | 4.6 | 2.3 |
| Landsat / HLS, 30 m | 900 m² | 3.1 | 2.2 | 1.1 |
| MODIS, 250 m | 62,500 m² | 0.04 | 0.03 | 0.02 |
| **EA LiDAR composite, 1 m** | 1 m² | **2,800** | **2,000** | **1,000** |

**Transformer patch tokens.** Vision transformers do not see pixels, they see patch tokens,
conventionally 16 × 16. That gives a token footprint of:

| Input resolution | One 16×16 token covers | Median site as % of one token |
|---|---|---|
| 10 m | 160 × 160 m = 2.56 ha | 10.9% |
| 20 m | 320 × 320 m = 10.24 ha | 2.7% |
| 30 m (HLS, Prithvi) | 480 × 480 m = 23.04 ha | 1.2% |

**This is the single most important number in Part 3.** Every transformer-based approach —
foundation models, VLMs, multimodal transformers, most temporal encoders — has the target
occupying a *fraction of one token*. The site is not merely small in the image; it is
smaller than the model's atomic unit of attention. Patch size 16 is the ViT convention and
is assumed here rather than read from each model's config; a model using patch size 8 at
10 m would still put the median site at 44% of one token.

## 3.1 Verdict summary

| # | Approach | Q1 — new information? | Q2a — survives scale? | Q2b — survives vegetation ambiguity? | Verdict |
|---|---|---|---|---|---|
| 1 | Anomaly detection | **No** — same pixels | No | **No** — decisively | Fails both |
| 2 | Self-supervised learning | **No** — same pixels | No | No | Novel, addresses neither |
| 3 | Multimodal foundation models | **No** unless new modalities added | No — worse (30 m HLS) | No | Novel, addresses neither |
| 4 | Vision-language models | **No** — same pixels, rendered | No | No | Novel, addresses neither |
| 5 | Graph neural networks | **Partly** — relational context, but derived from existing data | No | No | Novel, addresses neither |
| 6 | SAR (Sentinel-1) | **Yes** — genuinely new physics | **No** — same resolution class | Partly, unproven | Adds signal, fails scale |
| 7 | **LiDAR** | **Yes** — 3D structure | **Yes** — 2,800 cells per median site | **Yes, partly** — sees through and beneath vegetation | **Passes both.** Failure modes in §3.8 |
| 8 | Parcel-level temporal embeddings | **No** — same time series | No | No | Novel, addresses neither |
| 9 | Agentic data fusion | **No** — orchestration, not sensing | N/A | N/A | Not a sensing method |
| 10 | Multimodal transformers | **Only if** the added modalities do | Inherits from modalities | Inherits from modalities | Architecture, not evidence |

Two of ten add genuinely new physical measurement. **One of ten survives the scale
constraint.** The other eight are, on this analysis, different ways of processing the same
photons that notebook 09 already showed to be uninformative for this target.

---

## 3.2 Anomaly detection

**Q1 — new information? No.** Anomaly detection is a decision rule over an existing feature
space. It changes what is done with BSI, NDVI and reflectance; it does not add a measurement.

**Q2 — survives? No, and it fails in the most direct way of any approach here.**

Anomaly detection requires the target to be a statistical outlier against the background.
Notebook 09 §6 measured exactly this and found the opposite. The register and the urban
background are not merely overlapping; the notebook's own words are that the distributions
are "superimposed rather than merely overlapping," and that "there is no interval of BSI
within which a location is more likely to be registered brownfield than to be something
else." An anomaly detector run on this feature space would return the genuinely unusual
parts of Stoke — a quarry face, a reservoir, a rail yard — which is precisely the false
positive class the four-season labelling exercise already enumerated.

There is a second, independent failure. Anomaly detection also assumes the target is *rare*.
352 register sites in a city of roughly 93 km² is not rare, and the unregistered population
the product was meant to find is presumed larger still.

**Flag:** no directly on-point remote-sensing anomaly-detection reference was located for
this task. The argument above rests on this project's own measurement (notebook 09 §5–§6,
including Cohen's *d* of −0.092 for BSI and −0.117 for mean NDVI between register-matched
and unmatched candidates) rather than on external literature. That is internal evidence, and
it is decisive for *this* feature space, but it has not been independently published.

## 3.3 Self-supervised learning

**Q1 — new information? No.** SSL learns representations from unlabelled imagery. The
imagery is the same imagery.

**Q2 — survives? No.**

SSL addresses a real problem this project has — label scarcity. Mañas et al. (2021)
introduced Seasonal Contrast (SeCo), exploiting time and position invariance to pre-train on
uncurated Sentinel-2, outperforming ImageNet initialisation on downstream tasks. Yuan & Lin
(2020) do the equivalent for satellite image *time series*, pre-training a transformer by
predicting contaminated observations, and report substantial accuracy gains when labelled
data is scarce.

> Mañas, O., Lacoste, A., Giró-i-Nieto, X., Vázquez, D. & Rodríguez, P. (2021). Seasonal
> Contrast: Unsupervised Pre-Training from Uncurated Remote Sensing Data. *ICCV 2021*.
> DOI: [10.1109/ICCV48922.2021.00928](https://doi.org/10.1109/iccv48922.2021.00928)
>
> Yuan, Y. & Lin, L. (2020). Self-Supervised Pretraining of Transformers for Satellite Image
> Time Series Classification. *IEEE JSTARS*, 14, 474–487.
> DOI: [10.1109/JSTARS.2020.3036602](https://doi.org/10.1109/jstars.2020.3036602)
>
> *Online 2020, printed in JSTARS volume 14 (2021); both years are cited in the wild.*

Both are real results. Neither helps here, for reasons about this project's data rather than
about the method:

- **SSL reduces the number of labels needed. It cannot create positive examples.** This
  project has 38 manual labels and **zero positives** — 38 of 38 inspected candidates were
  false positives. Fine-tuning needs at least some examples of the class. There are none,
  and the register cannot supply them because it stores point locations, not footprints.
- **The pre-training signal is the same signal.** SeCo's pretext task is seasonal
  invariance. This project has already established that its target's seasonal behaviour is
  the *opposite* of what the pipeline assumed — derelict land greens over, active
  hardstanding stays bare. A representation learned to be invariant to season discards the
  one temporal cue in play.
- **Scale is untouched.** SSL on 7-pixel objects learns representations of 7-pixel objects.

**Architecturally novel; addresses neither constraint.**

## 3.4 Multimodal foundation models

**Q1 — new information? No, not as currently built.** Prithvi (Jakubik et al., 2023) is
pre-trained on >1 TB of **Harmonized Landsat-Sentinel 2 (HLS)** imagery — the same optical
sensors this project already uses, harmonised to **30 m**, which is *coarser* than the
Sentinel-2 20 m bands the detector currently gates on.

> Jakubik, J., Roy, S., Phillips, C., Fraccaro, P., Godwin, D., Zadrozny, B. et al. (2023).
> Foundation Models for Generalist Geospatial Artificial Intelligence. *arXiv:2310.18660*.
> DOI: [10.48550/arXiv.2310.18660](https://doi.org/10.48550/arxiv.2310.18660)

The demonstrated tasks are cloud gap imputation, flood mapping, wildfire scar segmentation
and multi-temporal crop segmentation — all large-extent phenomena, none of them
sub-hectare-object detection.

**Q2 — survives? No, and the scale failure is worse than for the current pipeline.**

At 30 m the median register site is **3.1 pixels** and a lower-quartile site is **1.1
pixels**. Under the 16×16 patch convention, one token covers 23 ha and the median site is
**1.2% of a single token**.

Huo et al. (2025), surveying foundation models in remote sensing, state the position
plainly: despite their potential, "open challenges concerning data, model, and task impact
the performance of remote sensing images and make foundation models far from practical
applications."

> Huo, C., Chen, K., Zhang, S., Wang, Z., Yan, H., Shen, J. et al. (2025). When Remote Sensing
> Meets Foundation Model: A Survey and Beyond. *Remote Sensing*, 17(2), 179.
> DOI: [10.3390/rs17020179](https://doi.org/10.3390/rs17020179)

A foundation model pre-trained on *multimodal* inputs including SAR or elevation would
change the Q1 answer — but then the new information is the SAR or the elevation, assessed in
§3.7 and §3.8, and the foundation model is the packaging.

**Architecturally novel; makes constraint (a) worse, not better.**

## 3.5 Vision-language models

**Q1 — new information? No.** A VLM reads rendered pixels and emits text. The pixels are the
same pixels, usually RGB only, which discards the SWIR bands BSI depends on.

**Q2 — survives? No, and there is a ceiling argument specific to this project.**

The evaluation infrastructure exists — VRSBench provides 29,614 images with human-verified
captions, 52,472 object references and 123,221 question-answer pairs — which is what makes
it possible to say that fine-grained remote-sensing understanding is an open benchmark
problem rather than a solved one.

> Li, X., Ding, J. & Elhoseiny, M. (2024). VRSBench: A Versatile Vision-Language Benchmark
> Dataset for Remote Sensing Image Understanding. *arXiv:2406.12384*.
> DOI: [10.48550/arXiv.2406.12384](https://doi.org/10.48550/arxiv.2406.12384)

The decisive objection is not benchmark scores. It is that **a VLM's ceiling on this task is
human photo-interpretation of a top-down view, and this project has already documented that
that ceiling is below the task.** `docs/labelling_protocol.md`, written for human raters,
states it directly:

> "When the top-down view shows a building you CANNOT tell occupied from abandoned."

The protocol's own remedy is Street View, a business listing search, and a `low` confidence
flag for "genuinely unresolvable cases." A model given only the top-down view inherits the
unresolvable cases and, unlike the human protocol, has no `low` confidence discipline unless
one is built. Asking a VLM "is this brownfield?" on a 28-pixel patch invites a fluent answer
to a question the pixels do not contain.

**Architecturally novel; addresses neither constraint.**

## 3.6 Graph neural networks

**Q1 — new information? Partly, but not new *measurement*.** A GNN adds relational and
topological structure — adjacency, neighbourhood composition, distance to road or rail,
containment within an industrial estate. That is genuinely a different kind of information
from per-pixel spectra, and it is the kind of context Xu & Ehlers's rule-based fusion
exploits by hand. But it is *derived* from data already held (OSM, boundaries, candidate
geometry), not sensed anew.

**Q2 — survives? No, and there is a prerequisite this project does not meet.**

- **A GNN over parcels needs parcel geometry.** The register stores **point locations**.
  Candidate footprints exist (migration 003) but are traced pixel blobs, not cadastral
  parcels — and notebook 08 records that their centroids move enough between dates that a
  50 m tolerance was needed to match a site to itself. There is no node set.
- **Context does not resolve the vegetation ambiguity.** Preston et al. (2023) found the
  *most* vegetated brownfield types are those "traditionally perceived as difficult to
  develop." A derelict vegetated plot inside an industrial estate and an amenity green space
  inside the same estate share their graph neighbourhood. The edges are the same; only the
  node's own status differs, which is what cannot be measured.
- **Scale is untouched.** Node features would be aggregated from the same 7 pixels.

The related object-based literature — Zhang et al. (2018) on object-based CNNs for urban
land use — shows contextual and object framing helping *land use* classification, but land
use is not occupancy, and that work runs on aerial imagery far finer than 20 m.

> Zhang, C., Sargent, I., Pan, X., Li, H., Gardiner, A., Hare, J. et al. (2018). An
> object-based convolutional neural network (OCNN) for urban land use classification.
> *Remote Sensing of Environment*, 216, 57–70.
> DOI: [10.1016/j.rse.2018.06.034](https://doi.org/10.1016/j.rse.2018.06.034)

**Architecturally novel; addresses neither constraint as the data currently stands.**

## 3.7 SAR — Sentinel-1

**Q1 — new information? Yes, genuinely.** This is one of only two approaches here that adds
physics rather than processing. C-band SAR measures backscatter, which responds to surface
roughness, geometry and dielectric constant (chiefly moisture) — none of which optical
reflectance measures. It sees through cloud and at night, and double-bounce returns from
vertical structures give a structural cue optical bands do not carry.

Goga et al. (2019), reviewing 73 abandonment-mapping studies, find "the benefit of the
fusion of optical and radar data, which supports the application of Sentinel-1 and
Sentinel-2 data" to be evident. That is a real, reviewed finding, and it is the strongest
external support for adding SAR.

**Q2 — survives? No. It fails constraint (a) at essentially the same point Sentinel-2 does.**

Sentinel-1 IW GRD has a spatial resolution of approximately **20 × 22 m**, resampled to
10 m pixel spacing. Pixel spacing is not resolution. The median register site is **6.4
resolution cells** — marginally *worse* than the 7 cells it occupies in Sentinel-2's 20 m
SWIR bands, which is exactly the band pair that produced the 0-of-352 result.

Three further degradations apply and all push the same way:

- **Speckle.** SAR intensity carries multiplicative noise; usable estimates require
  multi-looking or temporal averaging, both of which trade resolution or time for precision.
  Effective resolution for a stable per-site backscatter estimate is coarser than nominal.
- **Geometry.** Layover, foreshortening and shadow in a built-up area displace and occlude
  returns near structures — which is where brownfield sits.
- **Mixed pixels dominate.** At six cells, boundary pixels are most of the site.

On constraint (b), SAR is the most defensible of the ten after LiDAR: rubble, hardstanding
and colonising scrub differ in roughness and moisture in ways greenness does not capture, so
a vegetated derelict plot need not look like a vegetated amenity plot in backscatter. **But
no located study demonstrates this discrimination at sub-hectare scale in a UK urban
setting**, and Goga et al.'s fusion finding comes from agricultural abandonment at field
scale. Treat the constraint-(b) argument as plausible and unproven.

**Verdict: adds real new signal; fails the scale constraint. It does not become promising by
being fused with the optical data that already fails.**

## 3.8 LiDAR

**Q1 — new information? Yes, and of a different order from everything else here.** LiDAR
measures three-dimensional structure directly: ground elevation, surface elevation, and by
subtraction the height of everything on the ground. No optical index recovers this.

**Q2 — survives? Yes — this is the only approach of the ten that does.**

**On constraint (a), the margin is not close.** The Environment Agency's National LiDAR
Programme provides **1 m** elevation data for **~99% of England**, flown in winter across
302 survey blocks between January 2017 and February 2023, delivered as GeoTIFF in 5 km tiles
on the OS National Grid, with individual surveys at **±15 cm RMSE** vertical accuracy, under
open licence.

> Environment Agency. *National LIDAR Programme* / LIDAR Composite DTM and DSM, 1 m.
> https://environment.data.gov.uk/dataset/2e8d0733-4f43-48b4-9e51-631c25d1b0a9 ·
> [DTM on data.gov.uk](https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m)
>
> *Coverage, resolution, tiling, date range and vertical accuracy taken from dataset
> descriptions via search-result summaries; the environment.data.gov.uk pages could not be
> fetched directly from this environment. Licence stated as open with "no public access
> constraints" — the exact licence text was not read and should be confirmed before use.*

At 1 m the median register site is **2,800 cells**, the detection floor is 2,000, and a
lower-quartile 0.10 ha site is still **1,000 cells**. The 38.5% of the register that is
undetectable at 20 m is comfortably resolved. This is a three-orders-of-magnitude change in
sampling density, not an incremental one.

**On constraint (b), it attacks the problem at its root.** Preston et al.'s finding is that
half of brownfield is *vegetated*, so optical sensors see grass. LiDAR does not measure
greenness. DSM minus DTM gives vegetation height; the DTM gives the ground surface *beneath*
that vegetation. Foundations, slabs, platforms, loading aprons, spoil heaps, filled cuttings
and demolition rubble are topographic objects that persist under grass and scrub. This
matters especially because the NPPF definition of previously developed land turns on whether
land "is or was occupied by a permanent structure … and any associated fixed surface
infrastructure" — a question about *former structure*, which is structural, not spectral.
`docs/labelling_protocol.md` Step 1 already asks raters exactly this: "Was there ever a
permanent structure or lawful hardstanding here?"

**Failure modes, stated as fully as the case for it.**

- **It measures structure, not occupancy.** This is the central limitation and it is the
  same wall Sun et al. (2023) hit: a maintained active lorry yard and an abandoned one are
  both flat hardstanding. LiDAR can establish that land *was developed*; it cannot establish
  that it is *no longer in use*. That distinction is what the product needs, and LiDAR does
  not supply it.
- **Single-epoch, so no change detection.** The National LiDAR Programme composite is one
  pass per block over 2017–2023. **Not verified:** whether repeat coverage exists over
  Stoke-on-Trent from legacy Environment Agency surveys, which historically concentrated on
  flood-risk areas. Without two epochs there is no build-out or clearance signal.
- **Currency.** A block flown in 2017 is nine years stale; one flown in 2023 is three. Sites
  cleared or developed since are misrepresented, and the survey date varies by block.
- **It is not satellite data, and it is England-only.** Adopting it changes the project's
  premise from satellite detection to national-elevation-data analysis. Wales and Scotland
  have separate programmes with different coverage and terms; UK-wide expansion, already
  shelved, would need re-planning around three data regimes.
- **No published accuracy for this task.** No located study reports detecting unregistered
  derelict PDL from LiDAR in a UK city. The case above is an argument from sensor
  characteristics and the NPPF definition, not a result read off a paper. It is the same
  class of claim this review criticised elsewhere in the repository, and it should be held
  to the same standard.

**Verdict: the only approach of the ten that adds new information and survives the scale
constraint. It does not, on its own, solve the active-versus-abandoned problem.**

## 3.9 Parcel-level temporal embeddings

**Q1 — new information? No.** These encode a Sentinel-2 time series per parcel. Same sensor,
same bands, same revisit.

**Q2 — survives? No, on three counts.**

The reference method is Garnot et al. (2020), whose Pixel-Set Encoder deliberately discards
spatial arrangement and treats a parcel as an unordered *set* of pixels, with temporal
self-attention across dates. It was designed for agricultural parcel classification.

> Sainte Fare Garnot, V., Landrieu, L., Giordano, S. & Chehata, N. (2020). Satellite Image
> Time Series Classification with Pixel-Set Encoders and Temporal Self-Attention. *CVPR
> 2020*. DOI: [10.1109/CVPR42600.2020.01234](https://doi.org/10.1109/cvpr42600.2020.01234) ·
> [arXiv:1911.07757](https://arxiv.org/pdf/1911.07757)
>
> Miller, L., Pelletier, C. & Webb, G. I. (2024). Deep Learning for Satellite Image
> Time-Series Analysis: A Review. *IEEE Geoscience and Remote Sensing Magazine*.
> DOI: [10.1109/MGRS.2024.3393010](https://doi.org/10.1109/mgrs.2024.3393010)

- **It needs parcels, and this project has none.** The register is points; candidates are
  pixel blobs. The method's unit of analysis does not exist in the data.
- **The pixel set is too small to be a set.** PSE samples pixels from within a parcel to
  build a statistical descriptor. At seven pixels in the 20 m bands — and 2.5 at the lower
  quartile — there is no distribution to sample; sub-sampling degenerates and boundary
  mixing dominates. Agricultural parcels, the design target, are typically one to two orders
  of magnitude larger.
- **The temporal signal is the one Option C already found wanting.** A vegetated derelict
  parcel and a vegetated amenity parcel have similar annual NDVI trajectories. Preston et
  al. (2023) is the direct evidence: the vegetation is real vegetation.

**Architecturally novel; addresses neither constraint.**

## 3.10 Agentic data fusion

**Q1 — new information? No. It is not a sensing method at all.** An agentic pipeline
orchestrates retrieval and combination of sources. Its output is bounded entirely by the
sources it orchestrates.

**Q2 — not applicable in the form asked.** There is no resolution and no spectral response
to assess.

**No literature was located** evaluating agentic fusion for derelict-land detection, or for
any comparable remote-sensing detection task, with a reported accuracy. That absence is
itself the finding: this is an engineering pattern currently without an evidence base for
this problem.

The honest formulation is that agentic fusion is a *multiplier on whatever signal exists*.
If occupancy data (Part 2, Option B) or LiDAR (§3.8) carries signal, an agent can help
assemble it. If, as notebook 09 established, the optical signal is absent, an agent
assembling absent signal more fluently produces confident output from nothing — which, given
this project's history with the 100 m proximity match, is a demonstrated failure mode rather
than a hypothetical one.

**Not a sensing method. Adds no information.**

## 3.11 Multimodal transformers

**Q1 — new information? Only if the modalities do.** A multimodal transformer is a fusion
architecture. Its Q1 answer is inherited entirely from what is fused. Optical + optical adds
nothing. Optical + SAR adds §3.7's signal and inherits §3.7's scale failure. Optical + LiDAR
adds §3.8's signal and inherits §3.8's occupancy limitation.

**Q2 — survives? Inherited, and degraded by the token problem.** Per §3.0, at 10 m a 16×16
token covers 2.56 ha and the median site is 10.9% of one token. Fusing a 1 m LiDAR stream
with a 20 m optical stream in one transformer also raises a resampling question: harmonising
to the coarser grid discards the resolution that made LiDAR viable, and harmonising to the
finer one interpolates optical data that was never measured at that scale.

Huo et al. (2025) survey heterogeneous and multimodal foundation models and conclude the
field remains "far from practical applications" on account of data, model and task
challenges.

**Architecture, not evidence. It cannot make a modality informative that is not.**

---

## 3.12 What this leaves, stated plainly

- **Eight of the ten are different ways of processing the same photons.** Anomaly detection,
  SSL, foundation models, VLMs, GNNs, parcel temporal embeddings, agentic fusion and
  multimodal transformers add no new physical measurement. Notebook 09 established that the
  register and the urban background are superimposed in the space those photons span. A
  better model of an uninformative feature space returns a better-calibrated null.
- **Two add real information: SAR and LiDAR.**
- **Only LiDAR survives the scale constraint**, and by three orders of magnitude rather than
  by a margin.
- **LiDAR still does not answer the product's actual question.** It establishes that land
  was developed. It does not establish that it is unused. That is the same wall Sun et al.
  (2023) described and resolved with non-image occupancy data, and the same wall Part 2
  Option B describes.
- **The two constraints are not equally binding.** Constraint (a) is a hard limit that only
  a finer sensor removes. Constraint (b) is not a resolution problem at all — Preston et al.
  find brownfield genuinely *is* vegetated, so no amount of resolution makes it look
  different from other vegetation. Only a sensor measuring something other than colour, or
  data that is not imagery, addresses (b).

## 3.13 Flags and limits of this assessment

- **The anomaly-detection argument is internal.** It rests on notebook 09's measurement, not
  on published anomaly-detection literature; no on-point reference was located.
- **The LiDAR case is an argument from sensor specification, not a result.** No study was
  found detecting unregistered derelict PDL from LiDAR in a UK city. It should not be quoted
  as though it had a reported accuracy.
- **EA LiDAR metadata is second-hand.** Coverage, dates, tiling and accuracy come from
  dataset-description summaries; environment.data.gov.uk was not reachable directly. The
  licence is described as open but the exact terms were not read.
- **Repeat LiDAR coverage over Stoke is unverified**, and it determines whether any change
  detection is possible.
- **Transformer patch size 16 is assumed**, not read from each model's configuration.
- **Prithvi is one foundation model among many.** Models pre-trained natively at 10 m, or on
  SAR and elevation jointly, exist and were not individually assessed; the Q1 logic in §3.4
  applies to them, but their specific resolutions were not checked.
- **SAR's constraint-(b) argument is plausible and unproven.** No located study demonstrates
  roughness-based discrimination of derelict from amenity vegetation at sub-hectare scale in
  a UK city.
- **Search method.** OpenAlex, Crossref and Semantic Scholar by keyword and citation, plus
  targeted web search. Not a systematic review. Absence of a result here is weak evidence of
  absence in the literature.

## 3.14 References added in Part 3

10. Environment Agency. *National LIDAR Programme* (LIDAR Composite DTM/DSM, 1 m).
    https://environment.data.gov.uk/dataset/2e8d0733-4f43-48b4-9e51-631c25d1b0a9
11. Huo, C., Chen, K., Zhang, S., Wang, Z., Yan, H., Shen, J. et al. (2025). When Remote Sensing
    Meets Foundation Model: A Survey and Beyond. *Remote Sensing*, 17(2), 179.
    https://doi.org/10.3390/rs17020179
12. Jakubik, J. et al. (2023). Foundation Models for Generalist Geospatial Artificial
    Intelligence. *arXiv:2310.18660*. https://doi.org/10.48550/arxiv.2310.18660
13. Li, X., Ding, J. & Elhoseiny, M. (2024). VRSBench: A Versatile Vision-Language Benchmark
    Dataset for Remote Sensing Image Understanding. *arXiv:2406.12384*.
    https://doi.org/10.48550/arxiv.2406.12384
14. Mañas, O., Lacoste, A., Giró-i-Nieto, X., Vázquez, D. & Rodríguez, P. (2021). Seasonal
    Contrast: Unsupervised Pre-Training from Uncurated Remote Sensing Data. *ICCV 2021*,
    9394–9403. https://doi.org/10.1109/iccv48922.2021.00928
15. Miller, L., Pelletier, C. & Webb, G. I. (2024). Deep Learning for Satellite Image
    Time-Series Analysis: A Review. *IEEE Geoscience and Remote Sensing Magazine*.
    https://doi.org/10.1109/mgrs.2024.3393010
16. Sainte Fare Garnot, V., Landrieu, L., Giordano, S. & Chehata, N. (2020). Satellite Image
    Time Series Classification with Pixel-Set Encoders and Temporal Self-Attention. *CVPR
    2020*. https://doi.org/10.1109/cvpr42600.2020.01234
17. Yuan, Y. & Lin, L. (2020). Self-Supervised Pretraining of Transformers for Satellite
    Image Time Series Classification. *IEEE JSTARS*, 14, 474–487.
    https://doi.org/10.1109/jstars.2020.3036602
18. Zhang, C., Sargent, I., Pan, X., Li, H., Gardiner, A., Hare, J. et al. (2018). An
    object-based convolutional neural network (OCNN) for urban land use classification.
    *Remote Sensing of Environment*, 216, 57–70. https://doi.org/10.1016/j.rse.2018.06.034
