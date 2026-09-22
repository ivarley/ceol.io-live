"""What an expert is, and the two things every expert is handed.

An expert declares the observation types it consumes and produces, a relative
cost, and either a window schedule or nothing (event-driven). It gets a
read-only `BoardView` and a `Window`, and returns observations. That is all,
and it is deliberately little: the whole point of the board is that adding an
expert, deleting one, or running two versions of one side by side costs
nothing anywhere else.

`CandidateExpert` is how something that scored on the bench becomes an expert
without being rewritten. It runs the same candidate code over live features,
and records which bench result it came from.
"""

import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from lab.board.board import Observation


@dataclass(frozen=True)
class Window:
    t_start_ms: int
    t_end_ms: int
    clock_ms: int


@dataclass(frozen=True)
class WindowSpec:
    """How often a windowed expert runs, and how much it reads each time.

    `lookahead_ms` is the honest cost of context after the point of interest:
    a detector that needs fifteen seconds of "what came next" cannot answer
    until fifteen seconds have passed, and the harness measures that as
    latency rather than hiding it.
    """

    length_ms: int
    hop_ms: int
    lookahead_ms: int = 0
    warmup: bool = False

    def windows_complete_by(self, clock_ms, start_ms=0):
        """Every window that has become answerable by `clock_ms`.

        With `warmup`, short windows are emitted from the first hop rather
        than waiting for a full one. An expert that needs a minute of context
        would otherwise say nothing for a minute, which is the wrong answer
        live and an odd one in a replay; a cheap expert that can speak early
        with less context should.
        """
        out = []
        first_end = start_ms + (self.hop_ms if self.warmup else self.length_ms)
        t_end = first_end
        while t_end + self.lookahead_ms <= clock_ms:
            out.append((max(start_ms, t_end - self.length_ms), t_end))
            t_end += self.hop_ms
        return out


class Expert:
    name = "unnamed"
    version = "0"
    consumes = ()
    produces = ()
    cost = 1.0
    window: Optional[WindowSpec] = None

    def __init__(self, **params):
        self.params = dict(self.defaults())
        unknown = set(params) - set(self.params)
        if unknown:
            raise SystemExit(f"{self.name}: unknown params {sorted(unknown)}; have {sorted(self.params)}")
        self.params.update(params)
        self.setup()

    @classmethod
    def defaults(cls):
        return {}

    def setup(self):
        """Anything expensive that belongs once per run, not once per window."""

    def process(self, view, window: Window) -> List[Observation]:
        raise NotImplementedError

    # -- helper ----------------------------------------------------------

    def obs(self, type_, t_start_ms, t_end_ms, payload, inputs=(), cost_ms=0.0, cached=False):
        return Observation(
            type=type_, t_start_ms=int(t_start_ms), t_end_ms=int(t_end_ms), payload=payload,
            expert=self.name, expert_version=self.version, params=dict(self.params),
            inputs=[int(i) for i in inputs if i is not None], cost_ms=cost_ms, cached=cached,
        )


class CandidateExpert(Expert):
    """An expert that is a bench candidate run over live features.

    Subclasses set `candidate_name` and `produces`. Only candidates that need
    no fitting can graduate this way for now; a learned one would need its
    fitted model persisted alongside the bench result, which the steel thread
    does not do, so it fails loudly rather than silently predicting nonsense.
    """

    candidate_name = None
    emit_type = None

    @classmethod
    def defaults(cls):
        return {"candidate_params": {}, "bench_result": None}

    def setup(self):
        from lab.bench.candidates import get_candidate

        self._candidate = get_candidate(self.candidate_name, **(self.params["candidate_params"] or {}))
        if getattr(self._candidate, "fittable", False):
            raise SystemExit(
                f"{self.name}: candidate '{self.candidate_name}' is learned, and the lab does not yet "
                f"persist fitted models; score it on the bench and graduate a rule, or add model "
                f"persistence before configuring it as an expert")

    def scores_for(self, view, window):
        """The candidate's score curve over the window, on the feature grid."""
        feats = view.features(window.t_start_ms, window.t_end_ms)
        started = time.time()
        scores = self._candidate.predict(feats)
        return np.asarray(scores, dtype=np.float32), feats, (time.time() - started) * 1000.0
