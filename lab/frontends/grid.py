"""Putting a transcription back on the grid the corpus is notated on.

The note segmenter's documented weakness is that two notes of the same pitch
in a row fuse into one long note, because a run-length step over a pitch track
has nothing to cut on when the pitch does not change. That silently deletes a
zero from the interval sequence, and the zeros are not rare: measured over
sixty segments, the notation these tunes come from has a repeated note in
8.1% of its intervals and the transcription recovers 4.1%. One repeat in two
is lost.

A grid alone cannot fix it, because a held note and two struck notes of the
same pitch occupy the same span. What separates them is whether anything was
struck in between, so the split is gated on an onset. The cruder rule, split
anything long enough, is here too because it costs nothing to try and the
bench is what decides.
"""

import numpy as np


def _grid_lines(t0_ms, t1_ms, period_ms, phase_ms):
    """The grid positions strictly inside a span."""
    if period_ms <= 0:
        return []
    first = int(np.ceil((t0_ms - phase_ms) / period_ms))
    last = int(np.floor((t1_ms - phase_ms) / period_ms))
    return [phase_ms + k * period_ms for k in range(first, last + 1)
            if t0_ms < phase_ms + k * period_ms < t1_ms]


MIN_PIECE = 0.25            # of a grid spacing; see `split_fused_repeats`


def split_fused_repeats(notes, period_ms, phase_ms, attacks_ms=None,
                        min_slots=1.6, tolerance=0.35, require_attack=True):
    """Cut a long note at interior grid lines, into repeats of the same pitch.

    `tolerance` is how far from a grid line an attack may sit and still count,
    as a fraction of the grid spacing. `require_attack` off gives the crude
    rule: every long note is assumed to be repeats, which is wrong wherever
    the notation really does hold a note.

    A cut too near either end is dropped. A note that starts a hair before a
    grid line would otherwise be split into a sliver and the rest, and after
    rounding to whole milliseconds the sliver is a note of zero length -- which
    the interval step reads as a repeat, so the one thing this function exists
    to count would be counting its own rounding error.
    """
    if period_ms <= 0 or not notes:
        return list(notes)
    attacks = np.asarray(sorted(attacks_ms or []), dtype=float)
    window = tolerance * period_ms
    out = []
    for note in notes:
        span = note["t1_ms"] - note["t0_ms"]
        if span < min_slots * period_ms:
            out.append(note)
            continue
        cuts = []
        guard = MIN_PIECE * period_ms
        for line in _grid_lines(note["t0_ms"], note["t1_ms"], period_ms, phase_ms):
            if line - note["t0_ms"] < guard or note["t1_ms"] - line < guard:
                continue
            if not require_attack:
                cuts.append(line)
                continue
            if attacks.size:
                i = int(np.searchsorted(attacks, line))
                near = [attacks[j] for j in (i - 1, i) if 0 <= j < attacks.size]
                if any(abs(a - line) <= window for a in near):
                    cuts.append(line)
        if not cuts:
            out.append(note)
            continue
        edges = [note["t0_ms"]] + cuts + [note["t1_ms"]]
        for a, b in zip(edges, edges[1:]):
            if int(round(b)) - int(round(a)) <= 0:
                continue
            out.append({**note, "t0_ms": int(round(a)), "t1_ms": int(round(b))})
    return out


def drop_short_notes(notes, period_ms, min_eighths):
    """Notes shorter than a fraction of an eighth at this tune's tempo.

    The fixed minimum (`min_note_ms`) cannot do this job: on a polka the
    tracker's extra notes are about a third of an eighth, while a reel's real
    notes can be 80ms, and a millisecond cut that removes the first removes
    the second (100ms took reels from 0.845 to 0.769).
    """
    if not min_eighths or not period_ms:
        return notes
    floor = min_eighths * period_ms
    return [n for n in notes if n["t1_ms"] - n["t0_ms"] >= floor]


def regrid_notes(notes, period_ms, phase_ms, attacks_ms=None, mode="attack",
                 min_slots=1.6, tolerance=0.35, min_eighths=0.0):
    """The one entry point both loops call, so neither can drift from the other.

    The bench's front end and the board's note expert reach this from opposite
    directions -- one holds the audio, the other holds a `pulse` observation --
    and the mode-to-behaviour decision lives here rather than in each of them.
    It was in each of them for about an hour, and they already disagreed: the
    front end honoured the crude "grid" mode and the expert silently ignored
    it.
    """
    notes = drop_short_notes(notes, period_ms, min_eighths)
    if not mode or not notes or not period_ms:
        return notes
    return split_fused_repeats(
        notes, period_ms, phase_ms, attacks_ms=attacks_ms,
        min_slots=min_slots, tolerance=tolerance,
        require_attack=(mode == "attack"))
