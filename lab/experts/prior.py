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
        return {"repertoire_weight": 20.0, "played_tonight_weight": 0.2,
                "refresh_ms": 30000, "use_sequence": True, "beta": 0.15}

    def setup(self):
        self._repertoire = None
        self._last_emit_ms = None
        self._last_confirmed = None
        self._sequence = None

    def _sequence_model(self, view):
        """Transitions from every other night this session has logged.

        Tonight is excluded, which is both the right discipline and what a
        live system faces: it knows every previous evening and nothing about
        this one. Measured on the bench, decoding a whole set against these
        counts is worth nearly as much as being told the previous tune.
        """
        if self._sequence is None:
            from lab.corpus.sequence import SequenceModel

            rec = view.manifest["recording"]
            self._sequence = SequenceModel(
                rec["session_id"], exclude_instance_ids=[rec["session_instance_id"]])
        return self._sequence

    def process(self, view, window):
        if self._repertoire is None:
            self._repertoire = {int(r["tune_id"]) for r in (view.manifest.get("repertoire") or [])
                                if r.get("tune_id")}
        confirmed = tuple(view.confirmed_tune_ids())
        stale = (self._last_emit_ms is None
                 or window.clock_ms - self._last_emit_ms >= self.params["refresh_ms"])
        if not stale and confirmed == self._last_confirmed:
            return []   # nothing has changed; do not litter the board
        self._last_emit_ms = window.clock_ms
        self._last_confirmed = confirmed

        basis = {"repertoire": len(self._repertoire), "confirmed_tonight": list(confirmed)}
        if self.params["use_sequence"]:
            sequence = self._sequence_model(view)
            previous = confirmed[-1] if confirmed else None
            weights = sequence.weights(previous)   # keeps its own default for unlisted tunes
            basis["previous_tune_id"] = previous
            basis["source"] = "sequence"
        else:
            weights = {t: float(self.params["repertoire_weight"]) for t in self._repertoire}
            for t in confirmed:
                weights[t] = weights.get(t, 1.0) * float(self.params["played_tonight_weight"])
            basis["source"] = "repertoire"

        inputs = [o.obs_id for o in (view.new("music_activity") + view.new("hypothesis_update"))][:4]
        # The weight for a tune not listed. It used to be a fixed 1e-4, which
        # is right for the original weights and wrong for any that give an
        # unseen tune a considered share of its own.
        factory = getattr(weights, "default_factory", None)
        default_w = factory() if factory is not None else 1e-4
        return [self.obs(
            "tune_prior", window.t_start_ms, window.t_end_ms,
            {"weights": {str(k): round(v, 8) for k, v in weights.items()},
             "default_w": default_w, "beta": self.params["beta"], "basis": basis},
            inputs=inputs)]
