"""Transcription, step two: frequencies to notes, notes to intervals.

Two small experts kept separate because they fail differently and you will
want to look at them separately. Note segmentation decides where one note
stops; the interval step throws away absolute pitch, which is what makes a
transcription comparable with a corpus written in whatever key its author
liked.
"""


from lab.experts.base import Expert
from lab.frontends.segmentation import notes_from_pitch


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
                "min_voiced": 0.2, "edge_margin_ms": 1200, "fold_pitch_classes": True}

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
        """Delegates to the one implementation, shared with the front ends.

        This used to be a second copy of the same logic, and the copies drifted:
        the front end learned to fold pitch to classes before cutting notes,
        worth thirteen points on the bench, and the board did not. A test
        already checks the two agree; having one of them is better.
        """
        return notes_from_pitch(
            payload.get("times_ms") or [], payload.get("f0_hz") or [],
            payload.get("voiced_prob") or [],
            min_note_ms=self.params["min_note_ms"],
            median_frames=self.params["median_frames"],
            min_voiced=self.params["min_voiced"],
            fold_pitch_classes=self.params["fold_pitch_classes"])


class Intervals(Expert):
    """note_events -> interval_sequence over a trailing run of notes.

    Trailing rather than per-window: what the matcher wants is "the last forty
    notes", which is a musical amount of context, not a temporal one.

    Known weakness: one inserted or dropped note shifts exactly one interval,
    which n-gram voting tolerates and edit distance would not.
    """

    name = "intervals"
    version = "1"
    consumes = ("note_events", "boundary")
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
                "max_gap_ms": 1500, "min_notes": 12, "fold_octaves": True,
                # OFF by default, and measured: clearing the window at a
                # detected boundary is right in principle and harmful in
                # practice, because the detector's precision is 0.26, so three
                # resets in four throw away good context. Turning it on took
                # two nights from 29.6% and 40.5% to 19.8% and 27.0%, with
                # flips a segment going from about 5 to 14. It belongs with a
                # boundary source worth trusting, which is why the oracle
                # config turns it on and the baseline does not.
                "reset_on_boundary": False}

    def setup(self):
        self._by_source = {}

    def process(self, view, window):
        out = []
        if self.params["reset_on_boundary"]:
            for b in view.new("boundary"):
                # everything before a tune change is the previous tune, and
                # keeping it in the window is worse than having no context
                at = b.payload.get("t_ms", window.t_end_ms)
                for src, buf in self._by_source.items():
                    self._by_source[src] = [n for n in buf if n["t0_ms"] >= at]
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
