"""Where the grid is, for whoever needs to put notes back on it.

A separate expert rather than a step inside the note segmenter, because it
answers a different question from a different input and fails in its own way.
It reads audio and says how fast the eighth notes go, where they start and
whether they group in twos or threes; the note segmenter reads a pitch track
and says which notes were played. Keeping them apart is what lets `lab board
--type pulse` show the grid drifting without anything else being suspected.

It reads a long window on a slow hop on purpose. Tempo at a session is steady
within a tune and the estimate is much better over thirty seconds than over
five, so there is nothing to gain from asking more often, and the answer is
used by an expert that runs eight times as often.
"""

from lab.analysis.pulse import attack_times_ms, estimate_pulse
from lab.experts.base import Expert, WindowSpec


class Pulse(Expert):
    """audio_chunk -> pulse.

    Known weakness: it assumes one tempo across the window, so the window
    straddling a tune change describes neither tune. That matters less than it
    sounds, because a set is usually played at one tempo throughout, and it is
    visible as a widening of the estimate rather than as a silent wrong
    answer.
    """

    name = "pulse"
    version = "1"
    consumes = ("audio_chunk",)
    produces = ("pulse",)
    cost = 2.0
    window = WindowSpec(length_ms=30000, hop_ms=10000, warmup=True)

    @classmethod
    def defaults(cls):
        return {"sr": 22050, "with_attacks": True}

    def process(self, view, window):
        payload, cost, cached = view.cached(
            self.name, self.version, self.params, window.t_start_ms, window.t_end_ms,
            lambda: self._compute(view, window))
        if not payload.get("period_ms"):
            return []
        chunk = view.latest("audio_chunk")
        return [self.obs("pulse", window.t_start_ms, window.t_end_ms, payload,
                         inputs=[chunk.obs_id] if chunk else [], cost_ms=cost, cached=cached)]

    def _compute(self, view, window):
        y = view.audio(window.t_start_ms, window.t_end_ms)
        if y.size < 4096:
            return {}
        pulse = estimate_pulse(y, self.params["sr"])
        if not pulse:
            return {}
        # absolute, because everything downstream works in board time
        out = {
            "period_ms": round(pulse["period_ms"], 2),
            "phase_ms": round(window.t_start_ms + pulse["phase_ms"], 1),
            "grouping": int(pulse["grouping"]),
            "bpm_beat": round(pulse["bpm_beat"], 1),
            "grouping_margin": round(pulse["grouping_margin"], 3),
        }
        if self.params["with_attacks"]:
            out["attacks_ms"] = [round(window.t_start_ms + t, 1)
                                 for t in attack_times_ms(y, self.params["sr"])]
        return out
