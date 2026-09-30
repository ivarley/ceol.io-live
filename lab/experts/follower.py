"""Is this still the same tune? The change-detection bench's decoder, live.

Replaces the matcher and the assembler. Every `hop` it takes the notes the
`notes` expert has posted over the trailing `pool_ms`, per source, drops the
ones outside the key and its modal neighbour (the same `drop_out_of_key` the
front ends call, over the same span the bench uses), and hands them to the
bench's own `ChunkScorer` and `Decoder` (`lab.bench.stream`): a pool of
candidates from the index, each aligned against the latest `window_ms`, and
one step of the causal decoder over every tune plus "not a tune".

What it displays is written as the assembler writes it, so the harness,
`lab eval`, `lab timeline` and `lab display` read it unchanged: a new tune
opens a hypothesis, a different tune supersedes it, "not a tune" withdraws
it (nothing on display), and each step that keeps the tune is an update.

Known weakness: it hears notes only once the `notes` expert has settled
them, about a second behind the clock, and the neural trackers' windows add
their own delay; the bench cut notes from tracks that were complete to the
chunk's end. The difference is what this expert's board runs measure.
"""

from lab.experts.base import Expert, WindowSpec


class Follower(Expert):
    name = "follower"
    version = "1"
    consumes = ("note_events",)
    produces = ("hypothesis_update",)
    cost = 2.0
    window = WindowSpec(length_ms=24000, hop_ms=4000, warmup=True)

    @classmethod
    def defaults(cls):
        from lab.bench.stream import Decoder

        d = Decoder()
        return {"sources": None, "candidate_set": "repertoire", "n": 6, "fold_octaves": True,
                "window_ms": 6000, "pool_ms": 24000, "pool_top": 100, "keep": 6,
                "out_of_key_drop": "pair", "ranked_k": 5,
                "lam": d.lam, "tau": d.tau, "p_switch": d.p_switch, "p_none": d.p_none}

    def setup(self):
        from lab.bench.retrieval import Aligner
        from lab.bench.stream import ChunkScorer, Decoder
        from lab.corpus.index import Index

        p = self.params
        self.index = Index.load(p["candidate_set"], n=p["n"], fold_octaves=p["fold_octaves"])
        aligner = Aligner(reading="notes", mode="replace", shortlist=10 ** 6,
                          candidate_set=p["candidate_set"])
        self.scorer = ChunkScorer(self.index, aligner, window_ms=p["window_ms"],
                                  pool_top=p["pool_top"], keep=p["keep"])
        self.decoder = Decoder(lam=p["lam"], tau=p["tau"], p_switch=p["p_switch"],
                               p_none=p["p_none"])
        self.decoder.reset()
        self._notes = {}          # source -> notes, by start time
        self._showing = None      # tune id on display, or None
        self._hyp_id = None
        self._counter = 0

    def _ingest(self, view, t):
        for ev in view.new("note_events"):
            src = ev.payload.get("source") or "?"
            if self.params["sources"] and src not in self.params["sources"]:
                continue
            buf = self._notes.setdefault(src, [])
            known = {n["t0_ms"] for n in buf}
            buf.extend(n for n in ev.payload.get("notes", []) if n["t0_ms"] not in known)
            buf.sort(key=lambda n: n["t0_ms"])
        horizon = t - int(self.params["pool_ms"])
        for src, buf in self._notes.items():
            self._notes[src] = [n for n in buf if n["t0_ms"] >= horizon]

    def _context(self, t):
        from lab.analysis.key import drop_out_of_key

        order = self.params["sources"] or sorted(self._notes)
        out = {}
        for src in order:
            ctx = [n for n in self._notes.get(src, []) if n["t0_ms"] < t]
            out[src] = drop_out_of_key(ctx, self.params["out_of_key_drop"]) if ctx else []
        return out

    def process(self, view, window):
        t = window.t_end_ms
        self._ingest(view, t)
        chunk = self.scorer.score(t, self._context(t))
        state = self.decoder.step(chunk)
        from lab.bench.stream import NONE

        ranked = [{"tune_id": int(tid), "name": self.index.tune_names.get(tid), "conf": round(p, 4)}
                  for tid, p in self.decoder.belief(self.params["ranked_k"] + 1) if tid != NONE]
        ranked = ranked[:self.params["ranked_k"]]
        clock = window.clock_ms
        out = []
        now = None if state == NONE else int(state)
        if now != self._showing:
            if self._showing is not None and now is None:
                out.append(self._write(view, clock, "withdrawn", ranked, t))
                view.board.close_hypothesis(self._hyp_id, "withdrawn", t, clock)
                self._hyp_id = None
            elif self._showing is not None:
                old = self._hyp_id
                out.append(self._write(view, clock, "superseded", ranked, t))
                out.extend(self._open(view, clock, ranked, t, "rival"))
                view.board.close_hypothesis(old, "superseded", t, clock, superseded_by=self._hyp_id)
            else:
                out.extend(self._open(view, clock, ranked, t, "first_match"))
            self._showing = now
        elif now is not None:
            out.append(self._write(view, clock, "updated", ranked, t))
        return out

    def _open(self, view, clock, ranked, t, opened_by):
        self._counter += 1
        self._hyp_id = f"{view.run_id}:{self._counter}"
        start = max(0, t - int(self.params["window_ms"]))
        view.board.open_hypothesis(view.run_id, self._hyp_id, start, clock, opened_by)
        return [self._write(view, clock, "proposed", ranked, t)]

    def _write(self, view, clock, event, ranked, t):
        # the decoder's most believed tune leads `ranked`, and it is the one
        # displayed, so the harness reads the display from ranked[0]
        obs = self.obs("hypothesis_update", max(0, t - int(self.params["window_ms"])), t,
                       {"hyp_id": self._hyp_id, "event": event, "ranked": ranked})
        view.note_now(obs)
        view.board.add_hypothesis_event(view.run_id, self._hyp_id, clock, event, ranked, obs.obs_id)
        return obs
