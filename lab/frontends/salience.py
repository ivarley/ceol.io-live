"""Predominant melody: find the pitch the whole room is playing.

The monophonic trackers fail here for a structural reason. They assume one
voice and try to decide which one, so six instruments make the decision
harder. But a session is not six independent parts. Everyone is playing the
same tune, in unison or an octave apart, with their own ornaments. That means
the melody is the one pitch whose harmonics are reinforced by nearly every
instrument in the room, and the noise is everything else.

So instead of picking a voice, this builds a salience surface: for each
moment and each candidate pitch, add up the energy sitting at that pitch's
harmonics. A fiddle, a flute and a box all playing a G reinforce the same
candidate. A bodhrán, being broadband, reinforces nothing in particular.
Taking the strongest candidate per frame should then follow the tune rather
than any one player.

This is the classical approach to melody extraction from polyphonic audio,
in its simplest useful form. Deliberately simple: peak of the salience
surface, refined by interpolation, with no contour tracking yet. If it works
the tracking is the next version; if it does not, the tracking would not have
saved it.
"""

import numpy as np

from lab.frontends.base import FrontEnd, preprocess


class SalienceMelody(FrontEnd):
    name = "salience"
    version = "1"
    cost = 4.0
    TRACK_PARAMS = ("fmin", "fmax", "n_fft", "hop", "n_harmonics", "harmonic_decay",
                    "highpass_hz", "lowpass_hz", "hpss", "smooth_frames")

    @classmethod
    def defaults(cls):
        d = dict(FrontEnd.defaults())
        d.update({
            "fmin": 150.0,          # under a fiddle's open G, over most room rumble
            "fmax": 1400.0,
            # 8192 at 22.05kHz is 2.7Hz per bin, about a third of a semitone at
            # the bottom of the range. Coarse, which is why the peak is
            # interpolated rather than taken at bin resolution.
            "n_fft": 8192,
            "hop": 256,
            "n_harmonics": 6,
            "harmonic_decay": 0.8,   # weight of harmonic h is decay ** (h-1)
            "smooth_frames": 3,
            "highpass_hz": None, "lowpass_hz": None, "hpss": None,
            "min_voiced": 0.15,
        })
        return d

    def track(self, y, sr):
        import librosa

        p = self.params
        y = preprocess(y, sr, highpass_hz=p["highpass_hz"], lowpass_hz=p["lowpass_hz"],
                       hpss=p["hpss"])
        if y.size < p["n_fft"]:
            return np.zeros(0), np.zeros(0), np.zeros(0)

        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            S = np.abs(librosa.stft(y, n_fft=int(p["n_fft"]), hop_length=int(p["hop"])))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=int(p["n_fft"]))
        harmonics = list(range(1, int(p["n_harmonics"]) + 1))
        weights = [p["harmonic_decay"] ** (h - 1) for h in harmonics]
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            salience = librosa.salience(S, freqs=freqs, harmonics=harmonics,
                                        weights=weights, fill_value=0.0)
        salience = np.nan_to_num(salience, nan=0.0, posinf=0.0, neginf=0.0)

        band = (freqs >= p["fmin"]) & (freqs <= p["fmax"])
        idx = np.flatnonzero(band)
        if idx.size < 3:
            return np.zeros(0), np.zeros(0), np.zeros(0)
        sal = salience[idx, :]

        if p["smooth_frames"] and p["smooth_frames"] > 1:
            k = int(p["smooth_frames"])
            kernel = np.ones(k, dtype=np.float32) / k
            sal = np.apply_along_axis(lambda r: np.convolve(r, kernel, mode="same"), 1, sal)

        peak = np.argmax(sal, axis=0)
        f0 = self._interpolate(sal, peak, freqs[idx])

        # Voicing: how much the winning candidate stands out from the rest of
        # the band at that moment. A frame where everything is equally salient
        # is a frame with no melody in it.
        total = sal.sum(axis=0) + 1e-9
        top = sal[peak, np.arange(sal.shape[1])]
        voiced = np.clip(top / total * np.sqrt(sal.shape[0]), 0.0, 1.0)

        times = np.arange(f0.size) * p["hop"] * 1000.0 / sr
        return times, f0, voiced.astype(float)

    @staticmethod
    def _interpolate(sal, peak, band_freqs):
        """Quadratic interpolation around the winning bin.

        The transform's bins are a third of a semitone apart at the bottom of
        the range, so taking the bin centre would cause semitone errors when
        the notes are later rounded. Fitting a parabola to the peak and its
        neighbours recovers most of that.
        """
        n_bins, n_frames = sal.shape
        frames = np.arange(n_frames)
        centre = np.clip(peak, 1, n_bins - 2)
        a = sal[centre - 1, frames]
        b = sal[centre, frames]
        c = sal[centre + 1, frames]
        denom = (a - 2 * b + c)
        shift = np.where(np.abs(denom) > 1e-12, 0.5 * (a - c) / np.where(denom == 0, 1e-12, denom), 0.0)
        shift = np.clip(shift, -0.5, 0.5)
        log_freqs = np.log(band_freqs)
        lo = log_freqs[centre]
        step = np.where(shift >= 0,
                        np.log(band_freqs[np.minimum(centre + 1, n_bins - 1)]) - lo,
                        lo - np.log(band_freqs[np.maximum(centre - 1, 0)]))
        return np.exp(lo + shift * step)


class SalienceCleaned(SalienceMelody):
    """The same, with the percussion pulled out first.

    Worth its own entry rather than a parameter note: harmonic separation hurt
    the monophonic trackers badly, and there is no reason to assume it behaves
    the same way for a method that is summing harmonics on purpose.
    """

    name = "salience_cleaned"
    version = "1"

    @classmethod
    def defaults(cls):
        d = dict(SalienceMelody.defaults())
        d.update({"hpss": 2.0})
        return d
