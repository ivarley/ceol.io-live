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
        # `edge_margin_ms`: stay back from the trailing edge of the tracker's
        # window. The last note there is cut off by the window rather than by
        # the player, and the smoothing has nothing to its right, so notes
        # harvested from the edge are both fewer and worse. Harvesting the
        # settled middle instead cost a second of latency and recovered the
        # note rate the bench gets from one long pass.
        return {"sources": None, "min_note_ms": 60, "median_frames": 5,
                "min_voiced": 0.2, "edge_margin_ms": 1200}

    def setup(self):
        self._emitted_to = {}

    def process(self, view, window):
        out = []
        for track in view.new("pitch_track"):
            src = track.payload.get("source")
            if self.params["sources"] and src not in self.params["sources"]:
                continue
            notes = self._segment(track.payload)
            if not notes:
                continue
            # A pitch expert reads long windows on a short hop, so every
            # stretch of audio is transcribed several times over. Emitting all
            # of it put near-duplicates of the same phrase into the interval
            # sequence - not exact duplicates, because each window segments
            # the notes slightly differently, so they could not be removed
            # later either. The board matched nothing while the bench matched
            # the same audio correctly, and this was the difference.
            since = self._emitted_to.get(src, -1)
            settled = track.t_end_ms - int(self.params["edge_margin_ms"])
            fresh = [n for n in notes if since < n["t0_ms"] and n["t1_ms"] <= settled]
            if not fresh:
                continue
            self._emitted_to[src] = max(n["t0_ms"] for n in fresh)
            out.append(self.obs(
                "note_events", fresh[0]["t0_ms"], track.t_end_ms,
                {"source": src, "notes": fresh}, inputs=[track.obs_id]))
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
        # How much of the tune the matcher gets to see, and the single
        # strongest lever measured on the bench: 10s of audio scores 0.12
        # top-1, 30s scores 0.34, 120s scores 0.49. The old 48-note window was
        # about eight seconds, which is the worst point on that curve, and it
        # is why the ensemble scored zero while the bench scored 0.47.
        #
        # Bounded by time rather than by count, because the note rate varies
        # with the tune and with how well the tracker is doing.
        return {"window_ms": 120000, "window_notes": 900, "clip": 12,
                "max_gap_ms": 1500, "min_notes": 12, "fold_octaves": True}

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
            horizon = ev.t_end_ms - int(self.params["window_ms"])
            while buf and buf[0]["t1_ms"] < horizon:
                buf.pop(0)
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
