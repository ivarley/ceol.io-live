"""Quantising to eighths and writing it out.

The point of this step is that it needs the grid's PERIOD and not its phase.
A note's length in eighths does not depend on where the bar starts, and the
lab cannot find where the bar starts, so these tests check that property
directly as well as the spelling.
"""

import pytest

from lab.analysis.notation import (duration_histogram, notate, quantise, spell,
                                   staff_step, to_abc)


def notes(*spec):
    """(midi, start_ms, end_ms) triples."""
    return [{"midi": m, "t0_ms": a, "t1_ms": b, "conf": 0.9} for m, a, b in spec]


def eighths_of(q):
    return [i["ticks"] / 2 for i in q]


def test_lengths_come_out_in_eighths():
    q = quantise(notes((60, 0, 140), (62, 150, 450), (64, 450, 1050)), 150.0)
    played = [i for i in q if not i["rest"]]
    assert eighths_of(played) == [1, 2, 4]
    assert [i["pc"] for i in played] == [0, 2, 4]


def test_notes_faster_than_the_grid_are_kept_not_dropped():
    """The bug that made the stave unreadable.

    Rounding every note to the nearest eighth put a fifth of them in a slot
    that was already taken, and dropping those turned C B A C B A G B into
    C A C B G B, which is not the tune. Positions go on sixteenths so they
    survive; durations are still written in eighths.
    """
    run = [(p, int(i * 115), int(i * 115 + 110))
           for i, p in enumerate([60, 59, 57, 60, 59, 57, 55, 59])]
    q = [i for i in quantise(notes(*run), 139.0) if not i["rest"]]
    assert [i["pc"] % 12 for i in q] == [0, 11, 9, 0, 11, 9, 7, 11]


def test_the_phase_barely_moves_the_lengths():
    """The property the whole approach rests on, stated as it actually holds.

    Moving the phase cannot stretch or shrink the music, so the total length
    is identical whatever the phase. What it can do, at exactly half a grid
    step, is round two neighbouring notes into the same eighth, and then the
    shorter one loses its slot. That is inherent to quantising and is a
    different thing entirely from the drift this replaced, which accumulated
    without limit.
    """
    n = notes((60, 0, 140), (62, 150, 450), (64, 600, 900), (67, 900, 1200))
    base = quantise(n, 150.0, phase_ms=0.0)
    total = sum(i["ticks"] for i in base)
    played = sum(1 for i in base if not i["rest"])
    for phase in (10.0, 40.0, 75.0, 120.0, -30.0):
        got = quantise(n, 150.0, phase_ms=phase)
        assert sum(i["ticks"] for i in got) == total
        assert abs(sum(1 for i in got if not i["rest"]) - played) <= 1


def test_a_gap_becomes_a_rest():
    q = quantise(notes((60, 0, 150), (62, 600, 750)), 150.0)
    assert [(i["rest"], i["ticks"] / 2) for i in q] == [(False, 1), (True, 3), (False, 1)]


def test_overlapping_notes_do_not_overlap_afterwards():
    q = quantise(notes((60, 0, 400), (62, 150, 550)), 150.0)
    played = [i for i in q if not i["rest"]]
    assert played[0]["start"] + played[0]["ticks"] <= played[1]["start"]


def test_a_note_never_moves_from_its_own_slot():
    """The bug this replaced: overlaps pushed notes forward and the pushes
    piled up, until a hundred seconds of music ran eight seconds long and the
    note highlighted during playback was fourteen notes from the one heard."""
    n = notes(*[(60 + (i % 5), i * 140, i * 140 + 300) for i in range(60)])
    q = [i for i in quantise(n, 150.0) if not i["rest"]]
    last = q[-1]
    assert last["start"] <= round(n[-1]["t0_ms"] / 75.0) + 1


def test_two_notes_in_one_eighth_keep_the_longer():
    q = [i for i in quantise(notes((60, 0, 30), (64, 20, 300)), 150.0) if not i["rest"]]
    assert [i["pc"] for i in q] == [4]


def test_a_note_never_vanishes():
    """Even something far shorter than an eighth keeps a slot."""
    q = quantise(notes((60, 0, 20)), 150.0)
    assert len(q) == 1 and q[0]["ticks"] >= 1


@pytest.mark.parametrize("sharps,pc,letter,alteration,symbol", [
    (2, 6, "F", 1, ""),      # in D, F sharp is already in the key
    (0, 6, "F", 1, "^"),     # in C it needs a sharp
    (-1, 10, "B", -1, ""),   # in F, B flat is already in the key
    (0, 10, "B", -1, "_"),   # in C it needs a flat, and is not A sharp
    (1, 5, "F", 0, "="),     # in G, an F natural needs a natural sign
    (2, 0, "C", 0, "="),     # D mixolydian against D major is this one note
])
def test_spelling_follows_the_key_signature(sharps, pc, letter, alteration, symbol):
    from lab.analysis.notation import abc_accidental

    assert spell(pc, sharps) == (letter, alteration)
    assert abc_accidental(letter, alteration, sharps) == symbol


def test_abc_has_no_bar_lines():
    """Deliberate: the lab does not know where they go."""
    q = quantise(notes((62, 0, 150), (66, 150, 450)), 150.0)
    abc = to_abc(q, sharps=2)
    assert "|" not in abc
    assert "K:D" in abc and "L:1/8" in abc and "M:none" in abc
    assert "D F2" in abc


def test_an_eighth_carries_no_length_marker():
    q = quantise(notes((62, 0, 150), (62, 150, 300)), 150.0)
    assert to_abc(q, sharps=2).endswith("D D")


def test_staff_step_is_diatonic():
    assert staff_step(2, 2) == 1        # D
    assert staff_step(6, 2) == 3        # F sharp is still an F
    assert staff_step(11, 2) == 6       # B


def test_notate_guesses_the_key_when_not_told():
    scale = [2, 4, 6, 7, 9, 11, 1] * 6
    n = notes(*[(60 + pc, i * 150, i * 150 + 140) for i, pc in enumerate(scale)])
    out = notate(n, 150.0)
    assert out["sharps"] == 2 and out["key"] == "D"
    assert out["n_notes"] == len(scale)


def test_duration_histogram_sums_to_one():
    q = quantise(notes((60, 0, 150), (62, 150, 450), (64, 450, 600)), 150.0)
    h = duration_histogram(q)
    assert sum(h.values()) == pytest.approx(1.0)
    assert h[1.0] == pytest.approx(2 / 3)


def test_particalize_writes_held_notes_as_repeats():
    """The point of it: a transcriber hears pitch, not articulation.

    Two tongued Gs and one held G of the same length are the same pitch
    track, so both become two eighths and the matcher stops pretending it can
    tell them apart.
    """
    from lab.analysis.notation import particalize

    held = particalize(notes((67, 0, 300)), 150.0)
    tongued = particalize(notes((67, 0, 150), (67, 150, 300)), 150.0)
    assert held == [7, 7] == tongued


def test_particalize_gives_one_slot_per_eighth_of_audio():
    from lab.analysis.notation import particalize

    n = notes(*[(60 + (i % 7), i * 150, i * 150 + 140) for i in range(40)])
    assert len(particalize(n, 150.0)) == 40


def test_particalize_drops_notes_it_cannot_place_rather_than_drifting():
    """Ornaments arrive faster than the grid; letting them push would drift."""
    from lab.analysis.notation import particalize

    crowded = notes(*[(60 + i % 3, i * 40, i * 40 + 35) for i in range(30)])
    slots = particalize(crowded, 150.0, max_lag=1)
    assert len(slots) <= 12          # 30 notes in 1.2s cannot be 30 eighths


def test_the_corpus_particalizes_the_same_way():
    """The two sides have to agree or comparing them means nothing."""
    from lab.analysis.notation import particalize
    from lab.corpus.abc_pitch import parse_abc, particalized_pitches

    written = particalized_pitches(parse_abc("G2 A", key="Gmajor", meter="4/4"))
    assert [p % 12 for p in written] == [7, 7, 9]
    heard = particalize(notes((67, 0, 300), (69, 300, 450)), 150.0)
    assert heard == [7, 7, 9]
