"""interval_sequence -> tune_match: vote over the corpus index.

The symbolic back end. The index is loaded once per run against whichever
candidate set the config names, and its file hash goes into the run's
provenance, because a silently rebuilt index makes two runs incomparable.

Known weakness: five intervals is a short phrase, and a scale run appears in
thousands of tunes. The idf weighting damps that but does not remove it, and
nothing here uses rhythm or tempo at all, which is a large amount of thrown
away evidence.
"""

from lab.experts.base import Expert


class Matcher(Expert):
    name = "matcher"
    version = "1"
    consumes = ("interval_sequence",)
    produces = ("tune_match",)
    cost = 2.0

    @classmethod
    def defaults(cls):
        # n=6 over the folded index: measured on all 503 segments, folding
        # takes top-1 from 0.137 to 0.338 because a transcription of a room
        # gets the note names right and the octave wrong.
        return {"candidate_set": "repertoire", "n": 6, "top_k": 20,
                "fold_octaves": True, "recording_id": None,
                # Look the eighth-note reading up too, when the interval
                # expert provides one, and fuse the two rankings by score.
                # The two are wrong about different tunes -- one about
                # articulation, the other about tempo -- which is the only
                # condition under which fusing opinions is worth anything.
                "eighths": True, "fuse_depth": 40}

    def setup(self):
        from lab.corpus.index import Index

        self._index = Index.load(self.params["candidate_set"], n=self.params["n"],
                                 fold_octaves=self.params["fold_octaves"])
        self._eighths_index = None
        if self.params["eighths"]:
            self._eighths_index = Index.load(
                self.params["candidate_set"], n=self.params["n"],
                fold_octaves=self.params["fold_octaves"], particalized=True)
        self.index_meta = {"file": self._index.meta.get("file"), "sha1": self._index.meta.get("sha1"),
                           "n_tunes": self._index.n_tunes}

    def process(self, view, window):
        out = []
        for seq in view.new("interval_sequence"):
            ranked = self.rank(seq.payload)
            if not ranked:
                continue
            out.append(self.obs(
                "tune_match", seq.t_start_ms, seq.t_end_ms,
                {"source": seq.payload.get("source"),
                 "candidates": [
                     {"tune_id": r["tune_id"], "setting_id": r["setting_id"], "name": r["name"],
                      "score": round(r["score"], 5), "coverage": round(r["coverage"], 5),
                      "hits": r["hits"], "n_grams_queried": r["n_grams_queried"]}
                     for r in ranked],
                 "index_sha1": self.index_meta.get("sha1")},
                inputs=[seq.obs_id]))
        return out

    def rank(self, payload):
        """The plain reading, fused with the eighth-note one when there is one.

        The same `fuse` the bench uses, so the two loops cannot drift apart on
        how the readings are combined.
        """
        intervals = payload.get("intervals") or []
        eighths = payload.get("intervals_eighths")
        if self._eighths_index is None or not eighths:
            return self._index.lookup(intervals, top_k=self.params["top_k"])
        from lab.bench.retrieval import fuse

        depth = max(self.params["top_k"], self.params["fuse_depth"])
        plain = self._index.lookup(intervals, top_k=depth)
        heard = self._eighths_index.lookup(eighths, top_k=depth)
        return fuse([plain, heard], method="sum")[:self.params["top_k"]]
