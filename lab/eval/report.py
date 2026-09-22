"""`lab eval` — score a run and write eval.json and eval.md."""

import argparse
import json
import os
import sys

import lab.env  # noqa: F401
from lab import paths
from lab.audio.chunks import fmt_ms
from lab.board.board import Board
from lab.eval.metrics import evaluate_run


def add_parser(sub):
    p = sub.add_parser("eval", help="score a run against the corpus")
    p.add_argument("run_id")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=main)


def _pct(d):
    if not d or d.get("n", 0) == 0:
        return "-"
    return f"{d['value'] * 100:.1f}% [{d['lo'] * 100:.0f}-{d['hi'] * 100:.0f}] {d['k']}/{d['n']}"


def to_markdown(r):
    ident = r["identification"]
    lines = [
        f"# {r['name']} — {r['recording_label']} ({r['date']})",
        "",
        f"Run `{r['run_id']}`, recording {r['recording_id']}, "
        f"{(r['audio_ms'] or 0) / 60000:.1f} min replayed in {(r['wall_ms'] or 0) / 1000:.0f}s.",
        "",
        "## Identification",
        "",
    ]
    if ident.get("n_evaluated", 0) == 0:
        lines += ["No segments were scored.", ""]
    else:
        lines += [
            "| metric | value |",
            "|---|---|",
            f"| segments scored | {ident['n_evaluated']} ({ident['n_capped']} capped) |",
            f"| top-1 at end | {_pct(ident['top1'])} |",
            f"| top-5 at end | {_pct(ident['top5'])} |",
            f"| right within 30s | {_pct(ident['found_within_30s'])} |",
            f"| right within 60s | {_pct(ident['found_within_60s'])} |",
            f"| never right | {ident['never_found']} |",
            f"| time to first correct (median) | {fmt_ms(ident['ttfc_median_ms'])} |",
            f"| time to stable correct (median) | {fmt_ms(ident['ttsc_median_ms'])} over {ident['ttsc_n']} |",
            f"| flips per segment (mean) | {ident['flips_mean']:.2f} (max {ident['flips_max']}) |",
            f"| calibration error | {ident['calibration']['ece']:.3f} |",
            "",
        ]
        if ident["skipped"]:
            lines += ["Skipped: " + ", ".join(f"{k} {v}" for k, v in sorted(ident["skipped"].items())), ""]
        if ident["calibration"]["bins"]:
            lines += ["### Calibration", "", "| confidence | n | accuracy | mean conf |", "|---|---|---|---|"]
            for b in ident["calibration"]["bins"]:
                lines.append(f"| {b['bin'][0]:.1f}-{b['bin'][1]:.1f} | {b['n']} | "
                             f"{b['accuracy'] * 100:.0f}% | {b['mean_conf']:.2f} |")
            lines.append("")

    lines += ["## Segmentation", "", "| source | tol | recall | precision | f1 | false/hour | median error | latency |",
              "|---|---|---|---|---|---|---|---|"]
    for source, s in r["segmentation"].items():
        for tol, m in s["by_tolerance"].items():
            lines.append(
                f"| {source} | ±{int(tol) // 1000}s | {m['recall'] * 100:.0f}% | "
                f"{m['precision'] * 100:.0f}% | {m['f1']:.2f} | {m['false_per_hour']:.1f} | "
                f"{fmt_ms(m['median_abs_error_ms'])} | {fmt_ms(s['median_latency_ms'])} |")
    lines += ["", f"({r['segmentation'][list(r['segmentation'])[0]]['n_true']} true boundaries)", ""]

    lines += ["## Cost", "", "| expert | observations | cached | ms per audio minute |", "|---|---|---|---|"]
    for expert, c in sorted(r["cost_by_expert"].items(), key=lambda kv: -(kv[1]["cost_ms"] or 0)):
        per_min = c.get("cost_ms_per_audio_min")
        lines.append(f"| {expert} | {c['n']} | {c['cached'] or 0} | "
                     f"{per_min:.0f} |" if per_min is not None else
                     f"| {expert} | {c['n']} | {c['cached'] or 0} | - |")
    if r["scheduler_skips"]:
        lines += ["", "Scheduler skipped: " + ", ".join(f"{k} ×{v}" for k, v in sorted(r["scheduler_skips"].items()))]

    scored = [s for s in r["segments"] if s.get("evaluated")]
    if scored:
        lines += ["", "## Segments", "",
                  "| # | tune | start | length | ttfc | ttsc | top1 | top5 | flips | conf |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for s in scored:
            lines.append(
                f"| {s['segment_id']} | {s['name']} | {fmt_ms(s['start_ms'])} | "
                f"{fmt_ms(s['end_ms'] - s['start_ms'])} | {fmt_ms(s.get('ttfc_ms'))} | "
                f"{fmt_ms(s.get('ttsc_ms'))} | {'yes' if s.get('top1_end') else 'no'} | "
                f"{'yes' if s.get('top5_end') else 'no'} | {s.get('flips', 0)} | "
                f"{(s.get('end_conf') or 0):.2f} |")
    if r["warnings"]:
        lines += ["", "## Corpus warnings", ""] + [f"- {w}" for w in r["warnings"]]
    return "\n".join(lines) + "\n"


def summary_line(r):
    i = r["identification"]
    if not i.get("n_evaluated"):
        return f"{r['run_id']}: no segments scored"
    seg = r["segmentation"].get("boundary_observations", {}).get("by_tolerance", {}).get("3000", {})
    return (f"{r['run_id']}: top-1 {_pct(i['top1'])}, top-5 {_pct(i['top5'])}, "
            f"ttfc median {fmt_ms(i['ttfc_median_ms'])}, flips {i['flips_mean']:.1f}/segment, "
            f"boundary f1 {seg.get('f1', 0):.2f}")


def main(args):
    with Board() as board:
        r = evaluate_run(board, args.run_id)
        rows = []
        for s in r["segments"]:
            rows.append((args.run_id, r["recording_id"], s["segment_id"], s["tune_id"], s["name"],
                         s["start_ms"], s["end_ms"], int(bool(s["capped"])), int(bool(s["evaluated"])),
                         (s.get("detail") or {}).get("skip_reason"), s.get("ttfc_ms"), s.get("ttsc_ms"),
                         s.get("top1_end"), s.get("top5_end"), s.get("flips"), s.get("end_conf"),
                         s.get("cost_ms"), json.dumps(s.get("detail") or {})))
        board.save_eval_segments(args.run_id, rows)

    out_dir = paths.ensure_dir(paths.run_dir(args.run_id))
    with open(os.path.join(out_dir, "eval.json"), "w") as f:
        json.dump(r, f, indent=1, default=str)
    md = to_markdown(r)
    with open(os.path.join(out_dir, "eval.md"), "w") as f:
        f.write(md)
    print(md if not args.quiet else summary_line(r))
    print(f"  wrote {out_dir}/eval.md")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    sys.exit(main(parser.parse_args()))
