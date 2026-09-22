"""Does the tune come back from the index? The front end's own scoreboard.

The first real ensemble run scored zero, and reading why took a full replay
plus two inspection tools. That is far too slow a loop for choosing between
transcribers, and it confounds the front end with the assembler.

This asks the front end one question directly. Take a segment whose tune is
known, transcribe the first N seconds of it, look the intervals up in the
index, and see where the true tune lands. No board, no hypotheses, no
scheduler. Every label it needs is already in the corpus.

Two numbers matter and they answer different questions:

- **rank** of the true tune, reported as top-1/5/10 and a reciprocal-rank
  mean, which says whether the melody was recovered at all;
- **margin**, the true tune's score over the best wrong one, which says
  whether an assembler could ever tell them apart. A front end that puts the
  right tune second with a hair between them is far closer to working than
  one that puts it second by a mile.

Scored per night rather than leave-one-night-out, because a front end is not
fitted to anything. Transcriptions are cached on the same key the board uses,
so trying a different index, a different n, or a prior costs nothing.
"""

import json
import time
from collections import defaultdict

import numpy as np

from lab import paths
from lab.audio.chunks import AudioStore
from lab.audio.prepare import wav_sha1
from lab.bench.score import BenchResult, NightResult, git_sha
from lab.bench.tasks import load_ground_truth
from lab.board.board import Board
from lab.frontends.segmentation import intervals_from_notes

DEFAULT_SECONDS = 30


def transcribe_segment(frontend, store, audio_sha1, t0_ms, t1_ms, board=None):
    """Notes for a span. The PITCH TRACK is cached, not the notes.

    Tracking is the expensive step and note segmentation is not, so caching
    at this boundary means sweeping a voicing threshold costs one pass over
    the audio instead of one per value.
    """
    key = frontend.cache_key(audio_sha1, t0_ms, t1_ms)
    track = None
    cached = False
    if board is not None:
        hit = board.cache_get(key)
        if hit is not None:
            track, cost, cached = hit[0], hit[1], True
    if track is None:
        started = time.time()
        y = store.read(t0_ms, t1_ms)
        times, f0, voiced = frontend.track(y, store.sr)
        cost = (time.time() - started) * 1000.0
        track = {
            "times_ms": [round(float(t), 2) for t in times],
            "f0_hz": [None if not np.isfinite(v) else round(float(v), 2) for v in f0],
            "voiced_prob": [round(float(v), 4) for v in voiced],
        }
        if board is not None:
            board.cache_put(key, frontend.name, frontend.version, track, cost)
            # Commit per segment, not per night. Transcribing a night takes
            # minutes, and holding a write transaction that long stops any
            # other bench job writing to the same board at all, which is
            # exactly what happened the first time two ran side by side.
            board.conn.commit()
    f0 = np.array([np.nan if v is None else v for v in track["f0_hz"]], dtype=float)
    notes = frontend.notes_from_track(
        np.asarray(track["times_ms"], dtype=float), f0,
        np.asarray(track["voiced_prob"], dtype=float), t_offset_ms=t0_ms)
    return notes, cost, cached


def rerank(ranked, weights, beta=1.0, index=None, audio_floor=1e-3, prior_top=50):
    """Combine audio and prior over the UNION of what each proposes.

    Re-ranking only the audio's shortlist was wrong, and measurably so: the
    prior alone scored 0.245 top-1 while the prior applied to the audio's top
    25 scored 0.201. A tune the audio missed was excluded before the prior
    ever saw it, so the combination inherited the audio's recall and threw
    away the prior's. Scoring the union fixes that. A tune with no audio
    evidence gets `audio_floor`, which is what makes the prior able to carry
    a candidate the transcription never found.
    """
    import math

    if not weights:
        return ranked
    scores = {r["tune_id"]: r for r in ranked}
    for tune_id, _w in sorted(weights.items(), key=lambda kv: -kv[1])[:prior_top]:
        if tune_id not in scores:
            scores[tune_id] = {
                "tune_id": tune_id, "setting_id": None,
                "name": (index.tune_names.get(tune_id) if index else None),
                "tune_type": (index.tune_types.get(tune_id) if index else None),
                "score": 0.0, "coverage": 0.0, "hits": 0, "n_grams_queried": 0,
            }
    out = []
    for tune_id, r in scores.items():
        w = weights.get(tune_id, 1e-4)
        audio = max(audio_floor, r["score"])
        out.append({**r, "prior": w,
                    "combined": math.log(audio) + beta * math.log(max(1e-12, w))})
    out.sort(key=lambda d: -d["combined"])
    return out


def _blend(weights_by_prev, belief, floor=1e-4):
    """Weights when the previous tune is a distribution rather than a fact."""
    out = defaultdict(lambda: floor)
    for prev_id, p in belief.items():
        for tune_id, w in weights_by_prev(prev_id).items():
            out[tune_id] = out[tune_id] + p * w
    return out


def score_night(frontend, recording_id, index, seconds=DEFAULT_SECONDS, board=None,
                top_k=25, quiet=True, prior="none", beta=1.0, belief_k=5):
    gt = load_ground_truth(recording_id)
    sequence = previous_of = None
    if prior != "none":
        from lab.corpus.sequence import SequenceModel

        # the night being scored is held out of its own model
        sequence = SequenceModel(gt.session_id, exclude_instance_ids=[gt.session_instance_id])
        previous_of = gt.previous_tune_map()
    # For the self-chaining modes the system feeds its own answer forward
    # instead of being handed the true previous tune. Where a SET begins is
    # still taken from the log, because this measures the prior and not
    # boundary detection; only the identity of the previous tune is the
    # system's own. `belief` is what it currently thinks that was.
    belief = {}
    opens_set = True
    store = AudioStore(paths.wav_path(recording_id))
    store.clock_ms = store.duration_ms      # offline: the whole file is available
    sha = wav_sha1(recording_id) or ""
    rows = []
    try:
        for seg in gt.eval_segments():
            if not seg.evaluated or seg.tune_id is None:
                continue
            t0 = seg.start_ms
            t1 = min(seg.end_ms, t0 + int(seconds * 1000))
            if t1 - t0 < 5000:
                continue
            if prior in ("sequence_self", "sequence_soft"):
                opens_set = previous_of.get(seg.session_instance_tune_id) is None
                if opens_set:
                    belief = {}
            if prior == "prior_only":
                # the control: no audio at all, rank the repertoire by what
                # usually follows. If this beats the audio system, the audio
                # is not yet earning its keep.
                notes, cost, cached, intervals = [], 0.0, True, []
                weights = sequence.weights(previous_of.get(seg.session_instance_tune_id))
                ranked = [{"tune_id": t, "setting_id": None, "name": index.tune_names.get(t),
                           "tune_type": index.tune_types.get(t), "score": w, "coverage": 0.0,
                           "hits": 0, "n_grams_queried": 0}
                          for t, w in sorted(weights.items(), key=lambda kv: -kv[1])[:top_k]]
            else:
                notes, cost, cached = transcribe_segment(frontend, store, sha, t0, t1, board=board)
                intervals = intervals_from_notes(notes, fold=index.fold_octaves)
                ranked = index.lookup(intervals, top_k=(200 if prior == "sequence" else top_k))
                if prior == "sequence":
                    weights = sequence.weights(previous_of.get(seg.session_instance_tune_id))
                    ranked = rerank(ranked, weights, beta=beta, index=index)[:top_k]
                elif prior in ("sequence_self", "sequence_soft"):
                    if not belief:
                        weights = sequence.weights(None)
                    elif prior == "sequence_self":
                        weights = sequence.weights(max(belief, key=belief.get))
                    else:
                        weights = _blend(sequence.weights, belief)
                    ranked = rerank(ranked, weights, beta=beta, index=index)[:top_k]
                    # carry forward what it now believes it just heard
                    head = ranked[:belief_k]
                    total = sum(max(1e-9, r["score"]) for r in head) or 1.0
                    belief = {r["tune_id"]: max(1e-9, r["score"]) / total for r in head}
                    if prior == "sequence_self":
                        belief = {ranked[0]["tune_id"]: 1.0}
            rank = next((i + 1 for i, r in enumerate(ranked) if r["tune_id"] == seg.tune_id), None)
            true_score = next((r["score"] for r in ranked if r["tune_id"] == seg.tune_id), 0.0)
            best_wrong = next((r["score"] for r in ranked if r["tune_id"] != seg.tune_id), 0.0)
            rows.append({
                "segment_id": seg.segment_id, "tune_id": seg.tune_id, "name": seg.name,
                "tune_type": seg.tune_type, "seconds": (t1 - t0) / 1000.0,
                "n_notes": len(notes), "n_intervals": len([i for i in intervals if i is not None]),
                "rank": rank, "true_score": true_score, "best_wrong_score": best_wrong,
                "margin": true_score - best_wrong,
                "top1_name": ranked[0]["name"] if ranked else None,
                "cost_ms": cost, "cached": cached,
            })
            if not quiet and len(rows) % 20 == 0:
                print(f"    {len(rows)} segments ...", flush=True)
    finally:
        store.close()
    return rows


def decode_set(candidates, sequence, beta=1.0, audio_floor=1e-3, opener_bonus=True):
    """Best tune sequence for a whole set, rather than one tune at a time.

    Greedy chaining was barely worth anything: feeding the system's own answer
    forward gained one point over no prior, because that answer is wrong about
    two thirds of the time and a transition conditioned on a wrong tune is
    noise. The mistake is committing. A set is a short sequence with strong
    couplings, so the right thing is to score whole sequences and let later
    tunes correct an earlier guess.

    States are each segment's candidate tunes, emission is the audio score,
    transition is how often one tune follows another at this session. The
    result is the highest-scoring path, which can pick a tune the audio
    ranked third because the two tunes either side of it agree.
    """
    import math

    if not candidates:
        return []
    trans_cache = {}

    def weights_for(prev):
        if prev not in trans_cache:
            trans_cache[prev] = sequence.weights(prev)
        return trans_cache[prev]

    # first segment of the set: audio plus how often each tune opens a set
    opener = sequence.weights(None) if opener_bonus else None
    scores = []
    backs = []
    first = candidates[0]
    scores.append({
        c["tune_id"]: math.log(max(audio_floor, c["score"]))
        + (beta * math.log(max(1e-12, opener.get(c["tune_id"], 1e-4))) if opener else 0.0)
        for c in first})
    backs.append({c["tune_id"]: None for c in first})

    for step in range(1, len(candidates)):
        here = candidates[step]
        previous = scores[-1]
        best_here, back_here = {}, {}
        for c in here:
            tune_id = c["tune_id"]
            emission = math.log(max(audio_floor, c["score"]))
            best_score, best_prev = None, None
            for prev_id, prev_score in previous.items():
                w = weights_for(prev_id).get(tune_id, 1e-4)
                total = prev_score + beta * math.log(max(1e-12, w))
                if best_score is None or total > best_score:
                    best_score, best_prev = total, prev_id
            best_here[tune_id] = (best_score or 0.0) + emission
            back_here[tune_id] = best_prev
        scores.append(best_here)
        backs.append(back_here)

    path = [None] * len(candidates)
    last = scores[-1]
    if not last:
        return path
    path[-1] = max(last, key=last.get)
    for i in range(len(candidates) - 1, 0, -1):
        path[i - 1] = backs[i].get(path[i])
    return path


def summarise(rows):
    n = len(rows)
    if n == 0:
        return {"n": 0}
    ranks = [r["rank"] for r in rows]
    found = [r for r in ranks if r is not None]
    return {
        "n": n,
        "top1": sum(1 for r in ranks if r == 1) / n,
        "top5": sum(1 for r in ranks if r is not None and r <= 5) / n,
        "top10": sum(1 for r in ranks if r is not None and r <= 10) / n,
        "mrr": sum(1.0 / r for r in found) / n,
        "found_at_all": len(found) / n,
        "median_rank": float(np.median(found)) if found else None,
        "median_margin": float(np.median([r["margin"] for r in rows])),
        "median_notes": float(np.median([r["n_notes"] for r in rows])),
        "median_intervals": float(np.median([r["n_intervals"] for r in rows])),
        "cost_ms_per_segment": float(np.mean([r["cost_ms"] for r in rows])),
        # the metric that says whether a prior could rescue this: how often is
        # the true tune anywhere in the shortlist an assembler would consider
        "f1": sum(1 for r in ranks if r == 1) / n,   # so the leaderboard can rank it
    }


def score_night_set_decoded(frontend, recording_id, index, seconds=DEFAULT_SECONDS,
                            board=None, top_k=25, beta=1.0, audio_top=40):
    """Score a night by decoding each set as a whole.

    Two passes: transcribe and rank every segment as usual, then group the
    segments into sets using the log's breaks and run one Viterbi per set.
    Set boundaries come from the log because this measures the prior, not
    boundary detection; the tune identities are entirely the system's own.
    """
    from lab.corpus.sequence import SequenceModel

    gt = load_ground_truth(recording_id)
    sequence = SequenceModel(gt.session_id, exclude_instance_ids=[gt.session_instance_id])
    previous_of = gt.previous_tune_map()
    store = AudioStore(paths.wav_path(recording_id))
    store.clock_ms = store.duration_ms
    sha = wav_sha1(recording_id) or ""

    prepared = []
    try:
        for seg in gt.eval_segments():
            if not seg.evaluated or seg.tune_id is None:
                continue
            t0 = seg.start_ms
            t1 = min(seg.end_ms, t0 + int(seconds * 1000))
            if t1 - t0 < 5000:
                continue
            notes, cost, cached = transcribe_segment(frontend, store, sha, t0, t1, board=board)
            intervals = intervals_from_notes(notes, fold=index.fold_octaves)
            ranked = index.lookup(intervals, top_k=audio_top)
            prepared.append({"seg": seg, "ranked": ranked, "notes": notes,
                             "cost": cost, "cached": cached,
                             "opens_set": previous_of.get(seg.session_instance_tune_id) is None})
    finally:
        store.close()

    # split into sets, then decode each one
    sets, current = [], []
    for item in prepared:
        if item["opens_set"] and current:
            sets.append(current)
            current = []
        current.append(item)
    if current:
        sets.append(current)

    rows = []
    for group in sets:
        # union the audio's candidates with what the prior would suggest, so a
        # tune the transcription missed can still be carried by the sequence
        candidates = []
        for item in group:
            ranked = item["ranked"]
            known = {c["tune_id"] for c in ranked}
            extra = [{"tune_id": t, "setting_id": None, "name": index.tune_names.get(t),
                      "tune_type": index.tune_types.get(t), "score": 0.0, "coverage": 0.0,
                      "hits": 0, "n_grams_queried": 0}
                     for t in sequence.popularity() if t not in known][:0]
            candidates.append(ranked + extra)
        path = decode_set(candidates, sequence, beta=beta)
        for item, chosen in zip(group, path):
            seg = item["seg"]
            ordered = sorted(item["ranked"], key=lambda c: -c["score"])
            if chosen is not None:
                ordered = ([c for c in ordered if c["tune_id"] == chosen]
                           + [c for c in ordered if c["tune_id"] != chosen])
            rank = next((i + 1 for i, c in enumerate(ordered) if c["tune_id"] == seg.tune_id), None)
            true_score = next((c["score"] for c in ordered if c["tune_id"] == seg.tune_id), 0.0)
            best_wrong = next((c["score"] for c in ordered if c["tune_id"] != seg.tune_id), 0.0)
            rows.append({
                "segment_id": seg.segment_id, "tune_id": seg.tune_id, "name": seg.name,
                "tune_type": seg.tune_type, "seconds": seconds,
                "n_notes": len(item["notes"]),
                "n_intervals": len(item["notes"]) - 1 if item["notes"] else 0,
                "rank": rank, "true_score": true_score, "best_wrong_score": best_wrong,
                "margin": true_score - best_wrong,
                "top1_name": ordered[0]["name"] if ordered else None,
                "cost_ms": item["cost"], "cached": item["cached"],
            })
    return rows


def run_retrieval(frontend, recording_ids=None, candidate_set="repertoire", n=5,
                  seconds=DEFAULT_SECONDS, quiet=False, prior="none", beta=1.0,
                  fold_octaves=False, belief_k=5):
    from lab.corpus.index import Index

    index = Index.load(candidate_set, n=n, fold_octaves=fold_octaves)
    recording_ids = recording_ids or paths.prepared_recording_ids()
    nights, all_rows = [], []
    with Board() as board:
        for rid in recording_ids:
            t0 = time.time()
            if prior == "set_viterbi":
                rows = score_night_set_decoded(frontend, rid, index, seconds=seconds,
                                               board=board, beta=beta)
            else:
                rows = score_night(frontend, rid, index, seconds=seconds, board=board,
                                   quiet=quiet, prior=prior, beta=beta, belief_k=belief_k)
            board.conn.commit()
            gt = load_ground_truth(rid)
            m = summarise(rows)
            nights.append(NightResult(recording_id=rid, label=gt.label, date=gt.date,
                                      metrics=m, n_frames=len(rows),
                                      predict_seconds=round(time.time() - t0, 1)))
            all_rows.extend(rows)
            if not quiet:
                print(f"  {rid:>4} {gt.date}  {m['n']:>3} segments  top1 {m['top1']:.3f} "
                      f"top5 {m['top5']:.3f} mrr {m['mrr']:.3f}  "
                      f"median notes {m['median_notes']:.0f}  {time.time() - t0:.0f}s", flush=True)

    pooled = summarise(all_rows)
    pooled["nights"] = len(nights)
    result = BenchResult(
        task="tune_retrieval",
        candidate=frontend.name if prior == "none" else f"{frontend.name}+{prior}", version=frontend.version,
        params={**frontend.params, "candidate_set": candidate_set, "n": n,
                "seconds": seconds, "prior": prior, "beta": beta,
                "fold_octaves": fold_octaves},
        features_version="audio", split="per-night",
        nights=nights, pooled=pooled, warnings=[],
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"), git_sha=git_sha())
    return result, all_rows


def format_retrieval(result, rows=None):
    p = result.pooled
    lines = [f"{result.candidate} v{result.version} on tune_retrieval  "
             f"[{result.params['candidate_set']} index, first {result.params['seconds']}s of each segment]",
             f"  params: {json.dumps({k: v for k, v in result.params.items() if v is not None}, sort_keys=True)}"]
    for nres in result.nights:
        m = nres.metrics
        lines.append(f"  {nres.recording_id:>4} {nres.date}  {m['n']:>3} segments  "
                     f"top1 {m['top1']:.3f}  top5 {m['top5']:.3f}  mrr {m['mrr']:.3f}")
    lines.append(f"  ALL   {p['n']} segments  top1 {p['top1']:.3f}  top5 {p['top5']:.3f}  "
                 f"top10 {p['top10']:.3f}  mrr {p['mrr']:.3f}")
    lines.append(f"  found anywhere in top 25: {p['found_at_all']:.3f}"
                 + (f", median rank when found {p['median_rank']:.0f}" if p["median_rank"] else ""))
    lines.append(f"  median notes per segment {p['median_notes']:.0f}, "
                 f"intervals {p['median_intervals']:.0f}, "
                 f"median margin {p['median_margin']:+.4f}, "
                 f"{p['cost_ms_per_segment']:.0f}ms per segment")
    if rows:
        hits = [r for r in rows if r["rank"] == 1]
        lines.append(f"  correct on {len(hits)} segments"
                     + (": " + ", ".join(sorted({r['name'] for r in hits})[:6]) if hits else ""))
    return "\n".join(lines)
