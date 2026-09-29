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
from numba import njit


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
