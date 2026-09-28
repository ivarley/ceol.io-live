"""Taking one melody from the many notes Basic Pitch hears at once.

The loudest note per frame follows any brief louder interloper, a guitar
chord tone or a drum's pitched thump, and costs two wrong intervals each
time. The continuity path should stay on the line through a short one and
still move to a real melody note, which lasts.
"""

import numpy as np

from lab.frontends.basicpitch import continuity, highest, skyline


def midis(track):
    _, f0, voiced = track
    out = []
    for hz, v in zip(f0, voiced):
        m = None if not v else int(round(69 + 12 * np.log2(hz / 440.0)))
        if not out or out[-1] != m:
            out.append(m)
    return out


# (start_s, end_s, midi, amplitude)
LINE = [(0.0, 0.3, 74, 0.5), (0.3, 0.6, 76, 0.5), (0.6, 0.9, 78, 0.5)]
BLIP = [(0.35, 0.40, 62, 0.8)]      # 50ms, louder, an octave and more below


def test_the_loudest_note_follows_a_blip():
    assert 62 in midis(skyline(LINE + BLIP, 900))


def test_continuity_stays_on_the_line_through_a_blip():
    assert midis(continuity(LINE + BLIP, 900)) == [74, 76, 78, None]


def test_continuity_moves_to_a_note_that_lasts():
    long_low = [(0.3, 0.6, 62, 0.8)]
    assert 62 in midis(continuity(LINE[:1] + long_low + LINE[2:], 900))


def test_highest_takes_the_top_voice_over_a_chord():
    chord = [(0.0, 0.9, 64, 0.9), (0.0, 0.9, 67, 0.9)]
    assert midis(highest(LINE + chord, 900)) == [74, 76, 78, None]
