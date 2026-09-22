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
        return {"candidate_set": "repertoire", "n": 5, "top_k": 20, "recording_id": None}

    def setup(self):
        from lab.corpus.index import Index

        self._index = Index.load(self.params["candidate_set"], n=self.params["n"])
        self.index_meta = {"file": self._index.meta.get("file"), "sha1": self._index.meta.get("sha1"),
                           "n_tunes": self._index.n_tunes}

    def process(self, view, window):
        out = []
        for seq in view.new("interval_sequence"):
            intervals = seq.payload.get("intervals") or []
            ranked = self._index.lookup(intervals, top_k=self.params["top_k"])
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
