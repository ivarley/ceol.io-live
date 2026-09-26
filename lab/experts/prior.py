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
                "refresh_ms": 30000, "use_sequence": True, "beta": 0.15,
                # Where the previous tune comes from. "confirmed" waits for a
                # confirmation, which, measured, never happens (confidence
                # tops out near 0.75 against a 0.9 bar), so the transitions
                # were never used on the board at all. "closed" takes the
                # answer of the last finished span if it was at least
                # `chain_min_conf` sure.
                #
                # Measured on four nights, 290 tunes, top-1 / top-5 / flips:
                #   confirmed (never fires)        0.766 / 0.872 / 4.2
                #   closed, any confidence         0.769 / 0.883 / 3.7
                #   closed, at least 0.3 sure      0.772 / 0.883 / 4.0  <- chosen
                #   closed, at least 0.5 sure      0.766 / 0.883 / 4.2
                #   closed, any, no guard below    0.766 / 0.879 / 4.4
                # All within noise. Chaining now finds a previous tune for 99%
                # of mid-set tunes and the true one for 64%, yet it moves the
                # answer little, because the assembler sharpens towards the
                # audio as a span goes on and a fixed-size prior only counts
                # early. The same prior is worth 1.7 points on the bench.
                "chain_from": "closed", "chain_min_conf": 0.3,
                # A detected boundary is right about a quarter of the time, so
                # the "previous" span is often the tune still playing. Never
                # penalise that tune for following itself.
                "protect_continuation": True}

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
        if self.params["chain_from"] == "closed":
            last = view.last_closed_answer()
            confirmed = ((last[0],) if last and last[1] >= self.params["chain_min_conf"]
                         else ())
        else:
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
            if previous is not None and self.params["protect_continuation"]:
                weights[previous] = max(weights.values()) if weights else 1.0
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
