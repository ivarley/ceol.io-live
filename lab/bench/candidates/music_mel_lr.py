"""Is music playing: logistic regression on mel frames with context.

The first learned candidate, and the point of the bench: it costs a few lines
more than the energy rule and can in principle learn what a fiddle sounds like
as against a room. Whether it does is the measurement.

Frames are stacked with context at three offsets so the model sees a little
before and after, and training frames are subsampled because adjacent 100 ms
frames are nearly the same example.

Weakness: linear, and mel frames carry the room's timbre as strongly as the
music's, which is exactly what leave-one-night-out is there to expose.
"""

import numpy as np

from lab.bench.candidates.base import Candidate, smooth
from lab.bench.features import GRID_MS


def _stack(mel, offsets_frames):
    """Context stack: mel at t plus mel at each offset, clipped at the edges."""
    n = mel.shape[0]
    idx = np.arange(n)
    parts = [mel]
    for off in offsets_frames:
        parts.append(mel[np.clip(idx + off, 0, n - 1)])
    return np.concatenate(parts, axis=1)


class MusicMelLR(Candidate):
    name = "music_mel_lr"
    version = "1"
    needs = ("mel",)
    fittable = True

    @classmethod
    def defaults(cls):
        return {
            "context_s": 1.0,
            "subsample": 5,
            "C": 0.1,
            "smooth_s": 1.5,
            "max_train_frames": 200000,
        }

    def __init__(self, **params):
        super().__init__(**params)
        self._model = None
        self._mean = None
        self._std = None

    def _offsets(self):
        c = int(self.params["context_s"] * 1000 / GRID_MS)
        return (-c, c)

    def _design(self, mel):
        return _stack(np.asarray(mel, dtype=np.float32), self._offsets())

    def fit(self, nights):
        from sklearn.linear_model import LogisticRegression

        xs, ys = [], []
        step = max(1, int(self.params["subsample"]))
        for features, y, mask in nights:
            self._check(features)
            keep = np.flatnonzero(mask)[::step]
            if keep.size == 0:
                continue
            xs.append(self._design(features["mel"])[keep])
            ys.append(np.asarray(y)[keep])
        if not xs:
            raise SystemExit(f"{self.name}: no labelled training frames")
        X = np.concatenate(xs).astype(np.float32)
        Y = np.concatenate(ys).astype(np.int8)
        cap = int(self.params["max_train_frames"])
        if X.shape[0] > cap:
            sel = np.random.default_rng(0).choice(X.shape[0], cap, replace=False)
            X, Y = X[sel], Y[sel]
        self._mean = X.mean(axis=0)
        self._std = X.std(axis=0) + 1e-6
        X = (X - self._mean) / self._std
        if len(np.unique(Y)) < 2:
            raise SystemExit(f"{self.name}: training labels are all one class")
        self._model = LogisticRegression(
            C=float(self.params["C"]), max_iter=400, class_weight="balanced", n_jobs=None)
        self._model.fit(X, Y)
        return self

    def predict(self, features):
        self._check(features)
        if self._model is None:
            raise SystemExit(f"{self.name}: predict before fit")
        X = (self._design(features["mel"]) - self._mean) / self._std
        p = self._model.predict_proba(X)[:, 1].astype(np.float32)
        return smooth(p, int(self.params["smooth_s"] * 1000 / GRID_MS))
