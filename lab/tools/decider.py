"""Deciding on the phone (spec 053, "Listening on the phone, offline").

The phone already hears for itself (CeolKit's CeolHearing); this is what it
needs to decide too, with no connection: `listen.Listener.decide` and the data
it reads, in a file Swift maps (`lab.corpus.decider_file`, which documents it).

    python -m lab decider export              # from the lab's tunes.csv -> lab/data/index/decider-v1.bin
    python -m lab decider export --from-index # from the index the listener loads (for the fixtures)
    python -m lab decider publish             # build from the newest dump and publish it for the app
    python -m lab decider fixtures --out ios/CeolKit/Tests/CeolDecidingTests/Fixtures

The listening service's live configuration only (`Models()` as the service
builds it): the session's repertoire index with the whole corpus as the
fallback, the aligner on the "notes" reading in the written key, tune-ness,
no tempo evidence. The repertoire index is not shipped: it is the whole
corpus's postings restricted to the session's tunes, with its document
frequencies counted over those tunes (checked equal, posting for posting, to
the built one, 2026-10-10), so a session's repertoire is a list of tune ids.

Two ways to the same file. From the dump is what production publishes every
week (jobs/publish_decider_data.py), built in one pass with the standard
library. From the index packs the pickles `listen.Models` loads, so the file
and the fixtures (made by the listener with those) are about the same corpus:
the lab's index is rebuilt only deliberately, and the dump it came from is
usually not the newest. The two are held equal on the same dump by
lab/tests/test_decider_file.py.
"""

import copy
import json
import os
import tempfile
from array import array

import numpy as np

from lab.corpus import decider_file as D

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

    return os.path.join(paths.index_dir(), f"decider-v{D.FORMAT_VERSION}.bin")


def export_from_index(path):
    """The file from the lab's built index and sequences: what the listening
    service and the fixtures' listener decide with."""
    from lab.corpus.index import Index
    from lab.corpus.sequences import TuneSequences

    a = Index.load("all", n=6, fold_octaves=True)
    rep = Index.load("repertoire", n=6, fold_octaves=True)
    seqs = TuneSequences.load("all")
    postings = {}
    for g, v in a.postings.items():
        postings[D.gram_key(g)] = array("i", (t for t, _ in v))
    by_tune = {t: [bytes(int(x) % 256 for x in plain) for _, _, plain in v] for t, v in seqs.by_tune.items()}
    source = {"index_sha1": a.meta["sha1"], "repertoire_index_sha1": rep.meta["sha1"],
              "index_built_at": a.meta.get("built_at"), "parser_version": a.meta.get("parser_version")}
    return D.write(path, a.tune_names, a.tune_types, postings, by_tune, set(rep.tune_names), source)


def export(path=None, from_index=False):
    from lab import paths
    from lab.corpus.index import candidate_tune_ids

    path = path or default_path()
    if from_index:
        meta = export_from_index(path)
    else:
        meta = D.build(paths.tunes_csv_path(), candidate_tune_ids("repertoire"), path, progress=True)
    f = meta["file"]
    print(f"{path}: {f['bytes'] / 1e6:.1f} MB; {meta['n_tunes']} tunes, {f['n_grams']} n-grams, "
          f"{f['postings']} postings, {meta['sequences']['settings']} settings, {f['symbols']} symbols, "
          f"repertoire {meta['repertoire_n_tunes']}; sha256 {f['sha256'][:12]}")
    return path


def publish(force=False, csv_path=None):
    """Build from the newest dump (or `csv_path`) with production's repertoire
    and publish, as the weekly cron does. Reads production's database and
    writes to the recordings bucket: lab/.env's credentials."""
    import psycopg2

    from lab.env import prod_database_url
    from services import decider_data_service as dd

    conn = psycopg2.connect(prod_database_url())
    try:
        conn.set_session(readonly=True)
        outcome, m = dd.rebuild_and_publish(conn, csv_path=csv_path, force=force)
    finally:
        conn.close()
    print(f"{outcome}: s3://.../{m['key']}, {m['bytes'] / 1e6:.1f} MB, built {m['built_at']}, "
          f"{m['source'].get('n_tunes')} tunes, repertoire {m['source'].get('repertoire_n_tunes')}")


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
    # the index decided with: the Swift tests need the file packed from the same one
    return {"name": name, "recording": rec, "start_s": start_s, "index_sha1": models.fallback.meta["sha1"],
            "taps": done_taps, "steps": steps}


def add_parser(sub):
    p = sub.add_parser("decider", help="deciding on the phone: its data file, its fixtures (spec 053)")
    s = p.add_subparsers(dest="what", required=True)
    e = s.add_parser("export", help="the decider's data in one file the phone maps")
    e.add_argument("--out", help=f"default: lab/data/index/decider-v{D.FORMAT_VERSION}.bin")
    e.add_argument("--from-index", action="store_true",
                   help="pack the lab's built index (what the listener and the fixtures use), not the dump")
    e.set_defaults(func=main_export)
    u = s.add_parser("publish", help="build from the newest dump and publish it for the app (as the cron does)")
    u.add_argument("--force", action="store_true", help="publish even if nothing it is built from has changed")
    u.add_argument("--csv", help="build from this tunes.csv instead of downloading the dump")
    u.set_defaults(func=main_publish)
    f = s.add_parser("fixtures", help="fixtures holding the phone's deciding to the lab's")
    f.add_argument("--out", required=True)
    f.add_argument("--only", help="one clip by name")
    f.set_defaults(func=main_fixtures)


def main_export(args):
    export(args.out, from_index=args.from_index)
    return 0


def main_publish(args):
    publish(force=args.force, csv_path=args.csv)
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
