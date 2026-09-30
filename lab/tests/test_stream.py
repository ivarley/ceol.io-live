"""The change-detection decoder on made-up chunk scores."""

from lab.bench.stream import NONE, Decoder


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
    for kw in ({}, {"lam": 40, "tau": 0.45, "p_switch": 0.05, "p_none": 0.1}):
        assert HintDecoder(**kw).run(chunks) == Decoder(**kw).run(chunks)


def test_meter_hint_moves_off_a_jig_heard_in_twos():
    from lab.bench.stream import HintDecoder

    types = {1: "Jig", 2: "Reel"}
    jig = [{**chunk({1: 0.7, 2: 0.3}), "grouping": 3, "grouping_margin": 0.5} for _ in range(10)]
    # the reel starts but the jig still half-matches it (a related tune)
    reel = [{**chunk({1: 0.55, 2: 0.6}), "grouping": 2, "grouping_margin": 0.5} for _ in range(6)]
    plain = HintDecoder(tune_types=types).run(jig + reel)
    hinted = HintDecoder(tune_types=types, mu=0.1).run(jig + reel)
    assert hinted.index(2) < plain.index(2) if 2 in plain else 2 in hinted


def test_mix_windows_with_only_the_full_window_changes_nothing():
    from lab.bench.stream import mix_windows

    chunks = [{**chunk({1: 0.6, 2: 0.3}), "by_window": {4000: {1: 0.2, 2: 0.7}}}]
    assert mix_windows(chunks, {8000: 1.0})[0]["scores"] == {1: 0.6, 2: 0.3}
    assert mix_windows(chunks, {4000: 1.0})[0]["scores"] == {1: 0.2, 2: 0.7}
    half = mix_windows(chunks, {8000: 1, 4000: 1})[0]
    assert half["scores"] == {1: 0.4, 2: 0.5} and half["floor"] == 0.4
