"""Where the notes land: the eighth-note pulse, and how it groups.

Notation is entirely on a grid. Every note in every setting on thesession.org
is some number of eighths or sixteenths, and nothing in the lab has used that
yet: the matcher throws durations away and compares pitch shapes only. To use
them, the transcription has to be put on the same grid, and that means knowing
where the grid is.

This module used to look for the grid directly, on the theory that the fastest
steady periodicity in a session recording IS the eighth note. Hand-drawn beats
killed that theory. On a jig whose true eighth is 159ms, the onset envelope
correlates 0.011 at 159ms, 0.455 at the 478ms beat and 0.464 at the 955ms bar:
the eighth is not merely the weakest of the three, it is absent. Players slur
and roll across it, so most eighths are never articulated, and the estimator
was picking whatever noise sat in the band it was told to search.

The beat, by contrast, is the strongest peak in every one of 288 segments
surveyed, and always between 0.26s and 0.62s whatever the tune type. So the
beat is found first and the grid divided out of it.

What divides it is the meter, and the meter is legible in the same curve as
where the subdivision peaks sit RELATIVE to the beat:

    reels, polkas   peaks at 0.50, 1.00, 1.50, 2.00   halves
    jigs, slip jigs peaks at 0.36, 0.64, 1.00, 1.36   thirds

That is the reel-versus-jig question answered by its own definition rather
than by a proxy, and it gets 0.95 against the tune types the corpus records
where searching for the eighth directly got 0.80.

Note that the triple peaks sit at 0.36 and 0.64, not 0.33 and 0.67: a jig's
first eighth is longer than its second, which is most of what makes it sound
like a jig. The windows below are wide enough to hold that swing, and the
period is still reported as an even third of the beat, because the corpus
notates it evenly and the grid exists to line the two up.

Three things come out:

- `period_ms`, the eighth-note, which is what quantisation needs;
- `phase_ms`, where the grid starts, which is what alignment needs;
- `grouping`, 2 or 3, which is the meter.

Nothing here uses the ground truth, so `grouping` can be scored against the
tune types the corpus records, and `period_ms` against hand-drawn beats.
"""

import numpy as np

HOP = 256                      # 11.6ms at 22.05kHz
MIN_BEAT_S = 0.26              # faster than anyone plays
MAX_BEAT_S = 0.62              # slower than anyone dances to
# Where a subdivision peak may sit, as a fraction of the beat. Wide enough for
# the swing a jig and a hornpipe are played with, narrow enough not to overlap.
DUPLE_WINDOW = (0.44, 0.57)
TRIPLE_WINDOWS = ((0.28, 0.41), (0.59, 0.72))
# How strong half the period must be, relative to the period, to step down
# an octave. See `_prefer_faster`.
HALVING_RATIO = 0.80
DUPLE_TYPES = {"reel", "hornpipe", "polka", "barndance", "march", "strathspey", "waltz",
               "mazurka", "three-two"}
TRIPLE_TYPES = {"jig", "slip jig", "slide", "hop jig", "single jig"}


def onset_envelope(y, sr, hop=HOP):
    import librosa

    if y.size < hop * 8:
        return np.zeros(0, dtype=np.float32)
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    return np.asarray(onset, dtype=np.float32)


def _autocorrelation(onset):
    x = onset - onset.mean()
    denom = float(np.dot(x, x)) or 1.0
    ac = np.correlate(x, x, mode="full")[x.size - 1:] / denom
    return ac


def _strongest_peak(ac, lo_s, hi_s, frames_per_s):
    """(height, period in seconds) of the tallest peak in a lag window."""
    lo = max(2, int(lo_s * frames_per_s))
    hi = min(ac.size - 1, int(hi_s * frames_per_s))
    if hi <= lo:
        return 0.0, 0.0
    peaks = [(float(ac[i]), i) for i in range(lo, hi)
             if ac[i] >= ac[i - 1] and ac[i] >= ac[i + 1]]
    if not peaks:
        # no peak of its own in there; the window still has a height, and for
        # the subdivision test that height is the whole answer
        return float(ac[lo:hi].max()), (lo + hi) / 2.0 / frames_per_s
    height, lag = max(peaks)
    return height, _refine(ac, lag) / frames_per_s


def _prefer_faster(ac, strength, beat_s, frames_per_s, ratio=HALVING_RATIO):
    """Step down an octave while half the period is still a plausible beat.

    A half-bar inherits every peak the beat has, so it scores at least as well
    and the tallest-peak rule lands on it about a fifth of the time. Measured
    over 288 segments, reels came out with a median beat of 322ms and a 95th
    percentile of 603ms: one distribution with a copy of itself at twice the
    period, which is the signature of exactly this.

    Halving is safe only because the band stops it. A reel's eighth IS
    articulated, so ac at half of a correct 322ms beat is high too, and
    nothing here would tell the difference; what tells the difference is that
    161ms is not a tempo anyone's foot keeps.
    """
    while True:
        half = beat_s / 2.0
        if half < MIN_BEAT_S:
            return strength, beat_s
        half_strength, half_s = _strongest_peak(
            ac, half * 0.94, half * 1.06, frames_per_s)
        if half_strength < ratio * strength:
            return strength, beat_s
        strength, beat_s = half_strength, half_s


def estimate_pulse(y, sr, hop=HOP):
    """-> dict, or None when there is nothing periodic to find.

    Beat first, from the tallest peak in the band every Irish dance tune's
    beat falls in. Then the meter, by asking whether that beat is divided in
    half or in thirds. Then the grid, which is the beat divided by whichever
    won.
    """
    onset = onset_envelope(y, sr, hop=hop)
    if onset.size < 64:
        return None
    ac = _autocorrelation(onset)
    frames_per_s = sr / hop
    if ac.size < int(1.2 * frames_per_s):
        return None

    beat_strength, beat_s = _strongest_peak(ac, MIN_BEAT_S, MAX_BEAT_S, frames_per_s)
    if beat_s <= 0:
        return None
    beat_strength, beat_s = _prefer_faster(ac, beat_strength, beat_s, frames_per_s)

    duple, _ = _strongest_peak(ac, DUPLE_WINDOW[0] * beat_s, DUPLE_WINDOW[1] * beat_s,
                               frames_per_s)
    thirds = [_strongest_peak(ac, lo * beat_s, hi * beat_s, frames_per_s)[0]
              for lo, hi in TRIPLE_WINDOWS]
    # Both thirds, averaged: one of them alone is as likely to be a sidelobe of
    # the beat as a note, and a jig shows both.
    triple = float(np.mean(thirds))

    grouping = 3 if triple > duple else 2
    period_s = beat_s / grouping
    phase_s = _phase(onset, beat_s * frames_per_s,
                     frames_per_s=frames_per_s) / frames_per_s
    return {
        "period_ms": period_s * 1000.0,
        "phase_ms": phase_s * 1000.0,
        "grouping": grouping,
        "beat_ms": beat_s * 1000.0,
        "duple_strength": duple,
        "triple_strength": triple,
        "grouping_margin": abs(duple - triple) / max(1e-6, max(duple, triple)),
        "pulse_strength": beat_strength,
        "bpm_eighths": 60.0 / period_s,
        "bpm_beat": 60.0 / beat_s,
    }


def _refine(ac, lag):
    """Sub-frame peak position, so a grid over two minutes does not drift."""
    if lag <= 0 or lag + 1 >= ac.size:
        return float(lag)
    a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
    denom = a - 2 * b + c
    if abs(denom) < 1e-12:
        return float(lag)
    return float(lag) + float(np.clip(0.5 * (a - c) / denom, -0.5, 0.5))


def _phase(onset, period_frames, resolution_s=0.002, frames_per_s=None):
    """Where the grid starts: the offset whose pulse train best fits the onsets.

    Searched at 2ms rather than the period/24 it used to use, because the only
    segment with hand-drawn beats puts the phase error at 49ms against beats
    whose own scatter is 32ms rms, and 20ms of search quantisation is not a
    thing to spend when the budget is that tight.
    """
    period = max(2.0, float(period_frames))
    fps = frames_per_s or (HOP and 22050.0 / HOP)
    steps = int(np.clip(round(period / max(1e-6, resolution_s * fps)), 24, 512))
    best_offset, best_score = 0.0, -np.inf
    positions = np.arange(0, onset.size, period)
    for offset in np.linspace(0, period, steps, endpoint=False):
        idx = np.round(positions + offset).astype(int)
        idx = idx[idx < onset.size]
        if idx.size == 0:
            continue
        score = float(onset[idx].sum()) / idx.size
        if score > best_score:
            best_offset, best_score = float(offset), score
    return best_offset


def pulse_grid(pulse, duration_s):
    """Pulse times in seconds, with the index of each within its group."""
    if not pulse or pulse["period_ms"] <= 0:
        return []
    period = pulse["period_ms"] / 1000.0
    phase = pulse["phase_ms"] / 1000.0
    grouping = int(pulse["grouping"])
    per_bar = 8 if grouping == 2 else 6
    out = []
    i = 0
    t = phase
    while t < duration_s:
        out.append({"t": round(t, 4), "beat": i % grouping == 0, "bar": i % per_bar == 0})
        i += 1
        t = phase + i * period
    return out


def expected_grouping(tune_type):
    """What the corpus's tune type implies, for scoring. 2, 3 or None."""
    t = (tune_type or "").strip().lower()
    if t in DUPLE_TYPES:
        return 2
    if t in TRIPLE_TYPES:
        return 3
    return None
