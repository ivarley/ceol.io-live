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


def _grouping_margin(duple, triple):
    """How much the winning subdivision beats both the loser and nothing at all.

    This was a ratio, and on a segment with no rhythm in it at all the two
    strengths were 0.005 and -0.048, which the ratio reported as a confidence
    of 288380. The quantity wanted is bounded and falls to zero in both ways a
    meter call can be unsupported: when the two subdivisions are equally
    strong, and when neither is strong.
    """
    winner, loser = max(duple, triple), min(duple, triple)
    return float(np.clip(winner - max(loser, 0.0), 0.0, 1.0))


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
    return pulse_from_onset(onset_envelope(y, sr, hop=hop), sr, hop=hop)


def pulse_from_onset(onset, sr, hop=HOP):
    """`estimate_pulse` from an onset envelope already worked out."""
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
    # Which beat starts the bar. Entirely unverified: nothing has ever been
    # scored against a hand-marked bar line, and the beat phase it is built on
    # is itself known only to about 50ms on one segment. It is computed the
    # same way one level up, by fitting a train at the bar period, and a
    # caller that needs to be right about bar lines should treat it as a
    # guess until `lab bench pulse` has something to say about it.
    beats_per_bar = 4 if grouping == 2 else 2
    bar_s = beat_s * beats_per_bar
    bar_phase_s = _phase(onset, bar_s * frames_per_s,
                         frames_per_s=frames_per_s) / frames_per_s
    # keep it on the beat grid: a bar line that is not a beat is not a bar line
    k = round((bar_phase_s - phase_s) / beat_s)
    bar_phase_s = phase_s + k * beat_s
    return {
        "period_ms": period_s * 1000.0,
        "phase_ms": phase_s * 1000.0,
        "grouping": grouping,
        "beat_ms": beat_s * 1000.0,
        "beats_per_bar": beats_per_bar,
        "bar_ms": bar_s * 1000.0,
        "bar_phase_ms": bar_phase_s * 1000.0,
        "bar_phase_verified": False,
        "duple_strength": duple,
        "triple_strength": triple,
        "grouping_margin": _grouping_margin(duple, triple),
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


def attack_times_ms(y, sr, hop=HOP, delta=0.06):
    """Where notes are struck, in ms from the start of `y`.

    The grid says where a note COULD start; this says where one audibly did.
    Both are needed to split a note the tracker fused: two eighths of the same
    pitch look exactly like one quarter to a run-length segmenter, and the
    only thing that tells them apart is whether anything was struck in the
    middle.
    """
    import librosa

    onset = onset_envelope(y, sr, hop=hop)
    if onset.size < 4:
        return np.zeros(0, dtype=float)
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        frames = librosa.onset.onset_detect(
            onset_envelope=onset, sr=sr, hop_length=hop, units="frames", delta=delta)
    return np.asarray(frames, dtype=float) * hop * 1000.0 / sr


# tempo_map's windows read slices of one onset envelope over the whole span
# rather than each working its own out (the span's audio three times over).
# Not the same numbers: an envelope's floor is 80 dB under its loudest frame,
# the span's rather than the window's, and the frames at a window's edges see
# the audio beyond it. Measured before being made the default (spec 053).
SHARED_ONSET = False


def tempo_map(y, sr, window_s=20.0, hop_s=10.0, hop=HOP, shared_onset=None):
    """How the eighth note changes through a span -> {t_ms, period_ms, grouping}.

    One estimate for a whole segment is both blunt and, on at least one reel,
    simply wrong. Measured in twenty-second windows Father Kelly runs at 139
    to 143ms with most windows near 142, which is what a player drawing beats
    by hand also gave; the single whole-segment estimate came out 139.3 and a
    grid built on it ends the segment 1.48 seconds adrift, which is ten and a
    half eighth notes. The tempo is not drifting much -- under 3% -- but a
    grid integrates whatever error it starts with, so a small bias becomes a
    large displacement.

    The meter is taken across the whole span rather than per window, because
    a tune does not change from a jig to a reel halfway through and a short
    window is a much worse judge of it.

    `strength` is each window's pulse strength, so a caller can tell a window
    of music from one of chat between tunes, whose "tempo" is noise.
    """
    shared = SHARED_ONSET if shared_onset is None else shared_onset
    env = onset_envelope(y, sr, hop=hop) if shared else None
    whole = pulse_from_onset(env, sr, hop=hop) if shared else estimate_pulse(y, sr, hop=hop)
    if not whole:
        return None
    n = y.size
    step = int(hop_s * sr)
    width = int(window_s * sr)
    times, periods, strengths = [], [], []
    start = 0
    while start < n:
        end = min(n, start + width)
        if end - start >= int(4.0 * sr):
            if shared:
                local = pulse_from_onset(env[start // hop:end // hop], sr, hop=hop)
            else:
                local = estimate_pulse(y[start:end], sr, hop=hop)
            if local:
                # A window that disagrees by a factor is an octave error, not
                # a tempo change; fold it back rather than letting it bend the
                # map in half.
                p = local["period_ms"]
                while p > 1.5 * whole["period_ms"]:
                    p /= 2.0
                while p < 0.67 * whole["period_ms"]:
                    p *= 2.0
                times.append((start + end) / 2.0 / sr * 1000.0)
                periods.append(p)
                strengths.append(float(local["pulse_strength"]))
        if end >= n:
            break
        start += step
    if not times:
        return None
    return {"t_ms": times, "period_ms": periods, "strength": strengths, "grouping": whole["grouping"],
            "median_period_ms": float(np.median(periods)),
            "whole_period_ms": whole["period_ms"],
            "spread_ms": float(max(periods) - min(periods))}


def period_at(tmap, t_ms):
    """The eighth-note length at a moment, interpolated between windows."""
    if not tmap:
        return 0.0
    times, periods = tmap["t_ms"], tmap["period_ms"]
    if len(times) == 1 or t_ms <= times[0]:
        return periods[0]
    if t_ms >= times[-1]:
        return periods[-1]
    i = int(np.searchsorted(times, t_ms))
    a, b = i - 1, min(i, len(times) - 1)
    span = times[b] - times[a]
    if span <= 0:
        return periods[a]
    f = (t_ms - times[a]) / span
    return periods[a] * (1 - f) + periods[b] * f


def _cumulative(tmap, lo_ms, hi_ms, step_ms=20.0):
    """The running count of eighth notes across a span, built once and kept.

    The first version integrated in 50ms steps from the start of the segment
    on every call, and it is called twice for every note, so a two-minute
    segment cost millions of Python iterations and a sweep over five hundred
    of them did not finish in twenty minutes. Integrating once into a table
    and reading off it is the same answer for the price of a lookup.
    """
    cache = tmap.get("_cumulative")
    if cache is not None and cache[0] <= lo_ms and cache[1] >= hi_ms:
        return cache
    if cache is not None:
        lo_ms, hi_ms = min(lo_ms, cache[0]), max(hi_ms, cache[1])
    ts = np.arange(lo_ms, hi_ms + step_ms, step_ms)
    mids = (ts[:-1] + ts[1:]) / 2.0
    periods = np.interp(mids, tmap["t_ms"], tmap["period_ms"])
    cum = np.concatenate([[0.0], np.cumsum(np.diff(ts) / np.maximum(periods, 1e-6))])
    cache = (float(ts[0]), float(ts[-1]), ts, cum)
    tmap["_cumulative"] = cache
    return cache


def eighths_elapsed(tmap, t_ms, origin_ms=0.0):
    """How many eighth notes have gone by between two moments.

    The integral of 1/period, which is what a grid actually is once the tempo
    is allowed to move. Returned as a float so a caller can round it to a
    slot, and negative when `t_ms` is before `origin_ms`.
    """
    if not tmap:
        return 0.0
    lo, hi = min(t_ms, origin_ms), max(t_ms, origin_ms)
    _, _, ts, cum = _cumulative(tmap, lo - 2000.0, hi + 2000.0)
    return float(np.interp(t_ms, ts, cum) - np.interp(origin_ms, ts, cum))


def pulse_grid_mapped(pulse, tmap, duration_s):
    """Like `pulse_grid`, but the lines follow the tempo instead of a ruler.

    `pulse_grid` lays lines at one fixed spacing from the phase to the end of
    the clip, so any error in that spacing accumulates: on Father Kelly the
    lines were ten eighth notes adrift by the end, which is what a player
    watching them saw as bar lines sliding off the starts of the notes. Here
    each line is placed where the running count of eighths from the tempo map
    reaches the next whole number, so a small local error stays small.

    It does nothing about the PHASE, which is still wrong on reels (see the
    spec). The lines will sit consistently in the wrong place rather than
    wandering there, which is easier to read and easier to correct by hand.

    Lines before the phase are drawn too, which the fixed version skipped.
    `tmap` times are relative to the start of the clip, as `pulse` is.
    """
    if not pulse or pulse.get("period_ms", 0) <= 0:
        return []
    if not tmap:
        return pulse_grid(pulse, duration_s)
    end_ms = duration_s * 1000.0
    _, _, ts, cum = _cumulative(tmap, -2000.0, end_ms + 2000.0)
    origin = float(pulse["phase_ms"])
    c0 = float(np.interp(origin, ts, cum))
    first = int(np.ceil(float(np.interp(0.0, ts, cum)) - c0))
    last = int(np.floor(float(np.interp(end_ms, ts, cum)) - c0))
    grouping = int(pulse["grouping"])
    per_bar = 8 if grouping == 2 else 6
    out = []
    for k in range(first, last + 1):
        t = float(np.interp(k + c0, cum, ts))
        if 0.0 <= t <= end_ms:
            out.append({"t": round(t / 1000.0, 4), "beat": k % grouping == 0,
                        "bar": k % per_bar == 0})
    return out
