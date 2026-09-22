"""Ground truth, and the tasks cut from it.

One module owns the reading of a manifest into labels, because every score in
the lab — bench and eval alike — has to agree about what the corpus claims.
The rules, and why:

**An explicit end means the music stopped.** An implicit end means "the next
tune starts here" and says nothing about music stopping (spec 050). So the only
labelled silence in the corpus is the gap between an explicit end and the next
start. There is about five hours of it, which is plenty.

**Guard bands.** A human marking against a moving playhead is accurate to about
a second, and the operator's `M` lands after the tune has begun as often as
before. So GUARD_MS either side of every boundary is excluded from the
music-activity labels rather than being asserted as one thing or the other.
Boundary labels are unaffected: their whole point is a tolerance.

**Unmarked set ends are a data error, not a category.** If a tune's end is
implicit but the log says a set ended there, the operator forgot to type an
end and the segment has swallowed the chatter after it. That is fixable at
source, so this module *warns* (naming the segment) and excludes the tail,
rather than silently compensating. The warning firing means the corpus needs a
fix, and a quiet fallback would hide that.

**The log is not evidence.** `record_type` and the night's order are read here,
in ground-truth code, and nowhere else. No expert ever sees them.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from lab import paths
from lab.bench.features import GRID_MS

GUARD_MS = 2000          # excluded either side of a boundary in activity labels
BOUNDARY_TOL_MS = 3000   # default "near enough" for the boundary task
MIN_EVAL_SEGMENT_MS = 10000    # shorter segments are marks, not tunes
SETEND_TRUST_MS = 30000  # after an unmarked set end's start, music is certain this long
IDENT_CAP_MS = 600000    # hard cap on any segment for identification scoring


@dataclass
class Segment:
    """One placed tune, with everything the harness needs to judge it."""

    segment_id: int
    session_instance_tune_id: int
    tune_id: Optional[int]
    name: str
    tune_type: Optional[str]
    start_ms: int
    end_ms: int                 # resolved
    end_is_explicit: bool
    ends_a_set: bool            # the log says a set break follows this tune
    unmarked_set_end: bool      # implicit end + ends a set = the data error above
    overlaps_next: bool
    capped: bool = False
    evaluated: bool = True
    skip_reason: Optional[str] = None

    @property
    def duration_ms(self):
        return self.end_ms - self.start_ms

    @property
    def end_is_trustworthy(self):
        """Is `end_ms` a real statement about when this tune stopped?"""
        return self.end_is_explicit or not self.unmarked_set_end


@dataclass
class GroundTruth:
    recording_id: int
    duration_ms: int
    label: str
    session_id: int
    date: str
    segments: List[Segment]
    warnings: List[str] = field(default_factory=list)

    # -- boundaries -------------------------------------------------------

    def boundaries(self):
        """Every instant the corpus asserts a change: starts, and explicit ends.

        An implicit mid-set end is the next segment's start, so it is already
        here once; adding it again would double-count. An unmarked set end is
        not a known instant at all.
        """
        out = []
        for s in self.segments:
            out.append({"t_ms": s.start_ms, "kind": "start", "segment_id": s.segment_id})
            if s.end_is_explicit:
                out.append({"t_ms": s.end_ms, "kind": "end", "segment_id": s.segment_id})
        out.sort(key=lambda b: b["t_ms"])
        # two marks within a guard band are one boundary
        merged = []
        for b in out:
            if merged and b["t_ms"] - merged[-1]["t_ms"] < GUARD_MS // 2:
                continue
            merged.append(b)
        return merged

    # -- music activity ---------------------------------------------------

    def activity_intervals(self):
        """[(t0, t1, 1|0)] over regions the corpus can vouch for.

        Everything not returned is excluded: before the first tune, after the
        last, the tail of an unmarked set end, and a guard band around every
        boundary.
        """
        out = []
        segs = sorted(self.segments, key=lambda s: s.start_ms)
        for i, s in enumerate(segs):
            nxt = segs[i + 1] if i + 1 < len(segs) else None
            if s.unmarked_set_end:
                # certain music for a while after the mark; unknown thereafter
                out.append((s.start_ms + GUARD_MS, min(s.start_ms + SETEND_TRUST_MS, s.end_ms), 1))
            else:
                end = s.end_ms
                if nxt is not None:
                    end = min(end, nxt.start_ms)
                out.append((s.start_ms + GUARD_MS, end - GUARD_MS, 1))
            if s.end_is_explicit and nxt is not None and not s.unmarked_set_end:
                gap0, gap1 = s.end_ms + GUARD_MS, nxt.start_ms - GUARD_MS
                if gap1 > gap0:
                    out.append((gap0, gap1, 0))
        return [(int(a), int(b), v) for a, b, v in out if b > a]

    # -- arrays on the feature grid --------------------------------------

    def activity_labels(self, n_frames):
        """(y, mask) on the 100 ms grid. mask=False means "do not score here"."""
        y = np.zeros(n_frames, dtype=np.int8)
        mask = np.zeros(n_frames, dtype=bool)
        for t0, t1, v in self.activity_intervals():
            a = max(0, t0 // GRID_MS)
            b = min(n_frames, -(-t1 // GRID_MS))
            if b > a:
                y[a:b] = v
                mask[a:b] = True
        return y, mask

    def boundary_labels(self, n_frames, tol_ms=BOUNDARY_TOL_MS):
        """(y, mask): 1 within tol of a boundary. Everything is scored."""
        y = np.zeros(n_frames, dtype=np.int8)
        half = max(1, tol_ms // GRID_MS)
        for b in self.boundaries():
            c = b["t_ms"] // GRID_MS
            y[max(0, c - half):min(n_frames, c + half + 1)] = 1
        return y, np.ones(n_frames, dtype=bool)

    # -- identification ---------------------------------------------------

    def eval_segments(self, range_ms=None):
        """Segments worth scoring identification over, each with its verdict."""
        out = []
        for s in self.segments:
            s = Segment(**{**s.__dict__})
            if s.tune_id is None:
                s.evaluated, s.skip_reason = False, "no_tune_id"
            elif s.duration_ms < MIN_EVAL_SEGMENT_MS:
                s.evaluated, s.skip_reason = False, "too_short"
            if s.unmarked_set_end or s.duration_ms > IDENT_CAP_MS:
                s.end_ms = min(s.end_ms, s.start_ms + IDENT_CAP_MS)
                s.capped = True
            if range_ms is not None:
                r0, r1 = range_ms
                if s.end_ms <= r0 or s.start_ms >= r1:
                    s.evaluated, s.skip_reason = False, "outside_range"
                elif s.start_ms < r0 or s.end_ms > r1:
                    s.start_ms, s.end_ms = max(s.start_ms, r0), min(s.end_ms, r1)
                    s.skip_reason = "partial"
            out.append(s)
        return out


def load_ground_truth(recording_id) -> GroundTruth:
    with open(paths.manifest_path(recording_id)) as f:
        manifest = json.load(f)
    rec = manifest["recording"]

    # the log's set breaks: which tunes are followed by one
    ends_a_set = set()
    order = manifest.get("logged_order") or []
    for i, row in enumerate(order):
        if row.get("record_type") == "break":
            continue
        nxt = next((r for r in order[i + 1:] if True), None)
        if nxt is not None and nxt.get("record_type") == "break":
            ends_a_set.add(row["session_instance_tune_id"])
    if not order:
        ends_a_set = None  # unknown; the cross-check cannot run

    raw = sorted(manifest["segments"], key=lambda s: s["start_ms"])
    segments, warnings = [], []
    for i, s in enumerate(raw):
        nxt = raw[i + 1] if i + 1 < len(raw) else None
        sit = s["session_instance_tune_id"]
        ends_set = bool(ends_a_set and sit in ends_a_set)
        unmarked = (not s["end_is_explicit"]) and ends_set
        end_ms = int(s["resolved_end_ms"])
        overlaps = bool(nxt and end_ms > int(nxt["start_ms"]))
        if overlaps:
            warnings.append(
                f"recording {recording_id}: '{s['display_name']}' at {s['start_ms']}ms ends "
                f"{end_ms - int(nxt['start_ms'])}ms after the next tune starts; clamped")
            end_ms = int(nxt["start_ms"])
        if unmarked:
            warnings.append(
                f"recording {recording_id}: '{s['display_name']}' at {s['start_ms']}ms has no explicit end "
                f"but the log says a set ends there ({(end_ms - int(s['start_ms'])) / 60000:.1f} min). "
                f"Type an end in the segmenter; until then its tail is excluded from labels.")
        segments.append(Segment(
            segment_id=int(s["recording_tune_segment_id"]),
            session_instance_tune_id=sit,
            tune_id=s["tune_id"],
            name=s["display_name"],
            tune_type=s.get("tune_type"),
            start_ms=int(s["start_ms"]),
            end_ms=end_ms,
            end_is_explicit=bool(s["end_is_explicit"]),
            ends_a_set=ends_set,
            unmarked_set_end=unmarked,
            overlaps_next=overlaps,
        ))
    return GroundTruth(
        recording_id=int(rec["recording_id"]),
        duration_ms=int(rec["duration_ms"]),
        label=rec.get("label") or f"recording {recording_id}",
        session_id=rec["session_id"],
        date=str(rec.get("date"))[:10],
        segments=segments,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class Task:
    """A named target on the feature grid, plus how to score a prediction."""

    name = ""
    needs_threshold = True

    def labels(self, gt: GroundTruth, n_frames: int):
        raise NotImplementedError

    def score(self, y, mask, scores, gt=None):
        raise NotImplementedError


class MusicActivityTask(Task):
    name = "music_activity"

    def labels(self, gt, n_frames):
        return gt.activity_labels(n_frames)

    def score(self, y, mask, scores, gt=None, threshold=None):
        from lab.bench.score import best_threshold, binary_metrics

        y, scores = y[mask], scores[mask]
        if y.size == 0:
            return {"n": 0}
        thr = threshold if threshold is not None else best_threshold(y, scores)
        m = binary_metrics(y, scores >= thr)
        m.update({"n": int(y.size), "threshold": float(thr),
                  "positive_rate": float(y.mean())})
        return m


class BoundaryTask(Task):
    name = "boundary"

    def __init__(self, tol_ms=BOUNDARY_TOL_MS):
        self.tol_ms = tol_ms

    def labels(self, gt, n_frames):
        return gt.boundary_labels(n_frames, tol_ms=self.tol_ms)

    def score(self, y, mask, scores, gt=None, threshold=None):
        """Peak-picked boundaries against the corpus's, at a tolerance.

        Frame accuracy would be meaningless here (boundaries are ~1% of
        frames), so this picks peaks and matches them one-to-one.
        """
        from lab.bench.score import best_threshold, match_events, peak_times_ms

        if gt is None:
            return {"n": 0}
        truth = [b["t_ms"] for b in gt.boundaries()]
        thr = threshold if threshold is not None else best_threshold(y, scores, minimum=0.0)
        predicted = peak_times_ms(scores, threshold=thr, min_distance_ms=self.tol_ms * 2)
        matched, fp, fn, errors = match_events(truth, predicted, tol_ms=self.tol_ms)
        hours = max(1e-9, (scores.size * GRID_MS) / 3600000.0)
        recall = matched / len(truth) if truth else 0.0
        precision = matched / len(predicted) if predicted else 0.0
        f1 = (2 * recall * precision / (recall + precision)) if (recall + precision) else 0.0
        return {
            "n_true": len(truth), "n_predicted": len(predicted), "matched": matched,
            "recall": recall, "precision": precision, "f1": f1,
            "false_per_hour": fp / hours, "missed": fn,
            "median_abs_error_ms": float(np.median(np.abs(errors))) if errors else None,
            "threshold": float(thr), "tol_ms": self.tol_ms,
        }


TASKS = {
    "music_activity": MusicActivityTask,
    "boundary": BoundaryTask,
}


def get_task(name, **kw):
    if name not in TASKS:
        raise SystemExit(f"unknown task '{name}'; have {sorted(TASKS)}")
    return TASKS[name](**kw)
