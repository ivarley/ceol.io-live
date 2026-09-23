"""Key estimation, on note sequences whose key is a fact of the fixture.

The real measurement is against the corpus's own mode column over 501
segments, which needs the audio. These are the cheap checks underneath it,
plus the one property that matters most: the corpus and the estimator must
speak the same language, so a notated Bminor and a heard two sharps have to
come back as the same number.
"""

import pytest

from lab.analysis.key import (MAJOR, diatonic_fraction, estimate_key,
                              pitch_class_mass, root_for_sharps)
from lab.corpus.abc_pitch import key_sharps


def notes_for(pitch_classes, ms=200):
    return [{"midi": 60 + pc, "t0_ms": i * ms, "t1_ms": i * ms + ms - 10, "conf": 0.9}
            for i, pc in enumerate(pitch_classes)]


def scale(sharps, repeats=8):
    root = root_for_sharps(sharps)
    return [(root + d) % 12 for d in MAJOR] * repeats


@pytest.mark.parametrize("sharps", [-2, -1, 0, 1, 2, 3, 4])
def test_a_pure_scale_gives_its_own_key(sharps):
    key = estimate_key(notes_for(scale(sharps)))
    assert key["sharps"] == sharps
    assert key["diatonic_fraction"] == pytest.approx(1.0)


def test_relative_modes_are_the_same_answer():
    """Two sharps is two sharps, whichever note is called home."""
    # the four names this session would give the same seven notes
    assert key_sharps("Dmajor") == 2
    assert key_sharps("Bminor") == 2
    assert key_sharps("Amixolydian") == 2
    assert key_sharps("Edorian") == 2
    # and a few that are genuinely different sets
    assert key_sharps("Adorian") == 1        # G major's notes
    assert key_sharps("Emixolydian") == 3    # A major's notes
    assert key_sharps("Emajor") == 4
    assert key_sharps("Gmajor") == 1


def test_the_corpus_and_the_estimator_agree_on_the_number():
    """The property the whole comparison rests on."""
    for mode in ("Dmajor", "Bminor", "Amixolydian", "Edorian", "Emajor"):
        sharps = key_sharps(mode)
        assert estimate_key(notes_for(scale(sharps)))["sharps"] == sharps


def test_an_unreadable_key_is_no_information_not_zero():
    assert key_sharps("none") is None
    assert key_sharps("") is None
    assert key_sharps("HP") is None


def test_out_of_key_notes_lower_the_fraction_without_moving_the_key():
    clean = scale(2)
    dirty = clean + [1, 3, 6]      # three notes outside two sharps
    key = estimate_key(notes_for(dirty))
    assert key["sharps"] == 2
    assert 0.8 < key["diatonic_fraction"] < 1.0
    assert diatonic_fraction(notes_for(clean)) > key["diatonic_fraction"]


def test_time_is_what_counts_not_note_count():
    """One long note outweighs several ornaments, which is the musical truth."""
    long_note = [{"midi": 62, "t0_ms": 0, "t1_ms": 4000, "conf": 0.9}]
    ornaments = [{"midi": 61, "t0_ms": 4000 + i * 20, "t1_ms": 4000 + i * 20 + 15, "conf": 0.5}
                 for i in range(20)]
    mass = pitch_class_mass(long_note + ornaments)
    assert mass[2] > 10 * mass[1]


def test_too_few_notes_says_nothing():
    assert estimate_key(notes_for([0, 2, 4])) is None
    assert diatonic_fraction(notes_for([0, 2, 4])) is None
    assert estimate_key([]) is None


def test_chromatic_noise_has_a_low_fraction():
    """No key fits a chromatic run, and the fraction should say so."""
    key = estimate_key(notes_for(list(range(12)) * 4))
    assert key["diatonic_fraction"] == pytest.approx(7 / 12, abs=0.02)
    assert key["margin"] == pytest.approx(0.0, abs=1e-9)
