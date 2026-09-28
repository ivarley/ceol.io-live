"""`lab display` — what a player would have SEEN, replayed from a finished run.

The assembler's top guess changes whenever the evidence does, and a board run
counts every change as a flip. A screen does not have to show every change.
This replays the stored hypothesis events through a display rule and scores
what the rule would have put on screen, so a rule is tried in seconds over
runs already made rather than in half an hour of new ones.

The rule, in the player's terms:

- **A sure answer shows at once.** A new top guess replaces the one on screen
  as soon as its confidence reaches `show_conf`.
- **A less sure one has to hold.** Otherwise it replaces it only once it has
  stayed on top for `hold_ms`. A guess that is top for one update and gone
  the next never reaches the screen.
- **Unsure, show a short list.** While the top guess is below `show_conf`,
  every candidate at or above `list_floor`, up to `list_max`, is offered to
  pick from.

`show_conf=0, hold_ms=0` shows every change the moment it happens, which is
what `lab eval` scores; it is the control every rule is paired against.

Confidence here is the assembler's raw number, which is not calibrated (it
tops out near 0.75, and 0.5 is right about nine times in ten). `calibrate`
fits the thresholds that give each category its promised accuracy on the
other nights, and scores them on the night left out.
"""

import json

import lab.env  # noqa: F401
from lab.board.board import Board
from lab.bench.tasks import load_ground_truth
from lab.eval.metrics import segment_events
from lab.tools.compare import _latest_runs, sign_test

NIGHTS = "1,2,3,4,5,138,139,140"


def replay(events, truth, seg_start_ms, show_conf=0.0, hold_ms=0, list_floor=None,
           list_max=5):
    """One segment's events through the display rule -> what was shown, and when.

    `events` are the segment's hypothesis events in clock order (each with
    `clock_ms`, `event`, `top1_tune_id`, `top1_conf`, `ranked`). Returns
    first-correct times for the single answer and for "the answer or the
    short list", flips of the answer shown, what was shown at the end, and
    the short list's sizes while it was up.
    """
    shown, cand, cand_since = None, None, None
    shown_seq = []
    first_right = first_offered = None
    offered_size = None
    list_sizes = []
    for i, ev in enumerate(events):
        t = ev["clock_ms"]
        if ev["event"] == "withdrawn":
            # The boundary detector closes a span every few seconds and the
            # assembler reopens one at the same instant, usually on the same
            # tune; a reader never sees that. Only a withdrawal nothing
            # replaces clears the screen. (Clearing on every one restarted the
            # hold each time, and a 10s hold then showed almost nothing.)
            if i + 1 < len(events) and events[i + 1]["clock_ms"] == t:
                continue
            shown, cand, cand_since = None, None, None
            continue
        top, conf = ev["top1_tune_id"], ev["top1_conf"] or 0.0
        if top != cand:
            cand, cand_since = top, t
        if top != shown and (conf >= show_conf or t - cand_since >= hold_ms):
            shown = top
            shown_seq.append(shown)
        short = []
        if list_floor is not None and conf < show_conf:
            short = [c["tune_id"] for c in ev["ranked"] if c["conf"] >= list_floor][:list_max]
            if short:
                list_sizes.append(len(short))
        if first_right is None and shown == truth:
            first_right = t - seg_start_ms
        if first_offered is None and (shown == truth or truth in short):
            first_offered = t - seg_start_ms
            offered_size = 1 if shown == truth and truth not in short else max(1, len(short))
    return {
        "first_right_ms": first_right,
        "first_offered_ms": first_offered,
        "offered_size": offered_size,
        "flips": sum(1 for a, b in zip(shown_seq, shown_seq[1:]) if a != b),
        "right_at_end": int(shown == truth),
        "list_sizes": list_sizes,
    }


def load_segments(config, nights=NIGHTS):
    """(night, segment id, truth, start, events) for every scored segment of a
    config's latest runs."""
    out = []
    with Board() as board:
        latest = _latest_runs(board)
        for n in [int(x) for x in nights.split(",")]:
            run_id = latest[f"{config}-r{n}"]
            events = board.hypothesis_events(run_id)
            spans = {h["hyp_id"]: h for h in board.hypotheses(run_id)}
            for seg in load_ground_truth(n).eval_segments():
                if not seg.evaluated:
                    continue
                out.append((n, seg.segment_id, seg.tune_id, seg.start_ms,
                            segment_events(events, spans, seg.start_ms, seg.end_ms)))
    return out


def score(segments, **rule):
    rows = {}
    for night, seg_id, truth, start, events in segments:
        rows[seg_id] = {"night": night, **replay(events, truth, start, **rule)}
    return rows


def summarise(rows):
    n = len(rows)
    r = list(rows.values())

    def within(key, ms):
        return sum(1 for x in r if x[key] is not None and x[key] <= ms) / n

    sizes = [s for x in r for s in x["list_sizes"]]
    offered = [x["offered_size"] for x in r if x["offered_size"]]
    return {
        "n": n,
        "right_end": sum(x["right_at_end"] for x in r) / n,
        "right_30": within("first_right_ms", 30000),
        "right_60": within("first_right_ms", 60000),
        "offered_30": within("first_offered_ms", 30000),
        "offered_60": within("first_offered_ms", 60000),
        "never": sum(1 for x in r if x["first_right_ms"] is None) / n,
        "flips": sum(x["flips"] for x in r) / n,
        "list_mean": sum(sizes) / len(sizes) if sizes else 0.0,
        "offered_size_mean": sum(offered) / len(offered) if offered else 0.0,
    }


def pair(a, b):
    """Paired counts, b against a: within 30s, within 60s, right at the end, flips."""
    common = sorted(set(a) & set(b))
    out = {}
    for label, key, ms in (("within 30s", "first_right_ms", 30000),
                           ("within 60s", "first_right_ms", 60000)):
        def ok(x):
            return x[key] is not None and x[key] <= ms
        won = sum(1 for s in common if ok(b[s]) and not ok(a[s]))
        lost = sum(1 for s in common if ok(a[s]) and not ok(b[s]))
        out[label] = (won, lost, sign_test(won, lost))
    won = sum(1 for s in common if b[s]["right_at_end"] and not a[s]["right_at_end"])
    lost = sum(1 for s in common if a[s]["right_at_end"] and not b[s]["right_at_end"])
    out["right at end"] = (won, lost, sign_test(won, lost))
    fewer = sum(1 for s in common if b[s]["flips"] < a[s]["flips"])
    more = sum(1 for s in common if b[s]["flips"] > a[s]["flips"])
    out["fewer flips"] = (fewer, more, sign_test(fewer, more))
    return out


# -- calibration: confidence thresholds that keep a category's promise -------

def confidence_pairs(segments):
    """(night, conf, right, weight) for every non-withdrawal event, each
    segment weighted to one in total, so a long tune with many updates does
    not outvote a short one."""
    out = []
    for night, _, truth, _, events in segments:
        live = [ev for ev in events if ev["event"] != "withdrawn"]
        for ev in live:
            out.append((night, ev["top1_conf"] or 0.0, ev["top1_tune_id"] == truth,
                        1.0 / len(live)))
    return out


def fit_threshold(pairs, target, min_weight=5.0):
    """The lowest confidence at or above which the weighted accuracy is at
    least `target`, holding at least `min_weight` segments' worth of events;
    None if no threshold keeps the promise."""
    ranked = sorted(pairs, key=lambda p: -p[1])
    right = total = 0.0
    best = None
    for _, conf, ok, w in ranked:
        right += w * ok
        total += w
        if total >= min_weight and right / total >= target:
            best = conf
    return best


def held_out(pairs, targets):
    """Leave one night out: fit each category's threshold on the other nights,
    score it on the night left out. -> {category: (accuracy, share, thresholds)}"""
    nights = sorted({p[0] for p in pairs})
    out = {}
    for name, target in targets.items():
        right = total = 0.0
        share = 0.0
        thresholds = []
        for n in nights:
            t = fit_threshold([p for p in pairs if p[0] != n], target)
            thresholds.append(t)
            if t is None:
                continue
            test = [p for p in pairs if p[0] == n]
            sel = [p for p in test if p[1] >= t]
            right += sum(p[3] * p[2] for p in sel)
            total += sum(p[3] for p in sel)
            share += sum(p[3] for p in sel)
        weight = sum(p[3] for p in pairs)
        out[name] = (right / total if total else None, share / weight if weight else 0.0,
                     thresholds)
    return out


# -- command -------------------------------------------------------------

def add_parser(sub):
    p = sub.add_parser("display", help="replay runs through a display rule: what a player would have seen")
    p.add_argument("config", help="board config name, as in `lab compare` (runs named <config>-r<night>)")
    p.add_argument("--nights", default=NIGHTS)
    p.add_argument("--show-conf", type=float, default=0.0,
                   help="show a new top guess at once from this confidence")
    p.add_argument("--hold-s", type=float, default=0.0,
                   help="otherwise show it once it has been top this long")
    p.add_argument("--list-floor", type=float, help="offer a short list of candidates from this confidence")
    p.add_argument("--list-max", type=int, default=5)
    p.add_argument("--sweep", action="store_true",
                   help="sweep show-conf and hold-s against the control instead")
    p.add_argument("--calibrate", action="store_true",
                   help="fit category thresholds leave-one-night-out and score them")
    p.set_defaults(func=main)


def _line(label, m):
    return (f"  {label:<34} right at end {m['right_end']:.3f}  <30s {m['right_30']:.1%}  "
            f"<60s {m['right_60']:.1%}  never {m['never']:.1%}  flips {m['flips']:.2f}"
            + (f"  | offered <30s {m['offered_30']:.1%} <60s {m['offered_60']:.1%}, "
               f"list {m['list_mean']:.1f} long" if m["list_mean"] else ""))


def main(args):
    segments = load_segments(args.config, args.nights)
    control = score(segments)
    print(f"{args.config}, nights {args.nights}, {len(control)} segments")
    print(_line("control (every change shown)", summarise(control)))
    if args.calibrate:
        pairs = confidence_pairs(segments)
        cats = {"probably (80%)": 0.80, "very likely (90%)": 0.90, "certainly (98%)": 0.98}
        for name, (acc, share, ts) in held_out(pairs, cats).items():
            fitted = ", ".join("-" if t is None else f"{t:.2f}" for t in ts)
            print(f"  {name:<20} held-out accuracy "
                  + ("-" if acc is None else f"{acc:.1%}")
                  + f" on {share:.1%} of what was on screen; thresholds by night left out: {fitted}")
        return 0
    rules = ([{"show_conf": c, "hold_ms": int(h * 1000)}
              for c in (0.4, 0.5, 0.6, 1.1) for h in (2, 4, 6, 10)]
             if args.sweep else
             [{"show_conf": args.show_conf, "hold_ms": int(args.hold_s * 1000)}])
    for rule in rules:
        if args.list_floor is not None:
            rule.update(list_floor=args.list_floor, list_max=args.list_max)
        rows = score(segments, **rule)
        label = json.dumps({k: v for k, v in rule.items()}, sort_keys=True)
        print(_line(label, summarise(rows)))
        print("    paired against control: " + "; ".join(
            f"{k} +{w}/-{lo} (p {p:.3f})" for k, (w, lo, p) in pair(control, rows).items()))
    return 0
