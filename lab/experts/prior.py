"""Non-audio evidence: what this session actually plays.

Ceol's advantage over an app that listens in isolation, and a producer on the
board like any other. Two sources, both legitimate:

- the session's repertoire, which is a standing fact about the venue;
- the tunes THIS RUN has already confirmed, which is the board's own history.

What it deliberately does not read is the night's logged order. That sits in
the manifest and it is the ground truth's sibling; an expert that saw it would
be reading the answer sheet. The rule is in the spec and enforced by the fact
that BoardView has no accessor for it.

Known weakness on the current corpus: every one of the 274 eval tunes is in
the repertoire, so this looks stronger here than it will at a session whose
list is incomplete. That is exactly why the first comparison to run is
baseline against the same config with this expert removed.
"""

from lab.experts.base import Expert


class RepertoirePrior(Expert):
    name = "prior"
    version = "1"
    consumes = ("music_activity", "hypothesis_update")
    produces = ("tune_prior",)
    cost = 1.0

    @classmethod
    def defaults(cls):
        return {"repertoire_weight": 20.0, "played_tonight_weight": 0.2, "refresh_ms": 30000}

    def setup(self):
        self._repertoire = None
        self._last_emit_ms = None
        self._last_confirmed = None

    def process(self, view, window):
        if self._repertoire is None:
            self._repertoire = {int(r["tune_id"]) for r in (view.manifest.get("repertoire") or [])
                                if r.get("tune_id")}
        confirmed = tuple(sorted(view.confirmed_tune_ids()))
        stale = (self._last_emit_ms is None
                 or window.clock_ms - self._last_emit_ms >= self.params["refresh_ms"])
        if not stale and confirmed == self._last_confirmed:
            return []   # nothing has changed; do not litter the board
        self._last_emit_ms = window.clock_ms
        self._last_confirmed = confirmed

        weights = {t: float(self.params["repertoire_weight"]) for t in self._repertoire}
        for t in confirmed:
            # a tune played twice in a night happens, but it is the exception
            weights[t] = weights.get(t, 1.0) * float(self.params["played_tonight_weight"])
        inputs = [o.obs_id for o in (view.new("music_activity") + view.new("hypothesis_update"))][:4]
        return [self.obs(
            "tune_prior", window.t_start_ms, window.t_end_ms,
            {"weights": {str(k): round(v, 4) for k, v in weights.items()},
             "default_w": 1.0,
             "basis": {"repertoire": len(self._repertoire), "confirmed_tonight": list(confirmed)}},
            inputs=inputs)]
