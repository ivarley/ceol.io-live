"""Transcription, step two: frequencies to notes, notes to intervals.

Two small experts kept separate because they fail differently and you will
want to look at them separately. Note segmentation decides where one note
stops; the interval step throws away absolute pitch, which is what makes a
transcription comparable with a corpus written in whatever key its author
liked.
"""

import numpy as np

from lab.experts.base import Expert


def _median_filter(x, k):
    if k <= 1 or x.size == 0:
        return x
    pad = k // 2
    padded = np.pad(x, (pad, pad), mode="edge")
    out = np.empty_like(x)
    for i in range(x.size):
        out[i] = np.median(padded[i:i + k])
    return out


class Notes(Expert):
    """pitch_track -> note_events.

    Known weakness, and it is a real one for this music: a cut or a roll
    fragments one note into three, and two of the same pitch played in a row
    fuse into one long note, which silently deletes a zero from the interval
    sequence.
    """

    name = "notes"
    version = "1"
    consumes = ("pitch_track",)
    produces = ("note_events",)
    cost = 1.0

    @classmethod
    def defaults(cls):
        return {"sources": None, "min_note_ms": 60, "median_frames": 5, "min_voiced": 0.5}

    def process(self, view, window):
        out = []
        for track in view.new("pitch_track"):
            src = track.payload.get("source")
            if self.params["sources"] and src not in self.params["sources"]:
                continue
            notes = self._segment(track.payload)
            if not notes:
                continue
            out.append(self.obs(
                "note_events", track.t_start_ms, track.t_end_ms,
                {"source": src, "notes": notes}, inputs=[track.obs_id]))
        return out

    def _segment(self, payload):
        import librosa

        times = np.asarray(payload.get("times_ms") or [], dtype=float)
        f0 = np.asarray(payload.get("f0_hz") or [], dtype=float)
        voiced = np.asarray(payload.get("voiced_prob") or [], dtype=float)
        if f0.size == 0:
            return []
        keep = voiced >= self.params["min_voiced"]
        if not np.any(keep):
            return []
        midi = np.full(f0.shape, np.nan)
        midi[keep] = np.round(librosa.hz_to_midi(f0[keep]))
        smoothed = midi.copy()
        valid = np.isfinite(midi)
        if np.any(valid):
            smoothed[valid] = _median_filter(midi[valid], int(self.params["median_frames"]))
        notes = []
        start = None
        current = None
        for i in range(smoothed.size + 1):
            value = smoothed[i] if i < smoothed.size else np.nan
            if current is not None and (not np.isfinite(value) or value != current):
                t0, t1 = times[start], times[i - 1] if i - 1 < times.size else times[-1]
                span = (times[i] - t0) if i < times.size else (t1 - t0)
                if span >= self.params["min_note_ms"]:
                    conf = float(np.mean(voiced[start:i])) if i > start else 0.0
                    notes.append({"t0_ms": int(t0), "t1_ms": int(t0 + span),
                                  "midi": int(current), "conf": round(conf, 3)})
                current, start = None, None
            if np.isfinite(value) and current is None:
                current, start = value, i
        return notes


class Intervals(Expert):
    """note_events -> interval_sequence over a trailing run of notes.

    Trailing rather than per-window: what the matcher wants is "the last forty
    notes", which is a musical amount of context, not a temporal one.

    Known weakness: one inserted or dropped note shifts exactly one interval,
    which n-gram voting tolerates and edit distance would not.
    """

    name = "intervals"
    version = "1"
    consumes = ("note_events",)
    produces = ("interval_sequence",)
    cost = 1.0

    @classmethod
    def defaults(cls):
        return {"window_notes": 48, "clip": 12, "max_gap_ms": 1500, "min_notes": 8,
                "fold_octaves": True}

    def setup(self):
        self._by_source = {}

    def process(self, view, window):
        out = []
        for ev in view.new("note_events"):
            src = ev.payload.get("source") or "?"
            buf = self._by_source.setdefault(src, [])
            known = {n["t0_ms"] for n in buf}
            for n in ev.payload.get("notes", []):
                if n["t0_ms"] not in known:   # windows overlap; notes repeat
                    buf.append(n)
            buf.sort(key=lambda n: n["t0_ms"])
            keep = int(self.params["window_notes"])
            if len(buf) > keep:
                del buf[:-keep]
            if len(buf) < self.params["min_notes"]:
                continue
            from lab.frontends.segmentation import intervals_from_notes

            intervals = intervals_from_notes(
                buf, clip=self.params["clip"], max_gap_ms=self.params["max_gap_ms"],
                fold=self.params["fold_octaves"])
            starts = [n["t0_ms"] for n in buf[:-1]]
            out.append(self.obs(
                "interval_sequence", buf[0]["t0_ms"], buf[-1]["t1_ms"],
                {"source": src, "intervals": intervals, "note_t0_ms": starts, "n_notes": len(buf)},
                inputs=[ev.obs_id]))
        return out
