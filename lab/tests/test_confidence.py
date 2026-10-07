"""The chance a logged tune is right (analysis.confidence): its labels, its
features, and the cap that keeps 100 for a person's word."""

import numpy as np

from lab.analysis import confidence as cf


def _manifest(segments, duration_ms=600000):
    return {"recording": {"duration_ms": duration_ms}, "segments": segments}


def test_a_draft_is_right_wrong_or_over_nothing():
    m = _manifest([
        {"start_ms": 0, "tune_id": 1, "end_is_explicit": False},
        {"start_ms": 100000, "tune_id": 2, "end_is_explicit": True, "resolved_end_ms": 200000},
        {"start_ms": 300000, "tune_id": 1113, "end_is_explicit": True, "resolved_end_ms": 400000},
    ])
    drafts = [
        {"start_ms": 2000, "end_ms": None, "tune_id": 1},                # right
        {"start_ms": 101000, "end_ms": 199000, "tune_id": 3},            # wrong tune
        {"start_ms": 240000, "end_ms": 280000, "tune_id": 4},            # over no labelled tune
        {"start_ms": 300000, "end_ms": 400000, "tune_id": 5278},         # a thesession.org duplicate
    ]
    lab = cf.labels(drafts, m, same={1113: 1113, 5278: 1113})
    assert [lab[id(d)] for d in drafts] == [1, 0, 0, 1]


def test_features_read_the_stretch_the_tune_was_shown():
    states = [{"t_ms": t, "top": [{"tune_id": 7, "p": p}], "shown": 7 if p > 0.5 else None, "tuneness": 0.9}
              for t, p in ((4000, 0.2), (8000, 0.9), (12000, 1.0), (16000, 1.0), (20000, 0.4))]
    d = {"start_ms": 5000, "end_ms": 60000, "tune_id": 7, "conf": 1.0, "outside": False,
         "first_shown_ms": 8000, "last_shown_ms": 16000}
    cf.features([d], states, 600000)
    f = d["features"]
    assert f["belief"] == 1.0 and f["shown_frac"] == 1.0 and f["length_s"] == 55.0
    assert 0.9 <= f["belief_low"] < 1.0 and f["tuneness"] == 0.9 and f["outside"] is False


def test_the_model_never_says_100():
    m = cf.ConfidenceModel(coef=np.ones(len(cf.NAMES)) * 5, intercept=20, mu=np.zeros(len(cf.NAMES)),
                           sd=np.ones(len(cf.NAMES)), version=1)
    f = {"belief": 1.0, "belief_low": 1.0, "shown_frac": 1.0, "length_s": 300, "tunebooks": 5000,
         "outside": False, "tuneness": 1.0}
    assert m.p_right(f) > 0.999 and m.percent(f) == 99
