"""What a bench candidate is.

A candidate turns cached features into one score per grid frame. That is the
whole contract, and it is deliberately loose enough that a three-line rule and
a trained classifier are the same kind of object: the bench's value is that
they get compared on one axis.

`fittable = False` means the candidate has no parameters learned from data, so
the leave-one-night-out loop just predicts. A fitted threshold is still chosen
on the training nights, because picking the operating point on the night you
are scoring is the oldest way to fool yourself.
"""

import numpy as np


class Candidate:
    name = "unnamed"
    version = "0"
    needs = ()          # feature names this reads, checked before running
    fittable = False

    def __init__(self, **params):
        self.params = dict(self.defaults())
        unknown = set(params) - set(self.params)
        if unknown:
            raise SystemExit(f"{self.name}: unknown params {sorted(unknown)}; have {sorted(self.params)}")
        self.params.update(params)

    @classmethod
    def defaults(cls):
        return {}

    def fresh(self):
        """A new instance with the same parameters (one per held-out night)."""
        return type(self)(**self.params)

    def fit(self, nights):
        """nights: [(Features, y, mask)] from the training nights."""
        return self

    def predict(self, features):
        """-> float score per grid frame, higher meaning more of the target."""
        raise NotImplementedError

    # -- helpers shared by candidates ------------------------------------

    def _check(self, features):
        missing = [n for n in self.needs if n not in features]
        if missing:
            raise SystemExit(f"{self.name}: features {missing} are not cached; bump FEATURES_VERSION")


def smooth(x, window_frames):
    """Centred moving average, edges handled by reflection."""
    x = np.asarray(x, dtype=np.float32)
    w = max(1, int(window_frames))
    if w <= 1 or x.size == 0:
        return x
    pad = w // 2
    padded = np.pad(x, (pad, pad), mode="reflect")
    kernel = np.ones(w, dtype=np.float32) / w
    out = np.convolve(padded, kernel, mode="same")
    return out[pad:pad + x.size]


def rolling_percentile(x, window_frames, q=10.0, step=None):
    """Percentile of x over a sliding window, computed on a coarse lattice.

    Used for "the noise floor around here". Exact per-frame percentiles over a
    two-minute window would be the slowest thing in the lab for no benefit, so
    it is evaluated every `step` frames and interpolated.
    """
    x = np.asarray(x, dtype=np.float32)
    n = x.size
    if n == 0:
        return x
    w = max(1, int(window_frames))
    step = step or max(1, w // 8)
    centres = np.arange(0, n, step)
    vals = np.empty(centres.size, dtype=np.float32)
    for i, c in enumerate(centres):
        a, b = max(0, c - w // 2), min(n, c + w // 2 + 1)
        vals[i] = np.percentile(x[a:b], q)
    if centres.size == 1:
        return np.full(n, vals[0], dtype=np.float32)
    return np.interp(np.arange(n), centres, vals).astype(np.float32)


def normalise(x):
    """Map to roughly [0, 1] using robust percentiles, so scores compose."""
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return x
    lo, hi = np.percentile(x, 2), np.percentile(x, 98)
    if hi <= lo:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)
