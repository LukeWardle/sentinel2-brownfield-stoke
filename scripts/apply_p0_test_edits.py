"""
apply_p0_test_edits.py - Anchored edits to existing test files for P0-7,
P0-8/P0-10. Run from the repo root AFTER copying the new src/ files in:

    python scripts/apply_p0_test_edits.py

Edits (each verified present before applying; the script fails loudly on
any missing anchor rather than guessing):

tests/test_clustering.py (P0-7 — X_reduced parameter removed):
  - helper make_simple_mask_and_xreduced returns (mask, original_shape)
  - unpack sites updated to two names
  - inline X_reduced creations deleted
  - every group_pixels_for_candidate_sites call drops the X argument

tests/test_fnd_regressions.py (P0-7):
  - _synthetic_scene returns a 5-tuple (X_reduced dropped)
  - all unpacks and calls updated

tests/test_main.py (P0-10 auth bundle):
  - src.main.get_access_token patch -> src.main.authenticate returning a
    token bundle dict, so main's auth["access_token"] works under mock
"""

import re
import sys
from pathlib import Path


def edit_file(path, fixed_replacements, regex_replacements=(), delete_line_regexes=()):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n")

    for old, new, expected in fixed_replacements:
        count = text.count(old)
        if count < expected:
            print(f"FAIL {path}: expected >= {expected} of anchor, found {count}:")
            print(f"      {old[:70]!r}")
            sys.exit(1)
        text = text.replace(old, new)
        print(f"  {path}: replaced {count} x {old[:50]!r}")

    for pattern, repl in regex_replacements:
        text, count = re.subn(pattern, repl, text)
        print(f"  {path}: regex {pattern[:40]!r} -> {count} replacement(s)")

    for pattern in delete_line_regexes:
        text, count = re.subn(pattern, "", text, flags=re.MULTILINE)
        print(f"  {path}: deleted {count} line(s) matching {pattern[:40]!r}")

    p.write_text(text, encoding="utf-8", newline="\n")


# ---------------- tests/test_clustering.py ----------------
edit_file(
    "tests/test_clustering.py",
    fixed_replacements=[
        (
            "    n_valid = mask.sum()\n"
            "    X_reduced = np.random.rand(n_valid, 3)\n"
            "    return mask, X_reduced, original_shape",
            "    return mask, original_shape",
            1,
        ),
        (
            "mask, X_reduced, original_shape = make_simple_mask_and_xreduced()",
            "mask, original_shape = make_simple_mask_and_xreduced()",
            1,  # at least one; replace() handles all occurrences
        ),
        ("X_reduced, mask,", "mask,", 1),
    ],
    regex_replacements=[
        # multiline call style:  X_reduced,\n        mask,
        (r"X_reduced,\s*\n(\s*)mask,", r"\1mask,"),
    ],
    delete_line_regexes=[
        r"^\s*X_reduced = np\..*\n",
    ],
)

# ---------------- tests/test_fnd_regressions.py ----------------
edit_file(
    "tests/test_fnd_regressions.py",
    fixed_replacements=[
        (
            "Returns (X_reduced, mask, original_shape, bsi, ndvi, candidate_flat_indices).",
            "Returns (mask, original_shape, bsi, ndvi, candidate_flat_indices).",
            1,
        ),
        (
            "return X_reduced, mask, original_shape, bsi, ndvi, set(candidate_flat)",
            "return mask, original_shape, bsi, ndvi, set(candidate_flat)",
            1,
        ),
        ("X, mask, shape", "mask, shape", 1),
    ],
    delete_line_regexes=[
        r"^\s*X_reduced = np\..*\n",
    ],
)

# ---------------- tests/test_main.py ----------------
edit_file(
    "tests/test_main.py",
    fixed_replacements=[
        (
            '"src.main.get_access_token": MagicMock(return_value=mock_data["token"]),',
            '"src.main.authenticate": MagicMock(\n'
            "            return_value={\n"
            '                "access_token": mock_data["token"],\n'
            '                "refresh_token": "refresh",\n'
            '                "expires_at": 9.9e9,\n'
            "            }\n"
            "        ),",
            1,
        ),
        (
            'mocks["src.main.get_access_token"].assert_called_once()',
            'mocks["src.main.authenticate"].assert_called_once()',
            1,
        ),
    ],
)

print()
print("All test edits applied. Run: python -m pytest tests/ -q")
