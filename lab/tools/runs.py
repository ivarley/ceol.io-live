"""`lab runs` — what has been run."""

import json

import lab.env  # noqa: F401
from lab.board.board import Board


def add_parser(sub):
    p = sub.add_parser("runs", help="list runs")
    p.add_argument("--recording", type=int)
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=main)


def main(args):
    with Board() as board:
        rows = board.list_runs(recording_id=args.recording, limit=args.limit)
        if not rows:
            print("no runs yet")
            return 0
        print(f"{'run':<34} {'name':<12} {'rec':>4} {'status':<8} {'audio':>7} {'wall':>7}  selection")
        for r in rows:
            cfg = json.loads(r["config_json"])
            sel = cfg.get("selection") or {}
            audio = f"{(r['audio_ms'] or 0) / 60000:.1f}m"
            wall = f"{(r['wall_ms'] or 0) / 1000:.0f}s"
            parent = f"  (from {r['parent_run_id']})" if r["parent_run_id"] else ""
            print(f"{r['run_id']:<34} {r['name']:<12} {r['recording_id']:>4} {r['status']:<8} "
                  f"{audio:>7} {wall:>7}  {sel.get('kind', '?')} {sel.get('spec') or ''}{parent}")
    return 0
