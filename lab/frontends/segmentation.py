"""Frequencies to notes. Shared by the front ends and by the board's expert.

One implementation, because a front end that scores well on the bench and an
expert that behaves differently on the board would be the same bug the two
loops exist to prevent.
"""

import numpy as np


def median_filter(x, k):
    if k <= 1 or x.size == 0:
        return x
    pad = k // 2
    padded = np.pad(x, (pad, pad), mode="edge")
    out = np.empty_like(x)
    for i in range(x.size):
        out[i] = np.median(padded[i:i + k])
    return out


def merge_interlopers(notes, max_interloper_ms=70):
    """Drop a brief wrong note wedged between two of the same pitch.

    A tracker on a room wobbles. One frame of the note above, in the middle of
    a held note, splits it into three and inserts two intervals that are not
    in the tune. The run-length step cannot see this because it only compares
    neighbours; this looks at the note either side.
    """
    if len(notes) < 3:
        return notes
    out = [notes[0]]
    i = 1
    while i < len(notes) - 1:
        before, here, after = out[-1], notes[i], notes[i + 1]
        short = (here["t1_ms"] - here["t0_ms"]) <= max_interloper_ms
        bridged = before["midi"] == after["midi"] != here["midi"]
        if short and bridged:
            out[-1] = {**before, "t1_ms": after["t1_ms"]}   # swallow all three
            i += 2
            continue
        out.append(here)
        i += 1
    if i < len(notes):
        out.append(notes[i])
    return out


PITCH_CLASS_BASE = 60          # labels and folded notes live in C4..B4


def fold_pitch(midi):
    """A pitch reduced to its class, in one fixed octave.

    Octave carries no information about which tune this is: no two Irish tunes,
    and no two parts of one, differ by octave alone. Everything downstream
    already works in pitch classes, because folding an interval to its nearest
    direction is the same operation as taking the difference of pitch classes.

    Doing it here as well, before notes are cut, is not cosmetic. A tracker
    that jumps an octave in the middle of a held note makes the run-length
    step see a new pitch and cut the note in two, inserting an interval the
    tune does not contain. Folding first leaves the note whole.
    """
    return PITCH_CLASS_BASE + (int(round(midi)) % 12)


def notes_from_pitch(times_ms, f0_hz, voiced_prob, min_note_ms=60, median_frames=5,
                     min_voiced=0.5, merge_interlopers_ms=0, fold_pitch_classes=False):
    """A pitch track to note events.

    Known weakness, and a real one for this music: a cut or a roll fragments
    one note into three, and two of the same pitch in a row fuse into one long
    note, which silently deletes a zero from the interval sequence.
    """
    import librosa

    times_ms = np.asarray(times_ms, dtype=float)
    f0 = np.asarray(f0_hz, dtype=float)
    voiced = np.asarray(voiced_prob, dtype=float)
    if f0.size == 0:
        return []
    keep = voiced >= min_voiced
    if not np.any(keep):
        return []
    midi = np.full(f0.shape, np.nan)
    valid_hz = keep & np.isfinite(f0) & (f0 > 0)
    midi[valid_hz] = np.round(librosa.hz_to_midi(f0[valid_hz]))
    if fold_pitch_classes:
        midi[valid_hz] = PITCH_CLASS_BASE + np.mod(midi[valid_hz], 12)
    smoothed = midi.copy()
    valid = np.isfinite(midi)
    if np.any(valid):
        smoothed[valid] = median_filter(midi[valid], int(median_frames))

    notes = []
    current = None
    start = None
    for i in range(smoothed.size + 1):
        value = smoothed[i] if i < smoothed.size else np.nan
        if current is not None and (not np.isfinite(value) or value != current):
            t0 = times_ms[start]
            span = (times_ms[i] - t0) if i < times_ms.size else (times_ms[-1] - t0)
            if span >= min_note_ms:
                conf = float(np.mean(voiced[start:i])) if i > start else 0.0
                notes.append({"t0_ms": int(t0), "t1_ms": int(t0 + span),
                              "midi": int(current), "conf": round(conf, 3)})
            current, start = None, None
        if np.isfinite(value) and current is None:
            current, start = value, i
    if merge_interlopers_ms:
        notes = merge_interlopers(notes, max_interloper_ms=merge_interlopers_ms)
    return notes


def intervals_from_notes(notes, clip=12, max_gap_ms=1500, fold=False):
    """Semitone steps, with a gap breaking the phrase so no n-gram spans one.

    `fold` must match the index being queried: see abc_pitch.fold_interval.
    """
    from lab.corpus.abc_pitch import fold_interval

    out = []
    for prev, nxt in zip(notes, notes[1:]):
        if nxt["t0_ms"] - prev["t1_ms"] > max_gap_ms:
            out.append(None)
        else:
            d = int(nxt["midi"] - prev["midi"])
            out.append(fold_interval(d) if fold else int(np.clip(d, -clip, clip)))
    return out
