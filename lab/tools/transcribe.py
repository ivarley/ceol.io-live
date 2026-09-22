"""`lab transcribe` — what one part heard, in something a player can read.

The "is this component doing what we expect" tool. It runs only the chunk
source, a pitch tracker and note segmentation, through the same engine, and
prints the notes as ABC-ish text so they can be compared with the tune by eye
or by ear. With --match it also asks the index what it makes of them.

The run it creates is marked `scratch`, so scratch work does not clutter the
list of runs that mean something.
"""

import lab.env  # noqa: F401
from lab.audio.chunks import fmt_ms
from lab.board.board import Board
from lab.corpus.abc_pitch import to_abc_letters


def add_parser(sub):
    p = sub.add_parser("transcribe", help="pitch and notes for one segment, as ABC-ish text")
    p.add_argument("--recording", type=int, required=True)
    p.add_argument("--segment", type=int, help="segment number in time order (1-based)")
    p.add_argument("--range", dest="time_range", help="mm:ss-mm:ss")
    p.add_argument("--source", default="pitch_pyin", choices=["pitch_pyin", "pitch_yin"])
    p.add_argument("--match", action="store_true", help="also ask the index")
    p.add_argument("--candidate-set", default="repertoire")
    p.add_argument("-n", type=int, default=6, help="n-gram length of the index to query")
    p.add_argument("--no-fold", action="store_true",
                   help="query the unfolded index instead of the folded one")
    p.add_argument("--run", help="read an existing run instead of transcribing again")
    p.set_defaults(func=main)


def main(args):
    from lab.engine.run import execute

    if not args.segment and not args.time_range:
        raise SystemExit("give --segment N or --range mm:ss-mm:ss")

    with Board() as board:
        if args.run:
            run_id = args.run
        else:
            config = {
                "name": "transcribe",
                "chunk_ms": 2000,
                "experts": [
                    {"name": args.source},
                    {"name": "notes", "params": {"sources": [args.source]}},
                ],
                "scheduler": {"rule": "always"},
            }
            if args.segment:
                config["segments"] = str(args.segment)
            if args.time_range:
                config["range"] = args.time_range
            run_id = execute(config, args.recording, board=board, quiet=True, status="scratch")

        notes = []
        for o in board.observations(run_id, types=["note_events"]):
            if o.payload.get("source") != args.source:
                continue
            known = {n["t0_ms"] for n in notes}
            notes.extend(n for n in o.payload["notes"] if n["t0_ms"] not in known)
        notes.sort(key=lambda n: n["t0_ms"])

        if not notes:
            print(f"{run_id}: {args.source} produced no notes here")
            return 0

        durations = sorted(n["t1_ms"] - n["t0_ms"] for n in notes)
        unit = max(60, durations[len(durations) // 2])
        print(f"{run_id}  {args.source}  {len(notes)} notes, median {unit}ms\n")

        line, line_units, line_start = [], 0, notes[0]["t0_ms"]
        prev_end = None
        for n in notes:
            if prev_end is not None and n["t0_ms"] - prev_end > 200:
                line.append("z")
            letter = to_abc_letters([n["midi"]])
            length = max(1, round((n["t1_ms"] - n["t0_ms"]) / unit))
            line.append(letter + ("" if length == 1 else str(length)))
            line_units += length
            prev_end = n["t1_ms"]
            if line_units >= 8:
                print(f"  {fmt_ms(line_start):>8}  {' '.join(line)} |")
                line, line_units, line_start = [], 0, n["t1_ms"]
        if line:
            print(f"  {fmt_ms(line_start):>8}  {' '.join(line)} |")

        if args.match:
            from lab.corpus.abc_pitch import interval_sequence
            from lab.corpus.index import Index

            index = Index.load(args.candidate_set, n=args.n, fold_octaves=not args.no_fold)
            iv = interval_sequence([n["midi"] for n in notes], fold=index.fold_octaves)
            print(f"\n  against the {args.candidate_set} index "
                  f"({index.n_tunes} tunes, {len(iv)} intervals):")
            ranked = index.lookup(iv, top_k=10)
            if not ranked:
                print("    nothing matched")
            for i, r in enumerate(ranked, 1):
                print(f"    {i:>2}. {r['name']:<45} score {r['score']:.3f} "
                      f"coverage {r['coverage']:.3f} hits {r['hits']}")
    return 0
