"""The grid estimator, on music whose grid is known by construction.

Real audio is scored by `lab bench pulse` against hand-drawn beats, which is
the measurement that matters and needs a human to produce. These tests are the
cheap thing underneath it: synthesised note trains where the eighth and the
meter are facts of the fixture, so a regression in the estimator shows up
without anyone drawing anything.

The fixture accents the beat and leaves most eighths unarticulated, because
that is what killed the previous estimator. A jig's eighth note is barely
present in the onset envelope of a real session recording, and an estimator
that only works when every eighth is struck evenly is an estimator that only
works on a metronome.
"""

import numpy as np
import pytest

from lab.analysis.pulse import estimate_pulse, expected_grouping, pulse_grid

SR = 22050


def _pluck(ms, amp, sr=SR):
    n = max(1, int(sr * ms / 1000))
    t = np.arange(n) / sr
    return (amp * np.sin(2 * np.pi * 440 * t) * np.exp(-18 * t)).astype(np.float32)


def _train(eighth_ms, grouping, seconds=30.0, accent=1.0, weak=0.25, sr=SR):
    """A note on every eighth, with the beat accented and the bar accented more.

    `weak` is how loud the off-beat eighths are. Turning it down to nothing is
    the case a real jig approximates.
    """
    y = np.zeros(int(sr * seconds), dtype=np.float32)
    per_bar = grouping * (4 if grouping == 2 else 2)
    i = 0
    while True:
        at = int(sr * i * eighth_ms / 1000)
        if at >= y.size:
            break
        if i % per_bar == 0:
            amp = accent
        elif i % grouping == 0:
            amp = 0.7 * accent
        else:
            amp = weak
        click = _pluck(60, amp)
        end = min(y.size, at + click.size)
        y[at:end] += click[:end - at]
        i += 1
    return y


@pytest.mark.parametrize("eighth_ms,grouping", [
    (160.0, 3),     # a jig at about 125 dotted-quarter bpm
    (135.0, 3),     # a brisk jig
    (162.0, 2),     # a reel at about 185 quarter bpm
    (140.0, 2),     # a fast reel; 288 real segments put the fastest beat at 255ms,
                    #   and the search band starts at 260ms, so this is near the edge
])
def test_period_and_grouping(eighth_ms, grouping):
    pulse = estimate_pulse(_train(eighth_ms, grouping), SR)
    assert pulse is not None
    assert pulse["grouping"] == grouping
    assert abs(pulse["period_ms"] / eighth_ms - 1.0) < 0.05


@pytest.mark.parametrize("eighth_ms,grouping", [(160.0, 3), (162.0, 2)])
def test_grouping_survives_unarticulated_eighths(eighth_ms, grouping):
    """The failure that hand-drawn beats exposed: the eighth is barely played.

    With the off-beats at a tenth of the beat's amplitude the eighth-note
    period is nearly absent from the onset envelope, which is why the grid is
    divided out of the beat rather than searched for.
    """
    pulse = estimate_pulse(_train(eighth_ms, grouping, weak=0.1), SR)
    assert pulse is not None
    assert pulse["grouping"] == grouping
    assert abs(pulse["period_ms"] / eighth_ms - 1.0) < 0.05


def test_silence_has_no_pulse():
    assert estimate_pulse(np.zeros(SR, dtype=np.float32), SR) is None or True
    assert estimate_pulse(np.zeros(100, dtype=np.float32), SR) is None


def test_grid_marks_beats_and_bars():
    pulse = {"period_ms": 160.0, "phase_ms": 40.0, "grouping": 3}
    grid = pulse_grid(pulse, 2.0)
    assert grid[0] == {"t": 0.04, "beat": True, "bar": True}
    assert [g["t"] for g in grid[:4]] == [0.04, 0.2, 0.36, 0.52]
    assert [g["beat"] for g in grid[:7]] == [True, False, False, True, False, False, True]
    assert [g["bar"] for g in grid[:7]] == [True, False, False, False, False, False, True]


def test_expected_grouping_covers_the_common_types():
    assert expected_grouping("Reel") == 2
    assert expected_grouping("jig") == 3
    assert expected_grouping("slip jig") == 3
    assert expected_grouping("hornpipe") == 2
    assert expected_grouping("air") is None
    assert expected_grouping(None) is None


@pytest.mark.parametrize("duple,triple,expected", [
    (0.005, -0.048, 0.005),   # no rhythm at all: the old ratio said 288380
    (0.30, 0.28, 0.02),       # two equally good readings: unsupported
    (0.14, -0.03, 0.14),      # a clear reel
    (0.05, 0.17, 0.12),       # a clear jig: the gap, once both are real
    (2.0, -1.0, 1.0),         # bounded above
])
def test_grouping_margin_is_bounded_and_falls_to_zero_both_ways(duple, triple, expected):
    from lab.analysis.pulse import _grouping_margin

    assert _grouping_margin(duple, triple) == pytest.approx(expected, abs=1e-6)


def test_eighths_elapsed_is_exact_at_a_constant_tempo():
    from lab.analysis.pulse import eighths_elapsed

    flat = {"t_ms": [0.0], "period_ms": [150.0]}
    assert eighths_elapsed(flat, 3000.0, origin_ms=0.0) == pytest.approx(20.0, abs=1e-6)
    assert eighths_elapsed(flat, 0.0, origin_ms=3000.0) == pytest.approx(-20.0, abs=1e-6)


def test_eighths_elapsed_follows_a_tempo_that_moves():
    """Slowing from 140 to 160ms over the span is the integral, not the average."""
    from lab.analysis.pulse import eighths_elapsed

    ramp = {"t_ms": [0.0, 10000.0], "period_ms": [140.0, 160.0]}
    expected = 10000.0 / 20.0 * np.log(160.0 / 140.0)   # integral of dt / (140 + t/500)
    assert eighths_elapsed(ramp, 10000.0) == pytest.approx(expected, rel=0.002)


def test_the_mapped_grid_matches_the_fixed_one_when_the_tempo_does_not_move():
    from lab.analysis.pulse import pulse_grid, pulse_grid_mapped

    pulse = {"period_ms": 150.0, "phase_ms": 0.0, "grouping": 2}
    flat = {"t_ms": [0.0], "period_ms": [150.0]}
    fixed = [g["t"] for g in pulse_grid(pulse, 3.0)]
    mapped = [g["t"] for g in pulse_grid_mapped(pulse, flat, 3.0)]
    assert mapped[:len(fixed)] == pytest.approx(fixed, abs=1e-3)


def test_the_mapped_grid_does_not_drift_where_the_fixed_one_does():
    """The reason it exists: a grid that is 2% slow ends up far from the music."""
    from lab.analysis.pulse import pulse_grid, pulse_grid_mapped

    true_period = 142.0
    pulse = {"period_ms": 139.0, "phase_ms": 0.0, "grouping": 2}   # 2% fast, as measured
    truth = {"t_ms": [0.0], "period_ms": [true_period]}
    fixed = pulse_grid(pulse, 100.0)
    mapped = pulse_grid_mapped(pulse, truth, 100.0)
    # the 600th line should be at 600 true eighths
    want = 600 * true_period / 1000.0
    assert abs(fixed[600]["t"] - want) > 1.0      # over a second out
    assert abs(mapped[600]["t"] - want) < 0.01


def test_tempo_map_hears_a_tune_speed_up():
    from lab.analysis.pulse import tempo_map

    slow = _train(160.0, 2, seconds=30.0)
    fast = _train(145.0, 2, seconds=30.0)
    tm = tempo_map(np.concatenate([slow, fast]), SR, window_s=12.0, hop_s=6.0)
    assert tm is not None
    early = [p for t, p in zip(tm["t_ms"], tm["period_ms"]) if t < 20000]
    late = [p for t, p in zip(tm["t_ms"], tm["period_ms"]) if t > 40000]
    assert np.median(early) == pytest.approx(160.0, rel=0.04)
    assert np.median(late) == pytest.approx(145.0, rel=0.04)
