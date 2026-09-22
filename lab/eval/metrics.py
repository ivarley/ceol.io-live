"""Scoring a run against the corpus: identification and segmentation.

The metrics are chosen to be what a player at the table would notice, not
what is convenient to compute:

- **time to first correct** — how long after the tune started before the right
  name was on top, even briefly;
- **time to stable correct** — how long before it settled there and stayed,
  which is the one that matters if you are reading the screen;
- **top-1 and top-5 at the end** — did it get there at all;
- **flips** — how often a provisional answer changed under the reader, which
  is the thing that makes a good system feel untrustworthy;
- **calibration** — is 90% confidence right 90% of the time, because the
  scheduler stops paying for evidence on the strength of a confidence, and a
  confident wrong answer is the failure mode that would make this feel broken;
- **cost per audio minute** — the other axis of every trade here.

Proportions carry Wilson intervals. With 455 segments over eight nights, two
points of difference between runs is noise, and a number without an interval
invites reading it as signal.
"""

import json
from collections import defaultdict

from lab.bench.score import match_events, wilson
from lab.bench.tasks import load_ground_truth


def _answer_at(events, spans, t_ms):
    """What a reader would have on screen at this moment.

    The lifecycle replayed forward: an event sets the answer, a withdrawal
    clears it, and whatever survives is what was showing. An earlier version
    also required the hypothesis's SPAN to cover `t_ms`, which was wrong in a
    way that quietly scored correct answers as misses: a span is a range of
    audio, an event carries a clock time, and a span closed at the moment
    silence began is stamped earlier than the events that followed it.
    """
    current = None
    for e in events:
        if e["clock_ms"] > t_ms:
            break
        if e["event"] == "withdrawn":
            current = None
        else:
            current = e
    return current


def _final_answer(events, spans, seg_start, seg_end):
    """The last thing ever said about the span covering this segment.

    A hypothesis can be superseded long after its tune has finished, when the
    tunes either side of it make a different reading better. That is a claim
    withdrawn in favour of a better one, and it is what the reader ends up
    with, so it deserves its own number.
    """
    best_hyp, best_overlap = None, 0
    for hyp_id, h in spans.items():
        start = h["t_start_ms"]
        end = h["t_end_ms"] if h["t_end_ms"] is not None else seg_end
        overlap = min(end, seg_end) - max(start, seg_start)
        if overlap > best_overlap:
            best_hyp, best_overlap = hyp_id, overlap
    if best_hyp is None:
        return None
    for e in reversed(events):
        if e["hyp_id"] == best_hyp and e["event"] != "withdrawn":
            return e
    return None


def score_identification(board, run_id, gt, replay_range=None):
    """Per-segment identification results for one run.

    Reports what the system was claiming when the tune ended. There was
    briefly a second number here for what it *finally* settled on, added to
    make retroactive revision comparable with the bench, which decodes a whole
    set once it has been heard. It came out because it could not be defined
    cleanly: the assembler withdraws a span when a tune stops, so there is
    often no final claim to report, and a span that runs on into the next tune
    makes its later events about something else. Revision is off for separate
    and measured reasons; see the assembler.
    """
    events = board.hypothesis_events(run_id)
    spans = {h["hyp_id"]: h for h in board.hypotheses(run_id)}
    costs_by_window = [
        (o.t_start_ms, o.cost_ms) for o in board.observations(run_id) if o.cost_ms
    ]

    rows = []
    for seg in gt.eval_segments(range_ms=replay_range):
        detail = {"skip_reason": seg.skip_reason}
        if not seg.evaluated:
            rows.append((seg, None, detail))
            continue
        s, e = seg.start_ms, seg.end_ms
        inside = [ev for ev in events if s <= ev["clock_ms"] < e
                  and ev["hyp_id"] in spans
                  and spans[ev["hyp_id"]]["t_start_ms"] <= e
                  and (spans[ev["hyp_id"]]["t_end_ms"] is None
                       or spans[ev["hyp_id"]]["t_end_ms"] >= s)]
        tops = [ev["top1_tune_id"] for ev in inside]

        ttfc = next((ev["clock_ms"] - s for ev in inside if ev["top1_tune_id"] == seg.tune_id), None)

        ttsc = None
        for i, ev in enumerate(inside):
            if all(x["top1_tune_id"] == seg.tune_id for x in inside[i:]) and inside[i:]:
                ttsc = ev["clock_ms"] - s
                break

        final = _answer_at(events, spans, e - 1)
        top1_end = int(bool(final and final["top1_tune_id"] == seg.tune_id))
        top5 = [c["tune_id"] for c in (final["ranked"][:5] if final else [])]
        top5_end = int(seg.tune_id in top5)
        end_conf = final["top1_conf"] if final else None
        if final is not None and ttsc is not None and top1_end == 0:
            ttsc = None

        # What it settled on in the end, after any later revision. The
        # during-the-tune answer and the final answer are different questions
        # and the bench only ever answered the second: it decodes a whole set
        # once the set has been heard. Reporting both stops the two being
        # compared as though they were one number.
        final_answer = _final_answer(events, spans, s, e)
        top1_final = int(bool(final_answer and final_answer["top1_tune_id"] == seg.tune_id))
        top5_final = int(seg.tune_id in
                         [c["tune_id"] for c in (final_answer["ranked"][:5] if final_answer else [])])

        flips = sum(1 for a, b in zip(tops, tops[1:]) if a != b)
        cost = sum(c for t, c in costs_by_window if s <= t < e)

        detail.update({
            "events": len(inside),
            "final_tune_id": final["top1_tune_id"] if final else None,
            "final_name": (final["ranked"][0]["name"] if final and final["ranked"] else None),
            "top5": top5,
        })
        rows.append((seg, {
            "ttfc_ms": ttfc, "ttsc_ms": ttsc, "top1_end": top1_end, "top5_end": top5_end,
            "top1_final": top1_final, "top5_final": top5_final,
            "flips": flips, "end_conf": end_conf, "cost_ms": cost,
        }, detail))
    return rows


def aggregate_identification(rows):
    scored = [(seg, m) for seg, m, _ in rows if m is not None]
    n = len(scored)
    skipped = defaultdict(int)
    for seg, m, _ in rows:
        if m is None:
            skipped[seg.skip_reason or "unknown"] += 1
    if n == 0:
        return {"n_evaluated": 0, "skipped": dict(skipped)}

    top1 = sum(m["top1_end"] for _, m in scored)
    top5 = sum(m["top5_end"] for _, m in scored)
    top1f = sum(m.get("top1_final", 0) for _, m in scored)
    top5f = sum(m.get("top5_final", 0) for _, m in scored)
    found30 = sum(1 for _, m in scored if m["ttfc_ms"] is not None and m["ttfc_ms"] <= 30000)
    found60 = sum(1 for _, m in scored if m["ttfc_ms"] is not None and m["ttfc_ms"] <= 60000)
    never = sum(1 for _, m in scored if m["ttfc_ms"] is None)
    ttfc = sorted(m["ttfc_ms"] for _, m in scored if m["ttfc_ms"] is not None)
    ttsc = sorted(m["ttsc_ms"] for _, m in scored if m["ttsc_ms"] is not None)
    flips = [m["flips"] for _, m in scored]

    def pct(k):
        p, lo, hi = wilson(k, n)
        return {"value": p, "lo": lo, "hi": hi, "k": k, "n": n}

    return {
        "n_evaluated": n,
        "n_capped": sum(1 for seg, _ in scored if seg.capped),
        "skipped": dict(skipped),
        "top1": pct(top1),
        "top5": pct(top5),
        "top1_final": pct(top1f),
        "top5_final": pct(top5f),
        "found_within_30s": pct(found30),
        "found_within_60s": pct(found60),
        "never_found": never,
        "ttfc_median_ms": _median(ttfc),
        "ttfc_iqr_ms": _iqr(ttfc),
        "ttsc_median_ms": _median(ttsc),
        "ttsc_n": len(ttsc),
        "flips_mean": sum(flips) / n,
        "flips_max": max(flips) if flips else 0,
        "calibration": calibration([(m["end_conf"], m["top1_end"]) for _, m in scored]),
    }


def calibration(pairs, bins=10):
    """Confidence against correctness, plus expected calibration error."""
    out = []
    ece = 0.0
    total = sum(1 for c, _ in pairs if c is not None)
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        sel = [(c, ok) for c, ok in pairs
               if c is not None and (lo <= c < hi or (i == bins - 1 and c == 1.0))]
        if not sel:
            continue
        acc = sum(ok for _, ok in sel) / len(sel)
        conf = sum(c for c, _ in sel) / len(sel)
        out.append({"bin": [round(lo, 2), round(hi, 2)], "n": len(sel),
                    "accuracy": acc, "mean_conf": conf})
        if total:
            ece += (len(sel) / total) * abs(acc - conf)
    return {"bins": out, "ece": ece, "n": total}


def score_segmentation(board, run_id, gt, replay_range=None, tolerances=(1000, 3000, 5000)):
    """Boundary detection, tune identity ignored.

    Two sources are scored separately: the `boundary` observations themselves,
    and where the assembler actually opened and closed spans. They are not the
    same thing, and the difference is the assembler's own contribution.
    """
    covered = gt.covered_intervals()
    if replay_range:
        r0, r1 = replay_range
        covered = [(max(a, r0), min(b, r1)) for a, b in covered if b > r0 and a < r1]
    truth = [b["t_ms"] for b in gt.boundaries() if gt.within(b["t_ms"], covered)]

    sources = {
        "boundary_observations": [
            (o.payload.get("t_ms"), o.clock_ms) for o in board.observations(run_id, types=["boundary"])
            if o.payload.get("t_ms") is not None],
        "hypothesis_spans": [
            (h["t_start_ms"], h["opened_clock_ms"]) for h in board.hypotheses(run_id)],
    }

    out = {}
    hours = max(1e-9, sum(b - a for a, b in covered) / 3600000.0)
    for source, pairs in sources.items():
        # scored only where tunes were placed, so a night segmented over a
        # quarter of its length is not punished for the other three quarters
        predicted = sorted({int(t) for t, _ in pairs if gt.within(int(t), covered)})
        clock_of = {}
        for t, c in pairs:
            clock_of.setdefault(int(t), c)
        per_tol = {}
        for tol in tolerances:
            matched, fp, fn, errors = match_events(truth, predicted, tol_ms=tol)
            recall = matched / len(truth) if truth else 0.0
            precision = matched / len(predicted) if predicted else 0.0
            per_tol[str(tol)] = {
                "matched": matched, "recall": recall, "precision": precision,
                "f1": (2 * recall * precision / (recall + precision)) if (recall + precision) else 0.0,
                "false_per_hour": fp / hours, "missed": fn,
                "median_abs_error_ms": _median(sorted(abs(x) for x in errors)),
            }
        latencies = sorted(clock_of[t] - t for t in predicted if t in clock_of)
        out[source] = {
            "n_true": len(truth), "n_predicted": len(predicted),
            "scored_minutes": round(sum(b - a for a, b in covered) / 60000.0, 1),
            "by_tolerance": per_tol,
            "median_latency_ms": _median(latencies),
        }
    return out


def _median(values):
    values = list(values)
    if not values:
        return None
    n = len(values)
    mid = n // 2
    return float(values[mid]) if n % 2 else float((values[mid - 1] + values[mid]) / 2)


def _iqr(values):
    values = list(values)
    if len(values) < 4:
        return None
    q1 = values[len(values) // 4]
    q3 = values[(3 * len(values)) // 4]
    return [float(q1), float(q3)]


def evaluate_run(board, run_id):
    """Everything about one run, ready to write out or print."""
    run = board.get_run(run_id)
    config = json.loads(run["config_json"])
    gt = load_ground_truth(run["recording_id"])
    replay = tuple(config.get("replay_ms") or ()) or None

    rows = score_identification(board, run_id, gt, replay_range=replay)
    ident = aggregate_identification(rows)
    seg = score_segmentation(board, run_id, gt, replay_range=replay)
    costs = board.observation_costs(run_id)
    audio_min = (run["audio_ms"] or 0) / 60000.0
    for expert, c in costs.items():
        c["cost_ms_per_audio_min"] = c["cost_ms"] / audio_min if audio_min else None

    skips = defaultdict(int)
    for o in board.observations(run_id, types=["scheduler_skip"]):
        skips[o.payload.get("expert", "?")] += 1

    return {
        "run_id": run_id,
        "name": run["name"],
        "recording_id": run["recording_id"],
        "recording_label": gt.label,
        "date": gt.date,
        "status": run["status"],
        "audio_ms": run["audio_ms"],
        "wall_ms": run["wall_ms"],
        "config": config,
        "identification": ident,
        "segmentation": seg,
        "cost_by_expert": costs,
        "scheduler_skips": dict(skips),
        "warnings": gt.warnings,
        "segments": [
            {
                "segment_id": seg_.segment_id, "tune_id": seg_.tune_id, "name": seg_.name,
                "tune_type": seg_.tune_type, "start_ms": seg_.start_ms, "end_ms": seg_.end_ms,
                "capped": seg_.capped, "evaluated": seg_.evaluated,
                **(m or {}), **{"detail": d},
            }
            for seg_, m, d in rows
        ],
    }
