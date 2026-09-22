"""`lab bench pitch` — score a front end against pitch you labelled by hand.

Retrieval says whether the right tune came back; it cannot say what the
transcription got wrong. A note label can. Against a labelled segment a front
end has a frame-level accuracy, an octave-blind accuracy, and a recall of the
notes that were actually there, and those three separate the failures that
retrieval lumps together.

Scored over time rather than over notes, because two transcriptions that
disagree about where notes begin should still be comparable. Every 10ms of
labelled audio asks one question: what pitch is sounding, and did the front
end say so.

Needs labels, which come from `lab view`. With none it says so and stops.
"""

import json
import os
import time

import numpy as np

from lab import paths
from lab.audio.chunks import AudioStore
from lab.audio.prepare import wav_sha1
from lab.bench.retrieval import transcribe_segment
from lab.bench.score import BenchResult, NightResult, git_sha
from lab.board.board import Board
from lab.tools.viewer import ANNOTATIONS

GRID_S = 0.01


def load_annotations():
    out = []
    if not os.path.isdir(ANNOTATIONS):
        return out
    for name in sorted(os.listdir(ANNOTATIONS)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(ANNOTATIONS, name)) as f:
            record = json.load(f)
        if record.get("labels"):
            out.append(record)
    return out


def _to_grid(labels, duration_s):
    """Pitch per 10ms, or -1 where nothing was labelled."""
    n = max(1, int(round(duration_s / GRID_S)))
    grid = np.full(n, -1, dtype=np.int16)
    for v in labels:
        a = max(0, int(round(v["t0"] / GRID_S)))
        b = min(n, int(round(v["t1"] / GRID_S)))
        if b > a:
            grid[a:b] = int(v["midi"])
    return grid


def score_annotation(frontend, record, board=None):
    recording_id = record["recording_id"]
    t0 = int(record.get("t0_ms") or 0)
    duration_s = float(record.get("duration_s") or 0)
    if duration_s <= 0:
        return None
    truth = _to_grid(record["labels"], duration_s)
    labelled = truth >= 0
    if not labelled.any():
        return None

    store = AudioStore(paths.wav_path(recording_id))
    store.clock_ms = store.duration_ms
    sha = wav_sha1(recording_id) or ""
    notes, cost, _cached = transcribe_segment(
        frontend, store, sha, t0, t0 + int(duration_s * 1000), board=board)
    store.close()

    heard = np.full(truth.size, -1, dtype=np.int16)
    for nt in notes:
        a = max(0, int(round((nt["t0_ms"] - t0) / 1000.0 / GRID_S)))
        b = min(truth.size, int(round((nt["t1_ms"] - t0) / 1000.0 / GRID_S)))
        if b > a:
            heard[a:b] = int(nt["midi"])

    sel = labelled
    both = sel & (heard >= 0)
    exact = int(np.sum(both & (heard == truth)))
    octave = int(np.sum(both & (heard != truth) & (((heard - truth) % 12) == 0)))
    near = int(np.sum(both & (np.abs(heard.astype(int) - truth.astype(int)) <= 1)))
    total = int(np.sum(sel))
    return {
        "segment": record.get("tune_name"),
        "recording_id": recording_id,
        "labelled_s": total * GRID_S,
        "coverage": float(np.sum(both)) / total,        # did it say anything here
        "exact": exact / total,
        "octave_blind": (exact + octave) / total,
        "within_semitone": near / total,
        "octave_errors": octave / max(1, int(np.sum(both))),
        "cost_ms": cost,
        "f1": exact / total,
    }


def run_pitch(frontend, quiet=False):
    records = load_annotations()
    if not records:
        raise SystemExit(
            "no pitch labels yet. Open a segment with `lab view --recording N --segment K`, "
            "use accept and draw to mark what you actually hear, and save.")
    rows = []
    with Board() as board:
        for record in records:
            m = score_annotation(frontend, record, board=board)
            if m is None:
                continue
            rows.append(m)
            if not quiet:
                print(f"  r{m['recording_id']} {str(m['segment'])[:34]:<34} "
                      f"{m['labelled_s']:>5.0f}s labelled  exact {m['exact']:.3f}  "
                      f"octave-blind {m['octave_blind']:.3f}", flush=True)
    if not rows:
        raise SystemExit("labels found but none scorable (no duration recorded)")

    weights = np.array([r["labelled_s"] for r in rows], dtype=float)
    pooled = {k: float(np.average([r[k] for r in rows], weights=weights))
              for k in ("coverage", "exact", "octave_blind", "within_semitone", "octave_errors")}
    pooled.update({"segments": len(rows), "labelled_s": float(weights.sum()), "f1": pooled["exact"]})
    return BenchResult(
        task="pitch_accuracy", candidate=frontend.name, version=frontend.version,
        params=dict(frontend.params), features_version="audio", split="per-labelled-segment",
        nights=[NightResult(recording_id=r["recording_id"], label=str(r["segment"]), date="",
                            metrics=r, n_frames=int(r["labelled_s"] / GRID_S)) for r in rows],
        pooled=pooled, warnings=[], created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        git_sha=git_sha())


def format_pitch(result):
    p = result.pooled
    return "\n".join([
        f"{result.candidate} v{result.version} on pitch_accuracy  "
        f"[{p['segments']} labelled segments, {p['labelled_s']:.0f}s]",
        f"  said something          {p['coverage']:.3f} of labelled time",
        f"  exactly right           {p['exact']:.3f}",
        f"  right ignoring octave   {p['octave_blind']:.3f}",
        f"  within a semitone       {p['within_semitone']:.3f}",
        f"  of what it said, wrong octave  {p['octave_errors']:.3f}",
    ])
