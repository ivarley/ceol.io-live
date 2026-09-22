"""The monophonic trackers, and the same trackers with the input cleaned up.

The first real run showed both of these failing on a pub session, in opposite
ways: pyin locks onto a near-constant pitch, yin scatters across octaves. They
stay on the board as the floor, and the cleaned-up variants are here to answer
the cheapest question first — how much of that is the mix rather than the
tracker.
"""

import numpy as np

from lab.frontends.base import FrontEnd, preprocess


class _LibrosaTracker(FrontEnd):
    TRACK_PARAMS = ("fmin", "fmax", "hop", "frame_length",
                    "highpass_hz", "lowpass_hz", "hpss")

    @classmethod
    def defaults(cls):
        d = dict(FrontEnd.defaults())
        d.update({
            "fmin": 130.0, "fmax": 1400.0, "hop": 256, "frame_length": 2048,
            "min_voiced": 0.2,
            # input cleanup, off by default so the plain tracker is the floor
            "highpass_hz": None, "lowpass_hz": None, "hpss": None,
        })
        return d

    def _prepared(self, y, sr):
        return preprocess(y, sr, highpass_hz=self.params["highpass_hz"],
                          lowpass_hz=self.params["lowpass_hz"], hpss=self.params["hpss"])

    def _times(self, n_frames, sr):
        return np.arange(n_frames) * self.params["hop"] * 1000.0 / sr


class PyinFrontEnd(_LibrosaTracker):
    """Probabilistic YIN.

    Its voicing model is built for one instrument. Measured on a real segment
    of this corpus, the median voiced probability is 0.011 and only 4% of
    frames clear 0.5, so the threshold that suits solo audio discards almost
    everything. `min_voiced` is therefore something to sweep, not to assume.
    """

    name = "pyin"
    version = "1"
    cost = 10.0

    @classmethod
    def defaults(cls):
        d = dict(_LibrosaTracker.defaults())
        # Measured, not chosen: swept over all 503 segments, every threshold
        # above zero is worse, and 0.5 takes top-1 from 0.141 to 0.000. The
        # voicing probability is not a usable gate on this material, so the
        # gate is off and the note segmenter sees everything pyin produced.
        d["min_voiced"] = 0.0
        return d

    def track(self, y, sr):
        import librosa

        y = self._prepared(y, sr)
        if y.size < self.params["frame_length"]:
            return np.zeros(0), np.zeros(0), np.zeros(0)
        f0, _flag, voiced = librosa.pyin(
            y, fmin=self.params["fmin"], fmax=self.params["fmax"], sr=sr,
            frame_length=self.params["frame_length"], hop_length=self.params["hop"])
        return self._times(f0.size, sr), f0, voiced


class YinFrontEnd(_LibrosaTracker):
    name = "yin"
    version = "1"
    cost = 1.0

    def track(self, y, sr):
        import librosa

        y = self._prepared(y, sr)
        if y.size < self.params["frame_length"]:
            return np.zeros(0), np.zeros(0), np.zeros(0)
        f0 = librosa.yin(y, fmin=self.params["fmin"], fmax=self.params["fmax"], sr=sr,
                         frame_length=self.params["frame_length"], hop_length=self.params["hop"])
        # yin has no voicing model; loudness relative to this span stands in
        rms = librosa.feature.rms(y=y, frame_length=self.params["frame_length"],
                                  hop_length=self.params["hop"])[0]
        rms = rms[:f0.size] if rms.size >= f0.size else np.pad(rms, (0, f0.size - rms.size))
        ref = np.percentile(rms, 90) or 1.0
        return self._times(f0.size, sr), f0, np.clip(rms / ref, 0.0, 1.0)


class PyinCleaned(PyinFrontEnd):
    """pyin over a mix with the percussion removed and the melody band kept.

    The cheapest hypothesis for why pyin locks on: it is tracking something
    that is not the melody. Bodhrán and guitar go with the percussive part;
    the band limits cut the room rumble below a fiddle's G and the harmonics
    above where a flute stops carrying the tune.
    """

    name = "pyin_cleaned"
    version = "1"

    @classmethod
    def defaults(cls):
        d = dict(PyinFrontEnd.defaults())
        d.update({"highpass_hz": 180.0, "lowpass_hz": 2500.0, "hpss": 2.0})
        return d


class YinCleaned(YinFrontEnd):
    name = "yin_cleaned"
    version = "1"

    @classmethod
    def defaults(cls):
        d = dict(YinFrontEnd.defaults())
        d.update({"highpass_hz": 180.0, "lowpass_hz": 2500.0, "hpss": 2.0})
        return d
