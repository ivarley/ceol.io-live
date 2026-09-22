"""What kind of tune is this? Reel, jig, polka, hornpipe.

Worth building because it was worth measuring first. Restricting the
candidates to the true type takes retrieval from 0.485 to 0.577 top-1, which
is as much as the sequence prior is worth and comes without its bootstrapping
problem: the type of the tune playing now does not depend on having correctly
named the tune before it.

It should also be much easier than melody. The difference between a reel and
a jig is not which notes are played but how they are grouped: a reel divides
its beat in two, a jig in three. That is a property of the rhythm, and rhythm
survives a room full of people far better than pitch does.

The feature is the autocorrelation of the onset envelope. If notes land every
140ms and beats every 560ms, the envelope correlates with itself at those
lags, and the pattern of peaks says how the beat is divided. It is computed
at a finer hop than the cached grid on purpose: at 100ms per frame the fastest
resolvable period is 200ms, and the note rate being measured is faster than
that.
"""

import json
import time

import numpy as np

from lab import paths
from lab.audio.chunks import AudioStore
from lab.audio.prepare import wav_sha1
from lab.bench.score import BenchResult, NightResult, git_sha
from lab.bench.tasks import load_ground_truth
from lab.board.board import Board

HOP = 256                 # 11.6ms at 22.05kHz: fast enough for the note rate
MAX_LAG_S = 3.0
MIN_LAG_S = 0.08
FEATURE_VERSION = "1"


def rhythm_features(y, sr, hop=HOP):
    """Onset-envelope autocorrelation, normalised, plus a little context."""
    import librosa

    if y.size < hop * 8:
        return None
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    if onset.size < 16:
        return None
    onset = onset - onset.mean()
    norm = np.sqrt(np.sum(onset ** 2)) or 1.0
    ac = np.correlate(onset, onset, mode="full")[onset.size - 1:] / (norm ** 2)

    frames_per_s = sr / hop
    lo = int(MIN_LAG_S * frames_per_s)
    hi = min(ac.size, int(MAX_LAG_S * frames_per_s))
    if hi - lo < 16:
        return None
    band = ac[lo:hi]
    # resample to a fixed length so every segment gives the same shaped vector
    grid = np.linspace(0, band.size - 1, 128)
    resampled = np.interp(grid, np.arange(band.size), band)
    peak = float(np.max(resampled)) or 1.0
    return np.concatenate([resampled / peak, [peak, float(onset.mean()), float(onset.std())]])


def segment_features(recording_id, seconds=30.0, board=None):
    """Feature vectors and labels for one night's scorable segments."""
    gt = load_ground_truth(recording_id)
    store = AudioStore(paths.wav_path(recording_id))
    store.clock_ms = store.duration_ms
    sha = wav_sha1(recording_id) or ""
    rows = []
    try:
        for seg in gt.eval_segments():
            if not seg.evaluated or not seg.tune_type:
                continue
            t0 = seg.start_ms
            t1 = min(seg.end_ms, t0 + int(seconds * 1000))
            if t1 - t0 < 5000:
                continue
            key = f"rhythm-{FEATURE_VERSION}-{sha}-{t0}-{t1}-{HOP}"
            vec = None
            if board is not None:
                hit = board.cache_get(key)
                if hit is not None:
                    vec = np.asarray(hit[0], dtype=np.float32)
            if vec is None:
                started = time.time()
                vec = rhythm_features(store.read(t0, t1), store.sr)
                if vec is None:
                    continue
                if board is not None:
                    board.cache_put(key, "rhythm", FEATURE_VERSION,
                                    [float(x) for x in vec], (time.time() - started) * 1000)
                    board.conn.commit()
            rows.append({"x": np.asarray(vec, dtype=np.float32),
                         "y": seg.tune_type.strip().lower(),
                         "segment_id": seg.segment_id, "name": seg.name})
    finally:
        store.close()
    return gt, rows


def predictions_path():
    return paths.data("tune_type_predictions.json")


def run_tune_type(recording_ids=None, seconds=30.0, min_class=8, quiet=False,
                  emit_predictions=True):
    """Leave-one-night-out, because eight nights in one room is the whole risk."""
    from sklearn.ensemble import RandomForestClassifier

    recording_ids = recording_ids or paths.prepared_recording_ids()
    per_night = {}
    with Board() as board:
        for rid in recording_ids:
            gt, rows = segment_features(rid, seconds=seconds, board=board)
            per_night[rid] = (gt, rows)
            if not quiet:
                print(f"  {rid:>4} {gt.date}  {len(rows)} segments", flush=True)

    counts = {}
    for _gt, rows in per_night.values():
        for r in rows:
            counts[r["y"]] = counts.get(r["y"], 0) + 1
    # a class with a handful of examples cannot be learned or fairly scored
    keep = {k for k, v in counts.items() if v >= min_class}
    dropped = {k: v for k, v in counts.items() if k not in keep}

    nights, all_true, all_pred = [], [], []
    predictions = {}
    for held_out in recording_ids:
        train = [r for rid, (_g, rows) in per_night.items() if rid != held_out
                 for r in rows if r["y"] in keep]
        test = [r for r in per_night[held_out][1] if r["y"] in keep]
        if not train or not test:
            continue
        X = np.vstack([r["x"] for r in train])
        Y = [r["y"] for r in train]
        model = RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                       class_weight="balanced", random_state=0, n_jobs=-1)
        model.fit(X, Y)
        Xtest = np.vstack([r["x"] for r in test])
        pred = model.predict(Xtest)
        proba = model.predict_proba(Xtest)
        for r, row in zip(test, proba):
            # kept per segment, always from a model that never saw this night
            predictions[str(r["segment_id"])] = {
                cls: round(float(pv), 4) for cls, pv in zip(model.classes_, row)}
        true = [r["y"] for r in test]
        acc = float(np.mean([p == t for p, t in zip(pred, true)]))
        majority = max(counts, key=counts.get)
        baseline = float(np.mean([t == majority for t in true]))
        gt = per_night[held_out][0]
        nights.append(NightResult(recording_id=held_out, label=gt.label, date=gt.date,
                                  metrics={"accuracy": acc, "n": len(true),
                                           "majority_baseline": baseline},
                                  n_frames=len(true)))
        all_true.extend(true)
        all_pred.extend(pred)
        if not quiet:
            print(f"  held out {held_out:>4} {gt.date}  accuracy {acc:.3f} "
                  f"(always-'{majority}' would score {baseline:.3f})", flush=True)

    majority = max(counts, key=counts.get)
    pooled = {
        "accuracy": float(np.mean([p == t for p, t in zip(all_pred, all_true)])) if all_true else 0.0,
        "majority_baseline": float(np.mean([t == majority for t in all_true])) if all_true else 0.0,
        "n": len(all_true), "nights": len(nights), "classes": sorted(keep),
        "dropped_classes": dropped,
        "f1": float(np.mean([p == t for p, t in zip(all_pred, all_true)])) if all_true else 0.0,
    }
    per_class = {}
    for cls in sorted(keep):
        idx = [i for i, t in enumerate(all_true) if t == cls]
        if idx:
            per_class[cls] = {
                "n": len(idx),
                "recall": float(np.mean([all_pred[i] == cls for i in idx])),
            }
    pooled["per_class"] = per_class

    if emit_predictions:
        paths.ensure_dir(paths.DATA_DIR)
        with open(predictions_path(), "w") as f:
            json.dump({"seconds": seconds, "feature_version": FEATURE_VERSION,
                       "split": "leave-one-night-out", "by_segment": predictions}, f)

    result = BenchResult(
        task="tune_type", candidate="rhythm_forest", version=FEATURE_VERSION,
        params={"seconds": seconds, "hop": HOP, "min_class": min_class},
        features_version=f"rhythm-{FEATURE_VERSION}", split="leave-one-night-out",
        nights=nights, pooled=pooled, warnings=[],
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"), git_sha=git_sha())
    return result


def format_tune_type(result):
    p = result.pooled
    lines = [f"{result.candidate} v{result.version} on tune_type  [{result.split}]",
             f"  params: {json.dumps(result.params, sort_keys=True)}",
             f"  accuracy {p['accuracy']:.3f} over {p['n']} segments "
             f"(always the commonest type would score {p['majority_baseline']:.3f})"]
    for cls, m in sorted(p["per_class"].items(), key=lambda kv: -kv[1]["n"]):
        lines.append(f"    {cls:<12} {m['n']:>4} segments, recall {m['recall']:.3f}")
    if p["dropped_classes"]:
        lines.append(f"  too rare to score: {p['dropped_classes']}")
    spread = [n.metrics["accuracy"] for n in result.nights]
    if spread:
        lines.append(f"  per-night spread {min(spread):.3f} to {max(spread):.3f}")
    return "\n".join(lines)
