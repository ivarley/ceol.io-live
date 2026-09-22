"""The front-end registry."""

from lab.frontends.base import FrontEnd  # noqa: F401
from lab.frontends.salience import SalienceCleaned, SalienceMelody, SalienceViterbi
from lab.frontends.trackers import PyinCleaned, PyinFrontEnd, YinCleaned, YinFrontEnd

REGISTRY = {c.name: c for c in (
    PyinFrontEnd, YinFrontEnd, PyinCleaned, YinCleaned,
    SalienceMelody, SalienceCleaned, SalienceViterbi,
)}

# Named here so the gap is visible on the leaderboard rather than in a plan.
UNBUILT = {
    "basic_pitch": "polyphonic neural note transcription; emits note events directly",
    "crepe": "neural but monophonic, so likely the same failure as pyin, more robustly",
}


def get_frontend(name, **params):
    if name not in REGISTRY:
        hint = f"; not built yet: {sorted(UNBUILT)}" if name in UNBUILT else ""
        raise SystemExit(f"unknown front end '{name}'; have {sorted(REGISTRY)}{hint}")
    return REGISTRY[name](**params)
