"""A setting's played form: its repeats written out, on a grid of eighth notes.

The parser (corpus/abc_pitch) reads a setting once through as written, so a
tune written `|: A :|: B :|` is A then B. A session plays it A A B B, and
round again. To say how far into a tune some heard notes are, in eighth notes
counted from where the tune began, the setting has to be read as played:

- `|: ... :|` repeats the section, back to the last `|:` or, failing one, to
  the start of the tune or the last double bar;
- first and second endings (`|1`, `[1`, `:|2` ...) take the first ending on
  the first time through and the second on the repeat. A second ending lasts
  to the next double bar, repeat or section start, and no longer than the
  first ending did;
- `::` is the end of one repeated section and the start of the next.

Bar lines are kept, so every bar's first eighth is known, and so is every
section's: the places a tune can be started from, and the lengths a walk back
through it steps by.
"""

import re
from dataclasses import dataclass, field
from typing import List

import numpy as np

from lab.corpus import abc_pitch

_HEADER = re.compile(r"^\s*[A-Za-z]:")
# after normalising: an optional ':' each side of one or two bars, then an ending number
_BARLINE = re.compile(r"(:?)(\|\|?)(:?)([12])?")


@dataclass
class Bar:
    text: str
    start_rep: bool = False      # `|:` before it
    end_rep: bool = False        # `:|` after it
    hard_end: bool = False       # `||` or `|]` after it
    ending: int = 0              # 1 or 2: in a first or second ending


@dataclass
class Form:
    eighths: np.ndarray                      # pitch classes, -1 for nothing, played order
    bar_starts: List[int] = field(default_factory=list)       # eighth index of each bar
    section_starts: List[int] = field(default_factory=list)   # each time a section begins
    bars: List[int] = field(default_factory=list)             # the written bar each played bar is

    @property
    def length(self):
        return len(self.eighths)


def _normalise(body):
    body = body.replace("::", ":||:").replace("[|", "||").replace("|]", "||")
    body = re.sub(r"\|?\s*\[([12])(?![0-9])", r"|\1", body)     # [1 and |[1 -> |1
    return body


def split_bars(abc):
    """(header lines, [Bar]) of an ABC text."""
    head, lines = [], []
    for line in (abc or "").replace("\r", "").split("\n"):
        if _HEADER.match(line) and not abc_pitch._looks_like_notes(line):
            head.append(line.strip())
        else:
            lines.append(line)
    body = _normalise(" ".join(lines))
    bars, pending, pos = [], {}, 0
    for m in _BARLINE.finditer(body):
        text = body[pos:m.start()]
        pos = m.end()
        left, double, right, ending = m.group(1), m.group(2), m.group(3), m.group(4)
        if text.strip():
            bars.append(Bar(text=text, **pending))
            pending = {}
        elif bars and not pending:
            pass
        if bars and (left or double == "||"):
            if left:
                bars[-1].end_rep = True
            if double == "||":
                bars[-1].hard_end = True
        if right:
            pending["start_rep"] = True
        if ending:
            pending["ending"] = int(ending)
    tail = body[pos:]
    if tail.strip():
        bars.append(Bar(text=tail, **pending))
    _spread_endings(bars)
    return head, bars


def _spread_endings(bars):
    """An ending marker starts on one bar; carry it over the bars it covers."""
    first_len = 0
    i = 0
    while i < len(bars):
        b = bars[i]
        if b.ending == 1:
            j = i
            while j < len(bars) and not bars[j].end_rep:
                bars[j].ending = 1
                j += 1
            if j < len(bars):
                bars[j].ending = 1
            first_len = j - i + 1
            i = j + 1
            continue
        if b.ending == 2:
            j, n = i, 1
            while (j + 1 < len(bars) and n < max(first_len, 1) and not bars[j].hard_end
                   and not bars[j].end_rep and not bars[j + 1].start_rep and not bars[j + 1].ending):
                j += 1
                n += 1
                bars[j].ending = 2
            i = j + 1
            continue
        i += 1


def expand(bars):
    """Written bars -> played order (indices into `bars`), and where each
    section's pass begins (indices into the played order)."""
    out, starts = [], [0]
    sec, i, second = 0, 0, False
    while i < len(bars):
        b = bars[i]
        if b.start_rep and not second and i != sec:
            sec = i
            if out and starts[-1] != len(out):
                starts.append(len(out))
        if (b.ending == 1 and second) or (b.ending == 2 and not second):
            i += 1
            continue
        out.append(i)
        if b.end_rep and not second and b.ending != 2:
            second = True
            starts.append(len(out))
            i = sec
            continue
        nxt = bars[i + 1] if i + 1 < len(bars) else None
        if second and ((b.end_rep and b.ending != 1) or (b.ending == 2 and (nxt is None or nxt.ending != 2))
                       or (b.ending == 0 and b.end_rep)):
            second = False
            sec = i + 1
            if nxt is not None:
                starts.append(len(out))
        elif not second and b.hard_end:
            sec = i + 1
            if nxt is not None:
                starts.append(len(out))
        i += 1
    return out, sorted(set(starts))


def played_form(abc, key=None, meter=None):
    head, bars = split_bars(abc)
    order, sec_bars = expand(bars)
    prefix = "\n".join(h for h in head if h[:2] in ("K:", "L:"))
    lengths = []
    for idx in order:
        notes = abc_pitch.parse_abc(prefix + "\n" + bars[idx].text, key=key, meter=meter)
        lengths.append(sum((n.eighths if n is not None and n.eighths else 1) for n in notes))
    text = prefix + "\n" + " | ".join(bars[idx].text for idx in order)
    notes = abc_pitch.parse_abc(text, key=key, meter=meter)
    pcs = abc_pitch.particalized_pitches(notes)
    eighths = np.array([-1 if p is None else int(p) % 12 for p in pcs], dtype=np.int8)
    bar_starts, pos = [], 0
    for n in lengths:
        bar_starts.append(int(round(float(pos))))
        pos += n
    section_starts = [bar_starts[b] for b in sec_bars if b < len(bar_starts)]
    return Form(eighths=eighths, bar_starts=bar_starts, section_starts=section_starts, bars=order)


def played_forms(tune_ids, min_eighths=32):
    """{tune_id: [(setting_id, mode, Form)]} for every readable setting of these
    tunes in the thesession.org dump. A setting too short to be a tune (under
    `min_eighths`) or with no bar lines is left out."""
    from lab import paths
    from lab.corpus.tunes_csv import iter_settings

    out = {}
    for s in iter_settings(paths.tunes_csv_path(), tune_ids=set(tune_ids)):
        try:
            f = played_form(s.abc, key=s.mode, meter=s.meter)
        except Exception:  # one unreadable setting must not lose the tune
            continue
        if f.length >= min_eighths and f.bar_starts:
            out.setdefault(s.tune_id, []).append((s.setting_id, s.mode, f))
    return out
