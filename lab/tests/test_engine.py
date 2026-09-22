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
