"""
persistence_filter.py - Require candidates to persist across image dates.
=========================================================================
P1-4: transient bare soil (ploughed fields, construction phases, temporary
works) appears in one image and vanishes in the next; genuine brownfield
stays bare across seasons. This filter drops candidates from the current
run that have no supporting detection near the same location in a stored
run for a DIFFERENT image date.

The check runs against candidate_sites rows already in the database, so
temporal persistence costs nothing beyond running the pipeline on more than
one image date for the council. If the database holds no prior dates for
the council, the filter passes everything through with a warning rather
than destroying the first run — persistence cannot be required without
history.

Proximity uses centroid distance (ST_DWithin on stored utm_x/utm_y), which
works with or without the FND-3 geometry column and is robust to small
centroid drift between dates.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Candidates within this distance (metres) of a prior-date detection are
# considered the same persistent site. One 20m pixel of drift each way.
PERSISTENCE_DISTANCE_M = 50.0


def count_prior_detection_dates(
    utm_x: float,
    utm_y: float,
    gss_code: str,
    image_date: str,
    connection,
    distance_m: float = PERSISTENCE_DISTANCE_M,
) -> int:
    """
    Counts the distinct prior image dates on which a stored candidate exists
    within distance_m of the given location for the council. The current
    image date is excluded so a run never supports itself.

    Args:
        utm_x (float): Candidate centroid easting in EPSG:32630.
        utm_y (float): Candidate centroid northing in EPSG:32630.
        gss_code (str): GSS code for the council being processed.
        image_date (str): Current image date (YYYY-MM-DD) — excluded.
        connection: Active psycopg2 connection.
        distance_m (float): Match radius in metres.

    Returns:
        int: Number of distinct other image dates with a detection nearby.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(DISTINCT image_date)
        FROM candidate_sites
        WHERE gss_code = %s
          AND image_date <> %s
          AND ST_DWithin(
                ST_SetSRID(ST_MakePoint(utm_x, utm_y), 32630),
                ST_SetSRID(ST_MakePoint(%s, %s), 32630),
                %s
              )
        """,
        (gss_code, image_date, utm_x, utm_y, distance_m),
    )
    count = cursor.fetchone()[0]
    cursor.close()
    return int(count)


def filter_candidates_by_persistence(
    site_properties: list,
    gss_code: str,
    image_date: str,
    connection,
    min_prior_dates: int = 1,
    distance_m: float = PERSISTENCE_DISTANCE_M,
) -> tuple:
    """
    Drops candidates lacking a nearby stored detection on at least
    min_prior_dates other image dates. If the database does not hold
    min_prior_dates other dates for the council at all, the filter is
    skipped (all candidates kept, 0 dropped) and a warning printed —
    otherwise the first run for a council would erase itself.

    Args:
        site_properties (list): Candidate property dicts from the current run
                                (post-exclusion), each with centroid_utm_x/y.
        gss_code (str): GSS code for the council being processed.
        image_date (str): Current image date (YYYY-MM-DD).
        connection: Active psycopg2 connection.
        min_prior_dates (int): Distinct other image dates required. Default 1.
        distance_m (float): Match radius in metres.

    Returns:
        tuple:
            kept (list): Surviving site_properties dicts, in input order.
            dropped_count (int): Number of candidates removed.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(DISTINCT image_date)
        FROM candidate_sites
        WHERE gss_code = %s AND image_date <> %s
        """,
        (gss_code, image_date),
    )
    prior_dates_available = cursor.fetchone()[0]
    cursor.close()

    if prior_dates_available < min_prior_dates:
        print(
            f"Persistence filter skipped — only {prior_dates_available} prior "
            f"image date(s) stored for {gss_code}, {min_prior_dates} required. "
            f"Run the pipeline on more dates to enable persistence."
        )
        return site_properties, 0

    kept = []
    dropped_count = 0
    for site in site_properties:
        prior = count_prior_detection_dates(
            site["centroid_utm_x"],
            site["centroid_utm_y"],
            gss_code,
            image_date,
            connection,
            distance_m=distance_m,
        )
        if prior >= min_prior_dates:
            kept.append(site)
        else:
            dropped_count += 1
    return kept, dropped_count
