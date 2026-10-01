"""Where one tune stops and the next begins, on the board.

The graduated novelty candidate. It needs context on both sides of a moment,
so it runs on a long window with a real lookahead and its observations arrive
late by construction — which is the point of recording the window and letting
the harness measure detection latency rather than pretending the answer was
instant.

Only peaks inside the newest hop are emitted, so a boundary is announced once
rather than re-announced every time the window slides over it.
"""

from lab.bench.score import peak_times_ms
from lab.experts.base import CandidateExpert, WindowSpec


class BoundaryNovelty(CandidateExpert):
    name = "boundary_novelty"
    version = "1"
    candidate_name = "boundary_novelty"
    consumes = ("audio_chunk",)
    produces = ("boundary",)
    cost = 2.0
    window = WindowSpec(length_ms=120000, hop_ms=4000, lookahead_ms=16000)

    @classmethod
    def defaults(cls):
        d = dict(CandidateExpert.defaults())
        d.update({"threshold": 0.55, "min_distance_ms": 20000})
        return d

    def process(self, view, window):
        scores, feats, cost = self.scores_for(view, window)
        if scores.size == 0:
            return []
        base_t = int(feats.t_ms[0]) if feats.t_ms.size else window.t_start_ms
        peaks = peak_times_ms(scores, threshold=self.params["threshold"],
                              min_distance_ms=self.params["min_distance_ms"])
        # a peak's time is relative to the slice; make it absolute
        peaks = [base_t + p for p in peaks]
        # emit only what is newly decidable: the hop that just became complete
        new_from = window.t_end_ms - self.window.hop_ms
        chunk = view.latest("audio_chunk")
        out = []
        for t in peaks:
            if not (new_from <= t < window.t_end_ms):
                continue
            idx = feats.frame_at(t - base_t)
            out.append(self.obs(
                "boundary", window.t_start_ms, window.t_end_ms,
                {"t_ms": int(t),
                 "strength": float(scores[idx]) if idx < scores.size else None,
                 "kind": "novelty",
                 "latency_ms": int(window.clock_ms - t)},
                inputs=[chunk.obs_id] if chunk else [], cost_ms=cost))
        return out
