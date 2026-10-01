"""The harness and the inspection tools, on the synthetic night."""

import argparse
import os

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


CONFIG = {
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


def _run(board, config=None):
    from lab.engine.run import execute

    return execute(dict(config or CONFIG), RECORDING_ID, board=board, quiet=True)


def test_ground_truth_label_rules(lab_data):
    """The label rules the corpus supports, and the ones it does not."""
    from lab.bench.tasks import load_ground_truth

    gt = load_ground_truth(RECORDING_ID)
    assert len(gt.segments) == 2
    a, b = gt.segments
    assert not a.end_is_explicit and b.end_is_explicit
    # tune A runs straight into tune B, so its implicit end is a real boundary
    assert a.end_is_trustworthy and not a.unmarked_set_end
    # boundaries are the two starts plus the one explicit end
    kinds = [x["kind"] for x in gt.boundaries()]
    assert kinds == ["start", "start", "end"]
    # only the region after an explicit end is labelled "no music"
    labels = gt.activity_intervals()
    assert any(v == 1 for _, _, v in labels)
    assert all(v == 1 for *_, v in labels), "no explicit end is followed by another tune here"


def test_unmarked_set_end_warns_rather_than_compensating(lab_data, tmp_path):
    """The data error is reported by name; it is fixable at source."""
    import json

    from lab.bench.tasks import load_ground_truth

    path = paths.manifest_path(RECORDING_ID)
    with open(path) as f:
        manifest = json.load(f)
    # make tune B's end implicit while the log still says a set ends there
    manifest["segments"][1]["end_is_explicit"] = False
    with open(path, "w") as f:
        json.dump(manifest, f)

    gt = load_ground_truth(RECORDING_ID)
    assert gt.segments[1].unmarked_set_end
    assert any("no explicit end" in w for w in gt.warnings)
    assert any("Test Tune B" in w for w in gt.warnings)


def test_evaluate_run_reports_every_metric(lab_data):
    from lab.board.board import Board
    from lab.eval.metrics import evaluate_run

    with Board() as board:
        run_id = _run(board)
        r = evaluate_run(board, run_id)

    ident = r["identification"]
    assert ident["n_evaluated"] >= 1
    for key in ("top1", "top5", "found_within_30s", "found_within_60s"):
        assert set(ident[key]) == {"value", "lo", "hi", "k", "n"}
        assert 0.0 <= ident[key]["lo"] <= ident[key]["value"] <= ident[key]["hi"] <= 1.0
    assert "ece" in ident["calibration"]
    assert "flips_mean" in ident
    assert "boundary_observations" in r["segmentation"]
    assert "hypothesis_spans" in r["segmentation"]
    for src in r["segmentation"].values():
        assert set(src["by_tolerance"]) == {"1000", "3000", "5000"}
    assert r["cost_by_expert"]


def test_eval_writes_markdown_and_rows(lab_data):
    from lab.board.board import Board
    from lab.eval.report import main as eval_main

    with Board() as board:
        run_id = _run(board)
    eval_main(argparse.Namespace(run_id=run_id, quiet=True))
    out = paths.run_dir(run_id)
    assert os.path.exists(os.path.join(out, "eval.json"))
    md = open(os.path.join(out, "eval.md")).read()
    assert "## Identification" in md and "## Segmentation" in md and "## Cost" in md

    with Board() as board:
        rows = board.conn.execute(
            "SELECT COUNT(*) FROM eval_segment WHERE run_id=?", (run_id,)).fetchone()[0]
    assert rows == 2


def test_diff_refuses_incomparable_runs_and_compares_comparable_ones(lab_data, capsys):
    from lab.board.board import Board
    from lab.eval.diff import main as diff_main

    no_prior = dict(CONFIG)
    no_prior = {**CONFIG, "name": "no-prior",
                "experts": [e for e in CONFIG["experts"] if e["name"] != "prior"]}
    with Board() as board:
        a = _run(board)
        b = _run(board, no_prior)

    diff_main(argparse.Namespace(run_a=a, run_b=b, intersection=False))
    printed = capsys.readouterr().out
    assert "segments compared" in printed
    assert "top-1 at end" in printed
    assert "cost per audio minute" in printed

    with Board() as board:
        partial = _run(board, {**CONFIG, "range": "0:05-0:20"})
    with pytest.raises(SystemExit):
        diff_main(argparse.Namespace(run_a=a, run_b=partial, intersection=False))


def test_inspection_tools_run(lab_data, capsys):
    from lab.board.board import Board
    from lab.tools.dump import main as board_main
    from lab.tools.runs import main as runs_main
    from lab.tools.timeline import main as timeline_main

    with Board() as board:
        run_id = _run(board)

    runs_main(argparse.Namespace(recording=None, limit=10))
    assert run_id in capsys.readouterr().out

    board_main(argparse.Namespace(run_id=run_id, types=None, time_range=None,
                                  expert=None, limit=50, json=False))
    dumped = capsys.readouterr().out
    assert "audio_chunk" in dumped and "@1" in dumped

    timeline_main(argparse.Namespace(run_id=run_id, segment=None, top=3))
    tl = capsys.readouterr().out
    assert "segment" in tl and synthetic.TUNE_A["name"] in tl


def test_transcribe_prints_notes_and_can_match(lab_data, capsys):
    from lab.tools.transcribe import main as transcribe_main

    transcribe_main(argparse.Namespace(
        recording=RECORDING_ID, segment=1, time_range=None, source="pitch_yin",
        match=True, candidate_set="repertoire", run=None, n=6, no_fold=False))
    out = capsys.readouterr().out
    assert "notes, median" in out
    assert "against the repertoire index" in out


def test_pitch_labels_round_trip_and_score(lab_data, tmp_path, monkeypatch):
    """Hand-drawn pitch is the only thing that can score a front end directly.

    The corpus says which tune was playing, never which notes. These labels
    are made by hand and are not reproducible from anything else, so they are
    written outside lab/data and this checks they survive the trip.
    """
    import numpy as np

    from lab.bench import pitch as pitch_mod
    from lab.tools import viewer

    monkeypatch.setattr(viewer, "ANNOTATIONS", str(tmp_path / "annotations"))
    monkeypatch.setattr(pitch_mod, "ANNOTATIONS", str(tmp_path / "annotations"))

    assert viewer.load_annotation(RECORDING_ID, 1, 0) == []
    path, count = viewer.save_annotation({
        "recording_id": RECORDING_ID, "segment_id": 1, "t0_ms": 4000, "duration_s": 6.0,
        "tune_id": synthetic.TUNE_A["tune_id"], "tune_name": synthetic.TUNE_A["name"],
        "frontend": "yin v1",
        "labels": [{"t0": 1.0, "t1": 1.4, "midi": 62, "from": "accepted"},
                   {"t0": 0.2, "t1": 0.6, "midi": 74, "from": "drawn", "grid": True}],
    })
    assert count == 2
    back = viewer.load_annotation(RECORDING_ID, 1, 4000)
    assert [v["t0"] for v in back] == [0.2, 1.0], "labels come back in time order"
    # stored as pitch classes: 74 is a D two octaves up, and octave says
    # nothing about which tune is playing
    assert back[0]["midi"] == 62 and back[1]["midi"] == 62
    # an eighth drawn on the grid says so, so reloading does not fuse it
    # with a neighbour of the same pitch
    assert back[0].get("grid") is True and "grid" not in back[1]

    # the grid is what scoring compares, one question per 10ms
    grid = pitch_mod._to_grid(back, 6.0)
    assert grid.size == 600
    assert grid[30] == 62 and grid[110] == 62
    assert grid[400] == -1, "unlabelled time must not be scored"

    from lab.frontends import get_frontend

    result = pitch_mod.run_pitch(get_frontend("yin"), quiet=True)
    for key in ("coverage", "exact", "octave_blind", "within_semitone"):
        assert 0.0 <= result.pooled[key] <= 1.0
    assert result.pooled["segments"] == 1
    assert np.isclose(result.pooled["labelled_s"], 0.8, atol=0.05)


def test_pitch_task_says_so_when_there_is_nothing_to_score(lab_data, tmp_path, monkeypatch):
    from lab.bench import pitch as pitch_mod
    from lab.frontends import get_frontend

    monkeypatch.setattr(pitch_mod, "ANNOTATIONS", str(tmp_path / "empty"))
    with pytest.raises(SystemExit, match="no pitch labels yet"):
        pitch_mod.run_pitch(get_frontend("yin"))
