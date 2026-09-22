"""Cached features, served window by window, bounded by the clock.

The bench computes a feature grid once per recording. An expert on the board
wants the same numbers over its own window, and must not be able to see past
the clock — otherwise a replay quietly uses audio that a live system would not
have had, and every latency the harness reports is a lie.

So this is the exact analogue of `AudioStore`: random access into a
precomputed array, clipped at `clock_ms`. Live, the same interface would be
fed by computing features incrementally from the same functions in
`lab/bench/features.py`; nothing above this line changes.

One honest caveat: the cached grid was computed with a centred STFT, so a
frame draws on about 90ms either side of its timestamp. That is under one
grid step and far under any latency the harness reports, but it is not zero.
"""

import numpy as np

from lab.bench.features import GRID_MS, Features


class FeatureStore:
    def __init__(self, features: Features):
        self._features = features
        self.clock_ms = 0

    @property
    def n_frames(self):
        return self._features.n_frames

    def window(self, t0_ms, t1_ms) -> Features:
        """A Features view over [t0, t1), clipped at the clock.

        Timestamps stay absolute, so an expert can map a frame back to a
        moment in the recording without knowing how it was sliced.
        """
        t1_ms = min(int(t1_ms), self.clock_ms)
        t0_ms = max(0, min(int(t0_ms), t1_ms))
        a, b = self._features.slice(t0_ms, t1_ms)
        arrays = {}
        for name, arr in self._features.arrays.items():
            arrays[name] = arr[a:b]
        if "t_ms" not in arrays or arrays["t_ms"].size == 0:
            arrays["t_ms"] = np.arange(a, b, dtype=np.int64) * GRID_MS
        return Features(self._features.recording_id, arrays, dict(self._features.meta))
