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
    if (frontend.params.get("split_repeats") or frontend.params.get("min_note_eighths")
            or frontend.params.get("out_of_key_drop")):
        # The only thing here that needs the audio again. Cheap next to
        # tracking, and read only when it is asked for.
        notes = frontend.regrid(notes, store.read(t0_ms, t1_ms), store.sr,
                                t_offset_ms=t0_ms)
    return notes, cost, cached


def prior_weight(weights, tune_id, fallback=1e-4):
    """A tune's prior weight, using the weights' own default for a missing tune.

    `.get(tune_id, 1e-4)` looked equivalent and was not: it bypasses a
    defaultdict's own default, so a weighting that gives an unseen tune a
    considered share had that share replaced by 1e-4, quietly, everywhere the
    prior was read. For the original weights the default IS 1e-4, so nothing
    measured with them changes.
    """
    if tune_id in weights:
        return weights[tune_id]
    factory = getattr(weights, "default_factory", None)
    return factory() if factory is not None else fallback


def fuse(rankings, method="rrf", k=20):
    """Combine rankings from several front ends.

    The board's premise, tested: several experts produce the same kind of
    evidence and disagree, and the disagreement is worth something. Their
    scores are not on a common scale, so the default is reciprocal rank
    fusion, which only uses the order each one produced. A tune that two
    different transcriptions both rank highly is better supported than one
    that a single transcription loves.
    """
    if len(rankings) == 1:
        return rankings[0]
    merged = {}
    meta = {}
    for ranked in rankings:
        total = sum(max(0.0, r["score"]) for r in ranked) or 1.0
        for position, r in enumerate(ranked, start=1):
            tid = r["tune_id"]
            meta.setdefault(tid, r)
            if method == "sum":
                merged[tid] = merged.get(tid, 0.0) + max(0.0, r["score"]) / total
            else:
                merged[tid] = merged.get(tid, 0.0) + 1.0 / (k + position)
    out = [{**meta[t], "score": v} for t, v in merged.items()]
    out.sort(key=lambda d: -d["score"])
    return out


def ranked_for_segment(frontends, store, sha, t0, t1, index, board, audio_top,
                       fusion="rrf", particalized_index=None, aligner=None):
    """Transcribe with each front end and fuse what the index says about each.

    With `particalized_index`, the same transcription is also read as a run of
    eighth notes and looked up in an index built the same way, and the two
    rankings are fused. They disagree usefully: a transcriber hears pitch and
    not articulation, so two tongued Gs and one held G are indistinguishable
    to it, and writing both sides as eighths removes that confusion at the
    cost of leaning on the grid being right. One view is wrong about
    articulation, the other about tempo, and they are wrong about different
    tunes.
    """
    rankings, notes_all, cost_all, cached_all = [], [], 0.0, True
    heard = []   # (notes, eighth slots or None) per front end, for the aligner
    pulse = None
    for fe in frontends:
        notes, cost, cached = transcribe_segment(fe, store, sha, t0, t1, board=board)
        intervals = intervals_from_notes(notes, fold=index.fold_octaves)
        rankings.append(index.lookup(intervals, top_k=audio_top))
        slots = None
        if (particalized_index is not None or aligner is not None) and len(notes) >= 30:
            from lab.analysis.notation import particalize
            from lab.analysis.pulse import estimate_pulse
            from lab.corpus.abc_pitch import interval_sequence

            if pulse is None:
                pulse = estimate_pulse(store.read(t0, t1), store.sr) or {}
            if pulse:
                slots = particalize(notes, pulse["period_ms"], phase_ms=t0)
                if particalized_index is not None:
                    rankings.append(particalized_index.lookup(
                        interval_sequence(slots, fold=particalized_index.fold_octaves),
                        top_k=audio_top))
        heard.append((notes, slots))
        notes_all.extend(notes)
        cost_all += cost
        cached_all = cached_all and cached
    ranked = fuse(rankings, method=fusion)
    if aligner is not None:
        ranked = aligner.rerank(ranked, heard)
    return ranked, notes_all, cost_all, cached_all


def fifths_steps(max_fifths):
    """{semitone shift: steps round the circle of fifths}, out to
    `max_fifths` steps either way: 0 -> 0, a fifth up (+7) or down (+5) -> 1,
    a tone up (+2) or down (+10) -> 2, and so on."""
    out = {}
    for n in range(max_fifths + 1):
        for k in ((7 * n) % 12, (-7 * n) % 12):
            out.setdefault(k, n)
    return out


class Aligner:
    """Re-rank the n-gram shortlist by aligning what was heard against each
    candidate's notes (`analysis.align`), as Tunepal and FolkFriend match.

    `reading`: "eighths" (both sides as runs of eighth notes), "notes" (both
    sides as changes of pitch, tempo-free) or "both". `mode`: "replace" orders
    the shortlist by alignment alone; "fuse" sums it with the n-gram ranking
    the way front ends are fused. `transpose`: 0 aligns in each setting's
    written key; 12 also tries every transposition and keeps the best
    (untested); "fifths" is the player's key allowance: a tune may be played
    in another key than its settings, tried outward round the circle of
    fifths from each setting's own key, at most `max_fifths` steps (one step
    is a fifth either way, +7 or +5 semitones; two is a tone either way), each
    step costing `step_cost` off the score, so the written key stays the
    strong default and a wrong tune does not get twelve chances at a lucky
    match. A key some setting is written in costs nothing.

    Measured over 502 segments, audio alone, both readings, replace, 300-tune
    shortlist: yin at 30 s 0.687 -> 0.902 top-1 (+108/-0); yin, Basic Pitch
    and PESTO at 30 s 0.763 -> 0.950 (+95/-1), at 120 s 0.982. Replace beats
    fuse (0.843 against 0.739 at a 25-tune shortlist) and the longer the
    shortlist the better (0.843 / 0.886 / 0.902 at 25 / 100 / 300). Aligned
    against the wrong segment's audio it scores 0.008. With set decoding,
    `beta` 0.15 (tuned on the n-gram scores) swamps it (0.753 at 120 s);
    0.01 is harmless and adds nothing measurable (30 s 0.950 -> 0.956, +3/-0;
    +2/-1 with the weight chosen leave-one-night-out). See the spec, "The
    aligner".
    """

    def __init__(self, reading="eighths", mode="fuse", shortlist=25, chunk_eighths=32,
                 chunk_notes=24, transpose=0, max_fifths=2, step_cost=0.02, key_top=50,
                 candidate_set="repertoire"):
        from lab.corpus.sequences import TuneSequences

        self.reading, self.mode, self.shortlist = reading, mode, shortlist
        self.chunk_eighths, self.chunk_notes, self.transpose = chunk_eighths, chunk_notes, transpose
        self.max_fifths, self.step_cost = int(max_fifths), float(step_cost)
        self.key_top = int(key_top)
        self.sequences = TuneSequences.load(candidate_set)
        self._doubled = {}   # (tune, setting index, kind, shift) -> target as aligned

    def params(self):
        out = {"reading": self.reading, "mode": self.mode, "shortlist": self.shortlist,
               "chunk_eighths": self.chunk_eighths, "chunk_notes": self.chunk_notes,
               "transpose": self.transpose}
        if self.transpose == "fifths":
            out.update(max_fifths=self.max_fifths, step_cost=self.step_cost, key_top=self.key_top)
        return out

    def _queries(self, heard):
        out = []
        for notes, slots in heard:
            if self.reading in ("notes", "both") and notes:
                pcs = []
                for n in notes:
                    pc = int(round(n["midi"])) % 12
                    if not pcs or pcs[-1] != pc:
                        pcs.append(pc)
                out.append(("notes", pcs))
            if self.reading in ("eighths", "both") and slots:
                out.append(("eighths", [-1 if p is None else int(p) % 12 for p in slots]))
        return out

    def shift_scores(self, tune_id, queries, shifts):
        """{semitone shift: the tune's score played that far from each
        setting's written key}, each query taking its best setting."""
        from lab.analysis.align import chunk_score

        settings = self.sequences.by_tune.get(tune_id) or []
        if not settings or not queries:
            return {k: 0.0 for k in shifts}
        out = {}
        for k in shifts:
            total = 0.0
            for kind, q in queries:
                chunk = self.chunk_eighths if kind == "eighths" else self.chunk_notes
                total += max(chunk_score(q, eighths if kind == "eighths" else plain,
                                         chunk=chunk, transpose=k)
                             for _, eighths, plain in settings)
            out[k] = total / len(queries)
        return out

    def score(self, tune_id, queries):
        from lab.analysis.align import chunk_score

        if self.transpose == "fifths":
            steps = fifths_steps(self.max_fifths)
            by_shift = self.shift_scores(tune_id, queries, steps)
            return max(v - self.step_cost * steps[k] for k, v in by_shift.items())
        settings = self.sequences.by_tune.get(tune_id) or []
        if not settings or not queries:
            return 0.0
        shifts = range(12) if self.transpose == 12 else (0,)
        total = 0.0
        for kind, q in queries:
            chunk = self.chunk_eighths if kind == "eighths" else self.chunk_notes
            best = 0.0
            for _, eighths, plain in settings:
                target = eighths if kind == "eighths" else plain
                for k in shifts:
                    best = max(best, chunk_score(q, target, chunk=chunk, transpose=k))
            total += best
        return total / len(queries)

    def _batch_scores(self, tune_ids, queries, shift):
        """{tune: score at `shift`} for many tunes in one parallel pass
        (`analysis.align.batch_chunk_scores`), equal value for value to
        `shift_scores` one tune at a time: each query takes its best setting,
        averaged over queries."""
        from lab.analysis.align import batch_chunk_scores, doubled, query_pieces

        best = [dict() for _ in queries]     # per query: tune -> best setting's score
        for kind in ("eighths", "notes"):
            idx = [i for i, (k, _) in enumerate(queries) if k == kind]
            if not idx:
                continue
            chunk = self.chunk_eighths if kind == "eighths" else self.chunk_notes
            targets, owner = [], []
            for tid in tune_ids:
                for si, (_, eighths, plain) in enumerate(self.sequences.by_tune.get(tid) or []):
                    key = (tid, si, kind, shift)
                    if key not in self._doubled:
                        self._doubled[key] = doubled(eighths if kind == "eighths" else plain, shift)
                    targets.append(self._doubled[key])
                    owner.append(tid)
            m = batch_chunk_scores([query_pieces(queries[i][1], chunk) for i in idx], targets)
            for row, i in enumerate(idx):
                for ti, tid in enumerate(owner):
                    if m[row, ti] > best[i].get(tid, 0.0):
                        best[i][tid] = m[row, ti]
        out = {}
        for tid in tune_ids:
            if not self.sequences.by_tune.get(tid):
                out[tid] = 0.0
                continue
            total = 0.0
            for i in range(len(queries)):
                total += best[i].get(tid, 0.0)
            out[tid] = total / len(queries)
        return out

    def scores(self, tune_ids, queries):
        """Every shortlisted tune's score, as `score` would give it. With the
        key allowance, other keys are tried only for the first `key_top` in
        the index's order: the index matches intervals, so its order does not
        depend on key, and at 30 s trying the top 20 gives the same top-1 as
        trying all 300 on all 502 segments (Galway Belle is 17th, Mac's Fancy
        4th); 50 leaves a margin, at a third of the cost."""
        if self.transpose not in (0, "fifths"):
            return {tid: self.score(tid, queries) for tid in tune_ids}
        base = self._batch_scores(tune_ids, queries, 0)
        if self.transpose == 0:
            return base
        steps = fifths_steps(self.max_fifths)
        top = list(tune_ids[:self.key_top])
        best = dict(base)
        for k, n in steps.items():
            if k == 0:
                continue
            for tid, v in self._batch_scores(top, queries, k).items():
                best[tid] = max(best[tid], v - self.step_cost * n)
        return best

    def rerank(self, ranked, heard):
        queries = self._queries(heard)
        if not queries or not ranked:
            return ranked
        head, tail = ranked[:self.shortlist], ranked[self.shortlist:]
        by_tune = self.scores([r["tune_id"] for r in head], queries)
        aligned = [{**r, "score": by_tune[r["tune_id"]]} for r in head]
        aligned.sort(key=lambda r: -r["score"])
        if self.mode == "replace":
            return aligned + tail
        return fuse([head, aligned], method="sum") + tail


def _apply_type_filter(ranked, seg, type_filter, type_probs):
    """Narrow or reweight candidates by what kind of tune this is.

    Three strengths, because the right one is an empirical question. Hard
    filtering on the classifier's best guess is worse than no filter at all
    (0.479 against 0.485): when it is wrong it removes the answer. Keeping
    every type it has not ruled out is best (0.517), because a repertoire
    that is 43% reels still loses most of its field.
    """
    if type_filter == "none" or not ranked:
        return ranked

    def type_of(r):
        return (r.get("tune_type") or "").strip().lower()

    if type_filter == "oracle":
        if not seg.tune_type:
            return ranked
        kept = [r for r in ranked if type_of(r) == seg.tune_type.strip().lower()]
        return kept or ranked

    probs = (type_probs or {}).get(str(seg.segment_id)) or {}
    if not probs:
        return ranked
    if type_filter == "predicted_hard":
        best = max(probs, key=probs.get)
        return [r for r in ranked if type_of(r) == best] or ranked
    if type_filter == "predicted_plausible":
        allowed = {k for k, v in probs.items() if v >= 0.12}
        return [r for r in ranked if type_of(r) in allowed] or ranked
    if type_filter == "predicted":
        return sorted(ranked, key=lambda r: -(max(1e-6, r["score"])
                                              * max(0.05, probs.get(type_of(r), 0.0))))
    return ranked


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
        w = prior_weight(weights, tune_id)
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


def score_night(frontends, recording_id, index, seconds=DEFAULT_SECONDS, board=None,
                top_k=25, quiet=True, prior="none", beta=1.0, belief_k=5,
                type_filter="none", fusion="rrf", particalized_index=None, aligner=None):
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
    type_probs = None
    if type_filter.startswith("predicted"):
        from lab.bench.tunetype import predictions_path

        with open(predictions_path()) as f:
            type_probs = json.load(f)["by_segment"]
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
                ranked, notes, cost, cached = ranked_for_segment(
                    frontends, store, sha, t0, t1, index, board,
                    audio_top=max(200 if prior.startswith("sequence") else top_k,
                                  aligner.shortlist if aligner is not None else 0),
                    fusion=fusion, particalized_index=particalized_index, aligner=aligner)
                intervals = []
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
            ranked = _apply_type_filter(ranked, seg, type_filter, type_probs)
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


def evidence_strength(ranked):
    """How much this segment's audio is worth listening to, without the answer.

    Measured over 503 segments, the index's top score correlates +0.55 with
    being right and the gap to the runner-up +0.53, while the note rate
    correlates +0.02. The tracker always produces notes; what varies is
    whether they are the right ones, and the score says so before the truth
    does. A segment whose evidence is weak should defer to the sequence more
    than one whose evidence is strong, and a fixed weight cannot do that.
    """
    if not ranked:
        return 0.0
    top = max(0.0, ranked[0]["score"])
    second = max(0.0, ranked[1]["score"]) if len(ranked) > 1 else 0.0
    return top + (top - second)


def decode_set(candidates, sequence, beta=1.0, audio_floor=1e-3, opener_bonus=True,
               adaptive=False, reference_strength=0.11):
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
    betas = []
    for ranked in candidates:
        if not adaptive:
            betas.append(beta)
            continue
        strength = evidence_strength(ranked)
        # weak audio leans on the sequence, strong audio is left alone
        betas.append(beta * min(3.0, max(0.35, reference_strength / max(1e-6, strength))))

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
        + (betas[0] * math.log(max(1e-12, prior_weight(opener, c["tune_id"]))) if opener else 0.0)
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
                w = prior_weight(weights_for(prev_id), tune_id)
                total = prev_score + betas[step] * math.log(max(1e-12, w))
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


def score_night_set_decoded(frontends, recording_id, index, seconds=DEFAULT_SECONDS,
                            board=None, top_k=25, beta=1.0, audio_top=40,
                            type_filter="none", fusion="rrf", adaptive=False,
                            particalized_index=None, aligner=None):
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

    type_probs = None
    if type_filter.startswith("predicted"):
        from lab.bench.tunetype import predictions_path

        with open(predictions_path()) as f:
            type_probs = json.load(f)["by_segment"]

    prepared = []
    try:
        for seg in gt.eval_segments():
            if not seg.evaluated or seg.tune_id is None:
                continue
            t0 = seg.start_ms
            t1 = min(seg.end_ms, t0 + int(seconds * 1000))
            if t1 - t0 < 5000:
                continue
            ranked, notes, cost, cached = ranked_for_segment(
                frontends, store, sha, t0, t1, index, board,
                audio_top=max(audio_top, aligner.shortlist if aligner is not None else 0),
                fusion=fusion, particalized_index=particalized_index, aligner=aligner)
            ranked = _apply_type_filter(ranked, seg, type_filter, type_probs)
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
        path = decode_set(candidates, sequence, beta=beta, adaptive=adaptive)
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


def run_retrieval(frontends, recording_ids=None, candidate_set="repertoire", n=5,
                  seconds=DEFAULT_SECONDS, quiet=False, prior="none", beta=1.0,
                  fold_octaves=False, belief_k=5, type_filter="none", fusion="rrf",
                  adaptive=False, particalized=False, aligner=None):
    from lab.corpus.index import Index

    index = Index.load(candidate_set, n=n, fold_octaves=fold_octaves)
    particalized_index = (Index.load(candidate_set, n=n, fold_octaves=fold_octaves,
                                     particalized=True) if particalized else None)
    if not isinstance(frontends, (list, tuple)):
        frontends = [frontends]
    explicit_nights = bool(recording_ids)
    recording_ids = recording_ids or paths.prepared_recording_ids()
    nights, all_rows = [], []
    with Board() as board:
        for rid in recording_ids:
            t0 = time.time()
            if prior == "set_viterbi":
                rows = score_night_set_decoded(frontends, rid, index, seconds=seconds,
                                               board=board, beta=beta, adaptive=adaptive,
                                               type_filter=type_filter, fusion=fusion,
                                               particalized_index=particalized_index,
                                               aligner=aligner)
            else:
                rows = score_night(frontends, rid, index, seconds=seconds, board=board,
                                   quiet=quiet, prior=prior, beta=beta, belief_k=belief_k,
                                   type_filter=type_filter, fusion=fusion,
                                   particalized_index=particalized_index, aligner=aligner)
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
        candidate=("+".join(f.name for f in frontends)
                   + ("" if prior == "none" else f"+{prior}")), version=frontends[0].version,
        params={**frontends[0].params, "candidate_set": candidate_set, "n": n,
                "frontends": [f.name for f in frontends], "fusion": fusion,
                "seconds": seconds, "prior": prior, "beta": beta,
                "fold_octaves": fold_octaves, "type_filter": type_filter,
                "adaptive": adaptive,
                **({"align": aligner.params()} if aligner is not None else {}),
                # in the saved file's name, so a run over some nights does not
                # overwrite the same settings over all of them; absent for the
                # default (every prepared night) so those names are unchanged
                **({"recording_ids": list(recording_ids)} if explicit_nights else {})},
        features_version="audio", split="per-night",
        nights=nights, pooled=pooled, warnings=[],
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"), git_sha=git_sha(),
        rows=[{k: r[k] for k in PAIRED_ROW_KEYS} for r in all_rows])
    return result, all_rows


# what a saved result keeps of each segment: enough to pair two results
PAIRED_ROW_KEYS = ("segment_id", "tune_id", "name", "tune_type", "rank", "top1_name", "n_notes")


def pair_results(a_rows, b_rows):
    """Pair two results' per-segment rows: pooled rates, newly right, newly wrong.

    Returns {"n", "top1": (a, b, won, lost, p), "top5": ..., "by_type": {type: (n, a, b)},
    "won", "lost"} where won/lost are the top-1 segment ids that changed.
    """
    from lab.tools.compare import sign_test

    a = {r["segment_id"]: r for r in a_rows}
    b = {r["segment_id"]: r for r in b_rows}
    common = sorted(set(a) & set(b))
    out = {"n": len(common)}
    if not common:
        return out

    def top(r, k):
        return r["rank"] is not None and r["rank"] <= k

    for k in (1, 5):
        won = [s for s in common if top(b[s], k) and not top(a[s], k)]
        lost = [s for s in common if top(a[s], k) and not top(b[s], k)]
        out[f"top{k}"] = (sum(top(a[s], k) for s in common) / len(common),
                          sum(top(b[s], k) for s in common) / len(common),
                          len(won), len(lost), sign_test(len(won), len(lost)))
        if k == 1:
            out["won"], out["lost"] = won, lost
    by = {}
    for s in common:
        t = (a[s].get("tune_type") or "?").lower()
        n, ra, rb = by.get(t, (0, 0, 0))
        by[t] = (n + 1, ra + top(a[s], 1), rb + top(b[s], 1))
    out["by_type"] = by
    return out


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
