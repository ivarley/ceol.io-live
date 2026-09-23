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


def truth_period_ms(pulse):
    """The eighth note, taken from the beats themselves.

    The drawn beats are the fact; the stored period is an inference from them
    and the meter, and it goes stale the moment the meter is changed without
    re-saving. That happened on the first segment anyone drew, so it is
    derived here instead of trusted.
    """
    beats = sorted(pulse.get("beats") or [])
    grouping = int(pulse.get("grouping") or 2)
    if len(beats) >= 2:
        gaps = np.diff(np.asarray(beats))
        return float(np.median(gaps)) * 1000.0 / grouping
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
    i = np.arange(beats.size)
    a = np.vstack([i, np.ones(i.size)]).T
    (slope, intercept), residuals, *_ = np.linalg.lstsq(a, beats, rcond=None)
    rms = float(np.sqrt(residuals[0] / beats.size)) * 1000.0 if residuals.size else None
    return float(intercept) * 1000.0, rms


def truth_bar_phase_ms(pulse):
    """When a bar starts, from the beats marked as bar starts. None if none are.

    A marked bar line is the only statement about bar phase anywhere in the
    lab. The estimator infers one by fitting a train at the bar period, which
    is plausible and has never been checked, because until a person marks one
    there is nothing to check it against.
    """
    downs = sorted(pulse.get("downbeats") or [])
    return (float(downs[0]) * 1000.0) if downs else None


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
    phase_err = None
    truth_phase, drawn_rms = truth_phase_ms(truth)
    if abs(ratio - 1.0) <= 0.08:
        period = truth["period_ms"]
        diff = (got["phase_ms"] - truth_phase) % period
        phase_err = min(diff, period - diff)
    # Bar phase, in beats rather than milliseconds: being a whole beat out is a
    # different mistake from being a little early, and only the first is audible
    # as the wrong note starting the bar.
    bar_err_beats = None
    truth_bar = truth_bar_phase_ms(truth)
    if truth_bar is not None and abs(ratio - 1.0) <= 0.08:
        beat = truth["period_ms"] * int(truth.get("grouping") or 2)
        bar = beat * (4 if int(truth.get("grouping") or 2) == 2 else 2)
        diff = (got.get("bar_phase_ms", got["phase_ms"]) - truth_bar) % bar
        bar_err_beats = min(diff, bar - diff) / max(1e-6, beat)
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
        "grouping_right": int(got["grouping"]) == int(truth["grouping"]),
        "phase_error_ms": phase_err,
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
        lines.append(f"  phase error when the period is right  {p['median_phase_error_ms']:.0f}ms")
    if p.get("n_with_bars_marked"):
        lines.append(f"  bar lines marked on {p['n_with_bars_marked']} segment(s)")
        if p.get("median_bar_error_beats") is not None:
            lines.append(f"  bar start off by (median)  {p['median_bar_error_beats']:.2f} beats")
            lines.append(f"  bar start within half a beat  {p['bar_phase_right']:.3f}")
    else:
        lines.append("  bar lines: none marked, so nothing here checks the downbeat")
    if p["verdicts"]:
        where = ", ".join(f"{k} x{v}" for k, v
                          in sorted(p["verdicts"].items(), key=lambda kv: -kv[1]))
        lines.append(f"  where it lands: {where}")
    return "\n".join(lines)
