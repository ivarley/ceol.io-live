"""Is music playing: loudness above the room's own floor, plus onsets.

The baseline, and the one the spec says not to trust. A pub throws big
waveforms that are not the band — a shout, a dropped glass, the room laughing
— and a quiet air can sit under the chatter. It is here to be beaten, and to
give the ensemble one producer of `music_activity` before anything better
exists.

Weakness: no notion of pitch or periodicity, so anything loud and rhythmic
passes. Expect it to do well on the gaps between sets, which are quiet, and
badly on a loud room between tunes.
"""

import numpy as np

from lab.bench.candidates.base import Candidate, normalise, rolling_percentile, smooth
from lab.bench.features import GRID_MS


class MusicEnergy(Candidate):
    name = "music_energy"
    version = "1"
    needs = ("rms_db", "onset_strength")
    fittable = False

    @classmethod
    def defaults(cls):
        return {
            "floor_window_s": 120,   # how much context defines "the room right now"
            "floor_percentile": 15,
            "smooth_s": 2.0,
            "onset_weight": 0.4,
        }

    def predict(self, features):
        self._check(features)
        p = self.params
        rms = features["rms_db"]
        onset = features["onset_strength"]
        win = int(p["floor_window_s"] * 1000 / GRID_MS)
        floor = rolling_percentile(rms, win, q=p["floor_percentile"])
        above = smooth(rms - floor, int(p["smooth_s"] * 1000 / GRID_MS))
        onset_s = smooth(onset, int(p["smooth_s"] * 1000 / GRID_MS))
        return ((1.0 - p["onset_weight"]) * normalise(above)
                + p["onset_weight"] * normalise(onset_s)).astype(np.float32)
