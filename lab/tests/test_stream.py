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
