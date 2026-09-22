"""`lab board` — the observations themselves, with their provenance.

One line per observation in append order, summarised per type so a long run
is readable. `--json` prints the payloads when the summary is not enough.
"""

import json

import lab.env  # noqa: F401
from lab.audio.chunks import fmt_ms, parse_range
from lab.board.board import Board


def add_parser(sub):
    p = sub.add_parser("board", help="dump a run's observations")
    p.add_argument("run_id")
    p.add_argument("--type", dest="types", help="comma-separated observation types")
    p.add_argument("--range", dest="time_range", help="mm:ss-mm:ss")
    p.add_argument("--expert")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=main)


def summarise(o):
    p = o.payload
    t = o.type
    if t == "audio_chunk":
        return f"{p.get('n_samples')} samples @ {p.get('sr')}Hz"
    if t == "music_activity":
        return f"score {p.get('score', 0):.2f} {'music' if p.get('is_music') else 'quiet'}"
    if t == "boundary":
        return (f"at {fmt_ms(p.get('t_ms'))} strength {p.get('strength') or 0:.2f} "
                f"({p.get('kind')}, {p.get('latency_ms', 0) / 1000:.0f}s late)")
    if t == "pitch_track":
        f0 = p.get("f0_hz") or []
        voiced = p.get("voiced_prob") or []
        med = sorted(f0)[len(f0) // 2] if f0 else 0
        return (f"{len(f0)} frames, median {med:.0f}Hz, "
                f"voiced {100 * sum(1 for v in voiced if v >= 0.5) / max(1, len(voiced)):.0f}%")
    if t == "note_events":
        from lab.corpus.abc_pitch import to_abc_letters

        notes = p.get("notes") or []
        head = to_abc_letters([n["midi"] for n in notes[:12]])
        return f"{len(notes)} notes: {head}{' ...' if len(notes) > 12 else ''}"
    if t == "interval_sequence":
        iv = p.get("intervals") or []
        return f"{p.get('n_notes')} notes -> {len(iv)} intervals {iv[:10]}"
    if t == "tune_match":
        cands = p.get("candidates") or []
        return " | ".join(f"{c['name']} {c['score']:.2f}" for c in cands[:3]) or "nothing"
    if t == "tune_prior":
        b = p.get("basis") or {}
        return f"repertoire {b.get('repertoire')}, confirmed tonight {b.get('confirmed_tonight')}"
    if t == "hypothesis_update":
        ranked = p.get("ranked") or []
        top = ranked[0] if ranked else None
        return (f"{p.get('event')} {p.get('hyp_id')}  "
                + (f"{top['name']} {top['conf']:.2f}" if top else "nothing")
                + f"  (elapsed {p.get('elapsed_s')}s, hazard {p.get('hazard')})")
    if t == "scheduler_skip":
        return f"skipped {p.get('expert')}: {p.get('reason')}"
    return json.dumps(p)[:120]


def main(args):
    types = args.types.split(",") if args.types else None
    t0 = t1 = None
    if args.time_range:
        t0, t1 = parse_range(args.time_range)
    with Board() as board:
        rows = board.observations(args.run_id, types=types, t0=t0, t1=t1,
                                  expert=args.expert, limit=args.limit)
        if not rows:
            print("no observations match")
            return 0
        for o in rows:
            if args.json:
                print(json.dumps({
                    "obs_id": o.obs_id, "type": o.type, "window": [o.t_start_ms, o.t_end_ms],
                    "clock_ms": o.clock_ms, "expert": f"{o.expert}@{o.expert_version}",
                    "inputs": o.inputs, "cost_ms": round(o.cost_ms, 1), "cached": o.cached,
                    "params": o.params, "payload": o.payload}))
                continue
            window = f"{fmt_ms(o.t_start_ms)}-{fmt_ms(o.t_end_ms)}"
            print(f"{o.obs_id:>6} {fmt_ms(o.clock_ms):>8} {window:<17} {o.type:<18} "
                  f"{o.expert}@{o.expert_version:<3} {o.cost_ms:>7.1f}ms"
                  f"{' cached' if o.cached else '       '} "
                  f"in={o.inputs if o.inputs else '-'}  {summarise(o)}")
    return 0
