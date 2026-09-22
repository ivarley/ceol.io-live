"""Scoring a candidate: leave-one-night-out, and the metric primitives.

The split is the point. The eight nights share a room, a table and most of the
same players, so a model evaluated on frames from a night it trained on is
measuring the room, not the task. Every candidate here is fitted on seven
nights and scored on the eighth, rotated; rule-based candidates skip the fit
but take the same split, so their numbers sit on the same axis.

Per-night results are kept and reported, not just their mean. With eight nights
the spread is the honest part of the answer.
"""

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List

import numpy as np

from lab import paths
from lab.bench.features import FEATURES_VERSION, GRID_MS, Features
from lab.bench.tasks import get_task, load_ground_truth


# ---------------------------------------------------------------------------
# Metric primitives
# ---------------------------------------------------------------------------


def binary_metrics(y_true, y_pred):
    y_true = np.asarray(y_true).astype(bool)
    y_pred = np.asarray(y_pred).astype(bool)
    tp = int(np.sum(y_true & y_pred))
    fp = int(np.sum(~y_true & y_pred))
    fn = int(np.sum(y_true & ~y_pred))
    tn = int(np.sum(~y_true & ~y_pred))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    total = tp + fp + fn + tn
    return {
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def best_threshold(y_true, scores, minimum=None, n_steps=64):
    """The threshold maximising F1 on this data.

    A tuned threshold on the *evaluation* night would be cheating, so callers
    pass a threshold fitted on the training nights; this is used to fit it.
    """
    y_true = np.asarray(y_true).astype(bool)
    scores = np.asarray(scores, dtype=float)
    if scores.size == 0:
        return 0.0
    lo = minimum if minimum is not None else float(np.min(scores))
    hi = float(np.max(scores))
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return float(lo)
    best, best_f1 = lo, -1.0
    for thr in np.linspace(lo, hi, n_steps):
        f1 = binary_metrics(y_true, scores >= thr)["f1"]
        if f1 > best_f1:
            best, best_f1 = float(thr), f1
    return best


def wilson(successes, n, z=1.96):
    """95% interval for a proportion. Small n is the normal case here."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def peak_times_ms(scores, threshold, min_distance_ms=6000):
    """Local maxima above a threshold, greedily thinned by distance.

    A novelty curve does not produce one sample per boundary; it produces a
    hump. Taking every frame over the threshold would report dozens of
    boundaries where there is one, so the strongest frame wins its
    neighbourhood.
    """
    scores = np.asarray(scores, dtype=float)
    if scores.size == 0:
        return []
    above = np.flatnonzero(scores >= threshold)
    if above.size == 0:
        return []
    min_distance = max(1, int(min_distance_ms // GRID_MS))
    order = above[np.argsort(-scores[above], kind="stable")]
    taken = []
    blocked = np.zeros(scores.size, dtype=bool)
    for i in order:
        if blocked[i]:
            continue
        taken.append(int(i))
        blocked[max(0, i - min_distance):min(scores.size, i + min_distance + 1)] = True
    return sorted(int(i) * GRID_MS for i in taken)


def match_events(truth_ms, predicted_ms, tol_ms):
    """One-to-one nearest matching inside a tolerance.

    Greedy over the closest pairs, so one prediction cannot claim two true
    boundaries and a cluster of predictions around one boundary yields one
    match and the rest as false positives.
    """
    truth = sorted(truth_ms)
    pred = sorted(predicted_ms)
    pairs = []
    for i, t in enumerate(truth):
        for j, p in enumerate(pred):
            d = abs(p - t)
            if d <= tol_ms:
                pairs.append((d, i, j))
    pairs.sort()
    used_t, used_p, errors = set(), set(), []
    for d, i, j in pairs:
        if i in used_t or j in used_p:
            continue
        used_t.add(i)
        used_p.add(j)
        errors.append(pred[j] - truth[i])
    matched = len(used_t)
    return matched, len(pred) - len(used_p), len(truth) - matched, errors


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------


@dataclass
class NightResult:
    recording_id: int
    label: str
    date: str
    metrics: Dict
    n_frames: int
    fit_seconds: float = 0.0
    predict_seconds: float = 0.0


@dataclass
class BenchResult:
    task: str
    candidate: str
    version: str
    params: Dict
    features_version: str
    split: str
    nights: List[NightResult] = field(default_factory=list)
    pooled: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    created_at: str = ""
    git_sha: str = ""

    def to_json(self):
        d = asdict(self)
        return d

    def save(self):
        out_dir = paths.ensure_dir(paths.bench_dir(self.task))
        path = os.path.join(out_dir, f"{self.candidate}-v{self.version}.json")
        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=1)
        return path


def git_sha():
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(paths.DATA_DIR), capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return ""


def _mean(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def run_bench(task_name, candidate, recording_ids=None, tol_ms=None, quiet=False):
    """Score one candidate on one task, leave-one-night-out."""
    task = get_task(task_name, **({"tol_ms": tol_ms} if (tol_ms and task_name == "boundary") else {}))
    recording_ids = recording_ids or paths.prepared_recording_ids()
    if len(recording_ids) < 2 and getattr(candidate, "fittable", False):
        raise SystemExit("a learned candidate needs at least two prepared recordings to hold one out")

    loaded = {}
    warnings = []
    for rid in recording_ids:
        feats = Features.load(rid)
        gt = load_ground_truth(rid)
        warnings.extend(gt.warnings)
        y, mask = task.labels(gt, feats.n_frames)
        loaded[rid] = (feats, gt, y, mask)

    nights = []
    for held_out in recording_ids:
        train_ids = [r for r in recording_ids if r != held_out]
        t0 = time.time()
        model = candidate.fresh()
        if getattr(candidate, "fittable", False):
            model.fit([(loaded[r][0], loaded[r][2], loaded[r][3]) for r in train_ids])
        fit_s = time.time() - t0
        # The operating point is part of the model, and it is fitted on the
        # training nights against THE METRIC BEING REPORTED. Fitting it on
        # frame-level agreement instead was wrong in a way that only a
        # deliberately stupid baseline exposed: for the boundary task the
        # score is event-based, computed after peak-picking, so a threshold
        # that maximises frame overlap can be one that fires constantly. The
        # periodic baseline came back with 555 false boundaries an hour and a
        # recall of 0.99, which is not a baseline, it is a broken dial.
        threshold = getattr(candidate, "fixed_threshold", None)
        if threshold is None and task.needs_threshold and train_ids:
            threshold = fit_threshold(task, model, [loaded[r] for r in train_ids])
        feats, gt, y, mask = loaded[held_out]
        t1 = time.time()
        scores = model.predict(feats)
        predict_s = time.time() - t1
        metrics = task.score(y, mask, scores, gt=gt, threshold=threshold)
        nights.append(NightResult(
            recording_id=held_out, label=gt.label, date=gt.date, metrics=metrics,
            n_frames=feats.n_frames, fit_seconds=round(fit_s, 2), predict_seconds=round(predict_s, 2)))
        if not quiet:
            print(f"  held out {held_out:>4} {gt.date}  " + _fmt_metrics(metrics))

    keys = set()
    for n in nights:
        keys.update(k for k, v in n.metrics.items() if isinstance(v, (int, float)))
    pooled = {k: _mean([n.metrics.get(k) for n in nights]) for k in sorted(keys)}
    pooled["nights"] = len(nights)
    result = BenchResult(
        task=task_name,
        candidate=candidate.name,
        version=candidate.version,
        params=dict(candidate.params),
        features_version=FEATURES_VERSION,
        split="leave-one-night-out",
        nights=nights,
        pooled=pooled,
        warnings=sorted(set(warnings)),
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        git_sha=git_sha(),
    )
    return result


def fit_threshold(task, model, nights, n_steps=21):
    """Pick the operating point that scores best on the training nights.

    Predictions are computed once per night and re-thresholded, because the
    prediction is the expensive part and the sweep is the cheap one.
    """
    predicted = []
    lo, hi = np.inf, -np.inf
    for feats, gt, y, mask in nights:
        scores = np.asarray(model.predict(feats), dtype=float)
        if scores.size:
            lo = min(lo, float(np.nanmin(scores)))
            hi = max(hi, float(np.nanmax(scores)))
        predicted.append((feats, gt, y, mask, scores))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return float(lo) if np.isfinite(lo) else 0.0

    best, best_score = None, -1.0
    for thr in np.linspace(lo, hi, n_steps):
        total, weight = 0.0, 0
        for feats, gt, y, mask, scores in predicted:
            m = task.score(y, mask, scores, gt=gt, threshold=float(thr))
            f1 = m.get("f1")
            if f1 is None:
                continue
            n = m.get("n_true") or m.get("n") or 1
            total += f1 * n
            weight += n
        if weight and total / weight > best_score:
            best, best_score = float(thr), total / weight
    return best if best is not None else float(lo)


def _fmt_metrics(m):
    if "f1" in m and "recall" in m and "n_true" in m:
        return (f"recall {m['recall']:.2f} precision {m['precision']:.2f} f1 {m['f1']:.2f} "
                f"fp/h {m['false_per_hour']:.1f} ({m['matched']}/{m['n_true']})")
    if "accuracy" in m:
        return (f"acc {m['accuracy']:.3f} precision {m['precision']:.3f} recall {m['recall']:.3f} "
                f"f1 {m['f1']:.3f} (n={m.get('n', 0)})")
    return json.dumps(m)


def format_result(result: BenchResult):
    lines = [f"{result.candidate} v{result.version} on {result.task}  "
             f"[{result.split}, features v{result.features_version}]"]
    if result.params:
        lines.append(f"  params: {json.dumps(result.params, sort_keys=True)}")
    for n in result.nights:
        lines.append(f"  {n.recording_id:>4} {n.date}  {_fmt_metrics(n.metrics)}")
    lines.append("  mean:  " + ", ".join(
        f"{k} {v:.3f}" for k, v in result.pooled.items()
        if isinstance(v, float) and k in ("accuracy", "precision", "recall", "f1", "false_per_hour")))
    spread = [n.metrics.get("f1") for n in result.nights if n.metrics.get("f1") is not None]
    if spread:
        lines.append(f"  f1 spread: {min(spread):.3f} to {max(spread):.3f} over {len(spread)} nights")
    return "\n".join(lines)


def load_results(task):
    out = []
    d = paths.bench_dir(task)
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        if name.endswith(".json"):
            with open(os.path.join(d, name)) as f:
                out.append(json.load(f))
    return out
