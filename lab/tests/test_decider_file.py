"""The phone's decider file (corpus.decider_file) against the lab's own index and
sequences built from the same dump, and its configuration against the listener's."""

import csv
import os
import struct

import pytest

from lab.corpus import decider_file as D

SIZE = {"tune_ids": "i", "gram_count": "i", "gram_keys": "I", "post_off": "I", "postings": "H", "popular": "H",
        "rounds": "f",
        "set_off": "I", "seq_off": "I", "symbols": "b", "name_off": "I", "names": "B", "type_off": "I", "types": "B"}


def read_sections(path):
    from array import array

    with open(path, "rb") as f:
        b = f.read()
    out = {}
    for i, name in enumerate(D.SECTIONS):
        o, c = struct.unpack("<QQ", b[16 + 16 * i:32 + 16 * i])
        if name == "meta":
            continue
        a = array(SIZE[name])
        a.frombytes(b[o:o + c * a.itemsize])
        out[name] = a.tolist()
    return out


def expected(csv_path, popular, monkeypatch):
    """What the file should hold, from the lab's Index, TuneSequences and
    RoundLengths, the excluded settings left out as they load."""
    from array import array

    from lab import paths
    from lab.analysis.form import RoundLengths
    from lab.corpus.exclusions import apply_to_index, apply_to_sequences
    from lab.corpus.index import Index
    from lab.corpus.sequences import TuneSequences
    from lab.corpus.tunes_csv import iter_settings

    a = apply_to_index(Index.build(iter_settings(csv_path), n=6, fold_octaves=True, progress_every=0))
    monkeypatch.setattr(paths, "tunes_csv_path", lambda: csv_path)
    seqs = TuneSequences(apply_to_sequences(TuneSequences.build("all").by_tune))
    lengths = RoundLengths(csv_path)
    tune = sorted(set(a.tune_names) | set(seqs.by_tune))
    at = {t: i for i, t in enumerate(tune)}
    keys = sorted(a.postings, key=D.gram_key)
    post, post_off = [], [0]
    for g in keys:
        post += sorted({at[t] for t, _ in a.postings[g]})
        post_off.append(len(post))
    set_off, seq_off, symbols = [0], [0], []
    for t in tune:
        for _, _, plain in seqs.by_tune.get(t, []):
            symbols += [int(x) for x in plain]
            seq_off.append(len(symbols))
        set_off.append(len(seq_off) - 1)
    return {
        "tune_ids": tune, "gram_count": [a.tune_gram_count.get(t, 0) for t in tune],
        "gram_keys": [D.gram_key(g) for g in keys], "post_off": post_off, "postings": post,
        "popular": sorted(at[t] for t in popular if t in at),
        "rounds": array("f", (lengths(t) or 0.0 for t in tune)).tolist(),
        "set_off": set_off, "seq_off": seq_off,
        "symbols": symbols, "names": list(b"".join((a.tune_names.get(t) or "").encode() for t in tune)),
    }, a


def sample_csv(tmp_path, rows):
    """The first `rows` settings of the lab's dump, or skip."""
    from lab import paths

    src = paths.tunes_csv_path()
    if not os.path.exists(src):
        pytest.skip("no tunes.csv (lab pull)")
    out = tmp_path / "tunes.csv"
    with open(src, newline="", encoding="utf-8") as f, open(out, "w", newline="", encoding="utf-8") as g:
        r, w = csv.reader(f), csv.writer(g)
        for i, row in enumerate(r):
            if i > rows:
                break
            w.writerow(row)
    return str(out)


def popularity_csv(tmp_path, books):
    out = tmp_path / "tune_popularity.csv"
    out.write_text("name,tune_id,tunebooks\n" + "".join(f'"T{t}",{t},{n}\n' for t, n in books.items()))
    return str(out)


def test_the_file_holds_what_the_lab_builds(tmp_path, monkeypatch):
    path = sample_csv(tmp_path, 3000)
    pop = popularity_csv(tmp_path, {1: 5000, 2: 99, 3: 100, 50: 120, 999999: 400})
    want, a = expected(path, D.popular_tunes(pop), monkeypatch)
    assert D.popular_tunes(pop) == {1, 3, 50, 999999}
    meta = D.build(path, pop, str(tmp_path / "d.bin"))
    got = read_sections(str(tmp_path / "d.bin"))
    for name, v in want.items():
        assert got[name] == v, name
    assert meta["n_tunes"] == a.n_tunes
    assert D.read_meta(str(tmp_path / "d.bin"))["inputs_sha256"] == meta["inputs_sha256"]


def test_the_same_inputs_have_the_same_digest(tmp_path):
    path = sample_csv(tmp_path, 50)
    sha = D.file_sha256(path)
    assert D.inputs_digest(sha, {3, 1, 2}) == D.inputs_digest(sha, [1, 2, 3])
    assert D.inputs_digest(sha, [1, 2]) != D.inputs_digest(sha, [1, 2, 3])


def test_the_configuration_is_the_listeners():
    """LISTENER restates what the listening service builds; hold it to the code."""
    import inspect

    from lab.bench.stream import ChunkScorer, Decoder
    from lab.tools import listen

    dec = {k: v.default for k, v in inspect.signature(Decoder.__init__).parameters.items()
           if v.default is not inspect.Parameter.empty and k != "n_settings"}
    service = open(os.path.join(os.path.dirname(listen.__file__), "..", "..", "listen", "service.py")).read()
    assert f"NU_PARTLY = {D.LISTENER['decoder']['nu_partly']} " in service
    assert "second_tier=models.popular" in service and "Models, 0, True" in service
    assert D.LISTENER["decoder"] == {**dec, "nu": 0.05, "nu_partly": 0.5}      # Listener passes nu=0.05
    assert D.LISTENER["hop_ms"] == listen.HOP_MS and D.LISTENER["pool_ms"] == listen.POOL_MS
    assert D.LISTENER["keep"] == inspect.signature(ChunkScorer.__init__).parameters["keep"].default
    params = inspect.signature(listen.Listener.__init__).parameters
    assert D.LISTENER["rule_out_s"] == params["rule_out_s"].default
    assert params["drop_release_s"].default is None and params["change_rule"].default == "rounds"
    w = listen.ChangeWatch
    assert D.LISTENER["change_watch"] == {"full": w.FULL, "doubt": w.DOUBT, "rounds": w.ROUNDS, "held_ms": w.HELD_MS}
    src = inspect.getsource(listen.Listener)
    assert (f"top = {D.LISTENER['wide_shortlist_top']} if wide else {D.LISTENER['shortlist_top']}" in src)
    assert "window_ms=6000" in src
    assert D.POPULAR_MIN == 100
    assert ["yin", "basic_pitch", "pesto"] == D.LISTENER["frontends"]
