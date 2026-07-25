"""
make_persistent_labels.py - Build the labelling sheet for the persistent set.
=============================================================================
Writes outputs/persistent_labels.csv: one row per UNREGISTERED candidate that
is bare across all four seasonal dates, with a Google Maps satellite link and
a controlled label vocabulary.

Re-running is safe and non-destructive: any label already present in the CSV is
preserved. Only genuinely new rows are added blank. The KNOWN dict below is a
seed for a from-scratch generation and is deliberately limited to candidate IDs
confirmed during the 23 July 2026 session - everything else lives in the CSV.

    python scripts/make_persistent_labels.py

Label vocabulary (put ONE of these in the `label` column):

    sellable              a discrete parcel, no active use, a developer could buy it
    active_industrial     occupied units, depots, works, loading yards
    active_institutional  hospital, school, civic, healthcare
    active_retail         shops, supermarkets, dealerships, retail park
    construction          actively being built on (bare, but already sold)
    heritage_constrained  derelict but designated - scheduled monument, listed
    car_park              surface parking
    railway               track, sidings, embankment
    road_verge            carriageway, verge, roundabout, hardstanding
    canal                 towpath, canal infrastructure
    agriculture           ploughed or fallow farmland
    quarry                extraction, spoil, landfill
    water                 river scour, reservoir margin
    unclear               cannot tell from available imagery

Leave `label` BLANK rather than guessing. Blanks are excluded from the
precision denominator; a wrong label corrupts the headline metric.
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
OUT = Path(__file__).parent.parent / "outputs" / "persistent_labels.csv"

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

# Seed labels from the 23 July 2026 session. Only IDs confirmed explicitly
# during that session are recorded here; the remainder were entered directly
# into the CSV and are preserved on re-run by load_existing().
KNOWN = {
    1362: ("active_institutional", "Royal Stoke University Hospital"),
    1361: ("active_industrial", "Mossfield Road estate - D&G Bus, IAE"),
    1320: ("active_institutional", "Ormiston Horizon Academy"),
    1367: ("active_industrial", "Park Hall Business Village"),
    1371: ("active_industrial", "Fenton - Victoria Industrial Complex"),
    1332: ("active_industrial", "Scotia Business Park, Tunstall"),
    1319: (
        "heritage_constrained",
        "Chatterley Whitfield Colliery - scheduled monument",
    ),
    1375: ("car_park", "bet365 Stadium car park, Sideway"),
    1329: ("active_industrial", "Browns Distribution, Chemical Lane Tunstall"),
}

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
                    %s)) = 4
    ORDER BY w.pixel_count DESC
"""

FIELDS = [
    "candidate_id",
    "hectares",
    "compactness",
    "maps_url",
    "label",
    "site_name",
    "notes",
]


def load_existing() -> dict:
    """Preserve labels already entered so re-running never destroys work."""
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
    cursor.execute(QUERY, (GSS, WINTER, MATCH_M))
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
            # A label already in the sheet always wins over the seeded default.
            if cand_id in existing:
                label, site_name, notes = existing[cand_id]
            elif cand_id in KNOWN:
                label, site_name = KNOWN[cand_id]
                notes = ""
            else:
                label = site_name = notes = ""

            if label and label not in VALID_LABELS:
                raise ValueError(
                    f"candidate {cand_id} has label {label!r}, which is not in the "
                    f"vocabulary. Valid values: {sorted(VALID_LABELS)}"
                )

            lon, lat = transformer.transform(utm_x, utm_y)
            writer.writerow(
                {
                    "candidate_id": cand_id,
                    "hectares": hectares,
                    "compactness": compactness,
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
    print(f"  {written} unregistered persistent candidates")
    print(f"  {done} labelled, {written - done} outstanding")

    if counts:
        print("\n  class breakdown:")
        for label, n in counts.most_common():
            print(f"    {label:<22} {n}")
        sellable = counts.get("sellable", 0)
        print(f"\n  precision: {sellable}/{done} = {100 * sellable / done:.1f}%")


if __name__ == "__main__":
    main()
