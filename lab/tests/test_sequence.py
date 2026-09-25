"""How much the previous tune should pull on the next, and when not at all.

Some pairs at a session are all but fixed -- Cooley's is followed by The Wise
Maid 83% of seventy times -- and many are close to random. The weighting that
scales with that has to leave a random predecessor contributing nothing, keep
each row a proper distribution so the whole-set decoder is not biased towards
vague tunes, and, in its all-or-nothing form, agree with the rule the app
already uses to suggest the next tune to log.
"""

import json
import os

import pytest

from lab import paths
from lab.corpus.sequence import SequenceModel


def night(instance, *items):
    """items: tune ids, or "|" for a break between sets."""
    rows, pos = [], 0
    for it in items:
        pos += 1
        if it == "|":
            rows.append({"session_instance_id": instance, "record_type": "break",
                         "tune_id": None, "order_position": str(pos)})
        else:
            rows.append({"session_instance_id": instance, "record_type": "tune",
                         "tune_id": it, "order_position": str(pos)})
    return rows


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))

    def write(rows):
        path = paths.session_history_path(1)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"session_id": 1, "rows": rows}, f)
        return SequenceModel(1)
    saved = (SequenceModel.MODE, SequenceModel.SCALE_OPENERS, SequenceModel.GATE,
             SequenceModel.UNSEEN)
    yield write
    (SequenceModel.MODE, SequenceModel.SCALE_OPENERS, SequenceModel.GATE,
     SequenceModel.UNSEEN) = saved


def fixed_pair_and_random(n_nights=10):
    """Tune 1 is always followed by 2; tune 3 by something different each night."""
    rows = []
    for i in range(n_nights):
        rows += night(i, 1, 2, "|", 3, 100 + i, "|", 5, 6)
    return rows


def test_a_fixed_pair_pulls_and_a_random_one_does_not(history):
    SequenceModel.MODE, SequenceModel.UNSEEN = "strength", "share"
    m = history(fixed_pair_and_random())
    after_fixed = m.weights(1)
    after_random = m.weights(3)
    others = [t for t in m.played if t not in (2,)]
    assert after_fixed[2] > 10 * max(after_fixed[t] for t in others)
    spread = [after_random[t] for t in m.played]
    assert max(spread) / min(spread) < 1.6        # nearly flat: says almost nothing


def test_every_row_is_a_distribution(history):
    """Otherwise a tune with vague followers is a cheap state for the decoder."""
    SequenceModel.MODE, SequenceModel.UNSEEN = "strength", "share"
    m = history(fixed_pair_and_random())
    for prev in (1, 3, 5):
        assert sum(m.weights(prev)[t] for t in m.played) == pytest.approx(1.0)


def test_no_favourites_leak_in_through_a_weak_transition(history):
    """The old fallback gave popular tunes a boost after any weak transition."""
    SequenceModel.MODE, SequenceModel.UNSEEN = "strength", "share"
    rows = fixed_pair_and_random() + night(99, 7, 7, 7, 7, 7, 7)   # 7 is a favourite
    m = history(rows)
    after_random = m.weights(3)
    assert after_random[7] == pytest.approx(after_random[8] if 8 in m.played else after_random[6],
                                            rel=0.5)


@pytest.mark.parametrize("followers,qualifies", [
    ([2, 2, 2, 9], True),        # 3 of 4: the app's own qualifying case
    ([2, 2], False),             # seen only twice
    ([2, 2, 9, 9], False),       # exactly half is not more than half
])
def test_the_app_rule_is_the_apps_rule(history, followers, qualifies):
    SequenceModel.MODE, SequenceModel.GATE, SequenceModel.UNSEEN = "strength", "app", "share"
    rows = []
    for i, f in enumerate(followers):
        rows += night(i, 1, f)
    m = history(rows)
    w = m.weights(1)
    flat = all(abs(w[t] - w[1]) < 1e-12 for t in m.played)
    assert flat != qualifies


def test_a_break_ends_the_chain(history):
    """Also the app's rule: a transition across a set break does not count."""
    SequenceModel.MODE = "strength"
    rows = []
    for i in range(6):
        rows += night(i, 1, "|", 2)
    m = history(rows)
    assert m.follow_totals.get(1, 0) == 0


def test_by_default_a_weak_predecessor_still_says_who_has_followed_it(history):
    """What the corpus actually favoured over the pure design.

    After a tune whose follower is a coin toss, the ones that HAVE followed it
    keep a modest edge over ones that never have -- a session has habits
    beyond its fixed pairs -- while the favourite follower of a fixed pair is
    still pulled far harder, and a session favourite that never followed gets
    nothing for being a favourite.
    """
    SequenceModel.MODE, SequenceModel.UNSEEN = "strength", "floor"
    rows = fixed_pair_and_random() + night(99, 7, 7, 7, 7, 7, 7)
    m = history(rows)
    after_random = m.weights(3)
    followed_once = after_random[100]
    never_followed = after_random[1]
    favourite = after_random[7]
    assert followed_once > 3 * never_followed
    assert favourite == pytest.approx(never_followed)
    after_fixed = m.weights(1)
    assert after_fixed[2] / after_fixed[1] > followed_once / never_followed
