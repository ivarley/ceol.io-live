"""The front-end registry."""

from lab.frontends.base import FrontEnd  # noqa: F401
from lab.frontends.basicpitch import BasicPitchFrontEnd
from lab.frontends.crepetrack import CrepeFrontEnd
from lab.frontends.pestotrack import PestoFrontEnd
from lab.frontends.salience import SalienceCleaned, SalienceMelody, SalienceViterbi
from lab.frontends.trackers import PyinCleaned, PyinFrontEnd, YinCleaned, YinFrontEnd

REGISTRY = {c.name: c for c in (
    PyinFrontEnd, YinFrontEnd, PyinCleaned, YinCleaned,
    SalienceMelody, SalienceCleaned, SalienceViterbi, BasicPitchFrontEnd, PestoFrontEnd,
    CrepeFrontEnd,
)}

# Named here so the gap is visible on the leaderboard rather than in a plan.
UNBUILT = {
    "rmvpe": "a vocal melody over accompaniment; the polyphonic-aware tracker not yet tried",
}


def get_frontend(name, **params):
    if name not in REGISTRY:
        hint = f"; not built yet: {sorted(UNBUILT)}" if name in UNBUILT else ""
        raise SystemExit(f"unknown front end '{name}'; have {sorted(REGISTRY)}{hint}")
    return REGISTRY[name](**params)
