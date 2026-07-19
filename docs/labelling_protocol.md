# SiteSignal — Ground-Truth Labelling Protocol

## Purpose and scope
This protocol lets a consistent observer classify candidate sites against a
documented rule set, for measuring detector precision on unregistered candidates.
It is a **screening protocol, not a statutory planning determination**. A
planning-literate second rater validating a subset is what confirms it (see
Inter-rater check).

## Controlling definition
The live framework is the **December 2024 NPPF**. Previously developed land (PDL,
"brownfield") is land lawfully developed that is or was occupied by a permanent
structure plus its associated fixed surface infrastructure and curtilage; the
Dec 2024 revision also brings large areas of lawfully-developed hardstanding into
the definition (glasshouses were not included).

Excluded from PDL: land last occupied by agricultural or forestry buildings;
minerals-extraction or landfill sites where restoration is provided for through
planning procedures; residential gardens, parks, recreation grounds and allotments
in built-up areas; and land where former structures have blended back into the
landscape. (Note: residential gardens are excluded only when in a built-up area -
a rural garden can be PDL.)

## Label schema (one row per candidate)
- `is_brownfield` (yes/no) - is it PDL per the definition above?
- `is_developable` (yes/no) - is it a vacant/underused opportunity, not in active use?
- `fp_category` - if not a sellable lead, why: car-park | quarry | agriculture |
  construction | infrastructure-utility | active-industrial | recreation-education | other
- `confidence` - high | medium | low
- Provenance: `rater_id`, `label_date`, `imagery_source`, `imagery_date`

## Decision procedure (per site, in order)
**Step 0 - Evidence.** Open current top-down aerial, Street View (note its date),
and search the location for an active business listing. Record imagery source + date.
A recent satellite hit judged against old Street View is a low-confidence label.

**Step 1 - Was there ever a permanent structure or lawful hardstanding here?**
- No (natural ground, fields, scrub, water) -> not brownfield; go to Step 2 to categorise.
- Yes (buildings, foundations, slabs, industrial remains, made hardstanding) -> continue.

**Step 2 - Does an exclusion apply?**
- Only agricultural/forestry buildings -> not brownfield -> fp_category=agriculture
- Quarry / mineral / landfill -> not brownfield -> fp_category=quarry
- Garden/park/rec-ground/allotment in a built-up area -> not brownfield -> fp_category=recreation-education or other
- Former structures fully reclaimed by nature -> not brownfield (blended into landscape)
- None apply -> is_brownfield = yes

**Step 3 - If brownfield=yes, is it a developable opportunity?**
- Active use (working plant, occupied/maintained building, full car park, live depot)
  -> is_developable = no (PDL but in use; set fp_category to the active class, e.g.
  active-industrial, infrastructure-utility, car-park)
- Vacant / derelict / cleared / overgrown / fenced-off, no activity -> is_developable = yes
- Obvious hard constraint (sliver, waterlogged, inside live infrastructure) -> is_developable = no

**Step 4 - Confidence.** high = unambiguous from current imagery; medium = probable;
low = top-down can't resolve active-vs-derelict and Street View is old/missing. Be
liberal with `low` - it is the honest flag on genuinely unresolvable cases.

## False-positive categories - visual cues
- **agriculture** - furrow lines, tramlines, regular field geometry, hedgerow boundaries.
- **quarry** - benched terraces, exposed faces, haul roads, water voids; landfill = capped mounds, gas vents.
- **construction** - machinery, cabins, stockpiles, part-built frames, hoarding, fresh vehicle tracks (activity + new material distinguishes it from dereliction).
- **car-park** - painted bays, marked aisles, parked vehicles, tarmac by retail/stations. (Active = in use, false positive; disused/empty may be a real opportunity.)
- **infrastructure-utility** - sewage/water treatment, substations, depots; bare process surfaces read as high-BSI.
- **active-industrial** - occupied estate units, rooftops, working yards.
- **recreation-education** - school playgrounds/MUGAs, playing fields, parks.
- **other** - anything not covered above; note the reason.

## Key discipline
When the top-down view shows a building you CANNOT tell occupied from abandoned -
you must check Street View and the business listing. That one habit resolves most
of the "I wouldn't know the difference" cases; the rest are marked `low`.

## Inter-rater check
A second rater (ideally planning-literate) independently labels a sampled subset.
Record Cohen's kappa per field. Strong agreement demonstrates the labels track an
informed judgement; divergence flags that the labels aren't yet trustworthy.
