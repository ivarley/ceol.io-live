"""`lab compare` — several board configs pooled over the same nights, paired.

The way board experiments are read. `lab diff` compares two runs of one
night; a finding needs several nights, so a config is run once per night
under a name ending `-r<recording>` and this pools them:

    lab run --config C.json --recording 2 --name live-x-r2 --quiet   # per night
    lab compare live-steady live-x --nights 1,2,4,5

Each later config is also compared segment by segment against the first:
how many segments it newly got right at the end, how many it newly got
wrong, and a two-sided sign test on those two counts. The pooled means say
how big a change is; the pair says whether it is anything but noise.

`--record` adds the board's final record: the evaluator's answer at the end
of each tune, followed forward to that hypothesis's last word. It differs
from "top-1 at end" even with no revision, because a span runs on past its
tune until the next boundary and keeps updating; "changed" counts those.
With revision it is what the revision actually left behind.
"""

import subprocess
import sys
from math import comb

import lab.env  # noqa: F401
from lab.board.board import Board


def add_parser(sub):
    p = sub.add_parser(
        "compare",
        help="pool board runs per config over nights, paired against the first",
    )
    p.add_argument(
        "configs",
        nargs="+",
        help="run-name prefixes; runs are named <prefix>-r<recording>",
    )
    p.add_argument(
        "--nights", required=True, help="comma-separated recording ids, e.g. 1,2,4,5"
    )
    p.add_argument(
        "--record",
        action="store_true",
        help="also score the final record, revisions included",
    )
    p.set_defaults(func=main)


def sign_test(won, lost):
    """Two-sided exact sign test on paired wins and losses; ties are dropped."""
    n = won + lost
    if not n:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(won, lost) + 1)) / 2**n)


def _latest_runs(board):
    """Run name -> the newest finished run of that name."""
    return {
        r["name"]: r["run_id"]
        for r in board.conn.execute(
            "SELECT run_id, name FROM run WHERE status = 'done' ORDER BY created_at"
        )
    }


def _ensure_evaluated(board, run_ids):
    done = {
        r[0] for r in board.conn.execute("SELECT DISTINCT run_id FROM eval_segment")
    }
    for rid in run_ids:
        if rid not in done:
            subprocess.run(
                [sys.executable, "-m", "lab", "eval", rid, "--quiet"],
                capture_output=True,
                check=False,
            )


def final_record(board, run_id, recording_id):
    """(recording, segment) -> (shown at end is right, final record is right, changed)."""
    from lab.bench.tasks import load_ground_truth
    from lab.eval.metrics import _answer_at

    gt = load_ground_truth(int(recording_id))
    events = sorted(
        board.hypothesis_events(run_id), key=lambda e: (e["clock_ms"], e["event_id"])
    )
    spans = {h["hyp_id"]: h for h in board.hypotheses(run_id)}
    by_hyp = {}
    for ev in events:
        by_hyp.setdefault(ev["hyp_id"], []).append(ev)
    out = {}
    for seg in gt.eval_segments():
        if not seg.evaluated:
            continue
        s, e = seg.start_ms, seg.end_ms
        inside = [
            ev
            for ev in events
            if s <= ev["clock_ms"] < e
            and ev["hyp_id"] in spans
            and spans[ev["hyp_id"]]["t_start_ms"] <= e
            and (
                spans[ev["hyp_id"]]["t_end_ms"] is None
                or spans[ev["hyp_id"]]["t_end_ms"] >= s
            )
        ]
        at_end = _answer_at(inside, spans, e)
        shown = at_end["top1_tune_id"] if at_end else None
        final = shown
        if at_end:
            claims = [
                ev for ev in by_hyp[at_end["hyp_id"]] if ev["event"] != "withdrawn"
            ]
            final = claims[-1]["top1_tune_id"]
        out[(int(recording_id), seg.segment_id)] = (
            shown == seg.tune_id,
            final == seg.tune_id,
            final != shown,
        )
    return out


def main(args):
    nights = [n.strip() for n in args.nights.split(",") if n.strip()]
    with Board() as board:
        runs = _latest_runs(board)
        wanted = {p: {n: runs.get(f"{p}-r{n}") for n in nights} for p in args.configs}
        missing = [
            f"{p}-r{n}"
            for p, per in wanted.items()
            for n, rid in per.items()
            if not rid
        ]
        if missing:
            raise SystemExit("no finished run named: " + ", ".join(missing))
        _ensure_evaluated(
            board, [rid for per in wanted.values() for rid in per.values()]
        )

        per_seg = {}
        head = (
            f"{'config':<22}{'segs':>6}{'top-1':>8}{'top-5':>8}{'<30s':>8}"
            f"{'<60s':>8}{'never':>8}{'flips':>7}"
        )
        print(
            f"nights {','.join(nights)}\n\n{head}{'  record  changed' if args.record else ''}"
        )
        for p, per in wanted.items():
            rows = board.conn.execute(
                f"SELECT recording_id, segment_id, top1_end, top5_end, ttfc_ms, flips FROM eval_segment "
                f"WHERE run_id IN ({','.join('?' * len(per))}) AND evaluated = 1",
                list(per.values()),
            ).fetchall()
            per_seg[p] = {(r[0], r[1]): bool(r[2]) for r in rows}
            n = len(rows) or 1
            line = (
                f"{p:<22}{len(rows):>6}"
                f"{sum(r[2] or 0 for r in rows) / n:>8.3f}{sum(r[3] or 0 for r in rows) / n:>8.3f}"
                f"{sum(r[4] is not None and r[4] <= 30000 for r in rows) / n:>8.3f}"
                f"{sum(r[4] is not None and r[4] <= 60000 for r in rows) / n:>8.3f}"
                f"{sum(r[4] is None for r in rows) / n:>8.3f}"
                f"{sum(r[5] or 0 for r in rows) / n:>7.2f}"
            )
            if args.record:
                rec = {}
                for night, rid in per.items():
                    rec.update(final_record(board, rid, night))
                m = len(rec) or 1
                line += (
                    f"{sum(v[1] for v in rec.values()) / m:>8.3f}"
                    f"{sum(v[2] for v in rec.values()):>9}"
                )
            print(line)

    base = args.configs[0]
    if len(args.configs) > 1:
        print(f"\npaired against {base}, top-1 at end:")
    for p in args.configs[1:]:
        a, b = per_seg[base], per_seg[p]
        shared = a.keys() & b.keys()
        won = sum(1 for k in shared if b[k] and not a[k])
        lost = sum(1 for k in shared if a[k] and not b[k])
        print(
            f"  {p:<22} +{won} / -{lost}   p = {sign_test(won, lost):.3f}   ({len(shared)} shared)"
        )
    return 0
