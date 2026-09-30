"""Is this still the same tune? The change-detection bench (plan item 3).

The retrieval bench is handed each tune cut to its labelled boundaries. Live,
one tune simply becomes another without warning, and chat and false starts
come between sets. This bench replays a whole night the way the live logger
would hear it, a chunk at a time, and asks of every chunk whether it agrees
with the tune already believed, or a new one has begun, or none is playing.

Three steps, kept apart so the expensive one is done once:

1. **Features** (`night_features`, cached per night). Each tracker's notes
   for the whole night, tracked once in fixed blocks through the retrieval
   bench's own cached `transcribe_segment`. Every `hop_ms` the last
   `window_ms` of notes are aligned (the retrieval bench's `Aligner`, same
   implementation) against a pool of candidates: the index's shortlist over
   the trailing `pool_ms`, plus the pools of the last `keep` chunks, so the
   tune being followed stays scored while it plays.
2. **Decoding** (`Decoder`), causal: a forward filter over every tune seen
   plus "not a tune". Each chunk the belief either stays (1 - p_switch) or
   jumps; a jump lands on "not a tune" with share `p_none` of it. Emission is
   `lam` times the chunk's aligner score; a tune outside the chunk's pool is
   scored at the pool's floor; "not a tune" scores `lam * tau`. What is
   displayed is the state with the highest belief.
3. **Scoring** (`score_night`), the board's measures per labelled segment
   (right at the end, time to first right, never right, flips) plus the two
   this bench is for: how long the previous tune stays displayed after a
   change (carry-over), and how much of the unlabelled time between tunes is
   displayed as a tune.
"""

import math
import os
import pickle
import time
from collections import defaultdict

import numpy as np

from lab import paths
from lab.audio.chunks import AudioStore
from lab.audio.prepare import wav_sha1
from lab.bench.tasks import load_ground_truth

FEATURES_VERSION = "1"
NONE = -1          # the "not a tune" state


def _features_path(rid, key):
    import hashlib

    digest = hashlib.sha1(key.encode()).hexdigest()[:10]
    return os.path.join(paths.ensure_dir(paths.bench_dir("stream")),
                        f"r{rid}-{digest}.pkl")


def night_notes(frontends, rid, board, block_ms=60000, quiet=True):
    """{front end name: notes for the whole night, by start time}, tracked in
    fixed blocks (cached on the board like every bench track)."""
    from lab.bench.retrieval import transcribe_segment

    store = AudioStore(paths.wav_path(rid))
    store.clock_ms = store.duration_ms
    sha = wav_sha1(rid) or ""
    out = {}
    try:
        for fe in frontends:
            notes = []
            for t0 in range(0, int(store.duration_ms), block_ms):
                t1 = min(int(store.duration_ms), t0 + block_ms)
                if t1 - t0 < 2000:
                    continue
                block, _, _ = transcribe_segment(fe, store, sha, t0, t1, board=board)
                notes.extend(block)
            notes.sort(key=lambda n: n["t0_ms"])
            out[fe.name] = notes
            if not quiet:
                print(f"    night {rid}: {fe.name} {len(notes)} notes", flush=True)
    finally:
        store.close()
    return out, store.duration_ms


def _window(notes, starts, a, b):
    i, j = np.searchsorted(starts, a), np.searchsorted(starts, b)
    return notes[i:j]


def night_features(rid, frontends, index, aligner, board, hop_ms=4000, window_ms=8000,
                   pool_ms=24000, pool_top=100, keep=6, quiet=True):
    """Per chunk: {"t_ms": end of the chunk, "scores": {tune: aligner score},
    "floor": the pool's lowest score, "n_notes"}. Cached per night and
    settings."""
    from lab.bench.retrieval import fuse
    from lab.frontends.segmentation import intervals_from_notes

    key = repr((FEATURES_VERSION, rid, [f.name for f in frontends], [f.version for f in frontends],
                [sorted(f.params.items()) for f in frontends], index.candidate_set, index.n,
                aligner.params(), hop_ms, window_ms, pool_ms, pool_top, keep))
    path = _features_path(rid, key)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    started = time.time()
    by_fe, duration = night_notes(frontends, rid, board, quiet=quiet)
    starts = {k: np.array([n["t0_ms"] for n in v]) for k, v in by_fe.items()}
    chunks, recent = [], []
    for t in range(window_ms, int(duration) + 1, hop_ms):
        rankings = []
        for name, notes in by_fe.items():
            ctx = _window(notes, starts[name], t - pool_ms, t)
            rankings.append(index.lookup(intervals_from_notes(ctx, fold=index.fold_octaves),
                                         top_k=pool_top))
        pool = [r["tune_id"] for r in fuse(rankings, method="sum")[:pool_top]]
        recent = (recent + [pool])[-(keep + 1):]
        tunes = list(dict.fromkeys(tid for p in reversed(recent) for tid in p))
        heard = [(_window(notes, starts[name], t - window_ms, t), None)
                 for name, notes in by_fe.items()]
        n_notes = sum(len(h[0]) for h in heard)
        queries = aligner._queries(heard)
        scores = aligner.scores(tunes, queries) if (queries and tunes) else {}
        chunks.append({"t_ms": t, "scores": {k: float(v) for k, v in scores.items()},
                       "floor": float(min(scores.values())) if scores else 0.0,
                       "n_notes": n_notes})
    out = {"recording_id": rid, "hop_ms": hop_ms, "window_ms": window_ms, "chunks": chunks,
           "seconds": round(time.time() - started, 1)}
    with open(path, "wb") as f:
        pickle.dump(out, f)
    if not quiet:
        print(f"    night {rid}: {len(chunks)} chunks in {out['seconds']:.0f}s", flush=True)
    return out


class Decoder:
    """Causal belief over tunes and "not a tune", a chunk at a time."""

    def __init__(self, lam=10.0, tau=0.35, p_switch=0.02, p_none=0.3):
        self.lam, self.tau, self.p_switch, self.p_none = lam, tau, p_switch, p_none

    def params(self):
        return {"lam": self.lam, "tau": self.tau, "p_switch": self.p_switch, "p_none": self.p_none}

    def run(self, chunks):
        """-> the displayed state after each chunk (a tune id or NONE)."""
        ids = [NONE]                    # state order; row 0 is "not a tune"
        where = {NONE: 0}
        log = np.array([0.0])           # log belief per state, normalised each step
        shown = []
        ls, lj = math.log(1 - self.p_switch), math.log(self.p_switch)
        for c in chunks:
            scores, floor = c["scores"], c["floor"]
            fresh = [t for t in scores if t not in where]
            if fresh:
                for t in fresh:
                    where[t] = len(ids)
                    ids.append(t)
                log = np.concatenate([log, np.full(len(fresh), -1e9)])
            n = len(ids)
            emit = np.full(n, self.lam * floor)
            emit[0] = self.lam * self.tau
            in_pool = np.zeros(n, dtype=bool)
            if scores:
                rows = np.fromiter((where[t] for t in scores), dtype=np.int64, count=len(scores))
                emit[rows] = self.lam * np.fromiter(scores.values(), dtype=float, count=len(scores))
                in_pool[rows] = True
            # a jump lands on "not a tune" or on one of the tunes this chunk's
            # pool proposes; a tune outside the pool can only be stayed in
            total = np.logaddexp.reduce(log)
            jump_tune = lj + math.log(1 - self.p_none) + total - math.log(max(1, len(scores)))
            jump_none = lj + math.log(self.p_none) + total
            prior = ls + log
            prior[in_pool] = np.logaddexp(prior[in_pool], jump_tune)
            prior[0] = np.logaddexp(prior[0], jump_none)
            new = prior + emit
            log = new - np.logaddexp.reduce(new)
            log = np.maximum(log, -1e9)
            shown.append(ids[int(np.argmax(log))])
        return shown


def score_night(features, shown, rid, gap_min_ms=15000, edge_ms=5000):
    """Per labelled segment: right at the end, time to first right, flips,
    carry-over of the previous tune; and the share of unlabelled time between
    tunes that is displayed as a tune."""
    gt = load_ground_truth(rid)
    times = np.array([c["t_ms"] for c in features["chunks"]])
    shown = np.array(shown)
    segs = sorted(gt.eval_segments(), key=lambda s: s.start_ms)
    rows = []
    prev_end, prev_tune = None, None
    for s in segs:
        m = (times > s.start_ms) & (times <= s.end_ms)
        if s.evaluated and s.tune_id is not None and m.any():
            idx = np.where(m)[0]
            disp = shown[idx]
            right = np.where(disp == s.tune_id)[0]
            carry = None
            if prev_tune is not None and prev_end is not None and s.start_ms - prev_end < 5000:
                away = np.where(disp != prev_tune)[0]
                carry = (times[idx[away[0]]] - s.start_ms) if away.size else (s.end_ms - s.start_ms)
            rows.append({
                "segment_id": s.segment_id, "tune_id": s.tune_id, "name": s.name,
                "tune_type": s.tune_type,
                "top1_end": bool(disp[-1] == s.tune_id),
                "ttfc_ms": int(times[idx[right[0]]] - s.start_ms) if right.size else None,
                "flips": int((disp[1:] != disp[:-1]).sum()),
                "carry_ms": None if carry is None else int(carry),
                "prev_tune_id": prev_tune if carry is not None else None,
            })
        prev_end, prev_tune = s.end_ms, s.tune_id
    gaps = {"chunks": 0, "shown_tune": 0, "shown_previous": 0}
    for a, b in zip(segs, segs[1:]):
        g0, g1 = a.end_ms + edge_ms, b.start_ms - edge_ms
        if g1 - g0 < gap_min_ms - 2 * edge_ms:
            continue
        m = (times > g0) & (times <= g1)
        gaps["chunks"] += int(m.sum())
        gaps["shown_tune"] += int((shown[m] != NONE).sum())
        gaps["shown_previous"] += int((shown[m] == a.tune_id).sum())
    return rows, gaps


def summarise(rows, gaps=None):
    n = len(rows)
    if not n:
        return {"n": 0}
    carried = [r["carry_ms"] for r in rows if r["carry_ms"] is not None]
    out = {
        "n": n,
        "top1_end": sum(r["top1_end"] for r in rows) / n,
        "within_30s": sum(1 for r in rows if r["ttfc_ms"] is not None and r["ttfc_ms"] <= 30000) / n,
        "within_60s": sum(1 for r in rows if r["ttfc_ms"] is not None and r["ttfc_ms"] <= 60000) / n,
        "never": sum(1 for r in rows if r["ttfc_ms"] is None) / n,
        "flips": sum(r["flips"] for r in rows) / n,
        "carry_median_s": float(np.median(carried)) / 1000 if carried else None,
        "carry_over_20s": sum(1 for c in carried if c > 20000) / len(carried) if carried else None,
    }
    if gaps and gaps["chunks"]:
        out["gap_shown_as_tune"] = gaps["shown_tune"] / gaps["chunks"]
        out["gap_shown_previous"] = gaps["shown_previous"] / gaps["chunks"]
    return out


def run_stream(recording_ids, frontends, candidate_set="repertoire", decoder=None, hop_ms=4000,
               window_ms=8000, pool_ms=24000, pool_top=100, keep=6, reading="notes", quiet=True):
    """Features (cached) and decoding for each night -> (rows, gaps by night)."""
    from lab.bench.retrieval import Aligner
    from lab.board.board import Board
    from lab.corpus.index import Index

    index = Index.load(candidate_set, n=6, fold_octaves=True)
    aligner = Aligner(reading=reading, mode="replace", shortlist=10 ** 6, candidate_set=candidate_set)
    decoder = decoder or Decoder()
    rows, gaps = [], {}
    with Board() as board:
        for rid in recording_ids:
            feats = night_features(rid, frontends, index, aligner, board, hop_ms=hop_ms,
                                   window_ms=window_ms, pool_ms=pool_ms, pool_top=pool_top,
                                   keep=keep, quiet=quiet)
            r, g = score_night(feats, decoder.run(feats["chunks"]), rid)
            for x in r:
                x["recording_id"] = rid
            rows.extend(r)
            gaps[rid] = g
    return rows, gaps


def pooled_gaps(gaps):
    total = defaultdict(int)
    for g in gaps.values():
        for k, v in g.items():
            total[k] += v
    return dict(total)
