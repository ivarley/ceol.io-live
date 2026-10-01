"""Is this a tune at all? Tuning, noodling, a slow air and chat, told from a
tune by how the last few seconds sound.

The player's account of what the detector called tunes on night 137 (tuning
and noodling, a few phrases of a jig, a piper improvising a slow air with
no pulse) is that their musical coherence is far below any tune's. Measured
on the labels: a chunk inside a labelled tune is a tune, one well inside a
gap of 15 s or more is not. A logistic model over the features below
separates them with an AUC of 0.988 to 0.997 on each of eight nights, each
scored by a model fitted on the other seven, and 0.990 on night 137, which
it never saw. The strongest signs of a tune: loudness, how many notes, the
pulse, how much Basic Pitch hears as pitched, and how well the best tune
matches (`lab/configs/tuneness.json`, with its provenance).

The decoder takes the model's log-odds through `Decoder(gamma=...)`: "not a
tune" scores `lam * (tau - gamma * logodds / 10)`.
"""

import json
import os

import numpy as np

FRONTENDS = ("yin", "basic_pitch", "pesto")
NAMES = (["pulse_strength", "grouping_margin", "duple", "triple", "log_rms"]
         + [f"{f}_{k}" for f in FRONTENDS for k in ("voiced", "pc_entropy", "steady")]
         + ["n_notes", "top_score", "margin"])
PULSE_MS, FRAMES_MS = 12000, 6000
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "tuneness.json")


def audio_features(store, t, frames_by_source):
    """Everything but the aligner's evidence, for the chunk ending at `t`:
    the pulse over the last 12 s, loudness, and per tracker how much of the
    last 6 s is pitched, how spread its pitch classes are, and how settled
    its pitch is. `frames_by_source`: {front end name: (times_ms, f0_hz,
    voiced_prob)}."""
    from lab.analysis.pulse import estimate_pulse

    p = estimate_pulse(store.read(max(0, t - PULSE_MS), t), store.sr) or {}
    y = store.read(max(0, t - FRAMES_MS), t)
    row = {"pulse_strength": p.get("pulse_strength"), "grouping_margin": p.get("grouping_margin"),
           "duple": p.get("duple_strength"), "triple": p.get("triple_strength"),
           "log_rms": float(np.log10(np.sqrt(np.mean(y ** 2)) + 1e-6)) if len(y) else None}
    for name in FRONTENDS:
        times, f0, voiced = frames_by_source[name]
        i, j = np.searchsorted(times, t - FRAMES_MS), np.searchsorted(times, t)
        v, f = np.asarray(voiced[i:j]), np.asarray(f0[i:j], dtype=float)
        ok = np.isfinite(f) & (f > 0) & (v >= 0.2)
        row[f"{name}_voiced"] = float(ok.mean()) if j > i else 0.0
        row[f"{name}_pc_entropy"] = row[f"{name}_steady"] = None
        if ok.sum() > 10:
            midi = 69 + 12 * np.log2(f[ok] / 440.0)
            hist = np.bincount(np.round(midi).astype(int) % 12, minlength=12) / ok.sum()
            row[f"{name}_pc_entropy"] = float(-(hist[hist > 0] * np.log(hist[hist > 0])).sum())
            row[f"{name}_steady"] = float((np.abs(np.diff(midi)) < 0.5).mean())
    return row


def with_evidence(row, chunk):
    """Add the aligner's own evidence from a scored chunk."""
    sc = sorted(chunk["scores"].values(), reverse=True) + [0.0, 0.0]
    return {**row, "n_notes": chunk["n_notes"], "top_score": sc[0], "margin": sc[0] - sc[1]}


class TunenessModel:
    def __init__(self, coef, intercept, median, mu, sd, **meta):
        self.coef, self.intercept = np.asarray(coef), float(intercept)
        self.median, self.mu, self.sd = np.asarray(median), np.asarray(mu), np.asarray(sd)
        self.meta = meta

    @classmethod
    def load(cls, path=MODEL_PATH):
        with open(path) as f:
            d = json.load(f)
        if list(d["names"]) != NAMES:
            raise SystemExit(f"{path}: features {d['names']} are not this module's {NAMES}")
        return cls(**{k: v for k, v in d.items() if k != "names"})

    def logodds(self, row):
        """Log-odds that the chunk is a tune (positive: a tune)."""
        x = np.array([np.nan if row.get(n) is None else row[n] for n in NAMES], dtype=float)
        x = np.where(np.isnan(x), self.median, x)
        return float(((x - self.mu) / self.sd) @ self.coef + self.intercept)
