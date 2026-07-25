"""
make_persistent_labels_3of4.py - Label the 3-of-4 persistence band (#46).
=========================================================================
Companion to make_persistent_labels.py. That script handles the 4-of-4 set
(20 sites, all labelled, 0 sellable). This one produces the sheet for the
candidates bare on EXACTLY 3 of 4 dates - the 15 sites nobody has looked at.

WHY THIS MATTERS (the reasoning behind #46)
-------------------------------------------
The 4-of-4 all-seasons filter selected for permanence: things bare every single
date are maintained hardstanding, not derelict land. A 3-of-4 site is bare in
three seasons and VEGETATED in one - which is the signature of land left alone
long enough for weeds to grow and die back. That is what derelict ground does.
Tarmac never greens; neglected land does.

Issue #46's own acceptance criterion specifies k-of-N with a default of k=3 of
N=4. The 4-of-4 analysis used all-of-4 and never tested this band. If any of
these 15 are sellable, the persistence finding changes from "0/19, approach
dead" to "the threshold was wrong, not the approach".

This is the cheapest remaining detection experiment. One WHERE clause and an
afternoon of labelling against aerial imagery.

USAGE
-----
    python scripts/make_persistent_labels_3of4.py

Writes outputs/persistent_labels_3of4.csv with the ~15 candidates that are bare
on exactly 3 of the 4 dates (excluding the 4-of-4 set already labelled). Same
vocabulary and same label-against-Google-satellite loop as the 4-of-4 sheet.
Re-running preserves labels already entered.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_query import get_db_connection

GSS = "E06000021"
WINTER = "2025-12-26"
MATCH_M = 50
DATES_PRESENT = 3  # exactly-3-of-4 band
OUT = Path(__file__).parent.parent / "outputs" / "persistent_labels_3of4.csv"

VALID_LABELS = {
    "sellable",
    "active_industrial",
    "active_institutional",
    "active_retail",
    "construction",
    "heritage_constrained",
    "car_park",
    "railway",
    "road_verge",
    "canal",
    "agriculture",
    "quarry",
    "water",
    "unclear",
}

# Same anchored subquery as the 4-of-4 sheet, but selecting candidates whose
# distinct-date count is EXACTLY DATES_PRESENT rather than 4. Anchored on winter
# for consistency with the 4-of-4 analysis. Unregistered only.
QUERY = """
    SELECT w.id, w.utm_x, w.utm_y,
           ROUND((w.pixel_count * 0.04)::numeric, 2) AS hectares,
           ROUND(w.compactness::numeric, 3)          AS compactness
    FROM candidate_sites w
    WHERE w.gss_code = %s AND w.image_date = %s
      AND w.matched_site_reference IS NULL
      AND (SELECT COUNT(DISTINCT o.image_date)
             FROM candidate_sites o
            WHERE o.gss_code = w.gss_code
              AND ST_DWithin(
                    ST_SetSRID(ST_MakePoint(o.utm_x, o.utm_y), 32630),
                    ST_SetSRID(ST_MakePoint(w.utm_x, w.utm_y), 32630),
                    %s)) = %s
    ORDER BY w.pixel_count DESC
"""

FIELDS = [
    "candidate_id",
    "hectares",
    "compactness",
    "dates_present",
    "maps_url",
    "label",
    "site_name",
    "notes",
]


def load_existing() -> dict:
    if not OUT.exists():
        return {}
    rows = {}
    with open(OUT, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            label = (row.get("label") or "").strip()
            if label:
                rows[int(float(row["candidate_id"]))] = (
                    label,
                    row.get("site_name", "") or "",
                    row.get("notes", "") or "",
                )
    return rows


def main() -> None:
    existing = load_existing()
    if existing:
        print(f"preserving {len(existing)} label(s) already in the sheet")

    transformer = Transformer.from_crs("EPSG:32630", "EPSG:4326", always_xy=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(QUERY, (GSS, WINTER, MATCH_M, DATES_PRESENT))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    written = 0

    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for cand_id, utm_x, utm_y, hectares, compactness in rows:
            if cand_id in existing:
                label, site_name, notes = existing[cand_id]
            else:
                label = site_name = notes = ""

            if label and label not in VALID_LABELS:
                raise ValueError(
                    f"candidate {cand_id} has label {label!r}, not in vocabulary. "
                    f"Valid: {sorted(VALID_LABELS)}"
                )

            lon, lat = transformer.transform(utm_x, utm_y)
            writer.writerow(
                {
                    "candidate_id": cand_id,
                    "hectares": hectares,
                    "compactness": compactness,
                    "dates_present": DATES_PRESENT,
                    "maps_url": (
                        f"https://www.google.com/maps/@{lat:.6f},{lon:.6f},"
                        f"250m/data=!3m1!1e3"
                    ),
                    "label": label,
                    "site_name": site_name,
                    "notes": notes,
                }
            )
            written += 1
            if label:
                counts[label] += 1

    done = sum(counts.values())
    print(f"wrote {OUT}")
    print(
        f"  {written} unregistered candidates bare on exactly {DATES_PRESENT} of 4 dates"
    )
    print(f"  {done} labelled, {written - done} outstanding")

    if counts:
        print("\n  class breakdown:")
        for label, n in counts.most_common():
            print(f"    {label:<22} {n}")
        sellable = counts.get("sellable", 0)
        print(f"\n  precision: {sellable}/{done} = {100 * sellable / done:.1f}%")
        if sellable:
            print("\n  >>> NON-ZERO SELLABLE IN THE 3-OF-4 BAND <<<")
            print("  This is the result that would change the finding. The 4-of-4")
            print("  band was 0/19; a positive here means the all-seasons threshold")
            print("  was too strict, not that the approach is dead. Worth pursuing.")


if __name__ == "__main__":
    main()
