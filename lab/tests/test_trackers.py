"""The pitch tracker's two settings that exist because of a solo tin whistle.

yin can settle on a multiple of the true period. Twice or four times is
harmless here, because pitch is folded to one octave; three times is not, and
it is what made a whistle's F# come out as B, a fifth away.
"""

import numpy as np
import pytest

from lab.frontends import get_frontend
from lab.frontends.trackers import correct_twelfths

SR = 22050
N_FFT, HOP = 2048, 256


def tone(f, seconds=1.0, harmonics=(1.0, 0.5, 0.3, 0.2)):
    t = np.arange(int(SR * seconds)) / SR
    y = sum(a * np.sin(2 * np.pi * f * (k + 1) * t) for k, a in enumerate(harmonics))
    return (y / np.max(np.abs(y))).astype(np.float32)


def frames_of(y):
    return 1 + y.size // HOP


def test_a_third_of_the_pitch_is_put_back():
    f = 740.0                                    # F#5, a whistle note
    y = tone(f)
    wrong = np.full(frames_of(y), f / 3.0)       # what yin reported: B3
    fixed = correct_twelfths(y, SR, wrong, N_FFT, HOP, ratio=1.5)
    middle = fixed[10:-10]
    assert np.median(middle) == pytest.approx(f, rel=0.01)


def test_an_octave_error_is_left_alone():
    """Folding absorbs it already, and the spectrum still has energy at 2*f0."""
    f = 740.0
    y = tone(f)
    octave_down = np.full(frames_of(y), f / 2.0)
    fixed = correct_twelfths(y, SR, octave_down, N_FFT, HOP, ratio=1.5)
    assert np.median(fixed[10:-10]) == pytest.approx(f / 2.0, rel=0.01)


def test_a_correct_pitch_is_left_alone():
    f = 440.0
    y = tone(f)
    right = np.full(frames_of(y), f)
    fixed = correct_twelfths(y, SR, right, N_FFT, HOP, ratio=1.5)
    assert np.median(fixed[10:-10]) == pytest.approx(f, rel=0.01)


def test_the_old_cached_tracks_keep_their_key_and_the_new_default_does_not_reuse_it():
    """Tracks cached before the threshold existed were made at 0.1.

    Leaving the default out of the cache key would have let a request for 0.5
    be answered with one of those, silently. Only the legacy value is left
    out.
    """
    legacy = get_frontend("yin", trough_threshold=0.1)
    default = get_frontend("yin")
    assert "trough_threshold" not in legacy.track_params()
    assert default.track_params().get("trough_threshold") == 0.5
    assert legacy.cache_key("sha", 0, 1000) != default.cache_key("sha", 0, 1000)


def test_basic_pitch_melody_is_the_loudest_note_and_merges_repeats():
    """The skyline takes the loudest note in each frame, so a quiet guitar
    chord under the tune is ignored. Two back-to-back notes of one pitch are
    one note: keeping the model's repeats apart cost 5.6 points of top-1."""
    import numpy as np

    from lab.frontends.basicpitch import skyline
    from lab.frontends.segmentation import notes_from_pitch

    events = [(0.00, 0.20, 74, 0.9), (0.20, 0.40, 74, 0.8),     # two Ds, struck
              (0.40, 0.60, 76, 0.9), (0.00, 0.60, 55, 0.3)]     # an E; a quiet chord tone
    times, f0, voiced = skyline(events, 600.0)
    notes = notes_from_pitch(times, f0, voiced, min_note_ms=30, median_frames=1,
                             min_voiced=0.5, fold_pitch_classes=True)
    assert [n["midi"] % 12 for n in notes] == [2, 4]
    assert not np.isnan(f0[20]) and voiced[20] == 1


def test_pesto_band_is_applied_at_the_note_step():
    """PESTO has no search range; frames outside yin's band are unvoiced
    afterwards, so a bass note under the tune never becomes a melody note."""
    import numpy as np

    from lab.frontends.pestotrack import PestoFrontEnd

    fe = PestoFrontEnd(min_voiced=0.0, split_repeats=None, out_of_key_drop=None)
    times = np.arange(60) * 10.0
    f0 = np.array([110.0] * 30 + [587.33] * 30)    # A2 under the band, then D5
    notes = fe.notes_from_track(times, f0, np.ones(60))
    assert [n["midi"] % 12 for n in notes] == [2]
    assert "fmin" not in fe.note_params() and "fmin" not in fe.track_params()
