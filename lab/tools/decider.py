"""Deciding on the phone (spec 053, "Listening on the phone, offline").

The phone already hears for itself (CeolKit's CeolHearing); this is what it
needs to decide too, with no connection: `listen.Listener.decide` and the
data it reads, in a form Swift can map straight from a file.

    python -m lab decider export                  # -> lab/data/index/decider-v1.bin
    python -m lab decider fixtures --out ios/CeolKit/Tests/CeolDecidingTests/Fixtures

The listening service's live configuration only (`Models()` as the service
builds it): the session's repertoire index with the whole corpus as the
fallback, the aligner on the "notes" reading in the written key, tune-ness,
no tempo evidence. The repertoire index is not shipped: it is the whole
corpus's postings restricted to the session's tunes, with its document
frequencies counted over those tunes (checked equal, posting for posting, to
the built one, 2026-10-10), so a session's repertoire is a list of tune ids.

The file, little-endian throughout:

    "CEOLDEC1", u32 version, u32 section count, then per section u64 offset
    and u64 element count; each section starts on an 8-byte boundary.

     0 meta       utf-8 JSON: the configuration and provenance (below)
     1 tune_ids   i32 per tune, ascending; a tune's position is its index
     2 gram_count i32 per tune: distinct n-grams across its settings
     3 gram_keys  u32 per n-gram, ascending: sum((step + 6) * 12**i)
     4 post_off   u32, n_grams + 1: each n-gram's tunes in `postings`
     5 postings   u16 tune indexes, ascending within an n-gram
     6 repertoire u16 tune indexes: the default session's tunes
     7 set_off    u32, n_tunes + 1: each tune's settings in `seq_off`
     8 seq_off    u32, n_settings + 1: each setting's symbols
     9 symbols    i8 pitch classes, the "notes" reading (sequences.TuneSequences)
    10 name_off   u32, n_tunes + 1
    11 names      utf-8
    12 type_off   u32, n_tunes + 1
    13 types      utf-8

A tune's postings are per tune, not per setting: the lookup counts each tune
once per n-gram however many of its settings hold it, and the setting it
would name is not used live.
"""

import copy
import json
import os
import struct
import tempfile
import time

import numpy as np

VERSION = 1
MAGIC = b"CEOLDEC1"
SECTIONS = ("meta", "tune_ids", "gram_count", "gram_keys", "post_off", "postings", "repertoire",
            "set_off", "seq_off", "symbols", "name_off", "names", "type_off", "types")

# fixtures: (name, recording, start seconds, seconds, taps). A tap comes after
# the step it names (its index), as a person answering the state on screen:
# "this" names the state's second candidate (so it overrides the decoder),
# "none" rules out what is shown.
CLIPS = (
    ("r112-reel", 112, 1500, 240, []),
    ("r137-talk", 137, 900, 240, [{"after": 24, "action": "none"}]),
    ("r143-jig", 143, 2400, 240, [{"after": 8, "action": "this"}]),
)


def default_path():
    from lab import paths

    return os.path.join(paths.index_dir(), f"decider-v{VERSION}.bin")


def gram_key(g):
    return sum((v + 6) * 12 ** i for i, v in enumerate(g))


def listener_config():
    """What `Listener` and the service fix that the decider needs, read from
    the code rather than restated, so a change there shows up here."""
    import inspect

    from lab.bench.stream import ChunkScorer, Decoder
    from lab.tools import listen

    sig = inspect.signature(listen.Listener.__init__)
    dec = {k: v.default for k, v in inspect.signature(Decoder.__init__).parameters.items()
           if v.default is not inspect.Parameter.empty and k != "n_settings"}
    scorer = {k: v.default for k, v in inspect.signature(ChunkScorer.__init__).parameters.items()
              if k in ("keep",)}
    return {"hop_ms": listen.HOP_MS, "pool_ms": listen.POOL_MS, "window_ms": 6000,
            "keep": scorer["keep"], "pool_top": 100, "fallback_top": 20, "wide_pool_top": 300,
            "wide_fallback_top": 60, "rule_out_s": sig.parameters["rule_out_s"].default,
            "chunk_notes": 24, "decoder": {**dec, "nu": 0.05}, "frontends": ["yin", "basic_pitch", "pesto"]}


def export(path=None):
    from lab.analysis.tuneness import NAMES, TunenessModel
    from lab.corpus.index import Index
    from lab.corpus.sequences import TuneSequences

    path = path or default_path()
    t0 = time.time()
    a = Index.load("all", n=6, fold_octaves=True)
    rep = Index.load("repertoire", n=6, fold_octaves=True)
    seqs = TuneSequences.load("all")
    tune = sorted(set(a.tune_names) | set(seqs.by_tune))
    if len(tune) >= 1 << 16:
        raise SystemExit(f"{len(tune)} tunes: postings are u16, widen them")
    at = {t: i for i, t in enumerate(tune)}

    keys = sorted(a.postings, key=gram_key)
    post_off, postings = [0], []
    for g in keys:
        postings.extend(sorted({at[t] for t, _ in a.postings[g]}))
        post_off.append(len(postings))
    set_off, seq_off, symbols = [0], [0], []
    for t in tune:
        for _, _, plain in seqs.by_tune.get(t, []):
            symbols.extend(int(x) for x in plain)
            seq_off.append(len(symbols))
        set_off.append(len(seq_off) - 1)

    def strings(values):
        off, buf = [0], bytearray()
        for v in values:
            buf += (v or "").encode()
            off.append(len(buf))
        return np.array(off, "<u4"), np.frombuffer(bytes(buf), np.uint8)

    name_off, names = strings(a.tune_names.get(t) for t in tune)
    type_off, types = strings(a.tune_types.get(t) for t in tune)
    tm = TunenessModel.load()
    meta = {
        "version": VERSION, "n": a.n, "fold_octaves": a.fold_octaves, "n_tunes": a.n_tunes,
        "repertoire_n_tunes": rep.n_tunes, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "index": {k: a.meta.get(k) for k in ("parser_version", "index_version", "n_grams", "built_at", "sha1")},
        "repertoire_index": {k: rep.meta.get(k) for k in ("n_tunes", "built_at", "sha1")},
        "sequences": {"version": TuneSequences.VERSION, "reading": "notes", "path": os.path.basename(
            TuneSequences.path("all"))},
        "tuneness": {"names": list(NAMES), "coef": tm.coef.tolist(), "intercept": tm.intercept,
                     "median": tm.median.tolist(), "mu": tm.mu.tolist(), "sd": tm.sd.tolist(),
                     "gamma": tm.meta["gamma"], "kappa": tm.meta["kappa"], "fitted": tm.meta.get("fitted")},
        "listener": listener_config(),
    }
    arrays = {
        "meta": np.frombuffer(json.dumps(meta, separators=(",", ":")).encode(), np.uint8),
        "tune_ids": np.array(tune, "<i4"),
        "gram_count": np.array([a.tune_gram_count.get(t, 0) for t in tune], "<i4"),
        "gram_keys": np.array([gram_key(g) for g in keys], "<u4"),
        "post_off": np.array(post_off, "<u4"),
        "postings": np.array(postings, "<u2"),
        "repertoire": np.array(sorted(at[t] for t in rep.tune_names), "<u2"),
        "set_off": np.array(set_off, "<u4"),
        "seq_off": np.array(seq_off, "<u4"),
        "symbols": np.array(symbols, "i1"),
        "name_off": name_off, "names": names, "type_off": type_off, "types": types,
    }
    head = len(MAGIC) + 8 + 16 * len(SECTIONS)
    offsets, at_byte = [], (head + 7) // 8 * 8
    for name in SECTIONS:
        offsets.append(at_byte)
        at_byte = (at_byte + arrays[name].nbytes + 7) // 8 * 8
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(MAGIC + struct.pack("<II", VERSION, len(SECTIONS)))
        for name, off in zip(SECTIONS, offsets):
            f.write(struct.pack("<QQ", off, len(arrays[name])))
        for name, off in zip(SECTIONS, offsets):
            f.write(b"\0" * (off - f.tell()))
            f.write(arrays[name].tobytes())
    os.replace(tmp, path)
    sizes = {k: v.nbytes for k, v in arrays.items()}
    print(f"{path}: {os.path.getsize(path) / 1e6:.1f} MB in {time.time() - t0:.1f}s; "
          f"{len(tune)} tunes, {len(keys)} n-grams, {len(postings)} postings, "
          f"{len(seq_off) - 1} settings, {len(symbols)} symbols, repertoire {len(arrays['repertoire'])}")
    print("  by section (MB): " + ", ".join(f"{k} {v / 1e6:.2f}" for k, v in sizes.items() if v > 1e5))
    return path


# -- fixtures ------------------------------------------------------------------


def _heard_messages(rec, start_s, seconds):
    """Every step's `pack_heard` message for a stretch of a night, as the
    phone's hearing makes it (the hearing fixtures hold that to this)."""
    from lab.tools.hearing_fixtures import clip
    from lab.tools.listen import HOP_MS, Hearer, LiveStore

    y = clip(rec, start_s, seconds).astype(np.float32) / 32767
    hearer = Hearer(LiveStore(os.path.join(tempfile.mkdtemp(), "a.wav"), keep_s=120))
    hearer.store.append(y)
    out, t = [], HOP_MS
    while t <= len(y) * 1000 // 22050:
        out.append(hearer.heard(t))
        t += HOP_MS
    hearer.store.close()
    return out


def _r(x, nd=12):
    return float(round(x, nd))


def fixture(models, name, rec, start_s, seconds, taps):
    """One clip: each step's heard message, what the decider made of it on the
    way (the pool, the tunes aligned and their scores, tune-ness) and the
    state, with the taps a person made between steps."""
    from lab.tools.listen import Listener, unpack_heard

    msgs = _heard_messages(rec, start_s, seconds)
    lst = Listener(tempfile.mkdtemp(), models=models, audio=False)
    seen = {}
    step = lst.decoder.step

    def spy(c):                       # the chunk as the decoder gets it (bans applied)
        seen["chunk"] = {k: (dict(v) if isinstance(v, dict) else v) for k, v in c.items()}
        return step(c)

    lst.decoder.step = spy
    steps, done_taps = [], []
    for i, msg in enumerate(msgs):
        t, ctx, feats, heard_ms = unpack_heard(json.loads(json.dumps(msg)))
        lst.step_heard(t, ctx, feats, heard_ms)
        c = seen["chunk"]
        # a copy: the next step appends to this state's history list in place
        state = copy.deepcopy({k: v for k, v in lst.state.items() if k not in ("compute_ms", "timing")})
        steps.append({
            "heard": msg, "pool": list(lst.scorer.recent[-1]), "tunes": list(lst.scorer.last_tunes),
            "scores": {str(k): _r(v) for k, v in c["scores"].items()}, "floor": _r(c["floor"]),
            "outside": sorted(c.get("outside", [])), "n_notes": c["n_notes"],
            "tune_logodds": _r(c["tune_logodds"]),
            "belief": [[int(s), _r(p, 15)] for s, p in lst.decoder.belief(len(lst.decoder._ids))
                       if p > 1e-12],
            "state": state})
        for tap in (x for x in taps if x["after"] == i):
            shown = [c["tune_id"] for c in state["top"]]
            if tap["action"] == "this":
                pick = shown[1] if len(shown) > 1 else shown[0]
                lst.tap("this", pick, shown)
                done_taps.append({"after": i, "action": "this", "tune_id": pick, "shown": shown})
            else:
                lst.tap("none", None, shown)
                done_taps.append({"after": i, "action": "none", "shown": shown})
    lst.close()
    return {"name": name, "recording": rec, "start_s": start_s, "taps": done_taps, "steps": steps}


def add_parser(sub):
    p = sub.add_parser("decider", help="deciding on the phone: its data file, its fixtures (spec 053)")
    s = p.add_subparsers(dest="what", required=True)
    e = s.add_parser("export", help="the decider's data in one file the phone maps")
    e.add_argument("--out", help=f"default: lab/data/index/decider-v{VERSION}.bin")
    e.set_defaults(func=main_export)
    f = s.add_parser("fixtures", help="fixtures holding the phone's deciding to the lab's")
    f.add_argument("--out", required=True)
    f.add_argument("--only", help="one clip by name")
    f.set_defaults(func=main_fixtures)


def main_export(args):
    export(args.out)
    return 0


def main_fixtures(args):
    from lab.tools.listen import Models

    os.makedirs(args.out, exist_ok=True)
    models = Models()
    for name, rec, start, seconds, taps in CLIPS:
        if args.only and name != args.only:
            continue
        fx = fixture(models, name, rec, start, seconds, taps)
        path = os.path.join(args.out, f"{name}.json")
        with open(path, "w") as f:
            json.dump(fx, f, separators=(",", ":"))
        shown = [s["state"]["shown"] for s in fx["steps"]]
        names = []
        for s in fx["steps"]:
            h = s["state"]["history"]
            if h and (not names or names[-1] != h[-1]["name"]):
                names.append(h[-1]["name"])
        print(f"{name}: {len(fx['steps'])} steps, {sum(x is not None for x in shown)} showing a tune, "
              f"taps {fx['taps']}, named {names}, {os.path.getsize(path) // 1024} KB")
    return 0
