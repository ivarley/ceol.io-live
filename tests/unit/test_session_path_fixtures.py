"""session_path.py against the web's own cases (frontend/src/shared/sessionpath.fixtures.json).

The path check lives in three places: here (the authority), the web's forms and the iOS
app's (both inline, before the round trip). All three read the same fixture file, so a
path one of them accepts and another refuses shows up as a failing case, not as a
session saved from one client that the other calls broken.
"""

import json
import os

import pytest

from session_path import normalize_session_path

FIXTURES = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "frontend",
    "src",
    "shared",
    "sessionpath.fixtures.json",
)

with open(FIXTURES) as f:
    CASES = json.load(f)["functions"]["normalizeSessionPath"]["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_matches_the_web(case):
    path, error = normalize_session_path(case["input"].get("value"))
    assert {"path": path, "error": error} == case["expected"]
