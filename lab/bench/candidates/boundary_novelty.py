"""Where does one tune stop and the next begin: Foote novelty on chroma.

The classic structural-boundary detector, and the reason it belongs here is
that it needs no silence. It asks whether the harmonic content before a moment
resembles the content after it. A set of three reels run together has no gap,
but the second reel is usually in a different mode, or at least a different
melodic neighbourhood, and the self-similarity matrix shows that as a corner.

Computed on a band around the diagonal rather than the full matrix: three
hours at one-second resolution is ten thousand frames, and the full matrix is
a hundred million cells to find peaks along one line of it.

Weakness: two tunes in the same key at the same tempo (which a session picks
on purpose, because that is what makes a set flow) look identical to it. It
also fires on anything else that changes the harmony, such as the band
stopping and a singer starting.
"""

import numpy as np

from lab.bench.candidates.base import Candidate, normalise, smooth
from lab.bench.features import GRID_MS


def checkerboard_kernel(half, sigma_ratio=0.5):
    """Gaussian-tapered checkerboard: +1 on the two diagonal blocks, -1 off them."""
    size = 2 * half + 1
    idx = np.arange(size) - half
    xx, yy = np.meshgrid(idx, idx, indexing="ij")
    sign = np.sign(xx) * np.sign(yy)
    sign[sign == 0] = 0.0
    sigma = max(1.0, sigma_ratio * half)
    gauss = np.exp(-(xx ** 2 + yy ** 2) / (2.0 * sigma ** 2))
    kernel = (sign * gauss).astype(np.float32)
    kernel -= kernel.mean()
    return kernel


class BoundaryNovelty(Candidate):
    name = "boundary_novelty"
    version = "1"
    needs = ("chroma",)
    fittable = False

    @classmethod
    def defaults(cls):
        return {
            "resolution_s": 1.0,     # the SSM's grid; 1 s is plenty for tune-scale structure
            "kernel_s": 16.0,        # half-width: how much context each side
            "smooth_s": 2.0,
            "block": 2048,           # frames per einsum block, to bound memory
        }

    def predict(self, features):
        self._check(features)
        p = self.params
        chroma = np.asarray(features["chroma"], dtype=np.float32)
        n_frames = chroma.shape[0]
        if n_frames == 0:
            return np.zeros(0, dtype=np.float32)

        # 1. downsample to the SSM grid and L2-normalise, so similarity is cosine
        factor = max(1, int(p["resolution_s"] * 1000 / GRID_MS))
        n_coarse = n_frames // factor
        if n_coarse < 4:
            return np.zeros(n_frames, dtype=np.float32)
        coarse = chroma[:n_coarse * factor].reshape(n_coarse, factor, chroma.shape[1]).mean(axis=1)
        coarse /= np.linalg.norm(coarse, axis=1, keepdims=True) + 1e-8

        # 2. novelty along the diagonal only
        half = max(2, int(p["kernel_s"] / p["resolution_s"]))
        kernel = checkerboard_kernel(half)
        size = 2 * half + 1
        padded = np.pad(coarse, ((half, half), (0, 0)), mode="edge")
        novelty = np.zeros(n_coarse, dtype=np.float32)
        block = max(64, int(p["block"]))
        for start in range(0, n_coarse, block):
            stop = min(n_coarse, start + block)
            # windows[i] is the (size, 12) neighbourhood centred on frame start+i
            windows = np.lib.stride_tricks.sliding_window_view(
                padded, (size, coarse.shape[1]))[start:stop, 0]
            gram = np.einsum("nwd,nvd->nwv", windows, windows, optimize=True)
            novelty[start:stop] = np.einsum("nwv,wv->n", gram, kernel, optimize=True)

        # 3. back to the 100 ms grid
        novelty = smooth(novelty, max(1, int(p["smooth_s"] / p["resolution_s"])))
        out = np.repeat(novelty, factor)
        if out.size < n_frames:
            out = np.pad(out, (0, n_frames - out.size), mode="edge")
        return normalise(out[:n_frames]).astype(np.float32)
