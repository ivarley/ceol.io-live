"""`lab bench` — the fast loop.

    lab bench features                          compute the cached grid
    lab bench candidates                        what exists, and what does not
    lab bench run --task boundary --candidate boundary_novelty
    lab bench leaderboard --task boundary
"""

import argparse
import json
import sys

import lab.env  # noqa: F401
from lab import paths


def add_parser(sub):
    p = sub.add_parser("bench", help="score an idea against a task, leave-one-night-out")
    inner = p.add_subparsers(dest="bench_command", metavar="subcommand")

    run = inner.add_parser("run", help="score one candidate on one task")
    run.add_argument("--task", required=True)
    run.add_argument("--candidate", required=True)
    run.add_argument("--recordings", help="comma-separated ids (default: all prepared)")
    run.add_argument("--tol-ms", type=int, help="boundary tolerance (default 3000)")
    run.add_argument("--param", action="append", default=[], metavar="K=V",
                     help="override a candidate parameter; repeatable")
    run.add_argument("--no-save", action="store_true")
    run.set_defaults(func=cmd_run)

    board = inner.add_parser("leaderboard", help="candidates ranked for a task")
    board.add_argument("--task", required=True)
    board.set_defaults(func=cmd_leaderboard)

    cands = inner.add_parser("candidates", help="list candidates (built and not)")
    cands.add_argument("--task")
    cands.set_defaults(func=cmd_candidates)

    feats = inner.add_parser("features", help="compute the cached feature grid")
    feats.add_argument("--recordings")
    feats.add_argument("--force", action="store_true")
    feats.set_defaults(func=cmd_features)

    p.set_defaults(func=lambda args: (p.print_help(), 2)[1])


def _parse_params(pairs):
    out = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--param wants K=V, got {pair!r}")
        k, v = pair.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def _ids(text):
    return [int(x) for x in text.replace(" ", "").split(",") if x] if text else None


def cmd_run(args):
    from lab.bench.candidates import get_candidate
    from lab.bench.score import format_result, run_bench

    candidate = get_candidate(args.candidate, **_parse_params(args.param))
    result = run_bench(args.task, candidate, recording_ids=_ids(args.recordings), tol_ms=args.tol_ms)
    print(format_result(result))
    for w in result.warnings:
        print(f"  warning: {w}", file=sys.stderr)
    if not args.no_save:
        print(f"  saved {result.save()}")
    return 0


def cmd_leaderboard(args):
    from lab.bench.score import load_results

    results = load_results(args.task)
    if not results:
        raise SystemExit(f"no results for task '{args.task}'; run `lab bench run --task {args.task} --candidate ...`")
    key = "f1"
    results.sort(key=lambda r: -(r["pooled"].get(key) or 0))
    print(f"{args.task}  ({len(results)} candidates, leave-one-night-out)")
    print(f"{'candidate':<24} {'ver':<4} {'f1':>6} {'recall':>7} {'prec':>6} {'spread (f1)':>18}  params")
    for r in results:
        p = r["pooled"]
        spread = [n["metrics"].get("f1") for n in r["nights"] if n["metrics"].get("f1") is not None]
        sp = f"{min(spread):.2f}-{max(spread):.2f}" if spread else "-"
        print(f"{r['candidate']:<24} {r['version']:<4} {(p.get('f1') or 0):>6.3f} "
              f"{(p.get('recall') or 0):>7.3f} {(p.get('precision') or 0):>6.3f} {sp:>18}  "
              f"{json.dumps(r['params'], sort_keys=True)}")
    return 0


def cmd_candidates(args):
    from lab.bench.candidates import REGISTRY, TASK_HINT, UNBUILT

    names = TASK_HINT.get(args.task) if args.task else sorted(REGISTRY)
    print("built:")
    for name in names or sorted(REGISTRY):
        c = REGISTRY[name]
        print(f"  {name:<24} v{c.version}  {'learned' if c.fittable else 'rule   '}  needs {', '.join(c.needs)}")
    print("not built yet:")
    for name, why in sorted(UNBUILT.items()):
        print(f"  {name:<24} {why}")
    return 0


def cmd_features(args):
    from lab.bench.features import compute_features

    for rid in (_ids(args.recordings) or paths.prepared_recording_ids()):
        compute_features(rid, force=args.force)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    sys.exit(parser.parse_args().func(parser.parse_args()))
