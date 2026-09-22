"""`lab trace-set` — one set, end to end, at every stage.

The question this answers is "why did it say that", and it answers it by
showing the same thing at each stage rather than summarising: the notes it
heard, the intervals those became, what the index said about them, what the
session's history expected next, and what the whole-set decoder picked once
it could see the tunes either side.

Nothing here is a metric. It is the trace you read when a number is
surprising, and the reason the lab has a bench at all is that reading this
for every segment would be unbearable.
"""

import json

import lab.env  # noqa: F401
from lab import paths
from lab.audio.chunks import AudioStore, fmt_ms
from lab.audio.prepare import wav_sha1
from lab.bench.retrieval import decode_set, transcribe_segment
from lab.bench.tasks import load_ground_truth
from lab.board.board import Board
from lab.corpus.abc_pitch import ngrams, parse_abc, pitch_sequence, to_abc_letters
from lab.corpus.index import Index
from lab.corpus.sequence import SequenceModel
from lab.corpus.tunes_csv import iter_settings
from lab.frontends import get_frontend
from lab.frontends.segmentation import intervals_from_notes


def add_parser(sub):
    p = sub.add_parser("trace-set", help="one set, stage by stage, with what it matched against")
    p.add_argument("--recording", type=int, required=True)
    p.add_argument("--segment", type=int, required=True,
                   help="any segment id in the set; the whole set is traced")
    p.add_argument("--frontend", default="yin")
    p.add_argument("--seconds", type=float, default=120.0)
    p.add_argument("-n", type=int, default=6)
    p.add_argument("--candidate-set", default="repertoire")
    p.add_argument("--beta", type=float, default=0.15)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--notes", type=int, default=32, help="how many transcribed notes to print")
    p.set_defaults(func=main)


def _set_containing(gt, segment_id):
    previous_of = gt.previous_tune_map()
    segs = [s for s in gt.eval_segments() if s.evaluated and s.tune_id]
    groups, current = [], []
    for s in segs:
        if previous_of.get(s.session_instance_tune_id) is None and current:
            groups.append(current)
            current = []
        current.append(s)
    if current:
        groups.append(current)
    for g in groups:
        if any(s.segment_id == segment_id for s in g):
            return g
    raise SystemExit(f"segment {segment_id} is not a scorable segment of recording {gt.recording_id}")


def _abc_for(tune_id, index_n, fold):
    """The notation the index actually holds for a tune, as intervals."""
    for s in iter_settings(paths.tunes_csv_path(), tune_ids={tune_id}):
        pitches = pitch_sequence(parse_abc(s.abc, key=s.mode, meter=s.meter))
        return s, [p for p in pitches if p is not None]
    return None, []


def main(args):
    gt = load_ground_truth(args.recording)
    group = _set_containing(gt, args.segment)
    index = Index.load(args.candidate_set, n=args.n, fold_octaves=True)
    sequence = SequenceModel(gt.session_id, exclude_instance_ids=[gt.session_instance_id])
    frontend = get_frontend(args.frontend)
    store = AudioStore(paths.wav_path(args.recording))
    store.clock_ms = store.duration_ms
    sha = wav_sha1(args.recording) or ""

    print(f"{gt.label} ({gt.date}), a set of {len(group)} tunes")
    print(f"front end {frontend.name} v{frontend.version}, first {args.seconds:.0f}s of each tune, "
          f"{args.candidate_set} index of {index.n_tunes} tunes at n={args.n}, folded\n")

    candidates = []
    traces = []
    with Board() as board:
        for seg in group:
            t0 = seg.start_ms
            t1 = min(seg.end_ms, t0 + int(args.seconds * 1000))
            notes, _cost, cached = transcribe_segment(frontend, store, sha, t0, t1, board=board)
            intervals = intervals_from_notes(notes, fold=True)
            ranked = index.lookup(intervals, top_k=40)
            candidates.append(ranked)
            traces.append((seg, notes, intervals, ranked, cached))
    store.close()

    path = decode_set(candidates, sequence, beta=args.beta)
    names = {t: index.tune_names.get(t) for t in index.tune_names}

    previous_truth = None
    for (seg, notes, intervals, ranked, cached), chosen in zip(traces, path):
        print("=" * 78)
        print(f"TRUTH  {seg.name}  ({seg.tune_type})  {fmt_ms(seg.start_ms)}-{fmt_ms(seg.end_ms)}"
              f"  [tune {seg.tune_id}]")

        print(f"\n  1. HEARD   {len(notes)} notes in {(min(seg.end_ms, seg.start_ms + int(args.seconds*1000)) - seg.start_ms)/1000:.0f}s"
              f"{' (from cache)' if cached else ''}")
        head = [n["midi"] for n in notes[:args.notes]]
        print(f"     {to_abc_letters(head)}{' ...' if len(notes) > args.notes else ''}")

        usable = [i for i in intervals if i is not None]
        grams = ngrams(intervals, n=args.n)
        print(f"\n  2. SHAPE   {len(usable)} intervals, {len(grams)} usable {args.n}-grams")
        print(f"     {usable[:24]}{' ...' if len(usable) > 24 else ''}")

        setting, true_pitches = _abc_for(seg.tune_id, args.n, True)
        if setting:
            true_iv = [d for d in intervals_from_notes(
                [{"midi": p, "t0_ms": i * 100, "t1_ms": i * 100 + 90}
                 for i, p in enumerate(true_pitches)], fold=True) if d is not None]
            shared = len(set(grams) & set(ngrams(true_iv, n=args.n)))
            print(f"     the tune's own notation gives {len(true_iv)} intervals; "
                  f"{shared} of its {args.n}-grams appear in what was heard")

        print(f"\n  3. MATCHED against {index.n_tunes} tunes, top {args.top} by melody alone:")
        for i, r in enumerate(ranked[:args.top], 1):
            mark = " <- truth" if r["tune_id"] == seg.tune_id else ""
            print(f"     {i:>2}. {r['name']:<42} score {r['score']:.4f}  "
                  f"hits {r['hits']:>3}{mark}")
        rank = next((i + 1 for i, r in enumerate(ranked) if r["tune_id"] == seg.tune_id), None)
        if rank and rank > args.top:
            r = ranked[rank - 1]
            print(f"     ... truth is at rank {rank} with score {r['score']:.4f}")
        elif rank is None:
            print("     ... truth is not in the top 40 at all")

        expects = sequence.next_distribution(previous_truth)
        print(f"\n  4. EXPECTED after "
              f"{names.get(previous_truth) or 'the start of a set'}:")
        if expects:
            for t, p in sorted(expects.items(), key=lambda kv: -kv[1])[:args.top]:
                mark = " <- truth" if t == seg.tune_id else ""
                print(f"     {names.get(t) or t:<42} {p:.0%}{mark}")
        else:
            print("     nothing known; falls back to how often each tune is played at all")

        verdict = "CORRECT" if chosen == seg.tune_id else "WRONG"
        audio_pick = ranked[0]["name"] if ranked else None
        print(f"\n  5. DECIDED {names.get(chosen) or chosen}   [{verdict}]")
        if ranked and chosen != ranked[0]["tune_id"]:
            print(f"     the melody alone would have said {audio_pick}; "
                  f"the set changed its mind")
        print()
        previous_truth = seg.tune_id

    correct = sum(1 for (seg, *_), c in zip(traces, path) if c == seg.tune_id)
    print("=" * 78)
    print(f"{correct} of {len(group)} correct in this set")
    return 0


def _json_default(o):
    return json.dumps(o, default=str)
