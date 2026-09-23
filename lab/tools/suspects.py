"""`lab suspects` — labelled segments whose audio does not sound like a tune.

Ground-truth hygiene, not recognition. Every number the lab reports rests on
the segmenter's labels being right, and one of them was not: a segment marked
as a reel turned out to be two and a half minutes of between-sets noise with
the tune stapled to the end. It was spotted by ear in seconds and by nothing
in the lab at all, having quietly counted as a miss in every run since.

The measure that separates it is the height of the onset envelope's
autocorrelation at the beat. Music repeats; a room between sets does not. On
that segment it read 0.047; once the label was corrected the same audio read
0.334 and the tune came back at rank 1 from rank 84.

Two things this is not. It is not a label checker: plenty of weak-pulse
segments are labelled perfectly and simply have no dance rhythm, which is
what a slow air is, so the report shows the tune type and leaves the judging
to a person. And it is not a proposal to drop these segments from the eval
set, because a recogniser that only works on segments with a strong pulse is
not one worth having. The output is a list of places to look.
"""

import numpy as np

from lab import paths
from lab.analysis.pulse import estimate_pulse
from lab.audio.chunks import AudioStore, fmt_ms
from lab.audio.prepare import wav_sha1
from lab.bench.retrieval import transcribe_segment
from lab.bench.tasks import load_ground_truth
from lab.board.board import Board
from lab.corpus.index import Index
from lab.frontends import get_frontend
from lab.frontends.segmentation import intervals_from_notes

# Types with no dance pulse by nature, so a weak reading says nothing.
UNMETERED = {"waltz", "air", "slow air", "planxty", "song"}
BANDS = ((0.0, 0.10), (0.10, 0.18), (0.18, 0.28), (0.28, 0.40), (0.40, 9.0))


def add_parser(sub):
    p = sub.add_parser("suspects", help="labelled segments whose audio does not sound like a tune")
    p.add_argument("--recordings", help="comma-separated recording ids (default: all prepared)")
    p.add_argument("--frontend", default="yin")
    p.add_argument("--seconds", type=float, default=120.0)
    p.add_argument("-n", type=int, default=6)
    p.add_argument("--candidate-set", default="repertoire")
    p.add_argument("--threshold", type=float, default=0.18,
                   help="pulse strength below which a segment is listed (default 0.18)")
    p.add_argument("--top", type=int, default=20)
    p.set_defaults(func=main)


def scan(recording_ids, frontend, index, seconds=120.0):
    rows = []
    with Board() as board:
        for rid in recording_ids:
            gt = load_ground_truth(rid)
            store = AudioStore(paths.wav_path(rid))
            store.clock_ms = store.duration_ms
            sha = wav_sha1(rid) or ""
            segs = sorted(gt.eval_segments(), key=lambda s: s.start_ms)
            for i, seg in enumerate(segs):
                if not seg.evaluated or not seg.tune_id:
                    continue
                t1 = min(seg.end_ms, seg.start_ms + int(seconds * 1000))
                if t1 - seg.start_ms < 20000:
                    continue
                notes, _, _ = transcribe_segment(frontend, store, sha, seg.start_ms, t1,
                                                 board=board)
                ranked = index.lookup(intervals_from_notes(notes, fold=index.fold_octaves),
                                      top_k=25)
                rank = next((k + 1 for k, r in enumerate(ranked)
                             if r["tune_id"] == seg.tune_id), None)
                pulse = estimate_pulse(store.read(seg.start_ms, t1), store.sr)
                rows.append({
                    "recording_id": rid, "date": gt.date, "segment_id": seg.segment_id,
                    "name": seg.name, "tune_type": (seg.tune_type or "").strip().lower(),
                    "start_ms": seg.start_ms, "length_s": (seg.end_ms - seg.start_ms) / 1000.0,
                    "rank": rank, "strength": pulse["pulse_strength"] if pulse else 0.0,
                    "next": segs[i + 1].name if i + 1 < len(segs) else None,
                })
            store.close()
    return rows


def main(args):
    ids = ([int(x) for x in args.recordings.split(",")] if args.recordings
           else paths.prepared_recording_ids())
    index = Index.load(args.candidate_set, n=args.n, fold_octaves=True)
    frontend = get_frontend(args.frontend)
    rows = scan(ids, frontend, index, seconds=args.seconds)
    if not rows:
        print("no scorable segments")
        return 0

    vals = np.array([r["strength"] for r in rows])
    print(f"{len(rows)} segments over {len(ids)} recordings; pulse strength "
          f"median {np.median(vals):.3f}, 5th percentile {np.percentile(vals, 5):.3f}\n")
    print(f"{'pulse strength':<16}{'n':>5}{'top-1':>8}{'never found':>13}")
    for lo, hi in BANDS:
        band = [r for r in rows if lo <= r["strength"] < hi]
        if not band:
            continue
        label = f"{lo:.2f}-{hi:.2f}" if hi < 9 else f"over {lo:.2f}"
        print(f"{label:<16}{len(band):>5}"
              f"{np.mean([r['rank'] == 1 for r in band]):>8.3f}"
              f"{np.mean([r['rank'] is None for r in band]):>13.3f}")

    # Weak pulse AND the tune never came back is the shape the one known bad
    # label had. Weak pulse alone is common and usually means a slow tune.
    flagged = [r for r in rows
               if r["strength"] < args.threshold and r["tune_type"] not in UNMETERED]
    worst = [r for r in flagged if r["rank"] is None]
    rest = [r for r in flagged if r["rank"] is not None]
    print(f"\nno rhythm AND the tune never comes back ({len(worst)}) — look at these first:")
    _table(sorted(worst, key=lambda r: r["strength"])[:args.top])
    print(f"\nno rhythm but the tune is found anyway ({len(rest)}) — probably just slow:")
    _table(sorted(rest, key=lambda r: r["strength"])[:args.top])
    skipped = [r for r in rows if r["strength"] < args.threshold and r["tune_type"] in UNMETERED]
    if skipped:
        print(f"\n{len(skipped)} unmetered ({', '.join(sorted({r['tune_type'] for r in skipped}))}) "
              f"not listed: no dance pulse is the correct reading there")
    return 0


def _table(rows):
    if not rows:
        print("  none")
        return
    print(f"  {'rec':>4} {'date':<12}{'seg':>6}  {'at':<9}{'len':>6}{'pulse':>7}  "
          f"{'rank':<6}{'type':<10}tune")
    for r in rows:
        rank = "none" if r["rank"] is None else str(r["rank"])
        print(f"  {r['recording_id']:>4} {r['date']:<12}{r['segment_id']:>6}  "
              f"{fmt_ms(r['start_ms']):<9}{r['length_s']:>5.0f}s{r['strength']:>7.3f}  "
              f"{rank:<6}{(r['tune_type'] or '?'):<10}{r['name'][:30]}")
