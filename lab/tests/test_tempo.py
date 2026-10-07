"""analysis.tempo: a candidate's type against the beat heard."""

import math

from lab.analysis.tempo import CAP, TempoModel, fold


def _rows(t, period, grouping, n=20, rid=1):
    return [{"rid": rid, "type": t, "period_ms": period * (1 + 0.02 * ((i % 5) - 2)), "grouping": grouping}
            for i in range(n)]


def test_a_polka_beat_costs_a_reel_and_not_a_polka():
    m = TempoModel.fit(_rows("reel", 153, 2) + _rows("polka", 215, 2) + _rows("jig", 166, 3))
    cost = m.penalties(218, 2, 0.5)
    assert cost["polka"] == 0.0
    assert 0 < cost["reel"] <= CAP and cost["jig"] == CAP


def test_threes_cost_a_reel_at_a_jigs_speed():
    m = TempoModel.fit(_rows("reel", 153, 2) + _rows("jig", 166, 3))
    cost = m.penalties(166, 3, 0.5)
    assert cost["jig"] == 0.0 and cost["reel"] > 0


def test_a_weak_beat_says_nothing_and_a_night_can_be_left_out():
    m = TempoModel.fit(_rows("reel", 153, 2) + _rows("jig", 166, 3, rid=2), exclude_rids={2})
    assert m.penalties(166, 3, 0.05) == {}
    assert set(m.types) == {"reel"}
    assert fold(306) == 153 and fold(76.5) == 153


def test_a_slow_polka_is_not_halved_into_a_reel():
    m = TempoModel.fit(_rows("reel", 153, 2) + _rows("polka", 250, 2))
    assert abs(math.exp(m.types["polka"]["mu"]) - 250) < 10
    cost = m.penalties(252, 2, 0.5)
    assert cost["polka"] == 0.0 and cost["reel"] > 0
