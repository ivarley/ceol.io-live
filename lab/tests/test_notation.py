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


def test_lengths_come_out_in_whole_eighths():
    q = quantise(notes((60, 0, 140), (62, 150, 450), (64, 450, 1050)), 150.0)
    played = [i for i in q if not i["rest"]]
    assert [i["eighths"] for i in played] == [1, 2, 4]
    assert [i["pc"] for i in played] == [0, 2, 4]


def test_the_phase_cannot_change_any_length():
    """The property the whole approach rests on."""
    n = notes((60, 0, 140), (62, 150, 450), (64, 600, 900), (67, 900, 1200))
    base = [i["eighths"] for i in quantise(n, 150.0, phase_ms=0.0)]
    for phase in (10.0, 40.0, 75.0, 120.0, -30.0):
        assert [i["eighths"] for i in quantise(n, 150.0, phase_ms=phase)] == base


def test_a_gap_becomes_a_rest():
    q = quantise(notes((60, 0, 150), (62, 600, 750)), 150.0)
    assert [(i["rest"], i["eighths"]) for i in q] == [(False, 1), (True, 3), (False, 1)]


def test_overlapping_notes_do_not_overlap_afterwards():
    q = quantise(notes((60, 0, 400), (62, 150, 550)), 150.0)
    played = [i for i in q if not i["rest"]]
    assert played[0]["start"] + played[0]["eighths"] <= played[1]["start"]


def test_a_note_never_vanishes():
    """Even something far shorter than an eighth keeps a slot."""
    q = quantise(notes((60, 0, 20)), 150.0)
    assert [i["eighths"] for i in q] == [1]


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
    assert h[1] == pytest.approx(2 / 3)
