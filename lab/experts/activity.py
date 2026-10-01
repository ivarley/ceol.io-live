"""Is music playing, on the board.

The graduated bench baseline. It exists so the assembler has something to tell
it the room has gone quiet, and so the scheduler can decline to transcribe
silence. The spec is explicit that it is not to be trusted for boundaries: a
pub throws big waveforms that are not the band.
"""

import numpy as np

from lab.experts.base import CandidateExpert, WindowSpec


class MusicEnergy(CandidateExpert):
    name = "music_energy"
    version = "1"
    candidate_name = "music_energy"
    consumes = ("audio_chunk",)
    produces = ("music_activity",)
    cost = 1.0
    # Long enough for the candidate's noise floor to mean something, but with
    # warm-up so the assembler is not blind to silence for the first minute.
    window = WindowSpec(length_ms=30000, hop_ms=2000, warmup=True)

    @classmethod
    def defaults(cls):
        d = dict(CandidateExpert.defaults())
        d["threshold"] = 0.35
        return d

    def process(self, view, window):
        scores, feats, cost = self.scores_for(view, window)
        if scores.size == 0:
            return []
        # report only the newest hop; the rest of the window was context
        hop_ms = self.window.hop_ms
        t0 = max(window.t_start_ms, window.t_end_ms - hop_ms)
        a, b = feats.slice(t0, window.t_end_ms)
        recent = scores[a:b] if b > a else scores[-1:]
        score = float(np.mean(recent))
        chunk = view.latest("audio_chunk")
        return [self.obs(
            "music_activity", t0, window.t_end_ms,
            {"score": score,
             "is_music": bool(score >= self.params["threshold"]),
             "rms_db": float(np.mean(feats["rms_db"][a:b])) if b > a else None},
            inputs=[chunk.obs_id] if chunk else [], cost_ms=cost)]
