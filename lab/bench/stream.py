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
   `window_ms` of notes (6 s since 2026-09-30: 8 s kept the previous tune on
   display 2.5 s longer at no gain; see the spec) are aligned (the retrieval bench's `Aligner`, same
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


def night_tracks(frontends, rid, board, block_ms=60000):
    """{front end name: (times_ms, f0_hz, voiced_prob)} for the whole night,
    absolute times, from the same cached block tracks as `night_notes`."""
    from lab.bench.retrieval import transcribe_segment

    store = AudioStore(paths.wav_path(rid))
    store.clock_ms = store.duration_ms
    sha = wav_sha1(rid) or ""
    out = {}
    try:
        for fe in frontends:
            ts, fs, vs = [], [], []
            for t0 in range(0, int(store.duration_ms), block_ms):
                t1 = min(int(store.duration_ms), t0 + block_ms)
                if t1 - t0 < 2000:
                    continue
                key = fe.cache_key(sha, t0, t1)
                hit = board.cache_get(key) if board is not None else None
                if hit is None:       # track it (and cache it) the usual way
                    transcribe_segment(fe, store, sha, t0, t1, board=board)
                    hit = board.cache_get(key)
                tr = hit[0]
                ts.append(np.asarray(tr["times_ms"], dtype=float) + t0)
                fs.append(np.array([np.nan if v is None else v for v in tr["f0_hz"]], dtype=float))
                vs.append(np.asarray(tr["voiced_prob"], dtype=float))
            out[fe.name] = (np.concatenate(ts), np.concatenate(fs), np.concatenate(vs))
    finally:
        store.close()
    return out, store.duration_ms


def causal_notes(fe, track, store, a, t):
    """Notes from the frames and audio in [a, t) only: segmented, split and
    key-filtered on that span, so nothing after t shapes them, and a note
    still sounding at t is cut off there, as it would be live."""
    times, f0, voiced = track
    i, j = np.searchsorted(times, a), np.searchsorted(times, t)
    if j - i < 4:
        return []
    notes = fe.notes_from_track(times[i:j] - a, f0[i:j], voiced[i:j], t_offset_ms=a)
    if notes and (fe.params.get("split_repeats") or fe.params.get("min_note_eighths")
                  or fe.params.get("out_of_key_drop")):
        notes = fe.regrid(notes, store.read(a, t), store.sr, t_offset_ms=a)
    return notes


def _hint_features(store, t, scores, queries, aligner, meter_ms=12000, top=5):
    """What the player's hints need, per chunk: the meter heard over the
    trailing `meter_ms` (2 = eighths in twos, reels, hornpipes, polkas; 3 =
    in threes, jigs, slides, slip jigs), and for the `top` best-scoring tunes
    where in the tune the most recent notes sit (0..1 of the tune once
    through), from whichever tracker's latest notes align best."""
    from lab.analysis.align import where_in_tune
    from lab.analysis.pulse import estimate_pulse

    pulse = estimate_pulse(store.read(max(0, t - meter_ms), t), store.sr) or {}
    out = {"grouping": pulse.get("grouping"), "grouping_margin": pulse.get("grouping_margin"),
           "period_ms": pulse.get("period_ms"), "where": {}}
    plain = [q for kind, q in queries if kind == "notes"]
    for tid in sorted(scores, key=lambda k: -scores[k])[:top]:
        best = (0.0, None)
        for _, _, target in aligner.sequences.by_tune.get(tid) or []:
            for q in plain:
                got = where_in_tune(q, target, chunk=aligner.chunk_notes)
                if got[1] is not None and got[0] > best[0]:
                    best = got
        if best[1] is not None:
            out["where"][tid] = round(float(best[1]), 4)
    return out


def _window(notes, starts, a, b):
    i, j = np.searchsorted(starts, a), np.searchsorted(starts, b)
    return notes[i:j]


class ChunkScorer:
    """One chunk's evidence from the notes heard so far: the pool of
    candidates (the index's fused shortlist over the context, plus the last
    `keep` chunks' pools, so the tune being followed stays scored) and each
    candidate's aligner score on the latest `window_ms` of notes. The bench
    (`night_features`) and the board (`experts.follower`) both call this,
    so the two loops cannot drift apart here."""

    def __init__(self, index, aligner, window_ms=6000, pool_top=100, keep=6, known=None,
                 fallback_index=None, fallback_top=20, shortlists=None, preferred=None):
        self.index, self.aligner = index, aligner
        # Merged shortlists (spec 053, "One corpus for every session"): with
        # `shortlists` = [(only, top)], the pool is the union of each one's top
        # from this one index, `only` a set of tunes to rank among (the
        # session's own, or popular ones) or None for the whole index. Tunes not
        # in `preferred` are marked "outside", as the fallback's are.
        self.shortlists, self.preferred = shortlists, preferred
        self.window_ms, self.pool_top, self.keep = window_ms, pool_top, keep
        # A tune new to the session: `known` restricts the index's pool to
        # tunes the session has played (None: all of the index), and
        # `fallback_index` (the whole corpus) adds its own top
        # `fallback_top`, marked "outside" so the decoder can discount them.
        # The aligner must hold sequences for every tune either can propose.
        self.known, self.fallback_index, self.fallback_top = known, fallback_index, fallback_top
        # tunes scored on every chunk whatever the index proposes: a tune a
        # person has said is playing (`lab listen`)
        self.pinned = set()
        self.recent = []
        self.last_heard = self.last_queries = self.last_tunes = None

    def score(self, t, ctx_by):
        """`ctx_by`: {source: notes over the context, by start time}, the
        sources in a fixed order. -> {"t_ms", "scores", "floor", "n_notes"}."""
        from lab.bench.retrieval import fuse
        from lab.frontends.segmentation import intervals_from_notes

        if self.shortlists is not None:
            pool = []
            for only, top in self.shortlists:
                ranked = [self.index.lookup(intervals_from_notes(ctx, fold=self.index.fold_octaves),
                                            top_k=top, only=only) for ctx in ctx_by.values()]
                pool += [r["tune_id"] for r in fuse(ranked, method="sum")[:top] if r["tune_id"] not in pool]
            return self._finish(t, ctx_by, pool, outside_of=self.preferred)
        rankings = [self.index.lookup(intervals_from_notes(ctx, fold=self.index.fold_octaves),
                                      top_k=self.pool_top) for ctx in ctx_by.values()]
        pool = [r["tune_id"] for r in fuse(rankings, method="sum")[:self.pool_top]]
        if self.known is not None:
            pool = [t for t in pool if t in self.known]
        if self.fallback_index is not None:
            fb = [self.fallback_index.lookup(intervals_from_notes(ctx, fold=self.fallback_index.fold_octaves),
                                             top_k=self.fallback_top) for ctx in ctx_by.values()]
            pool += [r["tune_id"] for r in fuse(fb, method="sum")[:self.fallback_top]
                     if r["tune_id"] not in pool]
        outside_of = None
        if self.fallback_index is not None:
            outside_of = self.known if self.known is not None else set(self.index.tune_names)
        return self._finish(t, ctx_by, pool, outside_of=outside_of)

    def _finish(self, t, ctx_by, pool, outside_of=None):
        self.recent = (self.recent + [pool])[-(self.keep + 1):]
        tunes = list(dict.fromkeys(tid for p in reversed(self.recent) for tid in p))
        tunes += [t for t in self.pinned if t not in tunes]
        heard = [([n for n in ctx if n["t0_ms"] >= t - self.window_ms], None)
                 for ctx in ctx_by.values()]
        queries = self.aligner._queries(heard)
        scores = self.aligner.scores(tunes, queries) if (queries and tunes) else {}
        self.last_heard, self.last_queries, self.last_tunes = heard, queries, tunes
        out = {"t_ms": t, "scores": {k: float(v) for k, v in scores.items()},
               "floor": float(min(scores.values())) if scores else 0.0,
               "n_notes": sum(len(h[0]) for h in heard)}
        if outside_of is not None:
            out["outside"] = [k for k in scores if k not in outside_of]
        return out


def night_features(rid, frontends, index, aligner, board, hop_ms=4000, window_ms=6000,
                   pool_ms=24000, pool_top=100, keep=6, causal=True, extra_windows=(),
                   known=None, fallback_index=None, fallback_top=20, quiet=True):
    """Per chunk: {"t_ms": end of the chunk, "scores": {tune: aligner score},
    "floor": the pool's lowest score, "n_notes"}. Cached per night and
    settings.

    `causal` (the default since 2026-09-30): notes for each chunk are
    rebuilt from the frames and audio up to its end only (`causal_notes` over the trailing `pool_ms`), instead of
    cut from notes made over 60 s blocks, whose key filter and repeat
    splitting read up to a minute of later audio. The frame tracks are the
    same cached ones; the neural trackers' frames still see under about a
    second of later audio through their own input windows. On night 140,
    tuned decoder, causal against block notes: +0/-0 right at the end and
    within 30 s on all 86 segments; the time between tunes shown as a tune
    14.7% to 6.8%. The block mode reproduces its saved features exactly."""
    key = repr((FEATURES_VERSION, rid, [f.name for f in frontends], [f.version for f in frontends],
                [sorted(f.params.items()) for f in frontends], index.candidate_set, index.n,
                aligner.params(), hop_ms, window_ms, pool_ms, pool_top, keep)
               + (("causal", "hints-v1") if causal else ())
               + ((("extra_windows",) + tuple(extra_windows)) if extra_windows else ())
               + ((("known", tuple(sorted(known))) if known is not None else ()))
               + ((("fallback", fallback_index.candidate_set, fallback_top)) if fallback_index is not None else ()))
    path = _features_path(rid, key)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    started = time.time()
    store = None
    if causal:
        tracks, duration = night_tracks(frontends, rid, board)
        store = AudioStore(paths.wav_path(rid))
        store.clock_ms = store.duration_ms
    else:
        by_fe, duration = night_notes(frontends, rid, board, quiet=quiet)
        starts = {k: np.array([n["t0_ms"] for n in v]) for k, v in by_fe.items()}
    chunks = []
    scorer = ChunkScorer(index, aligner, window_ms=window_ms, pool_top=pool_top, keep=keep,
                         known=known, fallback_index=fallback_index, fallback_top=fallback_top)
    for t in range(window_ms, int(duration) + 1, hop_ms):
        if causal:
            a = max(0, t - pool_ms)
            ctx_by = {fe.name: causal_notes(fe, tracks[fe.name], store, a, t) for fe in frontends}
        else:
            ctx_by = {name: _window(notes, starts[name], t - pool_ms, t) for name, notes in by_fe.items()}
        chunk = scorer.score(t, ctx_by)
        heard, queries, tunes, scores = scorer.last_heard, scorer.last_queries, scorer.last_tunes, chunk["scores"]
        if causal:
            chunk.update(_hint_features(store, t, scores, queries, aligner))
        if extra_windows:
            # the same tunes scored on only the latest part of the window, so
            # the decoder can weight the newest notes (`mix_windows`)
            chunk["by_window"] = {}
            for w in extra_windows:
                q = aligner._queries([([n for n in h[0] if n["t0_ms"] >= t - w], None) for h in heard])
                sw = aligner.scores(tunes, q) if (q and tunes) else {}
                chunk["by_window"][w] = {k: float(v) for k, v in sw.items()}
        chunks.append(chunk)
    if store is not None:
        store.close()
    out = {"recording_id": rid, "hop_ms": hop_ms, "window_ms": window_ms, "chunks": chunks,
           "causal": causal,
           "seconds": round(time.time() - started, 1)}
    with open(path, "wb") as f:
        pickle.dump(out, f)
    if not quiet:
        print(f"    night {rid}: {len(chunks)} chunks in {out['seconds']:.0f}s", flush=True)
    return out


class Decoder:
    """Causal belief over tunes and "not a tune", a chunk at a time."""

    # defaults: tuned for the 6 s window on the seven tuning nights, causal
    # features (lam 40, tau 0.45, p_switch 0.05, p_none 0.3)
    def __init__(self, lam=40.0, tau=0.45, p_switch=0.05, p_none=0.3, nu=0.0, kappa=0.0,
                 n_settings=None, gamma=0.0):
        # `nu`: a tune outside the session's repertoire (a chunk's "outside",
        # from the full-corpus fallback) scores `lam * nu` less.
        # `kappa`: a tune with many settings scores `lam * kappa * ln(n)` less,
        # n its number of settings (`n_settings`, {tune: n}); a hub's best
        # setting has had more chances at a lucky match.
        self.lam, self.tau, self.p_switch, self.p_none, self.nu = lam, tau, p_switch, p_none, nu
        self.kappa, self.n_settings = kappa, n_settings or {}
        # `gamma`: "not a tune" scores `lam * (tau - gamma * logodds / 10)`, the
        # chunk's "tune_logodds" from `analysis.tuneness` (0 when absent)
        self.gamma = gamma

    def params(self):
        return {"lam": self.lam, "tau": self.tau, "p_switch": self.p_switch, "p_none": self.p_none,
                "nu": self.nu, "kappa": self.kappa, "gamma": self.gamma}

    def reset(self):
        self._ids = [NONE]              # state order; row 0 is "not a tune"
        self._where = {NONE: 0}
        self._log = np.array([0.0])     # log belief per state, normalised each step

    def step(self, c):
        """One chunk in; the state to display out (a tune id or NONE)."""
        if not hasattr(self, "_log"):
            self.reset()
        ids, where = self._ids, self._where
        ls, lj = math.log(1 - self.p_switch), math.log(self.p_switch)
        scores, floor = c["scores"], c["floor"]
        fresh = [t for t in scores if t not in where]
        if fresh:
            for t in fresh:
                where[t] = len(ids)
                ids.append(t)
            self._log = np.concatenate([self._log, np.full(len(fresh), -1e9)])
        log = self._log
        n = len(ids)
        emit = np.full(n, self.lam * floor)
        emit[0] = self.lam * (self.tau - self.gamma * c.get("tune_logodds", 0.0) / 10.0)
        in_pool = np.zeros(n, dtype=bool)
        if scores:
            rows = np.fromiter((where[t] for t in scores), dtype=np.int64, count=len(scores))
            emit[rows] = self.lam * np.fromiter(scores.values(), dtype=float, count=len(scores))
            in_pool[rows] = True
            if self.nu and c.get("outside"):
                emit[[where[t] for t in c["outside"]]] -= self.lam * self.nu
            if self.kappa:
                emit[rows] -= self.lam * self.kappa * np.log(np.fromiter(
                    (max(1, self.n_settings.get(t, 1)) for t in scores), dtype=float, count=len(scores)))
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
        self._log = np.maximum(log, -1e9)
        return ids[int(np.argmax(self._log))]

    def confirm(self, tune_id):
        """A person said "this is it": all belief on that tune. The decoder
        keeps listening, so a later change of tune is still followed."""
        if not hasattr(self, "_log"):
            self.reset()
        if tune_id not in self._where:
            self._where[tune_id] = len(self._ids)
            self._ids.append(tune_id)
            self._log = np.concatenate([self._log, [-1e9]])
        self._log = np.full(len(self._ids), -30.0)
        self._log[self._where[tune_id]] = 0.0

    def rule_out(self, tune_ids):
        """A person said "none of these": no belief left on them."""
        if not hasattr(self, "_log"):
            self.reset()
        for t in tune_ids:
            if t in self._where:
                self._log[self._where[t]] = -1e9
        self._log = np.maximum(self._log - np.logaddexp.reduce(self._log), -1e9)

    def belief(self, k=5):
        """The `k` most believed states now: [(state, probability)]."""
        order = np.argsort(-self._log)[:k]
        return [(self._ids[i], float(np.exp(self._log[i]))) for i in order]

    def run(self, chunks):
        """-> the displayed state after each chunk (a tune id or NONE)."""
        self.reset()
        return [self.step(c) for c in chunks]


def mix_windows(chunks, weights, window_ms=8000):   # the window the features were made with
    """Chunks whose scores are a weighted mix of the full window's and the
    extra windows' (`night_features(extra_windows=...)`), e.g. {8000: 0.5,
    4000: 0.5}; weights are normalised. The floor is mixed the same way."""
    total = sum(weights.values())
    out = []
    for c in chunks:
        by = {window_ms: c["scores"], **c.get("by_window", {})}
        tunes = c["scores"].keys()
        mixed = {t: sum(w * by[k].get(t, 0.0) for k, w in weights.items()) / total for t in tunes}
        floor = min(mixed.values()) if mixed else 0.0
        out.append({**c, "scores": mixed, "floor": floor})
    return out


# eighths in twos or in threes, by tune type; None where the pulse says
# nothing useful (waltzes, mazurkas, set dances)
METER = {"reel": 2, "hornpipe": 2, "polka": 2, "barndance": 2, "strathspey": 2, "march": 2,
         "jig": 3, "slide": 3, "slip jig": 3, "hop jig": 3}


class HintDecoder(Decoder):
    """`Decoder` with the player's hints, each making it easier to leave the
    tune on display at a likely moment, none calling a change on its own:

    - `m_dur`: the leave probability is multiplied by this once the tune has
      been displayed for `dur_frac` of its usual length at this session
      (`usual_s`, from labelled nights other than the one scored);
    - `m_end`: multiplied by this while its latest notes sit past `end_frac`
      of the tune as written (the end of a pass);
    - `m_pass`: multiplied by this once `n_pass` passes have been counted
      (the position wrapping from past 0.7 to under 0.3) and it is at the end
      of one;
    - `mu`: a tune whose meter disagrees with the meter heard, when the pulse
      is sure of it (`grouping_margin` >= `margin`), scores `lam * mu` less.

    With the factors at 1 and `mu` 0 it is `Decoder`, value for value.

    Measured 2026-09-30, each hint chosen leave-one-night-out on the seven
    tuning nights and paired against the same base with no hint: usual
    length +0/-0, end of a pass +0/-0, passes +0/-1, meter +0/-0; all four
    +0/-3; night 140's held-out 61 +0/-0 for every one. The audio already
    decides (see the spec). Off by default."""

    def __init__(self, usual_s=None, tune_types=None, m_dur=1.0, dur_frac=0.8, m_end=1.0,
                 end_frac=0.85, m_pass=1.0, n_pass=3, mu=0.0, margin=0.2, **kw):
        super().__init__(**kw)
        self.usual_s, self.tune_types = usual_s or {}, tune_types or {}
        self.m_dur, self.dur_frac, self.m_end, self.end_frac = m_dur, dur_frac, m_end, end_frac
        self.m_pass, self.n_pass, self.mu, self.margin = m_pass, n_pass, mu, margin

    def params(self):
        return {**super().params(), "m_dur": self.m_dur, "dur_frac": self.dur_frac,
                "m_end": self.m_end, "end_frac": self.end_frac, "m_pass": self.m_pass,
                "n_pass": self.n_pass, "mu": self.mu, "margin": self.margin}

    def run(self, chunks):
        ids = [NONE]
        where = {NONE: 0}
        log = np.array([0.0])
        shown = []
        showing, since_ms, passes, last_pos = None, None, 0, None
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
            heard = c.get("grouping")
            if self.mu and heard and (c.get("grouping_margin") or 0) >= self.margin:
                for t, row in where.items():
                    m = METER.get((self.tune_types.get(t) or "").strip().lower())
                    if m and m != heard:
                        emit[row] -= self.lam * self.mu
            # the displayed tune's leave probability, from the hints
            p = np.full(n, self.p_switch)
            if showing is not None and showing != NONE:
                factor = 1.0
                usual = self.usual_s.get(showing)
                if usual and (c["t_ms"] - since_ms) / 1000.0 >= self.dur_frac * usual:
                    factor *= self.m_dur
                pos = (c.get("where") or {}).get(showing)
                if pos is not None:
                    if last_pos is not None and last_pos > 0.7 and pos < 0.3:
                        passes += 1
                    last_pos = pos
                    if pos >= self.end_frac:
                        factor *= self.m_end
                        if passes >= self.n_pass - 1:
                            factor *= self.m_pass
                p[where[showing]] = min(0.9, self.p_switch * factor)
            jump = np.logaddexp.reduce(np.log(p) + log)
            jump_tune = jump + math.log(1 - self.p_none) - math.log(max(1, len(scores)))
            jump_none = jump + math.log(self.p_none)
            prior = np.log1p(-p) + log
            prior[in_pool] = np.logaddexp(prior[in_pool], jump_tune)
            prior[0] = np.logaddexp(prior[0], jump_none)
            new = prior + emit
            log = new - np.logaddexp.reduce(new)
            log = np.maximum(log, -1e9)
            now = ids[int(np.argmax(log))]
            if now != showing:
                showing, since_ms, passes, last_pos = now, c["t_ms"], 0, None
            shown.append(now)
        return shown


def usual_durations(recording_ids):
    """{tune: median labelled duration in seconds} over these nights, plus
    {type: median} as the fallback for a tune not labelled on any of them."""
    by_tune, by_type = defaultdict(list), defaultdict(list)
    for rid in recording_ids:
        for s in load_ground_truth(rid).eval_segments():
            if s.evaluated and s.tune_id is not None and not s.capped:
                by_tune[s.tune_id].append(s.duration_ms / 1000.0)
                by_type[(s.tune_type or "").strip().lower()].append(s.duration_ms / 1000.0)
    return ({t: float(np.median(v)) for t, v in by_tune.items()},
            {t: float(np.median(v)) for t, v in by_type.items()})


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
               window_ms=6000, pool_ms=24000, pool_top=100, keep=6, reading="notes", causal=True,
               extra_windows=(), quiet=True):
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
                                   keep=keep, causal=causal, extra_windows=extra_windows,
                                   quiet=quiet)
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
