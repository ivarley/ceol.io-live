"""Where does one tune stop and the next begin: learn it from mel deltas.

The learned boundary candidate. For each frame it builds a small description
of how different things are on either side, at three timescales, and asks a
logistic regression whether that pattern looks like a boundary.

Why three timescales: a tune change is not one event. A couple of seconds of
ritardando, a beat of silence, a new key over the next ten. One window length
would catch one of those.

Positives are rare (a boundary every couple of minutes), so the fit is
class-balanced and negatives are subsampled hard. With roughly six hundred
boundaries across eight nights this is small-data, and leave-one-night-out
should be believed over the pooled mean.
"""

import numpy as np

from lab.bench.candidates.base import Candidate, normalise, smooth
from lab.bench.features import GRID_MS


class BoundaryMelLR(Candidate):
    name = "boundary_mel_lr"
    version = "1"
    needs = ("mel", "rms_db", "chroma")
    fittable = True

    @classmethod
    def defaults(cls):
        return {
            "windows_s": (2.0, 5.0, 10.0),
            "negative_subsample": 15,
            "C": 0.05,
            "smooth_s": 2.0,
            "max_train_frames": 150000,
        }

    def __init__(self, **params):
        super().__init__(**params)
        self._model = None
        self._mean = None
        self._std = None

    def _design(self, features):
        """Per frame: |mean-after minus mean-before| summarised, per timescale."""
        mel = np.asarray(features["mel"], dtype=np.float32)
        chroma = np.asarray(features["chroma"], dtype=np.float32)
        rms = np.asarray(features["rms_db"], dtype=np.float32)
        n = mel.shape[0]
        cols = []
        for win_s in self.params["windows_s"]:
            w = max(2, int(win_s * 1000 / GRID_MS))
            for block in (mel, chroma):
                cs = np.concatenate([np.zeros((1, block.shape[1]), dtype=np.float64), np.cumsum(block, axis=0)])
                idx = np.arange(n)
                lo, hi = np.maximum(0, idx - w), np.minimum(n, idx + w)
                before = (cs[idx] - cs[lo]) / np.maximum(1, idx - lo)[:, None]
                after = (cs[hi] - cs[idx]) / np.maximum(1, hi - idx)[:, None]
                diff = (after - before).astype(np.float32)
                bn = before / (np.linalg.norm(before, axis=1, keepdims=True) + 1e-8)
                an = after / (np.linalg.norm(after, axis=1, keepdims=True) + 1e-8)
                cols.append(np.abs(diff).mean(axis=1, keepdims=True))
                cols.append(np.linalg.norm(diff, axis=1, keepdims=True))
                cols.append((1.0 - np.sum(bn * an, axis=1))[:, None].astype(np.float32))
            cs_r = np.concatenate([[0.0], np.cumsum(rms.astype(np.float64))])
            idx = np.arange(n)
            lo, hi = np.maximum(0, idx - w), np.minimum(n, idx + w)
            rb = (cs_r[idx] - cs_r[lo]) / np.maximum(1, idx - lo)
            ra = (cs_r[hi] - cs_r[idx]) / np.maximum(1, hi - idx)
            cols.append((ra - rb)[:, None].astype(np.float32))
            cols.append(np.abs(ra - rb)[:, None].astype(np.float32))
        return np.concatenate(cols, axis=1)

    def fit(self, nights):
        from sklearn.linear_model import LogisticRegression

        rng = np.random.default_rng(0)
        xs, ys = [], []
        step = max(1, int(self.params["negative_subsample"]))
        for features, y, mask in nights:
            self._check(features)
            y = np.asarray(y)
            X = self._design(features)
            pos = np.flatnonzero((y == 1) & mask)
            neg = np.flatnonzero((y == 0) & mask)[::step]
            keep = np.concatenate([pos, neg])
            if keep.size == 0:
                continue
            xs.append(X[keep])
            ys.append(y[keep])
        if not xs:
            raise SystemExit(f"{self.name}: no labelled training frames")
        X = np.concatenate(xs).astype(np.float32)
        Y = np.concatenate(ys).astype(np.int8)
        cap = int(self.params["max_train_frames"])
        if X.shape[0] > cap:
            sel = rng.choice(X.shape[0], cap, replace=False)
            X, Y = X[sel], Y[sel]
        if len(np.unique(Y)) < 2:
            raise SystemExit(f"{self.name}: training labels are all one class")
        self._mean, self._std = X.mean(axis=0), X.std(axis=0) + 1e-6
        self._model = LogisticRegression(
            C=float(self.params["C"]), max_iter=500, class_weight="balanced")
        self._model.fit((X - self._mean) / self._std, Y)
        return self

    def predict(self, features):
        self._check(features)
        if self._model is None:
            raise SystemExit(f"{self.name}: predict before fit")
        X = (self._design(features) - self._mean) / self._std
        p = self._model.predict_proba(X)[:, 1].astype(np.float32)
        return normalise(smooth(p, int(self.params["smooth_s"] * 1000 / GRID_MS)))
