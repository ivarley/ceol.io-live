"""Aligning what was heard against a tune's notes, as Tunepal and FolkFriend
do, instead of counting shared phrases.

The n-gram matcher's known weakness is that one inserted or dropped note
breaks every phrase that spans it: a tracker that adds ornament notes (yin)
or loses notes (the neural ones) destroys six 6-grams per error. An
alignment pays for the one note and carries on.

Local alignment (Smith-Waterman), because the heard notes are not the tune
from its first note: the tune is stored once through, repeats not written
out, so the heard notes are cut into chunks about a part-phrase long, each
chunk finds its best place anywhere in the tune (the tune written twice over
so a chunk can run from the end of a part into the start of the next), and
the chunk scores are summed. A chunk that is chat, a wrong part or the next
tune scores near nothing and costs nothing.

Symbols are pitch classes, -1 for unknown: an unknown on either side scores
zero, neither match nor mismatch.
"""

import numpy as np
from numba import njit, prange


@njit(cache=True)
def local_align(q, t, match, mismatch, gap):
    """Best local alignment score of q against t (Smith-Waterman, linear gaps)."""
    m = t.shape[0]
    prev = np.zeros(m + 1)
    cur = np.zeros(m + 1)
    best = 0.0
    for i in range(q.shape[0]):
        qi = q[i]
        cur[0] = 0.0
        for j in range(1, m + 1):
            tj = t[j - 1]
            if qi < 0 or tj < 0:
                s = 0.0
            elif qi == tj:
                s = match
            else:
                s = mismatch
            v = prev[j - 1] + s
            a = prev[j] + gap
            if a > v:
                v = a
            b = cur[j - 1] + gap
            if b > v:
                v = b
            if v < 0.0:
                v = 0.0
            cur[j] = v
            if v > best:
                best = v
        for j in range(m + 1):
            prev[j] = cur[j]
    return best


def chunk_score(query, target, chunk=32, match=2.0, mismatch=-1.0, gap=-1.0, transpose=0):
    """Summed best local score of each `chunk`-long piece of the query against
    the target written twice over, as a share of what the query's known
    symbols could score at most. 0..1."""
    q = np.asarray(query, dtype=np.int8)
    known = int((q >= 0).sum())
    if known == 0 or len(target) == 0:
        return 0.0
    t = np.asarray(target, dtype=np.int8)
    if transpose:
        t = np.where(t >= 0, (t + transpose) % 12, -1).astype(np.int8)
    t2 = np.concatenate([t, t])
    total = 0.0
    for start in range(0, len(q), chunk):
        piece = q[start:start + chunk]
        if (piece >= 0).sum() < chunk // 4:
            continue
        total += local_align(piece, t2, match, mismatch, gap)
    return total / (match * known)


@njit(cache=True, parallel=True)
def _batch_local_align(q_flat, q_off, t_flat, t_off, pairs_q, pairs_t, match, mismatch, gap):
    out = np.zeros(pairs_q.shape[0])
    for i in prange(pairs_q.shape[0]):
        a, b = pairs_q[i], pairs_t[i]
        out[i] = local_align(q_flat[q_off[a]:q_off[a + 1]], t_flat[t_off[b]:t_off[b + 1]],
                             match, mismatch, gap)
    return out


def query_pieces(query, chunk):
    """The chunks `chunk_score` scores, and the most the query could score:
    (list of int8 arrays, known symbols). Pieces with fewer than chunk // 4
    known symbols are dropped, as there."""
    q = np.asarray(query, dtype=np.int8)
    known = int((q >= 0).sum())
    pieces = []
    for start in range(0, len(q), chunk):
        piece = q[start:start + chunk]
        if (piece >= 0).sum() >= chunk // 4:
            pieces.append(piece)
    return pieces, known


def doubled(target, transpose=0):
    """A target as `chunk_score` aligns against it: transposed, written twice."""
    t = np.asarray(target, dtype=np.int8)
    if transpose:
        t = np.where(t >= 0, (t + transpose) % 12, -1).astype(np.int8)
    return np.concatenate([t, t])


def batch_chunk_scores(queries, targets, match=2.0, mismatch=-1.0, gap=-1.0):
    """`chunk_score` for every (query, target) pair at once, across all cores.

    `queries`: [(pieces, known)] from `query_pieces`; `targets`: doubled
    arrays from `doubled`. Returns an array [len(queries), len(targets)]
    equal, value for value, to calling `chunk_score` on each pair: the same
    local alignments, summed in the same order."""
    out = np.zeros((len(queries), len(targets)))
    if not queries or not targets:
        return out
    q_list, q_owner = [], []
    for qi, (pieces, _) in enumerate(queries):
        for p in pieces:
            q_list.append(p)
            q_owner.append(qi)
    if not q_list:
        return out
    q_off = np.zeros(len(q_list) + 1, dtype=np.int64)
    q_off[1:] = np.cumsum([len(p) for p in q_list])
    t_off = np.zeros(len(targets) + 1, dtype=np.int64)
    t_off[1:] = np.cumsum([len(t) for t in targets])
    q_flat = np.concatenate(q_list).astype(np.int8)
    t_flat = np.concatenate(targets).astype(np.int8)
    nq, nt = len(q_list), len(targets)
    pairs_q = np.repeat(np.arange(nq, dtype=np.int64), nt)
    pairs_t = np.tile(np.arange(nt, dtype=np.int64), nq)
    scores = _batch_local_align(q_flat, q_off, t_flat, t_off, pairs_q, pairs_t,
                                match, mismatch, gap).reshape(nq, nt)
    # sum each query's pieces in order, as chunk_score does
    for row, qi in enumerate(q_owner):
        out[qi] += scores[row]
    for qi, (_, known) in enumerate(queries):
        out[qi] = out[qi] / (match * known) if known else 0.0
    empty = [ti for ti, t in enumerate(targets) if len(t) == 0]
    out[:, empty] = 0.0
    return out


@njit(cache=True)
def local_align_end(q, t, match, mismatch, gap):
    """`local_align`, also returning where in t the best alignment ends
    (1-based column; 0 when nothing aligns)."""
    m = t.shape[0]
    prev = np.zeros(m + 1)
    cur = np.zeros(m + 1)
    best, end = 0.0, 0
    for i in range(q.shape[0]):
        qi = q[i]
        cur[0] = 0.0
        for j in range(1, m + 1):
            tj = t[j - 1]
            if qi < 0 or tj < 0:
                s = 0.0
            elif qi == tj:
                s = match
            else:
                s = mismatch
            v = prev[j - 1] + s
            a = prev[j] + gap
            if a > v:
                v = a
            b = cur[j - 1] + gap
            if b > v:
                v = b
            if v < 0.0:
                v = 0.0
            cur[j] = v
            if v > best:
                best, end = v, j
        for j in range(m + 1):
            prev[j] = cur[j]
    return best, end


def where_in_tune(query, target, chunk=24, match=2.0, mismatch=-1.0, gap=-1.0):
    """Where the most recent `chunk` symbols of the query sit in the tune:
    (score of that piece, position of its end as a share of the tune once
    through, 0..1). The tune is written twice over, as `chunk_score` aligns."""
    q = np.asarray(query[-chunk:], dtype=np.int8)
    t = np.asarray(target, dtype=np.int8)
    if len(t) == 0 or (q >= 0).sum() < chunk // 4:
        return 0.0, None
    score, end = local_align_end(q, np.concatenate([t, t]), match, mismatch, gap)
    if end == 0:
        return 0.0, None
    return score, ((end - 1) % len(t)) / len(t)
