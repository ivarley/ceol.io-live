"""name -> expert class, and building a run's experts from its config.

The registry is the only place that knows what exists. An expert is added by
importing it here; nothing else in the engine changes, which is the property
the board is for.
"""

from lab.experts.activity import MusicEnergy
from lab.experts.assembler import Assembler
from lab.experts.boundary import BoundaryNovelty
from lab.experts.follower import Follower
from lab.experts.matcher import Matcher
from lab.experts.notes import Intervals, Notes
from lab.experts.oracle import OracleBoundary
from lab.experts.pitch import PitchBasicPitch, PitchPesto, PitchPyin, PitchRmvpe, PitchYin
from lab.experts.prior import RepertoirePrior
from lab.experts.pulse import Pulse

REGISTRY = {
    c.name: c for c in (
        MusicEnergy, BoundaryNovelty, PitchPyin, PitchYin, PitchBasicPitch, PitchPesto,
        PitchRmvpe, Notes, Intervals,
        Matcher, RepertoirePrior, Assembler, OracleBoundary, Pulse, Follower,
    )
}


def build_experts(config):
    out = []
    for spec in config.get("experts", []):
        name = spec["name"] if isinstance(spec, dict) else spec
        params = dict(spec.get("params") or {}) if isinstance(spec, dict) else {}
        if name not in REGISTRY:
            raise SystemExit(f"unknown expert '{name}'; have {sorted(REGISTRY)}")
        expert = REGISTRY[name](**params)
        if isinstance(spec, dict) and spec.get("window"):
            from lab.experts.base import WindowSpec

            expert.window = WindowSpec(**spec["window"])
        out.append(expert)
    return out


def topological_order(experts):
    """Order by observation TYPE, not by expert.

    Several experts may produce one type and that is normal, so the sort is
    over the type graph: an expert comes after everything that produces what
    it consumes. Cycles are tolerated (top-down feedback is allowed by
    design); the leftovers keep their configured order, and the
    once-per-chunk rule is what actually bounds the loop.
    """
    produced_by = {}
    for e in experts:
        for t in e.produces:
            produced_by.setdefault(t, []).append(e.name)
    remaining = list(experts)
    placed, placed_types, out = set(), {"audio_chunk"}, []
    while remaining:
        progressed = False
        for e in list(remaining):
            if all(t in placed_types or not produced_by.get(t) for t in e.consumes):
                out.append(e)
                placed.add(e.name)
                remaining.remove(e)
                progressed = True
        if progressed:
            for e in out:
                placed_types.update(e.produces)
        else:
            out.extend(remaining)   # a cycle: keep configured order
            break
    return out
