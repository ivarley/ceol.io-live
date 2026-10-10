"""The phone's decider file, built straight from thesession.org's dump (spec 053,
"Listening on the phone, offline").

What the phone reads to decide with no connection (CeolKit's CeolDeciding): the
whole corpus's 6-gram postings per tune, every setting's "notes" reading for the
aligner, the tunes' names and types, the session's repertoire, and the
configuration and tune-ness model. It is what `corpus.index.Index` (all, n=6,
folded) and `corpus.sequences.TuneSequences` hold, setting for setting, made in
one pass with the standard library only, so the weekly cron can rebuild it from a
fresh dump in a small instance (jobs/publish_decider_data.py). The lab's tests
hold it equal to those two built the lab's way.

The file, little-endian throughout:

    "CEOLDEC1", u32 format version, u32 section count, then per section u64
    offset and u64 element count; each section starts on an 8-byte boundary.

     0 meta       utf-8 JSON: the configuration and provenance (`build`)
     1 tune_ids   i32 per tune, ascending; a tune's position is its index
     2 gram_count i32 per tune: distinct n-grams across its settings
     3 gram_keys  u32 per n-gram, ascending: sum((step + 6) * 12**i)
     4 post_off   u32, n_grams + 1: each n-gram's tunes in `postings`
     5 postings   u16 tune indexes, ascending within an n-gram
     6 repertoire u16 tune indexes: the default session's tunes
     7 set_off    u32, n_tunes + 1: each tune's settings in `seq_off`
     8 seq_off    u32, n_settings + 1: each setting's symbols
     9 symbols    i8 pitch classes, the "notes" reading
    10 name_off   u32, n_tunes + 1
    11 names      utf-8
    12 type_off   u32, n_tunes + 1
    13 types      utf-8

Postings are per tune, not per setting: the lookup counts a tune once per
n-gram however many of its settings hold it. The repertoire's own index is the
whole corpus's postings restricted to its tunes, with idf over those, so it is
not stored; the phone counts it.
"""

import hashlib
import json
import os
import struct
import sys
import time
from array import array

from lab.corpus import abc_pitch
from lab.corpus.tunes_csv import iter_settings

FORMAT_VERSION = 1          # the layout: bump when the phone must read it differently
BUILDER_VERSION = "1"       # what goes in it: bump when the same inputs would build otherwise
MAGIC = b"CEOLDEC1"
SECTIONS = ("meta", "tune_ids", "gram_count", "gram_keys", "post_off", "postings", "repertoire",
            "set_off", "seq_off", "symbols", "name_off", "names", "type_off", "types")
N = 6
TUNENESS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "tuneness.json")

# The listening service's live configuration, as `listen.Listener` and its scorer
# and decoder are built there. Restated here so the cron needs nothing but the
# standard library; lab/tests/test_decider_file.py holds it to the real values.
LISTENER = {
    "hop_ms": 4000, "pool_ms": 24000, "window_ms": 6000, "keep": 6,
    "pool_top": 100, "fallback_top": 20, "wide_pool_top": 300, "wide_fallback_top": 60,
    "rule_out_s": 30.0, "chunk_notes": 24,
    "decoder": {"lam": 40.0, "tau": 0.45, "p_switch": 0.05, "p_none": 0.3, "nu": 0.05, "kappa": 0.0,
                "gamma": 0.0},
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


def inputs_digest(csv_sha256, repertoire_ids):
    """What decides the file's contents, as one hash: the same digest means the
    same file but for its build time, so nothing new to publish."""
    h = hashlib.sha256()
    for part in (FORMAT_VERSION, BUILDER_VERSION, abc_pitch.PARSER_VERSION, csv_sha256,
                 sorted(int(t) for t in repertoire_ids), _tuneness(), LISTENER):
        h.update(json.dumps(part, sort_keys=True).encode())
    return h.hexdigest()


def build(csv_path, repertoire_ids, out_path, progress=False):
    """tunes.csv and the default session's tune ids -> the file at `out_path`
    (written beside it and renamed into place). Returns its meta."""
    t0 = time.time()
    csv_sha = file_sha256(csv_path)
    names, types = {}, {}
    postings = {}             # gram key -> array of tune ids, one per setting holding it
    by_tune = {}              # tune id -> [bytes of the setting's "notes" reading]
    parsed = failed = rows = 0
    for s in iter_settings(csv_path):
        rows += 1
        if progress and rows % 10000 == 0:
            print(f"  {rows} settings, {len(postings)} n-grams, {time.time() - t0:.0f}s", flush=True)
        names.setdefault(s.tune_id, s.name)
        types.setdefault(s.tune_id, s.tune_type)
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

    source = {"tunes_csv_sha256": csv_sha, "settings": rows, "settings_parsed": parsed,
              "settings_failed": failed, "parser_version": abc_pitch.PARSER_VERSION}
    meta = write(out_path, names, types, postings, by_tune, repertoire_ids, source,
                 inputs_digest(csv_sha, repertoire_ids))
    meta["file"]["build_seconds"] = round(time.time() - t0, 1)
    return meta


def write(out_path, names, types, postings, by_tune, repertoire_ids, source, digest=None):
    """The file from its parts: {tune id: name}, {tune id: type}, {n-gram key:
    tune ids holding it}, {tune id: [each setting's "notes" reading as bytes]},
    the default session's tune ids, and where they came from. Written beside
    `out_path` and renamed into place. Returns its meta."""
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
    rep = sorted({at[t] for t in repertoire_ids if t in at})

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
        "n_tunes": len(names), "repertoire_n_tunes": len(rep),
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
        "repertoire": array("H", rep), "set_off": set_off, "seq_off": seq_off,
        "symbols": bytes(symbols), "name_off": name_off, "names": name_bytes,
        "type_off": type_off, "types": type_bytes,
    }
    for name in ("tune_ids", "gram_count"):
        assert sections[name].itemsize == 4
    assert sections["gram_keys"].itemsize == 4 and sections["postings"].itemsize == 2

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
