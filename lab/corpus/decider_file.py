"""The phone's decider file, built straight from thesession.org's dump (spec 053,
"Listening on the phone, offline").

What the phone reads to decide with no connection (CeolKit's CeolDeciding), as
the listening service decides (`listen.Listener` on `Models(merged=True)`): the
whole corpus's 6-gram postings per tune, every setting's "notes" reading for the
aligner, the popular tunes (a session's second tier, and its first when its own
are not known), each tune's length once round (the meter's "may have changed"),
the tunes' names and types, and the configuration and tune-ness model. It is
what `corpus.index.Index` (all, n=6, folded), `corpus.sequences.TuneSequences`
and `analysis.form.RoundLengths` hold, with the excluded settings left out as
they are when those load (`corpus.exclusions`), made in one pass over the dump
so the weekly cron can rebuild it from a fresh one in a small instance
(jobs/publish_decider_data.py). The lab's tests hold it equal to those built
the lab's way.

The session's own tunes are not in it: the app fetches them for the night
(GET /api/session-instances/<id>/known-tunes), as the service does.

The file, little-endian throughout:

    "CEOLDEC1", u32 format version, u32 section count, then per section u64
    offset and u64 element count; each section starts on an 8-byte boundary.

     0 meta       utf-8 JSON: the configuration and provenance (`build`)
     1 tune_ids   i32 per tune, ascending; a tune's position is its index
     2 gram_count i32 per tune: distinct n-grams across its settings
     3 gram_keys  u32 per n-gram, ascending: sum((step + 6) * 12**i)
     4 post_off   u32, n_grams + 1: each n-gram's tunes in `postings`
     5 postings   u16 tune indexes, ascending within an n-gram
     6 popular    u16 tune indexes: at least POPULAR_MIN thesession.org tunebooks
     7 rounds     f32 per tune: eighths in one time through it as played (median
                  over its settings), 0 for none readable
     8 set_off    u32, n_tunes + 1: each tune's settings in `seq_off`
     9 seq_off    u32, n_settings + 1: each setting's symbols
    10 symbols    i8 pitch classes, the "notes" reading
    11 name_off   u32, n_tunes + 1
    12 names      utf-8
    13 type_off   u32, n_tunes + 1
    14 types      utf-8

Postings are per tune, not per setting: the lookup counts a tune once per
n-gram however many of its settings hold it.
"""

import csv
import hashlib
import json
import os
import struct
import sys
import time
from array import array

from lab.corpus import abc_pitch
from lab.corpus.exclusions import excluded_settings
from lab.corpus.tunes_csv import iter_settings

FORMAT_VERSION = 2          # the layout: bump when the phone must read it differently
BUILDER_VERSION = "2"       # what goes in it: bump when the same inputs would build otherwise
MAGIC = b"CEOLDEC1"
SECTIONS = ("meta", "tune_ids", "gram_count", "gram_keys", "post_off", "postings", "popular", "rounds",
            "set_off", "seq_off", "symbols", "name_off", "names", "type_off", "types")
N = 6
POPULAR_MIN = 100           # tunebooks: `candidate_tune_ids("popular")`
MIN_ROUND_EIGHTHS = 32      # RoundLengths' min_eighths
TUNENESS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "tuneness.json")

# The listening service's live configuration, as listen/service.py builds a
# stream's `listen.Listener` (merged shortlists, the popular tunes as the second
# tier, the default hop, no letting go on a drop, "may have changed" by rounds).
# Restated so the cron needs no listener; lab/tests/test_decider_file.py holds it
# to the real values.
LISTENER = {
    "hop_ms": 4000, "pool_ms": 24000, "window_ms": 6000, "keep": 6,
    "shortlist_top": 100, "wide_shortlist_top": 300,
    "rule_out_s": 30.0, "chunk_notes": 24,
    "decoder": {"lam": 40.0, "tau": 0.45, "p_switch": 0.05, "p_none": 0.3, "nu": 0.05, "kappa": 0.0,
                "gamma": 0.0, "nu_partly": 0.5},
    "change_watch": {"full": 0.99, "doubt": 0.8, "rounds": 1.8, "held_ms": 40000},
    "frontends": ["yin", "basic_pitch", "pesto"],
}

assert sys.byteorder == "little", "the file is little-endian and written with the machine's arrays"


def gram_key(g):
    return sum((v + 6) * 12 ** i for i, v in enumerate(g))


def _collapse(pcs):
    out = []
    for p in pcs:
        if p is None:
            continue
        if not out or out[-1] != p:
            out.append(p)
    return out


def file_sha256(path, block=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(block)
            if not b:
                return h.hexdigest()
            h.update(b)


def _tuneness():
    with open(TUNENESS_PATH) as f:
        d = json.load(f)
    return {"names": d["names"], "coef": d["coef"], "intercept": d["intercept"], "median": d["median"],
            "mu": d["mu"], "sd": d["sd"], "gamma": d["gamma"], "kappa": d["kappa"], "fitted": d.get("fitted")}


def popular_tunes(popularity_path):
    """Tune ids with at least POPULAR_MIN tunebooks, from TheSession-data's
    tune_popularity.csv."""
    with open(popularity_path, newline="", encoding="utf-8") as f:
        return {int(r["tune_id"]) for r in csv.DictReader(f) if int(r["tunebooks"]) >= POPULAR_MIN}


def inputs_digest(csv_sha256, popular):
    """What decides the file's contents, as one hash: the same digest means the
    same file but for its build time, so nothing new to publish."""
    h = hashlib.sha256()
    for part in (FORMAT_VERSION, BUILDER_VERSION, abc_pitch.PARSER_VERSION, csv_sha256,
                 sorted(int(t) for t in popular), sorted(excluded_settings()), _tuneness(), LISTENER):
        h.update(json.dumps(part, sort_keys=True).encode())
    return h.hexdigest()


def round_length(settings):
    """RoundLengths' answer for one tune from its (non-excluded) settings, or
    None: the median of each readable setting's played length."""
    import statistics

    from lab.analysis.form import played_form

    lengths = []
    for s in settings:
        try:
            f = played_form(s.abc, key=s.mode, meter=s.meter)
        except Exception:  # one unreadable setting must not lose the tune
            continue
        if f.length >= MIN_ROUND_EIGHTHS and f.bar_starts:
            lengths.append(f.length)
    return float(statistics.median(lengths)) if lengths else None


def build(csv_path, popularity_path, out_path, progress=False):
    """tunes.csv and tune_popularity.csv -> the file at `out_path` (written
    beside it and renamed into place). Returns its meta."""
    t0 = time.time()
    csv_sha = file_sha256(csv_path)
    popular = popular_tunes(popularity_path)
    drop = excluded_settings()
    names, types = {}, {}
    settings_of = {}          # tune id -> its settings, for the round lengths
    postings = {}             # gram key -> array of tune ids, one per setting holding it
    by_tune = {}              # tune id -> [bytes of the setting's "notes" reading]
    parsed = failed = rows = 0
    for s in iter_settings(csv_path):
        rows += 1
        if progress and rows % 10000 == 0:
            print(f"  {rows} settings, {len(postings)} n-grams, {time.time() - t0:.0f}s", flush=True)
        names.setdefault(s.tune_id, s.name)
        types.setdefault(s.tune_id, s.tune_type)
        if s.setting_id in drop:        # as the index and sequences load (corpus.exclusions)
            continue
        settings_of.setdefault(s.tune_id, []).append(s)
        try:
            notes = abc_pitch.parse_abc(s.abc, key=s.mode, meter=s.meter)
        except Exception:  # a bad setting must not lose the corpus
            failed += 1
            continue
        # the index's reading (corpus.index.Index.build)
        try:
            grams = abc_pitch.ngrams(abc_pitch.interval_sequence(abc_pitch.pitch_sequence(notes), fold=True), n=N)
        except Exception:
            grams = []
        if grams:
            parsed += 1
            for g in set(grams):
                key = gram_key(g)
                a = postings.get(key)
                if a is None:
                    postings[key] = a = array("i")
                a.append(s.tune_id)
        else:
            failed += 1
        # the aligner's (corpus.sequences.TuneSequences.build), which also needs
        # the eighths reading to come out without an error
        try:
            abc_pitch.particalized_pitches(notes)
            plain = _collapse(p % 12 if p is not None else None for p in abc_pitch.pitch_sequence(notes))
        except Exception:
            continue
        if len(plain) >= 8:
            by_tune.setdefault(s.tune_id, []).append(bytes(p % 256 for p in plain))

    rounds = {}
    for t, ss in settings_of.items():
        n = round_length(ss)
        if n:
            rounds[t] = n
    source = {"tunes_csv_sha256": csv_sha, "popularity_sha256": file_sha256(popularity_path), "settings": rows,
              "settings_parsed": parsed, "settings_failed": failed, "settings_excluded": len(drop),
              "parser_version": abc_pitch.PARSER_VERSION}
    meta = write(out_path, names, types, postings, by_tune, popular, rounds, source,
                 inputs_digest(csv_sha, popular))
    meta["file"]["build_seconds"] = round(time.time() - t0, 1)
    return meta


def write(out_path, names, types, postings, by_tune, popular, rounds, source, digest=None):
    """The file from its parts: {tune id: name}, {tune id: type}, {n-gram key:
    tune ids holding it}, {tune id: [each setting's "notes" reading as bytes]},
    the popular tune ids, {tune id: eighths per round}, and where they came
    from. Written beside `out_path` and renamed into place. Returns its meta."""
    tune = sorted(set(names) | set(by_tune))
    if len(tune) >= 1 << 16:
        raise SystemExit(f"{len(tune)} tunes: postings are u16, widen them")
    at = {t: i for i, t in enumerate(tune)}
    keys = sorted(postings)
    post_off, post = array("I", [0]), array("H")
    gram_count = array("i", [0] * len(tune))
    for k in keys:
        for i in sorted({at[t] for t in postings[k]}):
            post.append(i)
            gram_count[i] += 1
        post_off.append(len(post))
    set_off, seq_off, symbols = array("I", [0]), array("I", [0]), bytearray()
    n_settings = 0
    for t in tune:
        for seq in by_tune.get(t, ()):
            symbols += seq
            seq_off.append(len(symbols))
            n_settings += 1
        set_off.append(n_settings)
    pop = sorted({at[t] for t in popular if t in at})

    def strings(values):
        off, buf = array("I", [0]), bytearray()
        for v in values:
            buf += (v or "").encode()
            off.append(len(buf))
        return off, bytes(buf)

    name_off, name_bytes = strings(names.get(t) for t in tune)
    type_off, type_bytes = strings(types.get(t) for t in tune)
    tuneness = _tuneness()
    meta = {
        "version": FORMAT_VERSION, "builder": BUILDER_VERSION, "n": N, "fold_octaves": True,
        "n_tunes": len(names), "popular_n_tunes": len(pop), "rounds_n_tunes": len(rounds),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs_sha256": digest, "source": source,
        "sequences": {"reading": "notes", "settings": n_settings},
        "tuneness": tuneness,
        "listener": {**LISTENER, "decoder": {**LISTENER["decoder"], "kappa": tuneness["kappa"],
                                             "gamma": tuneness["gamma"]}},
    }
    sections = {
        "meta": json.dumps(meta, separators=(",", ":")).encode(),
        "tune_ids": array("i", tune), "gram_count": gram_count,
        "gram_keys": array("I", keys), "post_off": post_off, "postings": post,
        "popular": array("H", pop), "rounds": array("f", (rounds.get(t, 0.0) for t in tune)),
        "set_off": set_off, "seq_off": seq_off,
        "symbols": bytes(symbols), "name_off": name_off, "names": name_bytes,
        "type_off": type_off, "types": type_bytes,
    }
    for name in ("tune_ids", "gram_count"):
        assert sections[name].itemsize == 4
    assert sections["gram_keys"].itemsize == 4 and sections["postings"].itemsize == 2
    assert sections["rounds"].itemsize == 4

    def count(v):
        return len(v)

    def nbytes(v):
        return len(v) * v.itemsize if isinstance(v, array) else len(v)

    head = len(MAGIC) + 8 + 16 * len(SECTIONS)
    offsets, at_byte = [], (head + 7) // 8 * 8
    for name in SECTIONS:
        offsets.append(at_byte)
        at_byte = (at_byte + nbytes(sections[name]) + 7) // 8 * 8
    tmp = f"{out_path}.{os.getpid()}.part"
    with open(tmp, "wb") as f:
        f.write(MAGIC + struct.pack("<II", FORMAT_VERSION, len(SECTIONS)))
        for name, off in zip(SECTIONS, offsets):
            f.write(struct.pack("<QQ", off, count(sections[name])))
        for name, off in zip(SECTIONS, offsets):
            f.write(b"\0" * (off - f.tell()))
            v = sections[name]
            f.write(v.tobytes() if isinstance(v, array) else v)
    os.replace(tmp, out_path)
    meta["file"] = {"bytes": os.path.getsize(out_path), "sha256": file_sha256(out_path), "n_grams": len(keys),
                    "postings": len(post), "symbols": len(symbols)}
    return meta


def read_meta(path):
    """A file's meta section, without reading the rest."""
    with open(path, "rb") as f:
        head = f.read(len(MAGIC) + 8 + 16)
        if head[:len(MAGIC)] != MAGIC:
            raise ValueError(f"{path}: not a decider file")
        off, n = struct.unpack("<QQ", head[len(MAGIC) + 8:])
        f.seek(off)
        return json.loads(f.read(n))
