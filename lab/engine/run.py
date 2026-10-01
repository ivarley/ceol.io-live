"""`lab run` — replay a recording through the board with a named config.

The loop, and the two things it is careful about:

**The clock is the chunk, not the wall.** Nothing in here reads real time to
decide anything. An arrival chunk advances the clock; audio and features are
served only up to it. That is what makes a replay and a live stream the same
code, and what makes measured latency mean something.

**Windows are the expert's business.** A windowed expert runs once for every
grid window that has become complete, which may be none on a given chunk or
several after a gap. An event-driven expert runs when something it consumes
is new. Either way, at most once per chunk — which bounds the loop even
though the type graph is allowed to contain feedback.
"""

import argparse
import json
import os
import sys
import time
import uuid

import lab.env  # noqa: F401
from lab import paths
from lab.audio.chunks import AudioStore, WavChunkSource, parse_range
from lab.audio.feature_store import FeatureStore
from lab.board.board import Board, BoardView, Observation
from lab.engine.registry import build_experts, topological_order
from lab.engine.scheduler import Scheduler
from lab.experts.base import Window


def add_parser(sub):
    p = sub.add_parser("run", help="replay a recording through the board")
    p.add_argument("--config", help="path to a run config json")
    p.add_argument("--from", dest="from_run", help="re-execute a stored run's config verbatim")
    p.add_argument("--recording", help="recording id, or 'all' for every prepared one")
    p.add_argument("--segments", help="segment numbers to replay, e.g. 5 or 5-6 (1-based, in time order)")
    p.add_argument("--range", dest="time_range", help="mm:ss-mm:ss or seconds")
    p.add_argument("--name", help="override the config's name")
    p.add_argument("--scratch", action="store_true", help="mark the run scratch (inspection only)")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=main)


def load_config(path):
    with open(path) as f:
        return json.load(f)


def resolve_range(manifest, segments=None, time_range=None, pad_ms=5000):
    """What slice of the night to replay, and why it was chosen.

    Padding before a segment matters: the recogniser has to have heard the
    tune start, and a segment that begins at the first sample of the replay
    gives it nothing to work with.
    """
    if time_range:
        t0, t1 = parse_range(time_range)
        return int(t0), int(t1), {"kind": "range", "spec": time_range}
    if segments:
        rows = sorted(manifest["segments"], key=lambda s: s["start_ms"])
        if "-" in str(segments):
            a, b = str(segments).split("-", 1)
            lo, hi = int(a), int(b)
        else:
            lo = hi = int(segments)
        if lo < 1 or hi > len(rows):
            raise SystemExit(f"segments {segments} out of range; this recording has {len(rows)}")
        chosen = rows[lo - 1:hi]
        t0 = max(0, int(chosen[0]["start_ms"]) - pad_ms)
        t1 = int(chosen[-1]["resolved_end_ms"]) + pad_ms
        return t0, t1, {"kind": "segments", "spec": str(segments),
                        "segment_ids": [int(s["recording_tune_segment_id"]) for s in chosen]}
    return 0, int(manifest["recording"]["duration_ms"]), {"kind": "whole", "spec": None}


def execute(config, recording_id, board=None, quiet=False, parent_run_id=None, status="running"):
    from lab.bench.features import Features
    from lab.bench.score import git_sha
    from lab import LAB_VERSION

    with open(paths.manifest_path(recording_id)) as f:
        manifest = json.load(f)

    wav = paths.wav_path(recording_id)
    if not os.path.exists(wav):
        raise SystemExit(f"recording {recording_id} is not prepared; run `lab prepare --recordings {recording_id}`")

    t0, t1, selection = resolve_range(
        manifest, config.get("segments"), config.get("range"))
    config = dict(config)
    config["recording_id"] = int(recording_id)
    config["selection"] = selection
    config["replay_ms"] = [t0, t1]

    experts = topological_order(build_experts(config))
    for e in experts:
        if e.name == "matcher" and getattr(e, "index_meta", None):
            config.setdefault("index", e.index_meta)

    own_board = board is None
    board = board or Board()
    run_id = f"{config.get('name', 'run')}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    board.create_run(run_id, config.get("name", "run"), recording_id, config,
                     git_sha=git_sha(), lab_version=LAB_VERSION, status=status,
                     parent_run_id=parent_run_id)

    store = AudioStore(wav)
    from lab.audio.prepare import wav_sha1

    view = BoardView(board, run_id, store, manifest, config, audio_sha1=wav_sha1(recording_id) or "")
    try:
        view.attach_features(FeatureStore(Features.load(recording_id)))
    except SystemExit:
        if any(getattr(e, "candidate_name", None) for e in experts):
            raise
    scheduler = Scheduler(config.get("scheduler"))

    chunk_ms = int(config.get("chunk_ms", 2000))
    source = WavChunkSource(store, start_ms=t0, end_ms=t1, chunk_ms=chunk_ms)
    produced_at = {e.name: set() for e in experts}
    started = time.time()
    n_obs = 0

    if not quiet:
        print(f"{run_id}: recording {recording_id}, {(t1 - t0) / 60000:.1f} min "
              f"({selection['kind']} {selection['spec'] or ''}), {len(experts)} experts, "
              f"chunk {chunk_ms}ms")

    try:
        for chunk in source:
            view.clock_ms = chunk.t_end_ms
            if view._feature_store is not None:
                view._feature_store.clock_ms = chunk.t_end_ms
            view._pending = []
            view._appended = set()
            chunk_obs = Observation(
                type="audio_chunk", t_start_ms=chunk.t_start_ms, t_end_ms=chunk.t_end_ms,
                payload={"sr": chunk.sr, "n_samples": int(chunk.samples.size)},
                expert="chunk_source", expert_version="1", params={"chunk_ms": chunk_ms})
            board.append(run_id, chunk_obs, clock_ms=chunk.t_end_ms)
            view._pending.append(chunk_obs)
            view._appended.add(id(chunk_obs))
            n_obs += 1

            dirty = {"audio_chunk"}
            ran = set()
            while dirty:
                newly = set()
                for expert in experts:
                    if expert.name in ran or not (set(expert.consumes) & dirty):
                        continue
                    windows = _windows_for(expert, view, chunk, t0, produced_at)
                    if windows is None:
                        ran.add(expert.name)
                        continue
                    decision = scheduler.should_run(expert, view, windows[-1])
                    if not decision.run:
                        skip = Observation(
                            type="scheduler_skip", t_start_ms=chunk.t_start_ms,
                            t_end_ms=chunk.t_end_ms,
                            payload={"expert": expert.name, "reason": decision.reason},
                            expert="scheduler", expert_version="1", params={})
                        board.append(run_id, skip, clock_ms=chunk.t_end_ms)
                        board.conn.commit()
                        n_obs += 1
                        ran.add(expert.name)
                        continue
                    view.begin_expert(expert.name)
                    high_water = max((o.obs_id or 0) for o in view._pending) if view._pending else 0
                    for w in windows:
                        t_call = time.time()
                        produced = expert.process(view, w) or []
                        cost = (time.time() - t_call) * 1000.0
                        share = cost / max(1, len(produced))
                        for obs in produced:
                            if not obs.cost_ms:
                                obs.cost_ms = share
                            if not view.was_appended(obs):
                                board.append(run_id, obs, clock_ms=chunk.t_end_ms)
                                # Commit now rather than at the end of the
                                # chunk. The write lock is taken by the first
                                # insert and held until commit, and the old
                                # placement held it through every expert's
                                # computation for the chunk -- pitch tracking
                                # included -- so parallel runs queued behind
                                # one another and ran one at a time. Measured:
                                # five of six runs at 0% CPU, waiting.
                                board.conn.commit()
                                view.note(obs)
                            n_obs += 1
                            newly.add(obs.type)
                            if obs.type == "boundary":
                                scheduler.note_boundary()
                    view.mark_seen(expert.name, high_water)
                    ran.add(expert.name)
                dirty = newly
            board.conn.commit()
        wall = int((time.time() - started) * 1000)
        board.finish_run(run_id, status="scratch" if status == "scratch" else "done",
                         audio_ms=t1 - t0, wall_ms=wall)
        if not quiet:
            print(f"{run_id}: {n_obs} observations, {wall / 1000:.1f}s wall for "
                  f"{(t1 - t0) / 60000:.1f} min audio ({(t1 - t0) / max(1, wall):.1f}x realtime)")
    except Exception as e:
        board.finish_run(run_id, status="failed", wall_ms=int((time.time() - started) * 1000),
                         error=f"{type(e).__name__}: {e}")
        raise
    finally:
        store.close()
        if own_board:
            board.close()
    return run_id


def _windows_for(expert, view, chunk, replay_start_ms, produced_at):
    """Which windows this expert owes on this chunk, or None if it owes none."""
    if expert.window is None:
        return [Window(chunk.t_start_ms, chunk.t_end_ms, view.clock_ms)]
    done = produced_at[expert.name]
    windows = [
        Window(a, b, view.clock_ms)
        for a, b in expert.window.windows_complete_by(view.clock_ms, start_ms=replay_start_ms)
        if b not in done
    ]
    if not windows:
        return None
    for w in windows:
        done.add(w.t_end_ms)
    return windows


def main(args):
    if args.from_run:
        with Board() as board:
            parent = board.get_run(args.from_run)
            config = json.loads(parent["config_json"])
            recording_id = parent["recording_id"]
        if args.name:
            config["name"] = args.name
        run_id = execute(config, recording_id, parent_run_id=args.from_run, quiet=args.quiet)
        print(f"re-executed {args.from_run} as {run_id}")
        return 0

    if not args.config:
        raise SystemExit("give --config <file> or --from <run_id>")
    config = load_config(args.config)
    if args.name:
        config["name"] = args.name
    if args.segments:
        config["segments"] = args.segments
    if args.time_range:
        config["range"] = args.time_range

    ids = (paths.prepared_recording_ids() if str(args.recording) == "all"
           else [int(args.recording)] if args.recording
           else [int(config["recording_id"])] if config.get("recording_id")
           else paths.prepared_recording_ids())
    if not ids:
        raise SystemExit("no prepared recordings; run `lab pull` then `lab prepare`")
    status = "scratch" if args.scratch else "running"
    last = None
    with Board() as board:
        for rid in ids:
            last = execute(config, rid, board=board, quiet=args.quiet, status=status)
    return 0 if last else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    sys.exit(main(parser.parse_args()))
