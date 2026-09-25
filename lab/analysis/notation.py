"""A stream of heard notes, put on the eighth-note grid and written out.

Everything here needs the grid's PERIOD and nothing else. The phase decides
where a bar line goes and is the one thing the lab cannot find (see the
spec), but a note's length in eighths does not depend on where the bar
starts, and neither does the sequence of pitches. So notation without bar
lines is reachable now and notation with them is not.

That is not much of a loss for matching. The index compares interval
sequences and has never known where a bar was. What this adds is duration,
which the matcher currently throws away, and a way to look at what was heard
in the same form the corpus is written in.

Pitches are pitch classes in one octave, as everything downstream is: no two
Irish tunes differ by octave alone, and a tracker in a room gets the octave
wrong far more often than the note name.
"""

from lab.analysis.key import NAMES as KEY_NAMES
from lab.analysis.key import estimate_key

# The seven letters and the pitch classes they take in C major.
LETTERS = ["C", "D", "E", "F", "G", "A", "B"]
LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"]
FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"]


TICKS_PER_EIGHTH = 2          # the grid notes are placed on: sixteenths

# Lengths a single note head can actually be, in sixteenths: the powers of two
# and their dotted forms. A note of five sixteenths is not a note, it is a
# quarter tied to a sixteenth, and asking an engraver to draw one gets
# "Duration not representable" and a hole in the stave.
REPRESENTABLE = (1, 2, 3, 4, 6, 8, 12, 16)


def _drawable(ticks):
    """The longest drawable length that is no longer than `ticks`."""
    best = REPRESENTABLE[0]
    for value in REPRESENTABLE:
        if value <= ticks:
            best = value
    return best


def _split_rest(ticks):
    """A gap as one or more drawable rests, longest first."""
    out = []
    while ticks > 0:
        take = _drawable(ticks)
        out.append(take)
        ticks -= take
    return out


def quantise(notes, period_ms, phase_ms=0.0, max_eighths=8,
             ticks_per_eighth=TICKS_PER_EIGHTH, min_gap_ticks=2):
    """Notes onto the grid -> [{pc, ticks, start, rest}], start in ticks.

    Positions are placed on SIXTEENTHS and durations written in eighths. That
    sounds like a contradiction and is the whole point: this music is a stream
    of eighth notes, so eighths are what should be read, but the notes arrive
    slightly faster than the eighth grid can hold. Rounding every note to the
    nearest eighth put a fifth of them in a slot that was already taken, and
    dropping those turned `C B A C B A G B` into `C A C B G B`, which is not
    the tune. Half an eighth of resolution keeps them.

    `phase_ms` only shifts which grid line counts as zero. Moving it cannot
    stretch or shrink the music, though at exactly half a grid step it can
    round two neighbours into one slot.

    Every note keeps the slot its own timestamp puts it in. An earlier version
    pushed a note forward when it collided, and the pushes accumulated: a
    hundred seconds of music came out nearly eight seconds long, so the note
    highlighted during playback was about fourteen notes from the one being
    heard. A note's place in time is a fact and its length is an estimate, so
    it is the length that gives way.
    """
    if period_ms <= 0 or not notes:
        return []
    tick_ms = period_ms / float(ticks_per_eighth)
    max_ticks = int(max_eighths * ticks_per_eighth)
    slots = {}
    for n in sorted(notes, key=lambda n: n["t0_ms"]):
        start = int(round((n["t0_ms"] - phase_ms) / tick_ms))
        end = int(round((n["t1_ms"] - phase_ms) / tick_ms))
        ticks = max(1, end - start)
        held = slots.get(start)
        # two notes inside one sixteenth is an ornament, and the longer of them
        # is the one the tune is made of
        if held is None or ticks > held[0]:
            slots[start] = (ticks, int(n["midi"]) % 12)

    out = []
    starts = sorted(slots)
    prev_end = None
    for i, start in enumerate(starts):
        ticks, pc = slots[start]
        following = starts[i + 1] if i + 1 < len(starts) else None
        if following is not None:
            ticks = min(ticks, following - start)
        ticks = max(1, min(max_ticks, ticks))
        if prev_end is not None and start - prev_end >= min_gap_ticks:
            at = prev_end
            for chunk in _split_rest(start - prev_end):
                out.append({"pc": None, "ticks": chunk, "start": at, "rest": True})
                at += chunk
        # A note's length is an estimate, so it gives way to what can be
        # drawn; its start is a fact and never moves.
        ticks = _drawable(ticks)
        out.append({"pc": pc, "ticks": ticks, "start": start, "rest": False})
        prev_end = start + ticks
    return out


def key_signature_map(sharps):
    """{letter: -1/+1} for the letters this key signature alters."""
    sig = {}
    if sharps > 0:
        for letter in SHARP_ORDER[:min(sharps, 7)]:
            sig[letter] = 1
    elif sharps < 0:
        for letter in FLAT_ORDER[:min(-sharps, 7)]:
            sig[letter] = -1
    return sig


# Which black key gets which name when the key signature does not decide.
# These are the spellings this music actually uses: C sharp and F sharp, E
# flat and B flat, and G sharp rather than A flat.
PREFERRED = {1: 1, 3: -1, 6: 1, 8: 1, 10: -1}


def spell(pc, sharps):
    """A pitch class as (letter, alteration), alteration in -1, 0, +1.

    The alteration is semitones from the LETTER's natural pitch, not from the
    key signature, so an F natural in G major comes back as ("F", 0) and needs
    a natural sign rather than being renamed E sharp. Getting that wrong is
    how a modal tune ends up unreadable, and D mixolydian against D major is
    exactly that one note.
    """
    pc = int(pc) % 12
    sig = key_signature_map(sharps)
    best = None
    for letter in LETTERS:
        natural = LETTER_PC[letter]
        for alteration in (0, 1, -1):
            if (natural + alteration) % 12 != pc:
                continue
            cost = (
                0 if alteration == sig.get(letter, 0) else 1,   # already in the key
                0 if alteration == PREFERRED.get(pc, 0) else 1,  # the usual name
                abs(alteration),
            )
            if best is None or cost < best[0]:
                best = (cost, (letter, alteration))
    return best[1] if best else ("C", 0)


def abc_accidental(letter, alteration, sharps):
    """The symbol to write, given what the key signature already says."""
    if alteration == key_signature_map(sharps).get(letter, 0):
        return ""
    return {1: "^", -1: "_", 0: "="}[alteration]


def staff_step(pc, sharps):
    """Diatonic step of a pitch, 0 = C, 1 = D ... 6 = B. For drawing."""
    letter, _alteration = spell(pc, sharps)
    return LETTERS.index(letter)


def _abc_length(ticks, ticks_per_eighth=TICKS_PER_EIGHTH):
    """Length in ticks -> an ABC length marker, with L:1/8 as the unit.

    Whole eighths stay bare or numbered, which is how this music reads. A
    sixteenth becomes "/", which is ABC for half the unit, so the exceptions
    look like exceptions.
    """
    if ticks % ticks_per_eighth == 0:
        eighths = ticks // ticks_per_eighth
        return "" if eighths == 1 else str(int(eighths))
    if ticks_per_eighth == 2:
        return "/" if ticks == 1 else f"{ticks}/2"
    return f"{ticks}/{ticks_per_eighth}"


def to_abc(quantised, sharps=2, key_name=None, per_line=0):
    """The quantised stream as ABC, with no bar lines.

    Deliberately no bar lines: the lab does not know where they go, and
    writing them in the wrong place would be a claim it cannot support. ABC
    allows a body without them.
    """
    key = key_name or KEY_NAMES.get(sharps, "C")
    # per_line = 0 means one unbroken line, which is what the viewer wants:
    # a stave that runs alongside the piano roll rather than a page of music.
    body, line, used = [], [], 0
    for item in quantised:
        if item["rest"]:
            token = "z" + _abc_length(item["ticks"])
        else:
            letter, alteration = spell(item["pc"], sharps)
            token = (abc_accidental(letter, alteration, sharps) + letter
                     + _abc_length(item["ticks"]))
        line.append(token)
        used += item["ticks"] / float(TICKS_PER_EIGHTH)
        if per_line and used >= per_line:
            body.append(" ".join(line))
            line, used = [], 0
    if line:
        body.append(" ".join(line))
    # M:none is the truthful header: this has no bar lines because the lab
    # does not know where they go, and a meter would imply it did.
    return f"X:1\nM:none\nL:1/8\nK:{key}\n" + "\n".join(body)


def notate(notes, period_ms, phase_ms=0.0, sharps=None, max_eighths=8):
    """Everything at once: quantise, guess the key if not given, write ABC."""
    if sharps is None:
        key = estimate_key(notes)
        sharps = key["sharps"] if key else 0
    q = quantise(notes, period_ms, phase_ms=phase_ms, max_eighths=max_eighths)
    return {"sharps": int(sharps), "key": KEY_NAMES.get(int(sharps), "C"),
            "quantised": q, "abc": to_abc(q, sharps=int(sharps)),
            "n_notes": sum(1 for i in q if not i["rest"]),
            "n_rests": sum(1 for i in q if i["rest"]),
            "ticks_per_eighth": TICKS_PER_EIGHTH,
            "eighths": sum(i["ticks"] for i in q) / float(TICKS_PER_EIGHTH)}


def duration_histogram(quantised):
    """How long the heard notes are, in eighths. A sanity check on the grid."""
    lens = [i["ticks"] / float(TICKS_PER_EIGHTH) for i in quantised if not i["rest"]]
    if not lens:
        return {}
    counts = {}
    for v in lens:
        counts[v] = counts.get(v, 0) + 1
    total = float(len(lens))
    return {k: v / total for k, v in sorted(counts.items())}
