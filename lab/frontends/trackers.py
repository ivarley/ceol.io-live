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
            # 160Hz, measured: sweeping it over all 503 segments gives 0.616
            # at 130, 0.702 at 160, 0.666 at 190. Below about 150 the tracker
            # is offered energy that is not the melody at all, and takes it.
            "fmin": 160.0, "fmax": 1400.0, "hop": 256, "frame_length": 2048,
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

    # librosa's own default, which every track cached before this parameter
    # existed was made with. Only THAT value is left out of the cache key, so
    # those tracks stay usable -- and the new default is always in the key, so
    # a request for it can never be answered with one of them.
    LEGACY_TROUGH = 0.1
    # Measured over all 502 segments: 0.861 -> 0.873 top-1 with set decoding,
    # top-5 unchanged. Hand labels agreed on where to stop: a solo whistle
    # went from 25% of labelled time right to 42%, the other labelled
    # segments rose slightly, and at 0.8 those others fell away.
    DEFAULT_TROUGH = 0.5

    @classmethod
    def defaults(cls):
        d = dict(_LibrosaTracker.defaults())
        # How deep a dip in yin's difference function must be before the
        # SHORTEST period that has one is accepted. Too strict and yin walks
        # past the true period to a multiple of it. A multiple of two or four
        # is harmless here, since pitch is folded to one octave; a multiple of
        # three is not, because a third of a frequency is a twelfth below it
        # and lands on a different note name, a fifth away. On a solo tin
        # whistle that one error was most of what went wrong: F# heard as B,
        # B as E, D as G, with 88% of the reported frames below the lowest
        # note the instrument can play.
        d["trough_threshold"] = cls.DEFAULT_TROUGH
        # Put back a note that yin reported a twelfth too low; see
        # `correct_twelfths`. The value is how many times the energy at 3*f0
        # must exceed what sits at f0 and 2*f0. Measured over 502 segments
        # with set decoding: off 0.873 / 0.922 (top-1 / top-5), at 1.5
        # 0.873 / 0.930 but costing notes-only top-1 a point, at 3.0
        # 0.878 / 0.930 with nothing lost anywhere. At 1.5 it was also firing
        # on notes that were right.
        d["fix_twelfths"] = 3.0
        return d

    def track_params(self):
        out = super().track_params()
        if self.params.get("trough_threshold", self.LEGACY_TROUGH) != self.LEGACY_TROUGH:
            out["trough_threshold"] = self.params["trough_threshold"]
        if self.params.get("fix_twelfths"):
            out["fix_twelfths"] = self.params["fix_twelfths"]
        return out

    def track(self, y, sr):
        import librosa

        y = self._prepared(y, sr)
        if y.size < self.params["frame_length"]:
            return np.zeros(0), np.zeros(0), np.zeros(0)
        f0 = librosa.yin(y, fmin=self.params["fmin"], fmax=self.params["fmax"], sr=sr,
                         frame_length=self.params["frame_length"], hop_length=self.params["hop"],
                         trough_threshold=self.params.get("trough_threshold", self.DEFAULT_TROUGH))
        if self.params.get("fix_twelfths"):
            f0 = correct_twelfths(y, sr, f0, self.params["frame_length"], self.params["hop"],
                                  ratio=float(self.params["fix_twelfths"]))
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


def correct_twelfths(y, sr, f0, n_fft, hop, ratio=2.0):
    """Undo yin's one harmful mistake: reporting a third of the true pitch.

    A period-finding tracker can settle on a multiple of the true period.
    Twice or four times is harmless here, because pitch is folded to one
    octave. Three times is not: a third of a frequency is a twelfth below it,
    which is a different note name, a fifth away. On a solo tin whistle that
    error alone accounted for about a third of every labelled frame -- F#
    heard as B, B as E, D as G -- with most reported frames below the lowest
    note the instrument can play.

    The spectrum tells the two apart. If the true pitch is f0, there is energy
    at f0 and 2*f0. If it is 3*f0 (or 1.5*f0, which is the same note name),
    neither of those is a harmonic of what is sounding, and the energy sits at
    3*f0 instead. A true octave error, f/2, still has energy at 2*f0, so it is
    left alone -- which is right, since folding already absorbs it.
    """
    import librosa

    f0 = np.asarray(f0, dtype=float).copy()
    spec = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop, center=True))
    bin_hz = sr / float(n_fft)
    nyquist = sr / 2.0

    def energy(frame, hz):
        if hz <= 0 or hz >= nyquist:
            return 0.0
        b = int(round(hz / bin_hz))
        lo, hi = max(0, b - 1), min(spec.shape[0], b + 2)
        return float(spec[lo:hi, frame].max()) if hi > lo else 0.0

    frames = min(f0.size, spec.shape[1])
    for i in range(frames):
        f = f0[i]
        if not np.isfinite(f) or f <= 0 or 3 * f >= nyquist:
            continue
        own = energy(i, f) + energy(i, 2 * f)
        third = energy(i, 3 * f)
        if third > ratio * (own + 1e-9):
            f0[i] = 3 * f
    return f0
