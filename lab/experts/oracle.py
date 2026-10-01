"""An expert that cheats, on purpose, to size what a real one would be worth.

The board scores well below the bench on the same audio, and the reason is
structural rather than a bug: the bench is handed the segment and transcribes
exactly the tune, while the board keeps a trailing window that at the start of
a tune is still full of the previous one. Closing that gap is what boundary
detection is for.

So this emits a `boundary` at every true segment start, reading the ground
truth directly. It is not a detector and must never be in a scored
configuration; it exists to answer one question - if boundaries were perfect,
how much of the gap would close - and the answer says how much a real
detector is worth before anyone builds a better one.

The name is deliberately loud, and the run config records it, so a number
produced with this in the stack cannot be mistaken for a result.
"""

from lab.bench.tasks import load_ground_truth
from lab.experts.base import Expert, WindowSpec


class OracleBoundary(Expert):
    name = "oracle_boundary"
    version = "1"
    consumes = ("audio_chunk",)
    produces = ("boundary",)
    cost = 0.0
    window = WindowSpec(length_ms=2000, hop_ms=2000, warmup=True)

    @classmethod
    def defaults(cls):
        return {}

    def setup(self):
        self._starts = None
        self._emitted = set()

    def process(self, view, window):
        if self._starts is None:
            gt = load_ground_truth(view.manifest["recording"]["recording_id"])
            self._starts = sorted(s.start_ms for s in gt.segments)
        out = []
        for t in self._starts:
            if t in self._emitted:
                continue
            if window.t_start_ms <= t < window.t_end_ms:
                self._emitted.add(t)
                out.append(self.obs(
                    "boundary", window.t_start_ms, window.t_end_ms,
                    {"t_ms": int(t), "strength": 1.0, "kind": "oracle", "latency_ms": 0},
                    inputs=[]))
        return out
