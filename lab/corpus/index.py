"""`lab index` — an interval n-gram index over the ABC corpus.

The symbolic route's back end. Every setting's ABC becomes a pitch sequence,
then a sequence of semitone steps, then every run of n consecutive steps; those
n-grams are the postings. A transcription from audio produces the same kind of
n-grams, and matching is voting.

Intervals rather than pitches because a session plays in whatever key it plays
in and a transcriber's octave errors are common; the shape survives both.

Three candidate sets, chosen per run:

- `all` — every tune in the dump (~50k). The honest setting and the one the
  long tail needs.
- `repertoire` — the tunes a session is known to play (1,279 at B.D. Riley's).
  What the live system would use with the prior turned on.
- `eval_tunes` — only the tunes in the eval segments (274). Deliberately
  optimistic: it answers "does the matcher work at all" without the long tail's
  collisions, which is what you want when checking the plumbing.

The index records the parser version and the dump's date; a run records the
index file's hash. Nothing is comparable across a silent reindex.
"""

import argparse
import hashlib
import json
import math
import os
import pickle
import sys
import time
from collections import Counter, defaultdict

import lab.env  # noqa: F401
from lab import paths
from lab.corpus import abc_pitch
from lab.corpus.tunes_csv import iter_settings

DEFAULT_N = 5
INDEX_VERSION = "2"   # bump when the stored structure or the scoring changes


class Index:
    """Inverted index: interval n-gram -> the tunes whose settings contain it.

    Counting is per TUNE, never per setting. thesession.org holds up to dozens
    of settings for a popular tune and one for an obscure one, so a posting
    that lists settings makes "how many people have transcribed this" look
    like "how well does this match" — the first version of this scored
    Ballydesmond above a tune's own ABC because Ballydesmond has more
    settings. Document frequency is likewise a count of tunes.
    """

    def __init__(self, n=DEFAULT_N, candidate_set="all", fold_octaves=False):
        self.n = n
        self.candidate_set = candidate_set
        self.fold_octaves = fold_octaves
        self.postings = {}        # gram -> tuple of (tune_id, setting_id)
        self.df = {}              # gram -> number of distinct TUNES containing it
        self.tune_gram_count = {}  # tune_id -> distinct grams across its settings
        self.tune_names = {}      # tune_id -> name
        self.tune_types = {}      # tune_id -> type
        self.n_tunes = 0
        self.meta = {}

    # -- building ---------------------------------------------------------

    @classmethod
    def build(cls, settings, n=DEFAULT_N, candidate_set="all", progress_every=10000,
              fold_octaves=False):
        idx = cls(n=n, candidate_set=candidate_set, fold_octaves=fold_octaves)
        postings = defaultdict(set)
        parsed = failed = 0
        failures = []
        t0 = time.time()
        for i, s in enumerate(settings):
            if progress_every and i and i % progress_every == 0:
                print(f"  {i:>7} settings, {len(postings):>8} grams, {time.time() - t0:.0f}s", flush=True)
            idx.tune_names.setdefault(s.tune_id, s.name)
            idx.tune_types.setdefault(s.tune_id, s.tune_type)
            try:
                notes = abc_pitch.parse_abc(s.abc, key=s.mode, meter=s.meter)
                pitches = abc_pitch.pitch_sequence(notes)
                intervals = abc_pitch.interval_sequence(pitches, fold=fold_octaves)
                grams = abc_pitch.ngrams(intervals, n=n)
            except Exception as e:  # a bad setting must not lose the corpus
                failed += 1
                if len(failures) < 50:
                    failures.append({"tune_id": s.tune_id, "setting_id": s.setting_id, "error": str(e)[:200]})
                continue
            if not grams:
                failed += 1
                if len(failures) < 50:
                    failures.append({"tune_id": s.tune_id, "setting_id": s.setting_id, "error": "no n-grams"})
                continue
            parsed += 1
            for g in set(grams):  # once per setting: a repeated phrase is not more evidence
                postings[g].add((s.tune_id, s.setting_id))
        idx.postings = {g: tuple(sorted(v)) for g, v in postings.items()}
        idx.df = {g: len({t for t, _ in v}) for g, v in idx.postings.items()}
        tune_grams = defaultdict(set)
        for g, v in idx.postings.items():
            for t, _ in v:
                tune_grams[t].add(g)
        idx.tune_gram_count = {t: len(v) for t, v in tune_grams.items()}
        idx.n_tunes = len(idx.tune_names)
        idx.meta = {
            "n": n,
            "candidate_set": candidate_set,
            "fold_octaves": fold_octaves,
            "index_version": INDEX_VERSION,
            "parser_version": abc_pitch.PARSER_VERSION,
            "settings_parsed": parsed,
            "settings_failed": failed,
            "parse_rate": round(parsed / max(1, parsed + failed), 4),
            "n_tunes": idx.n_tunes,
            "n_grams": len(idx.postings),
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "build_seconds": round(time.time() - t0, 1),
            "failures_sample": failures,
        }
        return idx

    # -- querying ---------------------------------------------------------

    def idf(self, gram):
        """Inverse frequency over TUNES. A scale run is in thousands of tunes
        and says almost nothing; a distinctive phrase is in one and says a lot."""
        df = self.df.get(gram, 0)
        if df == 0:
            return 0.0
        return math.log(self.n_tunes / df)

    def lookup(self, intervals, top_k=20):
        """Vote over a query interval sequence. Returns ranked candidate dicts.

        Each n-gram contributes its idf to every tune that contains it, so a
        scale run (in thousands of tunes) counts for almost nothing while a
        distinctive phrase counts for a lot. The score is normalised by the
        total idf queried, so it is comparable between a short window and a
        long one.
        """
        grams = abc_pitch.ngrams(intervals, n=self.n)
        if not grams:
            return []
        scores = defaultdict(float)
        hits = defaultdict(int)            # gram OCCURRENCES matched: the query's side
        distinct_hits = defaultdict(int)   # distinct grams matched: the tune's side
        best_setting = {}
        total_idf = 0.0
        # Grouped by distinct gram: a phrase repeated in the query is more of
        # the query (so it counts twice in the score) but not more of the tune
        # (so it counts once in coverage). Conflating the two let coverage
        # exceed 1 for a tune that repeats a phrase, which is most of them.
        for g, mult in Counter(grams).items():
            w = self.idf(g)
            total_idf += w * mult
            if w <= 0:
                continue
            seen = set()
            for tune_id, setting_id in self.postings.get(g, ()):
                if tune_id not in seen:   # once per tune, however many settings
                    seen.add(tune_id)
                    scores[tune_id] += w * mult
                    hits[tune_id] += mult
                    distinct_hits[tune_id] += 1
                key = (tune_id, setting_id)
                best_setting[key] = best_setting.get(key, 0) + 1
        if not scores:
            return []
        setting_for = {}
        for (tune_id, setting_id), c in best_setting.items():
            cur = setting_for.get(tune_id)
            if cur is None or c > cur[1]:
                setting_for[tune_id] = (setting_id, c)
        denom = total_idf or 1.0
        out = [
            {
                "tune_id": tune_id,
                "setting_id": setting_for[tune_id][0],
                "name": self.tune_names.get(tune_id),
                "tune_type": self.tune_types.get(tune_id),
                # how much of the QUERY this tune explains
                "score": score / denom,
                # how much of the TUNE the query explains; breaks the ties that
                # a short query makes, and stops a tune with many settings (a
                # big union of grams) from winning on breadth alone
                "coverage": distinct_hits[tune_id] / max(1, self.tune_gram_count.get(tune_id, 1)),
                "hits": hits[tune_id],
                "distinct_hits": distinct_hits[tune_id],
                "n_grams_queried": len(grams),
            }
            for tune_id, score in scores.items()
        ]
        out.sort(key=lambda d: (-round(d["score"], 6), -d["coverage"], -d["hits"], d["tune_id"]))
        return out[:top_k]

    # -- persistence ------------------------------------------------------

    def path(self):
        return os.path.join(
            paths.index_dir(),
            f"{self.candidate_set}-n{self.n}{'-folded' if self.fold_octaves else ''}"
            f"-p{abc_pitch.PARSER_VERSION}i{INDEX_VERSION}.pkl",
        )

    def save(self, path=None):
        path = path or self.path()
        paths.ensure_dir(os.path.dirname(path))
        with open(path, "wb") as f:
            pickle.dump(
                {"n": self.n, "candidate_set": self.candidate_set,
                 "fold_octaves": self.fold_octaves, "postings": self.postings,
                 "df": self.df, "tune_gram_count": self.tune_gram_count,
                 "tune_names": self.tune_names, "tune_types": self.tune_types,
                 "n_tunes": self.n_tunes, "meta": self.meta},
                f, protocol=pickle.HIGHEST_PROTOCOL,
            )
        with open(os.path.splitext(path)[0] + ".meta.json", "w") as f:
            json.dump(self.meta, f, indent=1)
        return path

    @classmethod
    def load(cls, candidate_set="all", n=DEFAULT_N, path=None, fold_octaves=False):
        idx = cls(n=n, candidate_set=candidate_set, fold_octaves=fold_octaves)
        path = path or idx.path()
        if not os.path.exists(path):
            raise SystemExit(f"no index at {path}; build it with `lab index --candidate-set {candidate_set}`")
        with open(path, "rb") as f:
            d = pickle.load(f)
        idx.n = d["n"]
        idx.candidate_set = d["candidate_set"]
        idx.fold_octaves = d.get("fold_octaves", False)
        idx.postings = d["postings"]
        idx.df = d["df"]
        idx.tune_gram_count = d["tune_gram_count"]
        idx.tune_names = d["tune_names"]
        idx.tune_types = d["tune_types"]
        idx.n_tunes = d["n_tunes"]
        idx.meta = d["meta"]
        idx.meta["file"] = path
        idx.meta["sha1"] = file_sha1(path)
        return idx


def file_sha1(path, block=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def candidate_tune_ids(candidate_set, recording_id=None):
    """Which tunes the index should cover. None = every tune in the dump."""
    if candidate_set == "all":
        return None
    ids = set()
    rec_ids = [recording_id] if recording_id else paths.prepared_recording_ids()
    if not rec_ids:
        raise SystemExit(f"candidate set '{candidate_set}' needs a pulled recording; run `lab pull` first")
    for rid in rec_ids:
        with open(paths.manifest_path(rid)) as f:
            manifest = json.load(f)
        if candidate_set == "repertoire":
            ids.update(r["tune_id"] for r in manifest["repertoire"] if r["tune_id"])
        elif candidate_set == "eval_tunes":
            ids.update(s["tune_id"] for s in manifest["segments"] if s["tune_id"])
        else:
            raise SystemExit(f"unknown candidate set '{candidate_set}'")
    return ids


def add_parser(sub):
    p = sub.add_parser("index", help="build an interval n-gram index over the ABC corpus")
    p.add_argument("--candidate-set", default="all", choices=["all", "repertoire", "eval_tunes"])
    p.add_argument("--recording", type=int, help="restrict repertoire/eval_tunes to one recording")
    p.add_argument("-n", type=int, default=DEFAULT_N, help=f"n-gram length (default {DEFAULT_N})")
    p.add_argument("--fold-octaves", action="store_true",
                   help="reduce intervals so an octave error cannot matter")
    p.add_argument("--selftest", action="store_true", help="after building, look a known setting up in its own index")
    p.set_defaults(func=main)


def main(args):
    csv_path = paths.tunes_csv_path()
    if not os.path.exists(csv_path):
        raise SystemExit(f"no corpus at {csv_path}; run `lab pull` (it fetches tunes.csv)")
    tune_ids = candidate_tune_ids(args.candidate_set, args.recording)
    print(f"building {args.candidate_set} index (n={args.n}) over "
          f"{'every tune' if tune_ids is None else f'{len(tune_ids)} tunes'} ...", flush=True)
    idx = Index.build(iter_settings(csv_path, tune_ids=tune_ids), n=args.n,
                      candidate_set=args.candidate_set, fold_octaves=args.fold_octaves)
    path = idx.save()
    m = idx.meta
    print(f"{path}\n  {m['n_tunes']} tunes, {m['n_grams']} distinct {args.n}-grams, "
          f"{m['settings_parsed']} settings parsed, {m['settings_failed']} failed "
          f"({m['parse_rate'] * 100:.2f}% ok), {m['build_seconds']}s")
    if args.selftest:
        selftest(idx, csv_path, tune_ids)
    return 0


def selftest(idx, csv_path, tune_ids, n_probe=25):
    """Look settings up in the index built from them. Rank 1 should be their own tune.

    This is not an accuracy measurement: it checks that parse -> intervals ->
    n-grams -> postings -> lookup is self-consistent. If this fails, nothing
    downstream is worth reading.
    """
    ok = 0
    tried = 0
    ranks = []
    for s in iter_settings(csv_path, tune_ids=tune_ids):
        notes = abc_pitch.parse_abc(s.abc, key=s.mode, meter=s.meter)
        intervals = abc_pitch.interval_sequence(abc_pitch.pitch_sequence(notes),
                                                fold=idx.fold_octaves)
        if len(abc_pitch.ngrams(intervals, n=idx.n)) < 10:
            continue
        tried += 1
        res = idx.lookup(intervals, top_k=10)
        rank = next((i + 1 for i, r in enumerate(res) if r["tune_id"] == s.tune_id), None)
        ranks.append(rank)
        if rank == 1:
            ok += 1
        elif tried <= 8:
            got = res[0] if res else None
            print(f"  selftest miss (rank {rank}): tune {s.tune_id} ({s.name}) "
                  f"-> {got['tune_id'] if got else None} {got['name'] if got else ''} "
                  f"score {got['score']:.3f} vs own "
                  f"{next((r['score'] for r in res if r['tune_id'] == s.tune_id), float('nan')):.3f}")
        if tried >= n_probe:
            break
    top3 = sum(1 for r in ranks if r and r <= 3)
    print(f"  selftest: {ok}/{tried} settings rank their own tune first, {top3}/{tried} in the top 3")
    return ok, tried


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    sys.exit(main(parser.parse_args()))
