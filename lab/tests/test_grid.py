"""Splitting a fused repeat, which is the one thing the grid is used for.

Two eighths of the same pitch in a row look exactly like one quarter note to
a run-length step over a pitch track, because the pitch never changes. The
corpus notates them as two notes, so the transcription was dropping a real
symbol. The grid says where the second one would have started; an onset says
whether anything was actually struck there.
"""

from lab.frontends.grid import _grid_lines, split_fused_repeats

PERIOD = 160.0
PHASE = 0.0


def note(t0, t1, midi=64):
    return {"t0_ms": t0, "t1_ms": t1, "midi": midi, "conf": 0.5}


def test_grid_lines_are_strictly_inside():
    assert _grid_lines(0, 320, PERIOD, PHASE) == [160.0]
    assert _grid_lines(160, 480, PERIOD, PHASE) == [320.0]
    assert _grid_lines(0, 160, PERIOD, PHASE) == []


def test_splits_where_something_was_struck():
    out = split_fused_repeats([note(0, 320)], PERIOD, PHASE, attacks_ms=[0, 162])
    assert [(n["t0_ms"], n["t1_ms"]) for n in out] == [(0, 160), (160, 320)]
    assert all(n["midi"] == 64 for n in out)


def test_leaves_a_held_note_alone():
    """The whole point of the onset gate: nothing struck, nothing split."""
    out = split_fused_repeats([note(0, 320)], PERIOD, PHASE, attacks_ms=[0])
    assert [(n["t0_ms"], n["t1_ms"]) for n in out] == [(0, 320)]


def test_an_attack_too_far_from_the_line_does_not_count():
    # 0.12 of 160ms is 19ms; 40ms away is a different note, not this one
    out = split_fused_repeats([note(0, 320)], PERIOD, PHASE, attacks_ms=[0, 200],
                              tolerance=0.12)
    assert len(out) == 1
    out = split_fused_repeats([note(0, 320)], PERIOD, PHASE, attacks_ms=[0, 200],
                              tolerance=0.35)
    assert len(out) == 2


def test_short_notes_are_never_touched():
    notes = [note(0, 150), note(160, 300)]
    out = split_fused_repeats(notes, PERIOD, PHASE, attacks_ms=[0, 80, 160, 240])
    assert out == notes


def test_the_crude_rule_splits_everything_long():
    out = split_fused_repeats([note(0, 480)], PERIOD, PHASE, attacks_ms=[],
                              require_attack=False)
    assert [(n["t0_ms"], n["t1_ms"]) for n in out] == [(0, 160), (160, 320), (320, 480)]


def test_splitting_conserves_the_span_and_the_pitch():
    notes = [note(50, 690, midi=67)]
    out = split_fused_repeats(notes, PERIOD, PHASE, attacks_ms=[50, 161, 320, 480])
    assert out[0]["t0_ms"] == 50 and out[-1]["t1_ms"] == 690
    assert {n["midi"] for n in out} == {67}
    assert all(a["t1_ms"] == b["t0_ms"] for a, b in zip(out, out[1:]))


def test_no_pulse_means_no_change():
    notes = [note(0, 320)]
    assert split_fused_repeats(notes, 0.0, PHASE, attacks_ms=[0, 160]) == notes
    assert split_fused_repeats([], PERIOD, PHASE, attacks_ms=[0]) == []


def test_it_restores_the_zero_the_notation_has():
    """The reason any of this exists, stated as the sequence it produces."""
    from lab.frontends.segmentation import intervals_from_notes

    fused = [note(0, 320, 64), note(320, 480, 67)]
    assert intervals_from_notes(fused, fold=True) == [3]
    split = split_fused_repeats(fused, PERIOD, PHASE, attacks_ms=[0, 160, 320])
    assert intervals_from_notes(split, fold=True) == [0, 3]


def test_a_cut_on_the_note_start_does_not_make_a_zero_length_note():
    """Found by the bench-board agreement test, and it mattered.

    A note beginning a fraction of a millisecond before a grid line was split
    into a sliver and the rest. Rounded to whole milliseconds the sliver has
    zero length and the same pitch as what follows, so the interval step read
    it as a repeated note: this function inventing the very thing it exists to
    recover.
    """
    out = split_fused_repeats([note(114, 774)], 220.0, 114.04, attacks_ms=[],
                              require_attack=False)
    assert all(n["t1_ms"] > n["t0_ms"] for n in out)
    assert [(n["t0_ms"], n["t1_ms"]) for n in out] == [(114, 334), (334, 554), (554, 774)]


def test_the_short_note_floor_follows_the_tempo():
    """A third of an eighth goes at a polka's tempo; the same 80ms at a
    reel's tempo is more than half an eighth and stays."""
    from lab.frontends.grid import drop_short_notes

    note = {"t0_ms": 0, "t1_ms": 80, "midi": 62}
    assert drop_short_notes([note], 205.0, 0.4) == []          # polka eighth
    assert drop_short_notes([note], 140.0, 0.4) == [note]      # reel eighth
    assert drop_short_notes([note], 205.0, 0.0) == [note]      # off
