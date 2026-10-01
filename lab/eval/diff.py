"""`lab diff` — two runs side by side.

Refuses to compare runs that replayed different material unless told to
intersect, because "we changed the config and the number moved" is not a
finding if the second run also saw different audio.
"""

import argparse
import sys

import lab.env  # noqa: F401
from lab.audio.chunks import fmt_ms
from lab.board.board import Board
from lab.eval.metrics import evaluate_run


def add_parser(sub):
    p = sub.add_parser("diff", help="compare two runs")
    p.add_argument("run_a")
    p.add_argument("run_b")
    p.add_argument("--intersection", action="store_true",
                   help="compare only the segments both runs scored")
    p.set_defaults(func=main)


def _fmt(d):
    return "-" if not d or not d.get("n") else f"{d['value'] * 100:.1f}% [{d['lo'] * 100:.0f}-{d['hi'] * 100:.0f}]"


def main(args):
    with Board() as board:
        a = evaluate_run(board, args.run_a)
        b = evaluate_run(board, args.run_b)

    seg_a = {s["segment_id"] for s in a["segments"] if s.get("evaluated")}
    seg_b = {s["segment_id"] for s in b["segments"] if s.get("evaluated")}
    if seg_a != seg_b and not args.intersection:
        raise SystemExit(
            f"these runs scored different segments ({len(seg_a)} vs {len(seg_b)}, "
            f"{len(seg_a & seg_b)} shared). Pass --intersection to compare the shared ones.")
    shared = seg_a & seg_b

    print(f"A  {a['run_id']}  {a['name']}")
    print(f"B  {b['run_id']}  {b['name']}")
    print(f"   {len(shared)} segments compared\n")

    ia, ib = a["identification"], b["identification"]
    print(f"{'metric':<26} {'A':>22} {'B':>22}   delta")
    for key, label in (("top1", "top-1 at end"), ("top5", "top-5 at end"),
                       ("found_within_30s", "right within 30s"),
                       ("found_within_60s", "right within 60s")):
        da, db = ia.get(key), ib.get(key)
        delta = (db["value"] - da["value"]) * 100 if da and db and da.get("n") and db.get("n") else None
        print(f"{label:<26} {_fmt(da):>22} {_fmt(db):>22}   "
              f"{'' if delta is None else f'{delta:+.1f}pt'}")
    print(f"{'ttfc median':<26} {fmt_ms(ia.get('ttfc_median_ms')):>22} {fmt_ms(ib.get('ttfc_median_ms')):>22}")
    print(f"{'flips per segment':<26} {ia.get('flips_mean', 0):>22.2f} {ib.get('flips_mean', 0):>22.2f}   "
          f"{ib.get('flips_mean', 0) - ia.get('flips_mean', 0):+.2f}")
    print(f"{'calibration error':<26} {ia.get('calibration', {}).get('ece', 0):>22.3f} "
          f"{ib.get('calibration', {}).get('ece', 0):>22.3f}")

    ba = a["segmentation"].get("boundary_observations", {}).get("by_tolerance", {}).get("3000", {})
    bb = b["segmentation"].get("boundary_observations", {}).get("by_tolerance", {}).get("3000", {})
    if ba or bb:
        print(f"\n{'boundary recall ±3s':<26} {ba.get('recall', 0):>22.2f} {bb.get('recall', 0):>22.2f}")
        print(f"{'boundary precision ±3s':<26} {ba.get('precision', 0):>22.2f} {bb.get('precision', 0):>22.2f}")

    print("\ncost per audio minute")
    experts = sorted(set(a["cost_by_expert"]) | set(b["cost_by_expert"]))
    for e in experts:
        ca = (a["cost_by_expert"].get(e) or {}).get("cost_ms_per_audio_min")
        cb = (b["cost_by_expert"].get(e) or {}).get("cost_ms_per_audio_min")
        print(f"  {e:<24} {('-' if ca is None else f'{ca:.0f}'):>10} "
              f"{('-' if cb is None else f'{cb:.0f}'):>10}")

    by_a = {s["segment_id"]: s for s in a["segments"]}
    by_b = {s["segment_id"]: s for s in b["segments"]}
    fixed = [i for i in shared if not by_a[i].get("top1_end") and by_b[i].get("top1_end")]
    broken = [i for i in shared if by_a[i].get("top1_end") and not by_b[i].get("top1_end")]
    print(f"\nB fixed {len(fixed)}, B broke {len(broken)}")
    for label, ids in (("fixed", fixed), ("broke", broken)):
        for i in ids[:15]:
            print(f"  {label:<6} {i:>5} {by_a[i]['name']}")
    moved = [(i, (by_b[i].get("ttfc_ms") or 0) - (by_a[i].get("ttfc_ms") or 0))
             for i in shared
             if by_a[i].get("ttfc_ms") is not None and by_b[i].get("ttfc_ms") is not None
             and abs((by_b[i]["ttfc_ms"]) - (by_a[i]["ttfc_ms"])) > 10000]
    if moved:
        print(f"\ntime-to-first-correct moved by more than 10s on {len(moved)} segments")
        for i, d in sorted(moved, key=lambda kv: -abs(kv[1]))[:10]:
            print(f"  {i:>5} {by_a[i]['name']:<40} {d / 1000:+.0f}s")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    sys.exit(main(parser.parse_args()))
