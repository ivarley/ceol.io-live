"""`lab timeline` — the output to read first.

Per ground-truth segment: what was actually played, where the boundaries
really were and where the system thought they were, then every claim it made
with a star where the top answer was right. If something looks wrong in a run,
this is where it shows.
"""

import json

import lab.env  # noqa: F401
from lab.audio.chunks import fmt_ms
from lab.bench.tasks import load_ground_truth
from lab.board.board import Board


def add_parser(sub):
    p = sub.add_parser("timeline", help="per-segment ground truth against the run's claims")
    p.add_argument("run_id")
    p.add_argument("--segment", type=int, help="only this segment id")
    p.add_argument("--top", type=int, default=3, help="how many candidates to show per event")
    p.set_defaults(func=main)


def main(args):
    with Board() as board:
        run = board.get_run(args.run_id)
        config = json.loads(run["config_json"])
        replay = tuple(config.get("replay_ms") or ()) or None
        gt = load_ground_truth(run["recording_id"])
        events = board.hypothesis_events(args.run_id)
        spans = {h["hyp_id"]: h for h in board.hypotheses(args.run_id)}
        boundaries = [o.payload.get("t_ms") for o in board.observations(args.run_id, types=["boundary"])]

        print(f"{args.run_id}  {gt.label} ({gt.date})  replay "
              f"{fmt_ms(replay[0]) if replay else '0'}-{fmt_ms(replay[1]) if replay else 'end'}\n")

        shown = 0
        for seg in gt.eval_segments(range_ms=replay):
            if args.segment and seg.segment_id != args.segment:
                continue
            if not seg.evaluated and seg.skip_reason == "outside_range":
                continue
            shown += 1
            flag = []
            if seg.capped:
                flag.append("capped")
            if not seg.evaluated:
                flag.append(f"not scored: {seg.skip_reason}")
            if seg.unmarked_set_end:
                flag.append("unmarked set end")
            print(f"── segment {seg.segment_id}: {seg.name} ({seg.tune_type or '?'}) "
                  f"{fmt_ms(seg.start_ms)}-{fmt_ms(seg.end_ms)} "
                  f"[{fmt_ms(seg.end_ms - seg.start_ms)}]"
                  + (f"  {', '.join(flag)}" if flag else ""))

            near = [b for b in boundaries if seg.start_ms - 15000 <= b <= seg.start_ms + 15000]
            if near:
                closest = min(near, key=lambda b: abs(b - seg.start_ms))
                print(f"   boundary predicted at {fmt_ms(closest)} "
                      f"({(closest - seg.start_ms) / 1000:+.1f}s from the true start)")
            else:
                print("   boundary: none predicted within 15s of the start")

            inside = [e for e in events if seg.start_ms <= e["clock_ms"] < seg.end_ms]
            if not inside:
                print("   no claims made during this segment")
            for e in inside:
                ranked = e["ranked"][:args.top]
                mark = "*" if e["top1_tune_id"] == seg.tune_id else " "
                offset = (e["clock_ms"] - seg.start_ms) / 1000.0
                names = " | ".join(f"{c['name']} {c['conf']:.2f}" for c in ranked) or "nothing"
                opened = spans.get(e["hyp_id"], {}).get("opened_by", "?")
                print(f"  {mark}+{offset:>6.1f}s {e['event']:<11} {e['hyp_id'].split(':')[-1]:>3} "
                      f"({opened:<11}) {names}")
            print()
        if shown == 0:
            print("no segments fall inside this run's replayed range")
    return 0
