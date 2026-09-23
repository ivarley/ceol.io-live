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

    ret = inner.add_parser("retrieval", help="does the tune come back from the index (front ends)")
    ret.add_argument("--frontend", required=True,
                     help="one name, or several comma-separated to fuse their rankings")
    ret.add_argument("--fusion", default="rrf", choices=["rrf", "sum"])
    ret.add_argument("--recordings")
    ret.add_argument("--candidate-set", default="repertoire")
    ret.add_argument("-n", type=int, default=5)
    ret.add_argument("--seconds", type=float, default=30.0,
                     help="how much of each segment to transcribe (default 30)")
    ret.add_argument("--prior", default="none",
                     choices=["none", "sequence", "sequence_self", "sequence_soft",
                              "set_viterbi", "prior_only"],
                     help="sequence: re-rank by what usually follows (oracle previous tune); "
                          "sequence_self: chain the system's own top answer forward; "
                          "sequence_soft: chain its whole distribution forward; "
                          "set_viterbi: decode a whole set at once; "
                          "prior_only: ignore the audio entirely, as a control")
    ret.add_argument("--beta", type=float, default=1.0, help="how hard the prior pulls")
    ret.add_argument("--adaptive", action="store_true",
                     help="let each segment's own evidence decide how hard the prior pulls")
    ret.add_argument("--fold-octaves", action="store_true",
                     help="use the folded index, where an octave error costs nothing")
    ret.add_argument("--type-filter", default="none",
                     choices=["none", "oracle", "predicted",
                              "predicted_hard", "predicted_plausible"],
                     help="oracle: keep only candidates of the true tune type, to size "
                          "what a type classifier would be worth before building one")
    ret.add_argument("--param", action="append", default=[], metavar="K=V")
    ret.add_argument("--no-save", action="store_true")
    ret.set_defaults(func=cmd_retrieval)

    tt = inner.add_parser("tunetype", help="classify a segment's tune type from its rhythm")
    tt.add_argument("--recordings")
    tt.add_argument("--seconds", type=float, default=30.0)
    tt.add_argument("--no-save", action="store_true")
    tt.set_defaults(func=cmd_tunetype)

    pitch = inner.add_parser("pitch", help="score a front end against hand-labelled pitch")
    pitch.add_argument("--frontend", required=True,
                       help="one name, or several comma-separated to compare")
    pitch.add_argument("--param", action="append", default=[], metavar="K=V")
    pitch.add_argument("--no-save", action="store_true")
    pitch.set_defaults(func=cmd_pitch)

    pu = inner.add_parser("pulse", help="score the grid estimator against tapped tempo")
    pu.add_argument("--seconds", type=float, default=60.0)
    pu.add_argument("--no-save", action="store_true")
    pu.set_defaults(func=cmd_pulse)

    fronts = inner.add_parser("frontends", help="list front ends (built and not)")
    fronts.set_defaults(func=cmd_frontends)

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


def cmd_retrieval(args):
    from lab.bench.retrieval import format_retrieval, run_retrieval
    from lab.frontends import get_frontend

    params = _parse_params(args.param)
    frontends = [get_frontend(name.strip(), **params) for name in args.frontend.split(",")]
    result, rows = run_retrieval(
        frontends, recording_ids=_ids(args.recordings), candidate_set=args.candidate_set,
        n=args.n, seconds=args.seconds, prior=args.prior, beta=args.beta,
        fold_octaves=args.fold_octaves, type_filter=args.type_filter, fusion=args.fusion,
        adaptive=args.adaptive)
    print(format_retrieval(result, rows))
    if not args.no_save:
        print(f"  saved {result.save()}")
    return 0


def cmd_tunetype(args):
    from lab.bench.tunetype import format_tune_type, run_tune_type

    result = run_tune_type(recording_ids=_ids(args.recordings), seconds=args.seconds)
    print(format_tune_type(result))
    if not args.no_save:
        print(f"  saved {result.save()}")
    return 0


def cmd_pitch(args):
    from lab.bench.pitch import format_pitch, run_pitch
    from lab.frontends import get_frontend

    params = _parse_params(args.param)
    for name in args.frontend.split(","):
        result = run_pitch(get_frontend(name.strip(), **params))
        print(format_pitch(result))
        if not args.no_save:
            print(f"  saved {result.save()}")
        print()
    return 0


def cmd_pulse(args):
    from lab.bench.pulse import format_pulse, run_pulse

    result = run_pulse(seconds=args.seconds)
    print(format_pulse(result))
    if not args.no_save:
        print(f"  saved {result.save()}")
    return 0


def cmd_frontends(args):
    from lab.frontends import REGISTRY, UNBUILT

    print("built:")
    for name, c in sorted(REGISTRY.items()):
        print(f"  {name:<18} v{c.version}")
    print("not built yet:")
    for name, why in sorted(UNBUILT.items()):
        print(f"  {name:<18} {why}")
    return 0


def cmd_leaderboard(args):
    from lab.bench.score import load_results

    results = load_results(args.task)
    if not results:
        raise SystemExit(f"no results for task '{args.task}'; run `lab bench run --task {args.task} --candidate ...`")
    # Rank by accuracy where the task has it. For music-vs-not the classes are
    # lopsided — about three quarters of labelled frames are music — so f1
    # puts "always music" within a hair of a real detector, and accuracy is
    # the column that separates them.
    if args.task == "tune_retrieval":
        results.sort(key=lambda r: -(r["pooled"].get("top1") or 0))
        print(f"{args.task}  ({len(results)} entries, scored per night)")
        print(f"{'front end':<22} {'top1':>7} {'top5':>7} {'top10':>7} {'mrr':>7} "
              f"{'in top 25':>10} {'notes':>6}  params")
        for r in results:
            p = r["pooled"]
            keep = ("n", "fold_octaves", "prior", "beta", "seconds", "min_voiced")
            shown = {k: v for k, v in r["params"].items() if k in keep}
            print(f"{r['candidate']:<22} {p.get('top1', 0):>7.3f} {p.get('top5', 0):>7.3f} "
                  f"{p.get('top10', 0):>7.3f} {p.get('mrr', 0):>7.3f} "
                  f"{p.get('found_at_all', 0):>10.3f} {p.get('median_notes', 0):>6.0f}  "
                  f"{json.dumps(shown, sort_keys=True)}")
        return 0

    has_accuracy = any(r["pooled"].get("accuracy") is not None for r in results)
    key = "accuracy" if has_accuracy else "f1"
    results.sort(key=lambda r: -(r["pooled"].get(key) or 0))
    extra = f"{'accuracy':>9}" if has_accuracy else f"{'false/h':>9}"
    print(f"{args.task}  ({len(results)} candidates, leave-one-night-out, ranked by {key})")
    print(f"{'candidate':<22} {'ver':<4}{extra} {'f1':>6} {'recall':>7} {'prec':>6} "
          f"{'spread':>12}  params")
    for r in results:
        p = r["pooled"]
        spread = [n["metrics"].get(key) for n in r["nights"] if n["metrics"].get(key) is not None]
        sp = f"{min(spread):.2f}-{max(spread):.2f}" if spread else "-"
        col = (f"{p['accuracy']:>9.3f}" if has_accuracy
               else f"{(p.get('false_per_hour') or 0):>9.1f}")
        print(f"{r['candidate']:<22} {r['version']:<4}{col} {(p.get('f1') or 0):>6.3f} "
              f"{(p.get('recall') or 0):>7.3f} {(p.get('precision') or 0):>6.3f} {sp:>12}  "
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
