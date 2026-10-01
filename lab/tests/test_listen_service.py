"""The listening service takes each sample once, in order, whatever order and
how many times the chunks arrive (a phone resending after a reconnect)."""

import numpy as np


def _stream():
    from listen.service import Stream

    s = Stream.__new__(Stream)
    s.have, s.ahead = 0, {}
    got = []

    class Store:
        def append(self, y):
            got.append(np.array(y))

    s.listener = type("L", (), {"store": Store()})()
    return s, got


def test_chunks_in_order_repeated_and_ahead_of_a_gap():
    s, got = _stream()
    y = np.arange(100, dtype=np.float32)
    s.take(0, y[:30])
    s.take(60, y[60:90])          # ahead of a gap
    s.take(0, y[:30])             # a repeat after a reconnect
    s.take(20, y[20:45])          # overlaps what is held
    assert s.have == 45
    s.take(45, y[45:70])          # fills the gap and overlaps what was ahead
    s.take(90, y[90:100])
    assert s.have == 100
    assert np.array_equal(np.concatenate(got), y)


def test_skip_fills_a_gap_the_phone_no_longer_has_with_silence():
    s, got = _stream()
    s.take(0, np.ones(10, dtype=np.float32))
    s.take(30, np.ones(5, dtype=np.float32) * 2)     # arrives after the gap
    s.skip_to(25)
    assert s.have == 25                              # silence up to 25, then nothing at 25-30 yet
    s.skip_to(30)
    assert s.have == 35                              # the held chunk follows
    y = np.concatenate(got)
    assert list(y[:10]) == [1] * 10 and list(y[10:30]) == [0] * 20 and list(y[30:]) == [2] * 5
