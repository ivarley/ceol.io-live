"""Alignment forgives the single inserted or dropped note that breaks every
n-gram spanning it."""

import numpy as np

from lab.analysis.align import chunk_score, local_align

TUNE = [2, 4, 6, 7, 9, 11, 9, 7, 6, 4, 2, 4, 6, 9, 7, 6] * 2


def test_an_exact_copy_scores_the_most():
    assert chunk_score(TUNE[:16], TUNE, chunk=16) == 1.0


def test_one_inserted_note_costs_one_gap_not_a_phrase():
    heard = TUNE[:8] + [1] + TUNE[8:16]
    score = chunk_score(heard, TUNE, chunk=32)
    assert 0.9 < score < 1.0


def test_unknowns_score_nothing_either_way():
    q = np.array([2, -1, 6], dtype=np.int8)
    t = np.array([2, 4, 6], dtype=np.int8)
    assert local_align(q, t, 2.0, -1.0, -1.0) == 4.0


def test_a_chunk_may_run_from_the_end_of_the_tune_into_its_start():
    heard = TUNE[-4:] + TUNE[:4]
    assert chunk_score(heard, TUNE[:16] + TUNE[16:], chunk=8) == 1.0


def test_an_unrelated_line_scores_low():
    rng = np.random.default_rng(0)
    other = list(rng.integers(0, 12, 32))
    assert chunk_score(other, TUNE, chunk=16) < 0.5
