"""analysis.follow: a set followed through its tunes on a grid of eighths."""

import numpy as np

from lab.analysis.follow import Chain, boundaries, follow, heard_slots, slot_grid


def _tune(seed, n=64):
    return np.random.default_rng(seed).integers(0, 12, n).astype(np.int8)


def test_the_change_lands_where_one_tune_gives_way_to_the_next():
    a, b = _tune(1), _tune(2)
    noise = np.random.default_rng(3).integers(0, 12, 40).astype(np.int8)
    heard = np.concatenate([noise, a, a, b, b[:30], noise])
    # a transcription is not perfect: one slot in ten heard wrong, one lost
    rng = np.random.default_rng(4)
    heard = heard.copy()
    heard[rng.random(len(heard)) < 0.1] = rng.integers(0, 12)
    heard[rng.random(len(heard)) < 0.1] = -1
    chains = [Chain(0, 1, a, last_bar=8), Chain(1, 2, b, last_bar=8)]
    state, pos, chosen = follow(heard, chains, 2)
    times = np.arange(len(heard), dtype=float)
    starts, end = boundaries(state, times, 2)
    assert abs(starts[0] - 40) <= 1
    assert abs(starts[1] - (40 + 128)) <= 1
    assert abs(end - (40 + 128 + 64 + 30)) <= 8
    assert chosen == {0: 1, 1: 2}


def test_heard_slots_take_a_note_where_it_starts_and_hold_it():
    times = slot_grid(0, 1000, period_ms=100.0)
    notes = [{"t0_ms": 0, "t1_ms": 300, "midi": 62}, {"t0_ms": 500, "t1_ms": 600, "midi": 64}]
    assert list(heard_slots(notes, times)[:7]) == [2, 2, 2, -1, -1, 4, -1]

