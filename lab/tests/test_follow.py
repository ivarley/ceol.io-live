"""analysis.follow: a set followed through its tunes on a grid of eighths."""

import numpy as np

from lab.analysis.follow import Chain, boundaries, follow, follow_reference, heard_slots, slot_grid


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


def test_a_tune_the_session_plays_in_its_own_key_is_moved_there():
    from lab.analysis.follow import chains_for, tonic_pc
    from lab.analysis.form import played_form

    form = played_form("|:ABcd efga|bagf edcB:|", key="Amixolydian")
    assert tonic_pc("Amixolydian") == 9 and tonic_pc("Dmixolydian") == 2 and tonic_pc("F#minor") == 6
    (written,) = chains_for(0, [(1, "Amixolydian", form)])
    (moved,) = chains_for(0, [(1, "Amixolydian", form)], session_key="Dmixolydian")
    assert moved.shift == 5 and list(moved.form[:3]) == [(p + 5) % 12 for p in written.form[:3]]


def test_the_vectorised_path_is_the_loops_path():
    """`follow` steps every chain at once; `follow_reference` loops over them.
    Random sets of two to four tunes, several settings and keys each, heard
    with noise and gaps: the same path, positions and settings."""
    rng = np.random.default_rng(11)
    for trial in range(25):
        n_tunes = int(rng.integers(2, 5))
        chains, heard = [], []
        for k in range(n_tunes):
            for s in range(int(rng.integers(1, 4))):
                n = int(rng.integers(24, 64))
                form = rng.integers(-1, 12, n).astype(np.int8)
                chains.append(Chain(tune=k, setting_id=100 * k + s, form=form, last_bar=8))
            played = chains[-1].form
            heard += list(np.tile(played, 2)[: int(rng.integers(30, 90))])
        heard = np.array([-1] * 10 + heard + [-1] * 10, dtype=np.int8)
        noisy = np.where(rng.random(len(heard)) < 0.15, rng.integers(-1, 12, len(heard)), heard).astype(np.int8)
        a = follow(noisy, chains, n_tunes)
        b = follow_reference(noisy, chains, n_tunes)
        assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]) and a[2] == b[2], trial
