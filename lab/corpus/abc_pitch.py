"""ABC notation -> a pitch sequence.

The symbolic route needs one thing from a tune's ABC: the sequence of pitches,
so that an interval sequence transcribed from audio can be matched against it.
This parser produces exactly that and nothing cleverer — durations are kept
(cheaply, in eighth notes) because a rhythm-aware matcher will want them, but
repeats are NOT expanded, broken rhythms are NOT applied, and ornaments,
grace notes, chord symbols and decorations are stripped, because none of them
survive a transcription of a pub session anyway.

What it does get right, because the matcher cannot work without it:

- the key signature: `K:` (and the dump's `mode` column, which is the same
  thing spelled out) decides which notes are sharp or flat when nothing in the
  bar says otherwise — `K:D` makes every F an F#, and F vs F# is the difference
  between a D-major reel and a modal one;
- explicit accidentals, which persist to the end of the bar for that note name
  in that octave, as the ABC standard says;
- octave marks, and the upper/lower-case octave convention;
- inline fields (`[K:G]`) and header lines inside the body, since the dump's
  ABC often carries `K:` changes for a part in a different key.

Rests are kept as `None` so an n-gram never spans one.

PARSER_VERSION is part of every index file name: bump it when the output
changes and the indexes rebuild.
"""

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import List, Optional

PARSER_VERSION = "1"

# semitone above C for each letter
_LETTER_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# how many sharps (negative = flats) a major key has
_MAJOR_SHARPS = {
    "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
    "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7,
}
# a mode's key signature relative to the major key on the same tonic
_MODE_OFFSET = {
    "major": 0, "ionian": 0, "ion": 0, "maj": 0,
    "dorian": -2, "dor": -2,
    "phrygian": -4, "phr": -4,
    "lydian": 1, "lyd": 1,
    "mixolydian": -1, "mix": -1,
    "minor": -3, "aeolian": -3, "aeo": -3, "min": -3, "m": -3,
    "locrian": -5, "loc": -5,
}
_SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"]
_FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"]


@dataclass(frozen=True)
class Note:
    midi: int
    eighths: Fraction  # duration in eighth notes


class AbcParseError(ValueError):
    pass


def key_sharps(key_text: str) -> Optional[int]:
    """`K:` field text (or the dump's mode, e.g. 'Edorian') -> sharps, flats negative.

    This one number is the whole of what a key signature is, and it is the
    right currency for comparing a notated key with a heard one. Relative
    modes collapse onto it exactly: Dmajor, Bminor, Emixolydian and Adorian
    all come back as 2, because they are the same seven notes with a different
    note called home, and an audio estimate cannot tell those apart anyway.

    None for a key that cannot be read, which `key_signature` treats as no
    accidentals but a key estimator should treat as no information.
    """
    text = (key_text or "").strip()
    m = re.match(r"^([A-Ga-g])\s*([#b])?\s*([A-Za-z]*)", text)
    if not m or text.lower() in ("none", "hp"):
        return None
    tonic = m.group(1).upper() + (m.group(2) or "")
    mode_word = (m.group(3) or "").lower()
    offset = None
    for name, off in sorted(_MODE_OFFSET.items(), key=lambda kv: -len(kv[0])):
        if mode_word.startswith(name):
            offset = off
            break
    if offset is None:
        offset = 0
    sharps = _MAJOR_SHARPS.get(tonic)
    if sharps is None:
        sharps = _MAJOR_SHARPS.get({"A#": "Bb", "D#": "Eb", "G#": "Ab", "Fb": "E",
                                    "E#": "F", "B#": "C"}.get(tonic, "C"), 0)
    return sharps + offset


def key_signature(key_text: str) -> dict:
    """`K:` field text (or the dump's mode, e.g. 'Edorian') -> {letter: +1/-1/0}.

    Unknown or exotic keys (`HP`, `none`, explicit accidental lists) fall back
    to no sharps or flats rather than failing: a wrong key signature costs a
    few semitones in a few n-grams, a parse failure loses the whole tune.
    """
    text = (key_text or "").strip()
    m = re.match(r"^([A-Ga-g])\s*([#b])?\s*([A-Za-z]*)", text)
    if not m or text.lower() in ("none", "hp"):
        return {}
    tonic = m.group(1).upper() + (m.group(2) or "")
    mode_word = (m.group(3) or "").lower()
    # "K:Am" -> minor; "K:Amix" -> mixolydian; "K:A" -> major; "K:Aminor" -> minor
    offset = None
    for name, off in sorted(_MODE_OFFSET.items(), key=lambda kv: -len(kv[0])):
        if mode_word.startswith(name):
            offset = off
            break
    if offset is None:
        offset = 0
    sharps = _MAJOR_SHARPS.get(tonic)
    if sharps is None:
        # enharmonic fallbacks: A# -> Bb, D# -> Eb, G# -> Ab, Fb -> E, E# -> F, B# -> C
        sharps = _MAJOR_SHARPS.get({"A#": "Bb", "D#": "Eb", "G#": "Ab", "Fb": "E",
                                    "E#": "F", "B#": "C"}.get(tonic, "C"), 0)
    sharps += offset
    sig = {}
    if sharps > 0:
        for letter in _SHARP_ORDER[:min(sharps, 7)]:
            sig[letter] = 1
    elif sharps < 0:
        for letter in _FLAT_ORDER[:min(-sharps, 7)]:
            sig[letter] = -1
    return sig


def _unit_length_from_meter(meter_text: str) -> Fraction:
    """ABC's rule: L: defaults to 1/16 when the meter is under 0.75, else 1/8."""
    text = (meter_text or "").strip()
    if text == "C" or text == "C|":
        return Fraction(1, 8)
    m = re.match(r"^(\d+)\s*/\s*(\d+)", text)
    if not m:
        return Fraction(1, 8)
    value = Fraction(int(m.group(1)), int(m.group(2)))
    return Fraction(1, 16) if value < Fraction(3, 4) else Fraction(1, 8)


def _parse_length(text: str) -> Fraction:
    """'', '2', '/', '/2', '3/2', '//' -> multiplier of the unit length."""
    if not text:
        return Fraction(1)
    if re.fullmatch(r"/+", text):
        return Fraction(1, 2 ** len(text))
    m = re.fullmatch(r"(\d+)?(?:/(\d+)?)?", text)
    if not m:
        return Fraction(1)
    num = int(m.group(1)) if m.group(1) else 1
    if "/" in text:
        den = int(m.group(2)) if m.group(2) else 2
        return Fraction(num, den)
    return Fraction(num)


_HEADER_LINE = re.compile(r"^\s*([A-Za-z]):(.*)$")
_INLINE_FIELD = re.compile(r"\[([A-Za-z]):([^\]]*)\]")
_NOTE = re.compile(r"(\^\^|\^|__|_|=)?([A-Ga-g])([,']*)(\d*/*\d*)")
_REST = re.compile(r"([zxZX])(\d*/*\d*)")
_TUPLET = re.compile(r"\((\d)(?::(\d*))?(?::(\d*))?")
_BAR = re.compile(r"(\|\]|\[\||\|\||:\||\|:|::|\||\[[0-9]|\|[0-9])")


def parse_abc(abc: str, key: Optional[str] = None, meter: Optional[str] = None,
              unit_length: Optional[str] = None) -> List[Optional[Note]]:
    """Parse an ABC body (header lines allowed) into notes and rests.

    `key`/`meter`/`unit_length` are defaults from outside the text (the dump's
    `mode`/`meter` columns); `K:`, `M:` and `L:` inside the text override them.
    """
    sig = key_signature(key) if key else {}
    unit = Fraction(1, 8)
    if unit_length:
        m = re.match(r"^\s*(\d+)\s*/\s*(\d+)", unit_length)
        if m:
            unit = Fraction(int(m.group(1)), int(m.group(2)))
    elif meter:
        unit = _unit_length_from_meter(meter)
    saw_L = bool(unit_length)

    out: List[Optional[Note]] = []
    bar_accidentals = {}  # (letter, octave) -> semitone offset

    for raw_line in (abc or "").replace("\r", "").split("\n"):
        line = raw_line.split("%", 1)[0]
        if not line.strip():
            continue
        h = _HEADER_LINE.match(line)
        if h and not _looks_like_notes(line):
            field, value = h.group(1), h.group(2).strip()
            if field == "K":
                sig = key_signature(value)
                bar_accidentals = {}
            elif field == "L":
                m = re.match(r"^(\d+)\s*/\s*(\d+)", value)
                if m:
                    unit = Fraction(int(m.group(1)), int(m.group(2)))
                    saw_L = True
            elif field == "M" and not saw_L:
                unit = _unit_length_from_meter(value)
            continue  # every other header line (T:, R:, w:, ...) is ignored

        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if c in " \t\\$&":
                i += 1
                continue
            if c == "[":
                f = _INLINE_FIELD.match(line, i)
                if f:
                    if f.group(1) == "K":
                        sig = key_signature(f.group(2))
                        bar_accidentals = {}
                    elif f.group(1) == "L":
                        m = re.match(r"^\s*(\d+)\s*/\s*(\d+)", f.group(2))
                        if m:
                            unit = Fraction(int(m.group(1)), int(m.group(2)))
                            saw_L = True
                    i = f.end()
                    continue
                b = _BAR.match(line, i)
                if b:
                    bar_accidentals = {}
                    i = b.end()
                    continue
                # a chord: take its first note, skip to the closing bracket
                close = line.find("]", i)
                if close == -1:
                    close = n
                inner = line[i + 1:close]
                nm = _NOTE.search(inner)
                if nm:
                    # chord duration may follow the bracket; ignore, use the note's
                    out.append(_make_note(nm, sig, bar_accidentals, unit))
                i = close + 1
                continue
            b = _BAR.match(line, i)
            if b:
                bar_accidentals = {}
                i = b.end()
                continue
            if c == "!" or c == "+":
                # decoration !trill! / +trill+ ; a lone '!' (old line break) is skipped
                close = line.find(c, i + 1)
                i = close + 1 if close != -1 and close - i <= 20 else i + 1
                continue
            if c == "{":
                close = line.find("}", i)
                i = close + 1 if close != -1 else n
                continue
            if c == '"':
                close = line.find('"', i + 1)
                i = close + 1 if close != -1 else n
                continue
            if c == "(":
                t = _TUPLET.match(line, i)
                i = t.end() if t else i + 1
                continue
            if c in ")-<>~.":
                i += 1
                continue
            r = _REST.match(line, i)
            if r:
                out.append(None)
                i = r.end()
                continue
            nm = _NOTE.match(line, i)
            if nm:
                out.append(_make_note(nm, sig, bar_accidentals, unit))
                i = nm.end()
                continue
            # anything else: a decoration letter (H, L, M, O, P, S, T, u, v),
            # a stray digit, punctuation — skip it
            i += 1
    return out


def _looks_like_notes(line: str) -> bool:
    """Guard against a body line like 'A:|' being taken for a header.

    Header fields are a single letter, a colon, then free text; a real one
    never has a note letter immediately followed by a bar line or a repeat.
    """
    return bool(re.match(r"^\s*[A-Ga-g]:\|", line))


def _make_note(m, sig, bar_accidentals, unit) -> Note:
    acc, letter, octave_marks, length = m.group(1), m.group(2), m.group(3), m.group(4)
    upper = letter.upper()
    octave = 5 if letter.islower() else 4
    octave += octave_marks.count("'") - octave_marks.count(",")
    if acc:
        offset = {"^": 1, "^^": 2, "_": -1, "__": -2, "=": 0}[acc]
        bar_accidentals[(upper, octave)] = offset
    elif (upper, octave) in bar_accidentals:
        offset = bar_accidentals[(upper, octave)]
    else:
        offset = sig.get(upper, 0)
    midi = 12 * (octave + 1) + _LETTER_SEMITONE[upper] + offset
    eighths = _parse_length(length) * unit * 8
    return Note(midi=midi, eighths=eighths)


def particalized_pitches(notes, max_eighths: int = 8) -> List[Optional[int]]:
    """Notes -> one entry per eighth note, repeating a held pitch.

    The same reduction `analysis.notation.particalize` performs on a
    transcription, so that the two can be compared without either side having
    to guess at articulation. A quarter note and two tongued eighths of the
    same pitch are one entry and two entries in the notation, and are
    indistinguishable in a pitch track; here they are two entries in both.

    Rests stay as None so an n-gram never spans one, as everywhere else.
    """
    out: List[Optional[int]] = []
    for n in notes:
        if n is None:
            out.append(None)
            continue
        count = int(round(float(n.eighths))) or 1
        out.extend([n.midi] * min(count, max_eighths))
    return out


def pitch_sequence(notes) -> List[Optional[int]]:
    return [n.midi if n is not None else None for n in notes]


def fold_interval(d: int) -> int:
    """An interval reduced to its nearest-direction form in [-6, 5].

    Octave errors then cost nothing: a step of +1 and a step of +13 become the
    same thing. That matters because a transcription of a room recovers the
    note names well and the octave badly - measured on a real segment, 41% of
    one tracker's steps were octave-sized while its pitch classes matched the
    notation exactly.

    The price is discrimination: twelve possible values instead of
    twenty-five, so n-grams collide more often. Which way that trades is an
    empirical question, and both forms are built so it can be answered.
    """
    return ((int(d) + 6) % 12) - 6


def interval_sequence(pitches, clip=12, fold=False) -> List[Optional[int]]:
    """Semitone steps between consecutive pitches; None where a rest intervenes.

    Clipped to ±clip so an octave error in a transcription (or a real octave
    leap) stays comparable rather than producing a wild value. With `fold`,
    reduced further so an octave error cannot matter at all.
    """
    out = []
    prev = None
    for p in pitches:
        if p is None:
            prev = None
            out.append(None)
            continue
        if prev is not None:
            d = p - prev
            out.append(fold_interval(d) if fold else max(-clip, min(clip, d)))
        prev = p
    return out


def ngrams(intervals, n=5):
    """Every run of n consecutive non-None intervals, as tuples."""
    out = []
    run = []
    for v in intervals:
        if v is None:
            run = []
            continue
        run.append(v)
        if len(run) >= n:
            out.append(tuple(run[-n:]))
    return out


def to_abc_letters(pitches) -> str:
    """MIDI -> ABC note names, for printing transcriptions a player can read."""
    names = ["C", "^C", "D", "^D", "E", "F", "^F", "G", "^G", "A", "^A", "B"]
    parts = []
    for p in pitches:
        if p is None:
            parts.append("z")
            continue
        octave, semi = divmod(int(p), 12)
        octave -= 1
        name = names[semi]
        acc, letter = (name[0], name[1]) if len(name) == 2 else ("", name)
        if octave >= 5:
            letter = letter.lower() + "'" * (octave - 5)
        else:
            letter = letter + "," * (4 - octave)
        parts.append(acc + letter)
    return " ".join(parts)
