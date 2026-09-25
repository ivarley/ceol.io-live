"""`lab bench pulse` — score the grid estimator against hand-drawn beats.

The estimator was landing about half again too fast and nothing in the lab
could say so, because there was no ground truth for tempo. Drawing the
quarter notes where they actually fall produces one, and the first segment
anyone drew overturned the estimator's central assumption: on a jig whose
eighth note is 159ms, the onset envelope correlates 0.011 at 159ms and 0.455
at the 478ms beat. The eighth was not weak, it was absent.

The scoring is deliberately about ratios rather than differences. A grid at
twice or half the true spacing is not "a bit wrong", it is a different answer
that happens to line up, and it is the mistake this estimator actually makes,
so the report names which multiple it landed on.

Phase is reported but should be read with the scatter beside it. A beat drawn
by hand lands about 30ms from the line a least-squares fit puts through all of
them, so a phase error of that order is not distinguishable from the ground
truth's own noise, and there is one drawn segment to go on.
"""

import json
import time

import numpy as np

from lab import paths
from lab.analysis.pulse import estimate_pulse
from lab.audio.chunks import AudioStore
from lab.bench.score import BenchResult, NightResult, git_sha
from lab.tools.viewer import ANNOTATIONS

# the ratios worth naming: the ones a period estimator lands on by accident
RATIOS = ((1.0, "right"), (2.0, "twice too slow"), (0.5, "twice too fast"),
          (3.0, "three times too slow"), (1 / 3, "three times too fast"),
          (1.5, "half again too slow"), (2 / 3, "half again too fast"),
          (4.0, "four times too slow"), (0.25, "four times too fast"))


def name_ratio(ratio, tolerance=0.08):
    for value, label in RATIOS:
        if abs(ratio / value - 1.0) <= tolerance:
            return label
    return "unrelated"


def load_drawn():
    import os

    out = []
    if not os.path.isdir(ANNOTATIONS):
        return out
    for name in sorted(os.listdir(ANNOTATIONS)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(ANNOTATIONS, name)) as f:
            record = json.load(f)
        if record.get("pulse") and record["pulse"].get("period_ms"):
            out.append(record)
    return out


def eighths_per_beat(pulse):
    """How many eighth notes are inside one drawn beat.

    NOT the meter, which is the mistake this field used to encode. A reel
    counted in two has four eighths to a beat and counted in four has two, and
    it is the same reel; a jig has three, or six if counted in two. Castle
    Kelly was drawn at the half note and read as the quarter, and every number
    derived from it came out twice too slow.
    """
    return int(pulse.get("grouping") or 2)


def truth_meter(pulse):
    """2 or 3: how the beat divides, which is what the estimator reports."""
    return 3 if eighths_per_beat(pulse) in (3, 6) else 2


def eighths_per_bar(pulse):
    return 6 if truth_meter(pulse) == 3 else 8


def drawn_beat_ms(pulse):
    """The spacing of the drawn beats, ignoring the gaps between runs.

    Beats are drawn in patches -- a few bars here, a few bars there -- so the
    median over every consecutive pair includes the silences between patches.
    On Castle Kelly that was a 599ms median with a 1432ms spread over what are
    really two steady runs at 593 and 584ms.
    """
    beats = np.asarray(sorted(pulse.get("beats") or []), dtype=float)
    if beats.size < 2:
        return 0.0
    gaps = np.diff(beats)
    within = gaps[gaps < 2.5 * np.median(gaps)]
    return float(np.median(within if within.size else gaps)) * 1000.0


def truth_period_ms(pulse):
    """The eighth note, taken from the beats themselves.

    The drawn beats are the fact; the stored period is an inference from them
    and the level they were drawn at, and it goes stale the moment that is
    changed without re-saving. That happened on the first segment anyone drew,
    so it is derived here instead of trusted.
    """
    beat = drawn_beat_ms(pulse)
    if beat:
        return beat / max(1, eighths_per_beat(pulse))
    return float(pulse.get("period_ms") or 0.0)


def truth_phase_ms(pulse):
    """Where the beats start, fitted rather than read off the first one.

    The stored phase is whichever beat happened to be drawn first, and a hand
    drawn beat scatters about 30ms. A least-squares line through all of them
    is the same quantity measured eighty times, which is the only reason it is
    worth comparing an estimate against at all.
    """
    beats = np.asarray(sorted(pulse.get("beats") or []), dtype=float)
    if beats.size < 3:
        return float(pulse.get("phase_ms") or 0.0), None
    # Index by ELAPSED beats, not by position in the list. Beats are drawn in
    # patches, and counting the list straight through treats a nine-second gap
    # as one beat: on Castle Kelly that fitted a phase of -4668ms, which is
    # before the segment starts, and every phase number derived from it was
    # meaningless.
    spacing = drawn_beat_ms(pulse) / 1000.0
    if spacing <= 0:
        return float(beats[0]) * 1000.0, None
    n = np.round((beats - beats[0]) / spacing)
    a = np.vstack([n, np.ones(n.size)]).T
    (_slope, intercept), residuals, *_ = np.linalg.lstsq(a, beats, rcond=None)
    rms = float(np.sqrt(residuals[0] / beats.size)) * 1000.0 if residuals.size else None
    return float(intercept) * 1000.0, rms


def truth_bar_phase_ms(pulse):
    """When a bar starts, fitted across every mark. None if there are none.

    A marked bar line is the only statement about bar phase anywhere in the
    lab, and taking the first mark alone wastes the other eighteen. Marks are
    not placed every bar -- the gaps on Castle Kelly run 2, 2, 2, 8, 2, 2, 2,
    8, 4, 4, 2, 6 bars -- so each one is first snapped to the nearest whole
    number of bars from the first, and a line is fitted through the lot. That
    turns 61ms of drawing scatter into an estimate worth comparing against.
    """
    downs = np.asarray(sorted(pulse.get("downbeats") or []), dtype=float)
    if downs.size == 0:
        return None
    if downs.size < 3:
        return float(downs[0]) * 1000.0
    bar_s = truth_period_ms(pulse) / 1000.0 * eighths_per_bar(pulse)
    if bar_s <= 0:
        return float(downs[0]) * 1000.0
    n = np.round((downs - downs[0]) / bar_s)
    a = np.vstack([n, np.ones(n.size)]).T
    (_slope, intercept), *_ = np.linalg.lstsq(a, downs, rcond=None)
    return float(intercept) * 1000.0


def score_record(record, seconds=60.0):
    truth = dict(record["pulse"])
    truth["period_ms"] = truth_period_ms(truth) or truth.get("period_ms")
    t0 = int(record.get("t0_ms") or 0)
    store = AudioStore(paths.wav_path(record["recording_id"]))
    store.clock_ms = store.duration_ms
    got = estimate_pulse(store.read(t0, t0 + int(seconds * 1000)), store.sr)
    store.close()
    if got is None:
        return {"tune": record.get("tune_name"), "found": False}
    ratio = got["period_ms"] / max(1e-6, truth["period_ms"])
    # phase only means anything once the period is right
    # Wrapped at the BEAT, not the eighth. Wrapping at the eighth could only
    # ever report half an eighth of error, so a grid sitting on the offbeat --
    # which is what it does on a reel -- came back as a small number. The
    # figure that means something is the fraction of a beat, where 0.5 is as
    # wrong as it is possible to be.
    phase_err = None
    phase_err_beats = None
    truth_phase, drawn_rms = truth_phase_ms(truth)
    if abs(ratio - 1.0) <= 0.08:
        beat = got.get("beat_ms") or truth["period_ms"]
        diff = (got["phase_ms"] - truth_phase) % beat
        phase_err = min(diff, beat - diff)
        phase_err_beats = phase_err / max(1e-6, beat)
    # Bar phase, in beats rather than milliseconds: being a whole beat out is a
    # different mistake from being a little early, and only the first is audible
    # as the wrong note starting the bar.
    bar_err_beats = None
    truth_bar = truth_bar_phase_ms(truth)
    if truth_bar is not None and abs(ratio - 1.0) <= 0.08:
        # In WRITTEN bars, not in whatever span the marks were placed at: a
        # mark every second bar is still a statement about where a bar starts,
        # and the modulo takes care of the rest.
        bar = truth["period_ms"] * eighths_per_bar(truth)
        diff = (got.get("bar_phase_ms", got["phase_ms"]) - truth_bar) % bar
        bar_err_beats = min(diff, bar - diff) / max(1e-6, truth["period_ms"])
    return {
        "tune": record.get("tune_name"),
        "recording_id": record["recording_id"],
        "found": True,
        "bar_error_beats": bar_err_beats,
        "bars_marked": len(truth.get("downbeats") or []),
        "truth_period_ms": truth["period_ms"],
        "got_period_ms": got["period_ms"],
        "ratio": ratio,
        "verdict": name_ratio(ratio),
        "period_right": abs(ratio - 1.0) <= 0.08,
        "grouping_right": int(got["grouping"]) == truth_meter(truth),
        "phase_error_ms": phase_err,
        "phase_error_beats": phase_err_beats,
        "drawn_scatter_ms": drawn_rms,
        "f1": float(abs(ratio - 1.0) <= 0.08),
    }


def run_pulse(seconds=60.0, quiet=False):
    records = load_drawn()
    if not records:
        raise SystemExit(
            "no beats drawn yet. Open a segment with `lab view --recording N --segment K`, "
            "switch to draw beats, click where the quarter notes fall, and save.")
    rows = [score_record(r, seconds=seconds) for r in records]
    scored = [r for r in rows if r.get("found")]
    if not quiet:
        for r in scored:
            phase = "" if r["phase_error_ms"] is None else f", phase off {r['phase_error_ms']:.0f}ms"
            print(f"  {str(r['tune'])[:30]:<30} drawn {r['truth_period_ms']:>5.0f}ms  "
                  f"got {r['got_period_ms']:>5.0f}ms  ({r['verdict']}{phase})")
    pooled = {
        "n": len(scored),
        "period_right": float(np.mean([r["period_right"] for r in scored])) if scored else 0.0,
        "grouping_right": float(np.mean([r["grouping_right"] for r in scored])) if scored else 0.0,
        "median_ratio": float(np.median([r["ratio"] for r in scored])) if scored else 0.0,
        "f1": float(np.mean([r["f1"] for r in scored])) if scored else 0.0,
    }
    errs = [r["phase_error_ms"] for r in scored if r["phase_error_ms"] is not None]
    pooled["median_phase_error_ms"] = float(np.median(errs)) if errs else None
    pb = [r["phase_error_beats"] for r in scored if r.get("phase_error_beats") is not None]
    pooled["median_phase_error_beats"] = float(np.median(pb)) if pb else None
    bar = [r["bar_error_beats"] for r in scored if r.get("bar_error_beats") is not None]
    pooled["n_with_bars_marked"] = sum(1 for r in scored if r.get("bars_marked"))
    pooled["median_bar_error_beats"] = float(np.median(bar)) if bar else None
    pooled["bar_phase_right"] = float(np.mean([b < 0.5 for b in bar])) if bar else None
    verdicts = {}
    for r in scored:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    pooled["verdicts"] = verdicts
    return BenchResult(
        task="pulse", candidate="beat_first", version="1",
        params={"seconds": seconds}, features_version="audio", split="per-drawn-segment",
        nights=[NightResult(recording_id=r.get("recording_id", 0), label=str(r["tune"]), date="",
                            metrics=r, n_frames=1) for r in scored],
        pooled=pooled, warnings=[], created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        git_sha=git_sha())


def format_pulse(result):
    p = result.pooled
    lines = [f"{result.candidate} on pulse  [{p['n']} segments with beats drawn]",
             f"  period right (within 8%)  {p['period_right']:.3f}",
             f"  grouping right            {p['grouping_right']:.3f}",
             f"  median estimate / drawn   {p['median_ratio']:.3f}"]
    if p.get("median_phase_error_ms") is not None:
        lines.append(f"  beat phase off by (median)  {p['median_phase_error_ms']:.0f}ms"
                     f" = {p['median_phase_error_beats']:.2f} of a beat (0.5 is the worst possible)")
    if p.get("n_with_bars_marked"):
        lines.append(f"  bar lines marked on {p['n_with_bars_marked']} segment(s)")
        if p.get("median_bar_error_beats") is not None:
            lines.append(f"  bar start off by (median)  {p['median_bar_error_beats']:.2f} eighths")
            lines.append(f"  bar start within half an eighth  {p['bar_phase_right']:.3f}")
    else:
        lines.append("  bar lines: none marked, so nothing here checks the downbeat")
    if p["verdicts"]:
        where = ", ".join(f"{k} x{v}" for k, v
                          in sorted(p["verdicts"].items(), key=lambda kv: -kv[1]))
        lines.append(f"  where it lands: {where}")
    return "\n".join(lines)
