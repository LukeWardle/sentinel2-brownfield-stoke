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
