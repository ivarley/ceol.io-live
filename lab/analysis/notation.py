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


def quantise(notes, period_ms, phase_ms=0.0, max_eighths=8, min_gap_eighths=1):
    """Notes onto the eighth grid -> [{pc, eighths, start, rest}].

    A note becomes a start position and a length, both in whole eighths. Rests
    are emitted for gaps of a whole eighth or more, because a phrase boundary
    is part of the shape and an n-gram should not span one.

    `phase_ms` only shifts which grid line counts as zero. It cannot change
    any note's LENGTH, which is why this works without knowing the phase.
    """
    out = []
    if period_ms <= 0 or not notes:
        return out
    prev_end = None
    for n in sorted(notes, key=lambda n: n["t0_ms"]):
        start = int(round((n["t0_ms"] - phase_ms) / period_ms))
        end = int(round((n["t1_ms"] - phase_ms) / period_ms))
        length = max(1, min(int(max_eighths), end - start))
        if prev_end is not None:
            if start < prev_end:
                start = prev_end          # overlaps: the later note wins its slot
            gap = start - prev_end
            if gap >= min_gap_eighths:
                out.append({"pc": None, "eighths": gap, "start": prev_end, "rest": True})
        out.append({"pc": int(n["midi"]) % 12, "eighths": length, "start": start,
                    "rest": False})
        prev_end = start + length
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


def _abc_length(eighths):
    return "" if eighths == 1 else str(int(eighths))


def to_abc(quantised, sharps=2, key_name=None, per_line=32):
    """The quantised stream as ABC, with no bar lines.

    Deliberately no bar lines: the lab does not know where they go, and
    writing them in the wrong place would be a claim it cannot support. ABC
    allows a body without them.
    """
    key = key_name or KEY_NAMES.get(sharps, "C")
    body, line, used = [], [], 0
    for item in quantised:
        if item["rest"]:
            token = "z" + _abc_length(item["eighths"])
        else:
            letter, alteration = spell(item["pc"], sharps)
            token = (abc_accidental(letter, alteration, sharps) + letter
                     + _abc_length(item["eighths"]))
        line.append(token)
        used += item["eighths"]
        if used >= per_line:
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
            "eighths": int(sum(i["eighths"] for i in q))}


def duration_histogram(quantised):
    """How long the heard notes are, in eighths. A sanity check on the grid."""
    lens = [i["eighths"] for i in quantised if not i["rest"]]
    if not lens:
        return {}
    counts = {}
    for v in lens:
        counts[v] = counts.get(v, 0) + 1
    total = float(len(lens))
    return {k: v / total for k, v in sorted(counts.items())}
