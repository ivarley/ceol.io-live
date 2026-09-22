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


def notes_from_pitch(times_ms, f0_hz, voiced_prob, min_note_ms=60, median_frames=5,
                     min_voiced=0.5):
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
