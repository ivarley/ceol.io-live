"""Which seven notes is this tune using?

Irish dance music is almost entirely diatonic, so a transcription of it should
put nearly all its weight on one seven-note set. Measured over 501 segments,
the median transcription puts 95.5% of its note time inside the best-fitting
set, which is a remarkable amount of agreement from a monophonic tracker
pointed at a room.

The answer is reported as a number of sharps rather than a key name, because
that is all an audio estimate can honestly claim. D major, B minor, E
mixolydian and A dorian are the same seven notes with a different note called
home, and nothing in a pitch-class histogram distinguishes them. The corpus
collapses onto the same number through `abc_pitch.key_sharps`, so the two are
directly comparable.

Two things come out, and the second turned out to be the useful one:

- `sharps`, which the corpus can be checked against. It is right on 92.0% of
  segments, against 81.9% for never listening and always saying two sharps,
  which is what this repertoire mostly plays in.

- `diatonic_fraction`, the share of note time inside that set, which says
  nothing about which tune this is and a great deal about whether the
  transcription is worth believing. It correlates +0.386 with getting the
  tune right, where the strength of the pulse manages +0.163, and the two are
  nearly independent.

What it is NOT worth is narrowing the candidates. See the spec: knowing the
true key perfectly moves top-1 by four thousandths, because this session
plays in D and G and those two cover most of the corpus between them.
"""

import numpy as np

MAJOR = (0, 2, 4, 5, 7, 9, 11)
# The major key with this many sharps, as a pitch class. Each sharp added
# moves the tonic up a fifth.
NAMES = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
         -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb"}
SHARPS_RANGE = range(-5, 8)


def root_for_sharps(sharps):
    """Pitch class of the major tonic for a key signature."""
    return (7 * int(sharps)) % 12


def pitch_class_mass(notes):
    """How much note TIME each of the twelve pitch classes holds.

    Time rather than count, because an ornament and a held note are one note
    each and should not weigh the same. A note of no length still counts for
    something so that a badly cut transcription is not silent.
    """
    mass = np.zeros(12, dtype=float)
    for n in notes:
        mass[int(n["midi"]) % 12] += max(1.0, float(n["t1_ms"] - n["t0_ms"]))
    return mass


def estimate_key(notes, min_notes=30):
    """-> dict, or None when there are too few notes to say anything."""
    if len(notes) < min_notes:
        return None
    mass = pitch_class_mass(notes)
    total = float(mass.sum())
    if total <= 0:
        return None
    scored = []
    for sharps in SHARPS_RANGE:
        root = root_for_sharps(sharps)
        inside = float(sum(mass[(root + d) % 12] for d in MAJOR)) / total
        scored.append((inside, sharps))
    scored.sort(key=lambda s: (-s[0], abs(s[1])))
    best, runner = scored[0], scored[1]
    return {
        "sharps": int(best[1]),
        "name": NAMES.get(int(best[1]), "?"),
        "root": root_for_sharps(best[1]),
        "diatonic_fraction": best[0],
        "margin": best[0] - runner[0],
        "runner_up_sharps": int(runner[1]),
        "mass": [round(float(v) / total, 4) for v in mass],
    }


def diatonic_fraction(notes, min_notes=30):
    """The share of note time inside the best seven-note set, or None.

    Pulled out on its own because it is used as a confidence signal far more
    than the key itself is, and a caller wanting it should not have to know
    that a key estimate is how it is computed.
    """
    key = estimate_key(notes, min_notes=min_notes)
    return None if key is None else key["diatonic_fraction"]
