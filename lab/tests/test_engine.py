"""The steel thread, end to end, on synthetic audio.

Each test names the concept it is protecting, because the point of the steel
thread is that every concept is exercised somewhere a regression would show.
"""

import json

import pytest

from lab import paths
from lab.tests import synthetic

RECORDING_ID = 9001


@pytest.fixture
def lab_data(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))
    synthetic.build_night(str(tmp_path), recording_id=RECORDING_ID)
    from lab.bench.features import compute_features

    compute_features(RECORDING_ID)
    synthetic.build_index(str(tmp_path))
    return tmp_path


def _config(**over):
    cfg = {
        "name": "test",
        "chunk_ms": 2000,
        "experts": [
            {"name": "music_energy", "params": {"threshold": 0.3}},
            {"name": "pitch_yin"},
            {"name": "notes", "params": {"sources": ["pitch_yin"], "min_note_ms": 80}},
            {"name": "intervals", "params": {"window_notes": 32, "min_notes": 6}},
            {"name": "matcher", "params": {"candidate_set": "repertoire", "top_k": 5}},
            {"name": "prior"},
            {"name": "assembler", "params": {"min_update_ms": 0}},
        ],
        "scheduler": {"rule": "always"},
    }
    cfg.update(over)
    return cfg


def test_null_run_records_chunks_and_reexecutes(lab_data):
    """Concepts: the clock, the board, and a stored config re-executed."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        run_id = execute({"name": "null", "chunk_ms": 2000, "experts": []},
                         RECORDING_ID, board=board, quiet=True)
        chunks = board.observations(run_id, types=["audio_chunk"])
        assert len(chunks) > 5
        assert [c.t_start_ms for c in chunks] == sorted(c.t_start_ms for c in chunks)
        assert all(c.t_end_ms - c.t_start_ms <= 2000 for c in chunks)

        again = execute(json.loads(board.get_run(run_id)["config_json"]),
                        RECORDING_ID, board=board, quiet=True, parent_run_id=run_id)
        assert board.get_run(again)["parent_run_id"] == run_id
        assert len(board.observations(again, types=["audio_chunk"])) == len(chunks)


def test_full_thread_produces_every_observation_type(lab_data):
    """Concept: the DAG runs, from audio through to a hypothesis."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        run_id = execute(_config(), RECORDING_ID, board=board, quiet=True)
        types = {o.type for o in board.observations(run_id)}
        for expected in ("audio_chunk", "music_activity", "pitch_track", "note_events",
                         "interval_sequence", "tune_match", "tune_prior", "hypothesis_update"):
            assert expected in types, f"{expected} missing; got {sorted(types)}"


def test_provenance_is_on_every_observation(lab_data):
    """Concept: provenance. Expert, version, params, window, inputs, cost."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        run_id = execute(_config(), RECORDING_ID, board=board, quiet=True)
        for o in board.observations(run_id):
            assert o.expert and o.expert_version
            assert o.t_end_ms >= o.t_start_ms
            assert o.clock_ms is not None
            assert isinstance(o.params, dict)
            if o.type not in ("audio_chunk",):
                assert o.cost_ms >= 0
        derived = [o for o in board.observations(run_id, types=["note_events"])]
        assert derived and all(o.inputs for o in derived), "derived observations must name their inputs"


def test_two_experts_may_produce_one_type(lab_data):
    """Concept: the graph is over types, not experts."""
    from lab.board.board import Board
    from lab.engine.run import execute

    cfg = _config()
    cfg["experts"].insert(2, {"name": "pitch_pyin"})
    with Board() as board:
        run_id = execute(cfg, RECORDING_ID, board=board, quiet=True)
        sources = {o.expert for o in board.observations(run_id, types=["pitch_track"])}
        assert sources == {"pitch_yin", "pitch_pyin"}


def test_experts_only_see_audio_up_to_the_clock(lab_data):
    """Concept: the replay must not leak the future, or latency is a lie."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        run_id = execute(_config(), RECORDING_ID, board=board, quiet=True)
        for o in board.observations(run_id):
            assert o.t_end_ms <= o.clock_ms, f"{o.expert} read past the clock"


def test_hypotheses_open_and_carry_a_distribution(lab_data):
    """Concept: the lifecycle, and a ranked answer rather than one guess."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        run_id = execute(_config(), RECORDING_ID, board=board, quiet=True)
        hyps = board.hypotheses(run_id)
        events = board.hypothesis_events(run_id)
        assert hyps, "no hypothesis was ever opened"
        assert events and events[0]["event"] == "proposed"
        assert all(0.0 <= e["top1_conf"] <= 1.0 for e in events if e["top1_conf"] is not None)
        assert any(len(e["ranked"]) > 1 for e in events), "a hypothesis should rank more than one tune"
        assert {e["event"] for e in events} <= {
            "proposed", "updated", "superseded", "withdrawn", "confirmed"}


def test_the_matcher_finds_the_synthetic_tunes(lab_data):
    """Not an accuracy claim: the audio is rendered from the indexed ABC, so
    failing here means the transcription chain is broken, not outmatched."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        run_id = execute(_config(), RECORDING_ID, board=board, quiet=True)
        seen = set()
        for o in board.observations(run_id, types=["tune_match"]):
            seen.update(c["tune_id"] for c in o.payload["candidates"])
        assert synthetic.TUNE_A["tune_id"] in seen or synthetic.TUNE_B["tune_id"] in seen, \
            "neither synthetic tune was ever a candidate"


def test_prior_reads_repertoire_and_never_the_logged_order(lab_data):
    """Concept: non-audio evidence, and the rule that the log is not evidence."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        run_id = execute(_config(), RECORDING_ID, board=board, quiet=True)
        priors = board.observations(run_id, types=["tune_prior"])
        assert priors
        basis = priors[0].payload["basis"]
        assert basis["repertoire"] == 2
        assert set(priors[0].payload["weights"]) == {
            str(synthetic.TUNE_A["tune_id"]), str(synthetic.TUNE_B["tune_id"])}
    # the view has no accessor for it at all, which is the actual guarantee
    from lab.board.board import BoardView

    assert not hasattr(BoardView, "logged_order")


def test_scheduler_can_skip_an_expensive_expert(lab_data):
    """Concept: the value-of-information hook exists and is recorded."""
    from lab.board.board import Board
    from lab.engine.run import execute

    cfg = _config()
    cfg["experts"].insert(2, {"name": "pitch_pyin"})
    cfg["scheduler"] = {"rule": "never_expensive", "cost_threshold": 5}
    with Board() as board:
        run_id = execute(cfg, RECORDING_ID, board=board, quiet=True)
        skips = board.observations(run_id, types=["scheduler_skip"])
        assert skips, "the expensive expert was never skipped"
        assert {s.payload["expert"] for s in skips} == {"pitch_pyin"}
        assert all(s.payload["reason"] for s in skips)
        assert not board.observations(run_id, types=["pitch_track"], expert="pitch_pyin")


def test_transcription_is_cached_across_runs(lab_data):
    """Concept: re-running downstream experts must not re-transcribe."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        first = execute(_config(), RECORDING_ID, board=board, quiet=True)
        second = execute(_config(), RECORDING_ID, board=board, quiet=True)
        a = board.observations(first, types=["pitch_track"])
        b = board.observations(second, types=["pitch_track"])
        assert a and b
        assert not any(o.cached for o in a)
        assert all(o.cached for o in b), "the second run should have hit the cache"


def test_a_windowed_expert_reads_more_than_one_chunk(lab_data):
    """Concept: analysis windows are not arrival chunks."""
    from lab.board.board import Board
    from lab.engine.run import execute

    with Board() as board:
        run_id = execute(_config(chunk_ms=1000), RECORDING_ID, board=board, quiet=True)
        tracks = board.observations(run_id, types=["pitch_track"])
        assert tracks
        assert max(o.t_end_ms - o.t_start_ms for o in tracks) > 1000


def test_frontend_and_expert_produce_the_same_notes(lab_data):
    """One implementation of note segmentation, used by both loops.

    A front end that scores well on the bench and an expert that behaves
    differently on the board would be the exact bug the two loops exist to
    prevent, so they share the code and this checks they still agree.
    """
    import numpy as np

    from lab.audio.chunks import AudioStore
    from lab.frontends import get_frontend
    from lab.frontends.segmentation import notes_from_pitch

    from types import SimpleNamespace

    from lab.analysis.pulse import attack_times_ms, estimate_pulse
    from lab.experts.notes import Notes

    store = AudioStore(paths.wav_path(RECORDING_ID))
    store.clock_ms = store.duration_ms
    fe = get_frontend("yin", min_voiced=0.3)
    y = store.read(5000, 35000)
    times, f0, voiced = fe.track(y, store.sr)
    store.close()

    # the segmentation half
    segmented = fe.notes_from_track(times, f0, voiced, t_offset_ms=5000)
    viaseg = notes_from_pitch(times, f0, voiced, **fe.note_params())
    assert len(segmented) == len(viaseg)
    assert [n["midi"] for n in segmented] == [n["midi"] for n in viaseg]
    assert all(np.isfinite(n["midi"]) for n in segmented)

    # the regridding half, which is where the two loops last drifted apart
    pulse = estimate_pulse(y, store.sr)
    assert pulse, "this fixture should have a pulse"
    obs = SimpleNamespace(payload={
        "period_ms": pulse["period_ms"], "phase_ms": 5000 + pulse["phase_ms"],
        "grouping": pulse["grouping"],
        "attacks_ms": [5000 + t for t in attack_times_ms(y, store.sr)]})

    # A note deliberately long enough to split, because the synthetic fixture
    # has no repeated notes and so nothing to fuse. Both modes, because the
    # expert used to honour only one of them.
    long_note = {"t0_ms": 5000 + int(pulse["phase_ms"]),
                 "t1_ms": 5000 + int(pulse["phase_ms"] + 3 * pulse["period_ms"]),
                 "midi": 64, "conf": 0.9}
    for mode in ("attack", "grid"):
        fe2 = get_frontend("yin", min_voiced=0.3, split_repeats=mode)
        expert = Notes(sources=["pitch_yin"], min_voiced=0.3, split_repeats=mode)
        direct = fe2.regrid([dict(long_note)], y, store.sr, t_offset_ms=5000)
        viaboard = expert._split([dict(long_note)], obs)
        assert [(n["t0_ms"], n["t1_ms"], n["midi"]) for n in direct] == \
               [(n["t0_ms"], n["t1_ms"], n["midi"]) for n in viaboard], mode
    pieces = expert._split([dict(long_note)], obs)
    assert len(pieces) == 3, "grid mode splits every slot"
    assert all(n["t1_ms"] > n["t0_ms"] for n in pieces)


def test_track_cache_is_keyed_on_tracking_params_only(lab_data):
    """Sweeping a voicing threshold must not re-run the tracker.

    pyin over a night is minutes; note segmentation is milliseconds. Keying
    the cache on every parameter made a six-value threshold sweep cost six
    full passes over the audio instead of one.
    """
    from lab.frontends import get_frontend

    a = get_frontend("yin", min_voiced=0.1)
    b = get_frontend("yin", min_voiced=0.9)
    assert a.cache_key("sha", 0, 1000) == b.cache_key("sha", 0, 1000)

    c = get_frontend("yin", fmin=200.0)
    assert a.cache_key("sha", 0, 1000) != c.cache_key("sha", 0, 1000)


def test_sequence_prior_leaves_its_own_night_out(lab_data, tmp_path, monkeypatch):
    """A transition model that saw tonight would be reading the answer sheet."""
    import json
    import os

    from lab.corpus.sequence import SequenceModel

    hist = {
        "session_id": 1,
        "rows": [
            # two nights where A is followed by B, and one where A is followed by C
            {"session_instance_id": 10, "tune_id": 1, "record_type": "tune", "order_position": "a"},
            {"session_instance_id": 10, "tune_id": 2, "record_type": "tune", "order_position": "b"},
            {"session_instance_id": 11, "tune_id": 1, "record_type": "tune", "order_position": "a"},
            {"session_instance_id": 11, "tune_id": 2, "record_type": "tune", "order_position": "b"},
            {"session_instance_id": 12, "tune_id": 1, "record_type": "tune", "order_position": "a"},
            {"session_instance_id": 12, "tune_id": 3, "record_type": "tune", "order_position": "b"},
        ],
    }
    path = os.path.join(str(tmp_path), "sessions", "1", "logged_order.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(hist, f)

    everything = SequenceModel(1)
    assert everything.follow_totals[1] == 3

    without = SequenceModel(1, exclude_instance_ids=[12])
    assert without.follow_totals[1] == 2
    assert 3 not in without.follows[1], "the held-out night's transition leaked in"
    assert without.n_instances == 2


def test_sequence_prior_never_assigns_zero(lab_data, tmp_path):
    """A prior that can veto must not, since the log is human and fallible."""
    import json
    import os

    from lab.corpus.sequence import SequenceModel

    path = os.path.join(str(tmp_path), "sessions", "1", "logged_order.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"session_id": 1, "rows": [
            {"session_instance_id": 1, "tune_id": 1, "record_type": "tune", "order_position": "a"},
            {"session_instance_id": 1, "tune_id": 2, "record_type": "tune", "order_position": "b"},
        ]}, f)
    m = SequenceModel(1)
    w = m.weights(1)
    assert w[2] > 0
    assert w[999999] > 0, "a tune never seen must still be possible"


def test_a_break_ends_the_chain(lab_data, tmp_path):
    import json
    import os

    from lab.corpus.sequence import SequenceModel

    path = os.path.join(str(tmp_path), "sessions", "1", "logged_order.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"session_id": 1, "rows": [
            {"session_instance_id": 1, "tune_id": 1, "record_type": "tune", "order_position": "a"},
            {"session_instance_id": 1, "tune_id": None, "record_type": "break", "order_position": "b"},
            {"session_instance_id": 1, "tune_id": 2, "record_type": "tune", "order_position": "c"},
        ]}, f)
    m = SequenceModel(1)
    assert m.follow_totals.get(1, 0) == 0, "a set boundary is not a transition"
    assert m.set_openers[1] == 1 and m.set_openers[2] == 1


def test_the_board_reads_eighths_and_fuses_them_as_the_bench_does(lab_data):
    """The eighth-note reading, end to end on the board.

    Four times already the board has quietly run something other than what
    the bench measured. This checks that a run with a pulse expert produces
    the eighth-note reading, and that the matcher combines the two readings
    with the bench's own `fuse`, not a copy of it.
    """
    from lab.bench.retrieval import fuse
    from lab.board.board import Board
    from lab.engine.run import execute
    from lab.experts.matcher import Matcher

    cfg = _config()
    cfg["experts"].insert(2, {"name": "pulse"})
    with Board() as board:
        run_id = execute(cfg, RECORDING_ID, board=board, quiet=True)
        seqs = board.observations(run_id, types=["interval_sequence"])
        with_eighths = [s for s in seqs if s.payload.get("intervals_eighths")]
        assert with_eighths, "no interval sequence carried the eighth-note reading"

    matcher = Matcher(candidate_set="repertoire", top_k=5)
    payload = with_eighths[-1].payload
    got = [r["tune_id"] for r in matcher.rank(payload)]
    plain = matcher._index.lookup(payload["intervals"], top_k=40)
    eighths = matcher._eighths_index.lookup(payload["intervals_eighths"], top_k=40)
    want = [r["tune_id"] for r in fuse([plain, eighths], method="sum")[:5]]
    assert got == want


def test_the_assembler_can_average_its_evidence(lab_data):
    """The moving-average mode runs end to end and still reaches an answer.

    It is off by default -- measured as costing more accuracy than the
    stability it buys -- but it is kept, so it has to keep working.
    """
    from lab.board.board import Board
    from lab.engine.run import execute

    cfg = _config()
    for e in cfg["experts"]:
        if e["name"] == "assembler":
            e["params"].update({"evidence_mode": "ema", "half_life_s": 6.0})
    with Board() as board:
        run_id = execute(cfg, RECORDING_ID, board=board, quiet=True)
        assert board.hypotheses(run_id), "no hypothesis was ever proposed"
