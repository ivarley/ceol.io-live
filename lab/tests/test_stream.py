"""The change-detection decoder on made-up chunk scores."""

from lab.bench.stream import NONE
from lab.bench.stream import Decoder as _Decoder


def Decoder(**kw):
    # the mechanism is tested at the gentle setting these cases were written
    # for; the tuned default (lam 40) is decisive enough that one strongly
    # contrary chunk flips it for a chunk, which on real nights it does about
    # twice a tune
    return _Decoder(**{"lam": 10.0, "tau": 0.35, "p_switch": 0.02, "p_none": 0.3, **kw})


def chunk(scores, floor=0.2):
    return {"t_ms": 0, "scores": scores, "floor": floor, "n_notes": 40}


def test_follows_a_change_within_a_few_chunks():
    a = [chunk({1: 0.7, 2: 0.25, 3: 0.3}) for _ in range(10)]
    b = [chunk({1: 0.25, 2: 0.7, 3: 0.3}) for _ in range(10)]
    shown = Decoder().run(a + b)
    assert shown[5] == 1
    switch = shown.index(2)
    assert 10 <= switch <= 13
    assert all(s == 2 for s in shown[switch:])


def test_chat_reads_as_not_a_tune():
    tune = [chunk({1: 0.7, 2: 0.25}) for _ in range(8)]
    chat = [chunk({1: 0.15, 2: 0.2, 3: 0.22}, floor=0.1) for _ in range(8)]
    shown = Decoder().run(tune + chat)
    assert shown[-1] == NONE


def test_one_odd_chunk_does_not_flip_the_answer():
    run = [chunk({1: 0.7, 2: 0.25}) for _ in range(8)]
    odd = [chunk({1: 0.3, 2: 0.6})]
    shown = Decoder().run(run + odd + run)
    assert all(s == 1 for s in shown[4:])


def test_hint_decoder_with_hints_off_is_the_decoder():
    import random

    from lab.bench.stream import HintDecoder

    rnd = random.Random(3)
    chunks = []
    for i in range(60):
        tune = 1 if i < 25 else (NONE if i < 32 else 2)
        sc = {t: rnd.uniform(0.15, 0.35) for t in (1, 2, 3, 4)}
        if tune != NONE:
            sc[tune] = rnd.uniform(0.5, 0.8)
        chunks.append({**chunk(sc), "t_ms": 4000 * i, "grouping": 2, "grouping_margin": 0.5,
                       "where": {1: (i % 10) / 10, 2: (i % 7) / 7}})
    for kw in ({"lam": 10.0, "tau": 0.35, "p_switch": 0.02, "p_none": 0.3},
               {"lam": 40, "tau": 0.45, "p_switch": 0.05, "p_none": 0.1}, {}):
        assert HintDecoder(**kw).run(chunks) == _Decoder(**kw).run(chunks)


def test_meter_hint_moves_off_a_jig_heard_in_twos():
    from lab.bench.stream import HintDecoder

    types = {1: "Jig", 2: "Reel"}
    jig = [{**chunk({1: 0.7, 2: 0.3}), "grouping": 3, "grouping_margin": 0.5} for _ in range(10)]
    # the reel starts but the jig still half-matches it (a related tune)
    reel = [{**chunk({1: 0.55, 2: 0.6}), "grouping": 2, "grouping_margin": 0.5} for _ in range(6)]
    gentle = {"lam": 10.0, "tau": 0.35, "p_switch": 0.02, "p_none": 0.3}
    plain = HintDecoder(tune_types=types, **gentle).run(jig + reel)
    hinted = HintDecoder(tune_types=types, mu=0.1, **gentle).run(jig + reel)
    assert hinted.index(2) < plain.index(2) if 2 in plain else 2 in hinted


def test_mix_windows_with_only_the_full_window_changes_nothing():
    from lab.bench.stream import mix_windows

    chunks = [{**chunk({1: 0.6, 2: 0.3}), "by_window": {4000: {1: 0.2, 2: 0.7}}}]
    assert mix_windows(chunks, {8000: 1.0})[0]["scores"] == {1: 0.6, 2: 0.3}
    assert mix_windows(chunks, {4000: 1.0})[0]["scores"] == {1: 0.2, 2: 0.7}
    half = mix_windows(chunks, {8000: 1, 4000: 1})[0]
    assert half["scores"] == {1: 0.4, 2: 0.5} and half["floor"] == 0.4


def test_confirm_and_rule_out():
    d = Decoder()
    tune1 = [chunk({1: 0.7, 2: 0.6, 3: 0.2}) for _ in range(5)]
    d.run(tune1)
    d.rule_out([1])
    assert d.belief(1)[0][0] != 1
    d.confirm(3)
    assert d.belief(1)[0][0] == 3
    d.confirm(99)                       # a tune the decoder had not seen yet
    assert d.belief(1)[0][0] == 99


def test_meter_says_the_tune_may_have_changed_when_held_then_doubted():
    """ChangeWatch, rule "held": a tune at 99% for 40 s whose belief falls
    under 95% is no longer claimed, until it is back at 99% or another is
    shown."""
    from lab.tools.listen import ChangeWatch

    w = ChangeWatch()

    def at(t, p, shown=7, none=0.0, other=None):
        belief = {7: p}
        if other:
            belief[other] = 1 - p
        return w.step(t, belief, shown, none)

    for t in range(0, 44000, 4000):
        assert at(t, 0.995) is None
    assert at(44000, 0.9) == 7                 # held 44 s, now doubted
    assert at(48000, 0.97) == 7                # still not back to 99%
    assert at(52000, 0.995) is None            # back: claimed again
    assert at(56000, 0.6) == 7
    assert at(60000, 0.4, shown=9, other=9) is None   # another shown: the meter names it
    assert at(64000, 0.995) is None
    assert at(68000, 0.8) is None              # a new tune, held 4 s only
    assert at(72000, 0.2, none=0.8) is None    # "not a tune" ends it


def test_meter_says_the_tune_may_have_changed_once_played_round_and_doubted():
    """ChangeWatch, rule "rounds": a tune at 99% that has gone round 1.8 times
    (time over the beat times its eighths per round) and falls under 80%."""
    from lab.tools.listen import ChangeWatch

    w = ChangeWatch(rounds=lambda tune: {7: 100}.get(tune))   # 100 eighths a round
    period = 200                                             # ms an eighth: 20 s a round

    def at(t, p, shown=7):
        return w.step(t, {shown: p}, shown, 0.0, period)

    assert at(0, 0.995) is None
    assert at(30000, 0.7) is None              # 1.5 rounds: a dip mid-tune says nothing
    assert at(34000, 0.85) is None
    assert at(36000, 0.995) is None
    assert at(40000, 0.7) == 7                 # 2 rounds, doubted
    assert at(44000, 0.9) == 7                 # until back at 99%
    assert at(48000, 0.995) is None
    # a tune with no readable setting counts by time: 40 s
    assert at(52000, 0.995, shown=9) is None
    assert at(80000, 0.7, shown=9) is None
    assert at(96000, 0.7, shown=9) == 9
    # the beat folded to an eighth: a quarter-note period counts the same
    w2 = ChangeWatch(rounds=lambda tune: 100)
    w2.step(0, {7: 0.995}, 7, 0.0, 400)
    assert w2.step(40000, {7: 0.7}, 7, 0.0, 400) == 7
