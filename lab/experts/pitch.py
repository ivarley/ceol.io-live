"""Transcription, step one: what frequency is sounding.

Two producers of the same observation type from the first day, because the
board's whole premise is that experts agree on a type and not on an answer.
`lab board --type pitch_track` shows them disagreeing, which is the thing
worth looking at.

Both are monophonic trackers pointed at a room where six people play the same
melody their own way at once. That is not a defect of the implementation; it
is the measurement the lab exists to make, and the successor is a multi-pitch
or neural front end producing this same type.
"""

import numpy as np

from lab.experts.base import Expert, WindowSpec


class _PitchExpert(Expert):
    consumes = ("audio_chunk",)
    produces = ("pitch_track",)
    # Ten seconds of context on a two-second hop: pyin's HMM is much better
    # with a run of audio than with two seconds in isolation, and the cache
    # means the overlap is paid for once per (window, version, params).
    window = WindowSpec(length_ms=10000, hop_ms=2000)

    @classmethod
    def defaults(cls):
        return {"fmin": 130.0, "fmax": 1400.0, "hop": 256, "sr": 22050}

    def _track(self, y, sr):
        raise NotImplementedError

    def process(self, view, window):
        payload, cost, cached = view.cached(
            self.name, self.version, self.params, window.t_start_ms, window.t_end_ms,
            lambda: self._compute(view, window))
        if not payload.get("f0_hz"):
            return []
        chunk = view.latest("audio_chunk")
        return [self.obs("pitch_track", window.t_start_ms, window.t_end_ms, payload,
                         inputs=[chunk.obs_id] if chunk else [], cost_ms=cost, cached=cached)]

    def _compute(self, view, window):
        y = view.audio(window.t_start_ms, window.t_end_ms)
        if y.size < self.params["hop"] * 4:
            return {"source": self.name, "hop": self.params["hop"], "times_ms": [], "f0_hz": [],
                    "voiced_prob": []}
        f0, voiced = self._track(y, self.params["sr"])
        times = window.t_start_ms + (np.arange(f0.size) * self.params["hop"] * 1000.0 / self.params["sr"])
        keep = np.isfinite(f0)
        return {
            "source": self.name,
            "hop": self.params["hop"],
            "times_ms": [int(t) for t in times[keep]],
            "f0_hz": [round(float(v), 2) for v in f0[keep]],
            "voiced_prob": [round(float(v), 3) for v in np.asarray(voiced)[keep]],
        }


class PitchPyin(_PitchExpert):
    name = "pitch_pyin"
    version = "1"
    cost = 10.0

    def _track(self, y, sr):
        import librosa

        f0, voiced_flag, voiced_prob = librosa.pyin(
            y, fmin=self.params["fmin"], fmax=self.params["fmax"], sr=sr,
            frame_length=2048, hop_length=self.params["hop"])
        return f0, voiced_prob


class PitchYin(_PitchExpert):
    name = "pitch_yin"
    version = "1"
    cost = 1.0

    def _track(self, y, sr):
        import librosa

        f0 = librosa.yin(y, fmin=self.params["fmin"], fmax=self.params["fmax"], sr=sr,
                         frame_length=2048, hop_length=self.params["hop"])
        # yin has no voicing model at all. Standing in for one with "is the
        # frame loud relative to this window" is crude and deliberately so:
        # this expert is here to be the fast, worse opinion.
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=self.params["hop"])[0]
        rms = rms[:f0.size] if rms.size >= f0.size else np.pad(rms, (0, f0.size - rms.size))
        ref = np.percentile(rms, 90) or 1.0
        return f0, np.clip(rms / ref, 0.0, 1.0)
