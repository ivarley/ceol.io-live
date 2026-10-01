"""Where does one tune stop and the next begin: the key changed.

Cruder than novelty and aimed at one specific cue. A tune's chroma, averaged
over half a minute, is close to its key's scale. Compare the average before a
moment with the average after it; a big cosine distance means the notes being
played have moved.

It is here partly because it is almost free, and partly because it fails
differently from novelty: novelty responds to any change in texture, this only
to a change in pitch content. Two detectors that fail differently is the
beginning of an ensemble.

Weakness: blind to a tune change within a key, which at a session is the
common case, since sets are usually built to stay in one key.
"""

import numpy as np

from lab.bench.candidates.base import Candidate, normalise, smooth
from lab.bench.features import GRID_MS


class BoundaryKeyChange(Candidate):
    name = "boundary_keychange"
    version = "1"
    needs = ("chroma",)
    fittable = False

    @classmethod
    def defaults(cls):
        return {"window_s": 30.0, "smooth_s": 2.0}

    def predict(self, features):
        self._check(features)
        p = self.params
        chroma = np.asarray(features["chroma"], dtype=np.float32)
        n = chroma.shape[0]
        if n == 0:
            return np.zeros(0, dtype=np.float32)
        w = max(2, int(p["window_s"] * 1000 / GRID_MS))
        # prefix sums make both trailing and leading means O(1) per frame
        cs = np.concatenate([np.zeros((1, chroma.shape[1]), dtype=np.float64), np.cumsum(chroma, axis=0)])
        idx = np.arange(n)
        lo = np.maximum(0, idx - w)
        hi = np.minimum(n, idx + w)
        before = (cs[idx] - cs[lo]) / np.maximum(1, (idx - lo))[:, None]
        after = (cs[hi] - cs[idx]) / np.maximum(1, (hi - idx))[:, None]
        before /= np.linalg.norm(before, axis=1, keepdims=True) + 1e-8
        after /= np.linalg.norm(after, axis=1, keepdims=True) + 1e-8
        distance = 1.0 - np.sum(before * after, axis=1)
        # the edges compare a window with itself; suppress rather than report
        edge = min(w, n // 2)
        distance[:edge] = 0.0
        distance[n - edge:] = 0.0
        return normalise(smooth(distance.astype(np.float32), int(p["smooth_s"] * 1000 / GRID_MS)))
