# tests/conftest.py
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _seed_numpy():
    """Deterministic RNG for every test - prevents seed-dependent flakiness."""
    np.random.seed(0)


@pytest.fixture(scope="session", autouse=True)
def _seed_council_boundary():
    """Ensure the Stoke-on-Trent (E06000021) council boundary exists so that
    DB-backed tests can insert child rows (exclusion_zones, candidate_sites,
    brownfield_sites) without tripping the gss_code foreign key.

    On a developer machine the boundary is usually already loaded, so this is
    a no-op guarded by ON CONFLICT. On a fresh CI database it seeds a minimal
    real polygon around Stoke (enough for FK satisfaction and bbox derivation)
    committed for the session, then removes it and its child rows at the end.

    Only E06000021 is seeded; tests that assert a missing-boundary ValueError
    use a different GSS code (e.g. E09999999) and remain valid.
    """
    from src.database_query import get_db_connection

    try:
        conn = get_db_connection()
    except Exception:
        # No database available (pure-unit CI job) - nothing to seed.
        yield
        return

    cur = conn.cursor()
    # Did the boundary already exist before we touched it? If so, leave it alone.
    cur.execute("SELECT 1 FROM council_boundaries WHERE gss_code = 'E06000021'")
    pre_existing = cur.fetchone() is not None

    if not pre_existing:
        cur.execute("""
            INSERT INTO council_boundaries (gss_code, name, boundary)
            VALUES (
                'E06000021',
                'Stoke-on-Trent',
                ST_GeomFromText(
                    'POLYGON((-2.25 52.95, -2.05 52.95, -2.05 53.10, -2.25 53.10, -2.25 52.95))',
                    4326
                )
            )
            ON CONFLICT (gss_code) DO NOTHING
            """)
        conn.commit()

    cur.close()
    yield

    # Teardown: only remove what we added, and only if we added it.
    if not pre_existing:
        cur = conn.cursor()
        # Remove child rows first (FK), then the boundary itself.
        cur.execute("DELETE FROM candidate_sites WHERE gss_code = 'E06000021'")
        cur.execute("DELETE FROM exclusion_zones WHERE gss_code = 'E06000021'")
        cur.execute("DELETE FROM brownfield_sites WHERE gss_code = 'E06000021'")
        cur.execute("DELETE FROM council_boundaries WHERE gss_code = 'E06000021'")
        conn.commit()
        cur.close()
    conn.close()
