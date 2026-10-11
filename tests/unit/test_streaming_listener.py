"""
The streaming sidecar's global LISTEN survives a database restart (spec 024 §A4).

The loop is driven with a fake connection: no server, no DB. Backoff sleeps are
recorded rather than waited for.
"""

import asyncio

import pytest

import streaming.service as svc

pytestmark = pytest.mark.unit


class FakeConn:
    """Enough of asyncpg.Connection for _listener_loop: a termination listener, a
    LISTEN, a ping, and a way for the test to kill it."""

    def __init__(self, ping_fails=False):
        self._on_terminate = []
        self.listening = []
        self.terminated = False
        self.ping_fails = ping_fails

    def add_termination_listener(self, cb):
        self._on_terminate.append(cb)

    async def add_listener(self, channel, cb):
        self.listening.append(channel)

    async def execute(self, sql):
        if self.ping_fails:
            raise ConnectionResetError("socket died silently")

    def terminate(self):
        self.terminated = True

    def drop(self):
        """What asyncpg does when the server closes the connection."""
        for cb in self._on_terminate:
            cb(self)


class Harness:
    def __init__(self, monkeypatch):
        self.conns = []
        self.sleeps = []
        self.make = lambda: FakeConn()
        self.queue = asyncio.Queue()

        async def connect():
            conn = self.make()
            self.conns.append(conn)
            return conn

        async def sleep(seconds):
            self.sleeps.append(seconds)
            await asyncio.sleep(0)  # yield, so the loop stays cancellable

        monkeypatch.setattr(svc, "_connect_listener", connect)
        monkeypatch.setattr(svc, "_sleep", sleep)
        monkeypatch.setattr(svc, "PRESENCE", {7: {1: {"queue": self.queue}}})

    async def until(self, pred, what):
        for _ in range(2000):
            if pred():
                return
            await asyncio.sleep(0.001)
        raise AssertionError(f"timed out waiting for {what}")

    @property
    def listening(self):
        return [c for c in self.conns if c.listening]


def run(test):
    """Run one async test body under a fresh loop with a hard timeout."""

    async def body():
        task = asyncio.create_task(svc._listener_loop())
        try:
            await test()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(asyncio.wait_for(body(), timeout=5))


@pytest.fixture
def h(monkeypatch):
    return Harness(monkeypatch)


def test_listens_on_the_channel_and_does_not_resync_on_first_connect(h):
    async def t():
        await h.until(lambda: h.listening, "the first LISTEN")
        assert h.conns[0].listening == [svc.LIVE_EVENT_CHANNEL]
        assert h.queue.empty()
        assert h.sleeps == []

    run(t)


def test_reconnects_after_the_server_drops_it_and_resyncs_open_streams(h):
    async def t():
        await h.until(lambda: h.listening, "the first LISTEN")
        h.conns[0].drop()
        await h.until(lambda: len(h.listening) == 2, "a second LISTEN")
        assert h.conns[0].terminated
        assert h.conns[1].listening == [svc.LIVE_EVENT_CHANNEL]
        assert h.queue.get_nowait() == ("resync",)
        assert h.sleeps == [svc.LISTENER_RETRY_SECONDS]

    run(t)


def test_backs_off_while_connecting_fails_then_resets(h):
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] <= 3:
            raise OSError("connection refused")
        return FakeConn()

    h.make = flaky

    async def t():
        await h.until(lambda: h.listening, "a LISTEN after three failures")
        assert h.sleeps == [1.0, 2.0, 4.0]
        h.listening[0].drop()
        await h.until(lambda: len(h.listening) == 2, "the reconnect")
        assert h.sleeps[-1] == 1.0  # a successful connect resets the backoff

    run(t)


def test_backoff_is_capped(h):
    def never():
        raise OSError("still down")

    h.make = never

    async def t():
        await h.until(lambda: len(h.sleeps) >= 8, "eight retries")
        assert h.sleeps[:6] == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
        assert max(h.sleeps) == svc.LISTENER_RETRY_MAX_SECONDS

    run(t)


def test_a_silently_dead_socket_is_noticed_by_the_idle_ping(h, monkeypatch):
    monkeypatch.setattr(svc, "LISTENER_PING_SECONDS", 0.01)
    h.make = lambda: FakeConn(
        ping_fails=len(h.conns) == 0
    )  # only the first one is dead

    async def t():
        await h.until(lambda: len(h.listening) == 2, "a reconnect driven by the ping")
        assert h.conns[0].terminated
        assert h.queue.get_nowait() == ("resync",)

    run(t)
