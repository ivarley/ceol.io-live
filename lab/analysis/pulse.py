"""Where the notes land: the eighth-note pulse, and how it groups.

Notation is entirely on a grid. Every note in every setting on thesession.org
is some number of eighths or sixteenths, and nothing in the lab has used that
yet: the matcher throws durations away and compares pitch shapes only. To use
them, the transcription has to be put on the same grid, and that means knowing
where the grid is.

The fastest steady periodicity in a session recording IS that grid. Irish
dance tunes are played in a near-constant stream of eighth notes, so the
onset envelope repeats at the eighth-note period, and again at the beat, and
again at the bar. Finding the shortest strong period gives the grid; asking
whether it groups in twos or threes gives the meter.

That second question is the reel-versus-jig question, and it is a better
handle on it than a classifier: a reel divides its beat in two and a jig in
three, so the onset envelope correlates with itself at twice the eighth
period in a reel and at three times in a jig. It is the definition rather
than a proxy for it.

Three things come out:

- `period_ms`, the eighth-note, which is what quantisation needs;
- `phase_ms`, where the grid starts, which is what alignment needs;
- `grouping`, 2 or 3, which is the meter.

Nothing here uses the ground truth, so `grouping` can be scored against the
tune types the corpus records.
"""

import numpy as np

HOP = 256                      # 11.6ms at 22.05kHz
MIN_EIGHTH_S = 0.11            # faster than anyone plays
MAX_EIGHTH_S = 0.30            # slower than anyone dances to
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


def estimate_pulse(y, sr, hop=HOP):
    """-> dict, or None when there is nothing periodic to find.

    The eighth-note is not simply the strongest short period. Measured on a
    real reel, the eighth sits at 174ms with an autocorrelation of 0.12 while
    the beat at 337ms reaches 0.36 and the bar at 1347ms reaches 0.20: the
    grid is the WEAKEST of the three, because only some eighths are accented
    and every beat and bar is. Picking the tallest peak lands on the beat.

    So each candidate is judged by how well a comb at that period explains
    everything above it, and ties are broken towards the shortest, since a
    grid twice too slow explains the same peaks and is no use for
    quantisation.
    """
    onset = onset_envelope(y, sr, hop=hop)
    if onset.size < 64:
        return None
    ac = _autocorrelation(onset)
    frames_per_s = sr / hop

    def at(seconds):
        target = seconds * frames_per_s
        a, b = int(np.floor(target)), int(np.ceil(target))
        if b >= ac.size or a < 1:
            return 0.0
        frac = target - a
        return float(ac[a] * (1 - frac) + ac[b] * frac)

    lo = max(2, int(MIN_EIGHTH_S * frames_per_s))
    hi = min(ac.size - 1, int(MAX_EIGHTH_S * frames_per_s))
    if hi - lo < 4:
        return None
    candidates = [i for i in range(max(2, lo), hi)
                  if ac[i] >= ac[i - 1] and ac[i] >= ac[i + 1] and ac[i] > 0.02]
    if not candidates:
        return None

    scored = []
    for lag in candidates:
        period = _refine(ac, lag) / frames_per_s
        # Two combs for CHOOSING the grid: a real eighth-note explains the
        # structure above it, whichever way that structure groups.
        comb2 = at(period * 2) + 0.7 * at(period * 4) + 0.5 * at(period * 8)
        comb3 = at(period * 3) + 0.7 * at(period * 6) + 0.5 * at(period * 12)
        # But the BEAT alone decides the grouping, because that is what the
        # meter is: a reel divides its beat in two, a jig in three. Adding the
        # higher multiples took jigs from 74% to 51%, since four and eight
        # eighths land near real peaks in 6/8 without meaning anything.
        scored.append((at(period) + max(comb2, comb3), period,
                       at(period * 2), at(period * 3)))
    best = max(s[0] for s in scored)
    # The shortest period that explains the structure nearly as well, because
    # a grid at twice the spacing fits the same peaks and quantises nothing.
    # Written as a margin rather than a fraction so it still means something
    # when the best score is negative, which happens on a segment with no
    # steady pulse at all.
    tolerance = 0.15 * max(abs(best), 1e-6)
    good = [s for s in scored if s[0] >= best - tolerance] or scored
    score, period_s, duple, triple = min(good, key=lambda s: s[1])

    grouping = 2 if duple >= triple else 3
    return {
        "period_ms": period_s * 1000.0,
        "phase_ms": _phase(onset, period_s * frames_per_s) / frames_per_s * 1000.0,
        "grouping": grouping,
        "duple_strength": duple,
        "triple_strength": triple,
        "grouping_margin": abs(duple - triple) / max(1e-6, max(duple, triple)),
        "pulse_strength": at(period_s),
        "comb_score": score,
        "bpm_eighths": 60.0 / period_s,
        "bpm_beat": 60.0 / (period_s * grouping),
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


def _phase(onset, period_frames):
    """Where the grid starts: the offset whose pulse train best fits the onsets."""
    period = max(2.0, float(period_frames))
    best_offset, best_score = 0.0, -np.inf
    positions = np.arange(0, onset.size, period)
    for offset in np.linspace(0, period, 24, endpoint=False):
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
