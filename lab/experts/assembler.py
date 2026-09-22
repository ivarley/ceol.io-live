"""The fusion layer: matcher evidence plus prior, over a span, as a lifecycle.

This is where the hard part lives, and it is deliberately the only expert that
writes hypotheses. Everything else contributes evidence; this decides what to
claim, how sure to be, and when to stop claiming it.

Four ideas, each of which the harness can measure separately:

**Evidence accumulates over a span.** A tune is played three times through, so
by the end there have been half a dozen hearings of the same eight bars. Match
scores since the span opened are summed, not replaced.

**Confidence sharpens with evidence.** The softmax temperature falls as the
span gets longer, so early guesses are flat and late ones are peaked. A
reserved "something else" mass keeps early confidence honestly low, which is
what stops the scheduler from skipping expensive experts on a guess.

**The tune will stop.** A confident answer is a claim about a span that is
still running, and every span ends. A change hazard grows with elapsed time
against the expected length for the candidate's tune type, so a reel that has
been going four minutes is treated as due to change. A `boundary` observation
closes the span outright.

**Flips are visible, not hidden.** When the top candidate changes, the old
hypothesis is superseded and a new one proposed rather than the old one being
quietly edited, so the harness can count how often a provisional answer
changed under the reader.

Known weaknesses: the temperature schedule, the reserved mass and the hazard
curve are all hand-set numbers that should be fitted once there is enough
data to fit them on; and evidence from overlapping windows is summed as if
independent, which it is not.
"""

import math

from lab.experts.base import Expert

# Rough expected length, in seconds, of one tune played the usual number of
# times through. The corpus median is 110s; these differentiate by type.
EXPECTED_LENGTH_S = {
    "reel": 110, "jig": 105, "slip jig": 100, "hornpipe": 115, "polka": 80,
    "slide": 95, "waltz": 130, "march": 120, "barndance": 115, "mazurka": 110,
    "strathspey": 110, "three-two": 120, "air": 150,
}
DEFAULT_LENGTH_S = 110


class Assembler(Expert):
    name = "assembler"
    version = "1"
    consumes = ("tune_match", "tune_prior", "music_activity", "boundary")
    produces = ("hypothesis_update",)
    cost = 1.0

    @classmethod
    def defaults(cls):
        return {
            "base_temperature": 0.25,
            "sharpen_after_s": 30.0,
            "other_mass": 0.25,
            "confirm_conf": 0.9,
            "silence_close_s": 10.0,
            "min_update_ms": 2000,
            "top_k": 10,
            "hazard_at_expected": 0.5,
            # How to treat successive matches. The interval expert keeps a
            # trailing window, so each match already integrates everything
            # heard in it; summing them then counts the same phrase once per
            # update and lets an early wrong guess run away. "latest" trusts
            # the newest match, which is what the bench does with one lookup
            # over the whole span.
            "evidence_mode": "latest",
        }

    def setup(self):
        self._reset_span()
        self._prior = {}
        self._prior_default = 1.0
        self._prior_beta = 1.0
        self._silence_since = None
        self._counter = 0

    def _reset_span(self):
        self._evidence = {}
        self._names = {}
        self._types = {}
        self._span_start_ms = None
        self._hyp_id = None
        self._last_update_ms = None
        self._last_top = None

    # -- the posterior ----------------------------------------------------

    def _elapsed_s(self, clock_ms):
        if self._span_start_ms is None:
            return 0.0
        return max(0.0, (clock_ms - self._span_start_ms) / 1000.0)

    def _hazard(self, clock_ms):
        """How overdue a change is, 0 upward, 0.5 at the expected length."""
        top = self._last_top
        expected = EXPECTED_LENGTH_S.get((self._types.get(top) or "").lower(), DEFAULT_LENGTH_S)
        return self.params["hazard_at_expected"] * self._elapsed_s(clock_ms) / max(1.0, expected)

    def _ranked(self, clock_ms):
        if not self._evidence:
            return []
        elapsed = self._elapsed_s(clock_ms)
        temperature = self.params["base_temperature"] / (1.0 + elapsed / self.params["sharpen_after_s"])
        # Evidence is normalised against the best candidate before the
        # softmax. The matcher's scores are small and close together - a good
        # match is about 0.05 and the gap to the runner-up about 0.02 - so
        # dividing the raw values by any sensible temperature produced a
        # nearly uniform distribution, and every confidence came out around
        # 0.04 whether the answer was obvious or a coin toss. Relative
        # evidence is what the temperature should act on.
        best_ev = max(self._evidence.values()) or 1e-9
        scaled = {}
        for tune_id, ev in self._evidence.items():
            weight = self._prior.get(str(tune_id), self._prior_default)
            scaled[tune_id] = ((ev / best_ev) / max(1e-6, temperature)
                               + self._prior_beta * math.log(max(1e-9, weight)))
        peak = max(scaled.values())
        exps = {t: math.exp(v - peak) for t, v in scaled.items()}
        # reserved mass for "a tune not in these candidates", shrinking as
        # evidence accumulates and growing again as a change becomes overdue
        other = (self.params["other_mass"] * math.exp(-elapsed / 60.0)
                 + min(0.5, self._hazard(clock_ms)))
        total = sum(exps.values())
        ranked = [
            {"tune_id": t, "name": self._names.get(t), "tune_type": self._types.get(t),
             "conf": round((1.0 - other) * v / total, 4), "evidence": round(self._evidence[t], 4)}
            for t, v in exps.items()
        ]
        ranked.sort(key=lambda d: -d["conf"])
        return ranked[: self.params["top_k"]]

    # -- the loop ---------------------------------------------------------

    def process(self, view, window):
        clock = window.clock_ms
        out = []

        prior = view.latest("tune_prior")
        if prior is not None:
            self._prior = prior.payload.get("weights") or {}
            self._prior_default = prior.payload.get("default_w", 1.0)
            self._prior_beta = float(prior.payload.get("beta", 1.0))

        for act in view.new("music_activity"):
            if act.payload.get("is_music"):
                self._silence_since = None
            elif self._silence_since is None:
                self._silence_since = act.t_end_ms

        boundaries = view.new("boundary")
        matches = view.new("tune_match")
        inputs = [o.obs_id for o in (boundaries + matches)]

        # 1. a boundary ends the span, whatever we were claiming
        for b in boundaries:
            if self._hyp_id is not None:
                out.extend(self._close(view, clock, b.payload.get("t_ms", clock), inputs=[b.obs_id]))
            self._reset_span()
            self._span_start_ms = int(b.payload.get("t_ms", clock))
            self._opened_by = "boundary"

        # 2. silence ends it too
        if (self._hyp_id is not None and self._silence_since is not None
                and clock - self._silence_since >= self.params["silence_close_s"] * 1000):
            out.extend(self._close(view, clock, self._silence_since, inputs=inputs))
            self._reset_span()

        # 3. accumulate
        for m in matches:
            if self.params["evidence_mode"] == "latest":
                self._evidence = {}
            for c in m.payload.get("candidates", []):
                tune_id = c["tune_id"]
                self._evidence[tune_id] = self._evidence.get(tune_id, 0.0) + float(c["score"])
                self._names.setdefault(tune_id, c.get("name"))
                self._types.setdefault(tune_id, c.get("tune_type"))
            if self._span_start_ms is None:
                self._span_start_ms = m.t_start_ms
                self._opened_by = "first_match"

        if not self._evidence:
            return out

        ranked = self._ranked(clock)
        if not ranked:
            return out
        top = ranked[0]["tune_id"]

        # 4. open, flip, or update
        if self._hyp_id is None:
            out.append(self._open(view, clock, ranked, inputs,
                                  opened_by=getattr(self, "_opened_by", "first_match")))
        elif top != self._last_top:
            out.extend(self._supersede(view, clock, ranked, inputs))
        elif (self._last_update_ms is None
              or clock - self._last_update_ms >= self.params["min_update_ms"]):
            out.append(self._update(view, clock, ranked, inputs))
        self._last_top = top
        return out

    # -- lifecycle writes -------------------------------------------------

    def _new_hyp_id(self, view):
        self._counter += 1
        return f"{view.run_id}:{self._counter}"

    def _write(self, view, hyp_id, clock, event, ranked, inputs):
        """One observation plus its hypothesis event, in that order."""
        obs = self.obs("hypothesis_update", self._span_start_ms or clock, clock,
                       {"hyp_id": hyp_id, "event": event, "ranked": ranked,
                        "elapsed_s": round(self._elapsed_s(clock), 1),
                        "hazard": round(self._hazard(clock), 3)},
                       inputs=inputs)
        view.note_now(obs)
        view.board.add_hypothesis_event(view.run_id, hyp_id, clock, event, ranked, obs.obs_id)
        self._last_update_ms = clock
        return obs

    def _open(self, view, clock, ranked, inputs, opened_by):
        self._hyp_id = self._new_hyp_id(view)
        view.board.open_hypothesis(view.run_id, self._hyp_id, self._span_start_ms or clock,
                                   clock, opened_by)
        return self._write(view, self._hyp_id, clock, "proposed", ranked, inputs)

    def _update(self, view, clock, ranked, inputs):
        return self._write(view, self._hyp_id, clock, "updated", ranked, inputs)

    def _supersede(self, view, clock, ranked, inputs):
        """The top candidate changed. The old claim is closed as superseded
        and a new one opened over the same span, rather than the old one being
        edited in place — a reader saw the old answer, and the harness counts
        how often that happens."""
        old, start = self._hyp_id, self._span_start_ms
        out = [self._write(view, old, clock, "superseded", ranked, inputs)]
        self._span_start_ms = start
        out.append(self._open(view, clock, ranked, inputs, opened_by="rival"))
        view.board.close_hypothesis(old, "superseded", clock, clock, superseded_by=self._hyp_id)
        return out

    def _close(self, view, clock, t_end_ms, inputs):
        if self._hyp_id is None:
            return []
        ranked = self._ranked(clock)
        conf = ranked[0]["conf"] if ranked else 0.0
        event = "confirmed" if conf >= self.params["confirm_conf"] else "withdrawn"
        obs = self._write(view, self._hyp_id, clock, event, ranked, inputs)
        view.board.close_hypothesis(self._hyp_id, event, t_end_ms, clock)
        return [obs]
