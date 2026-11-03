"""Recording on the server (spec 061 stage 5): the listening service files a
night's stream as the night's recording, through the web app's own recording
endpoints (listen/recording.py), and the service decides when (listen/service.py).

The web app and the bucket are one small HTTP server here, which records what
it was sent."""

import asyncio
import datetime
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
import soundfile as sf

from listen import recording
from listen.recording import SR, NightRecording, meter_log


class FakeCeol:
    """The web app's recording endpoints and a bucket, at one address."""

    def __init__(self):
        self.calls = []
        self.objects = {}
        self.refuse = set()  # paths answered 403
        self.fail_times = {}  # path -> 500s to answer first
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(n) if n else b""

            def _reply(self, code, obj):
                raw = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _handle(self):
                body = self._body()
                path = self.path.split("?")[0]
                fake.calls.append(
                    (
                        self.command,
                        path,
                        self.headers.get("Authorization"),
                        self.headers.get("Content-Type"),
                        body,
                    )
                )
                if path in fake.refuse:
                    return self._reply(
                        403,
                        {
                            "success": False,
                            "error": "You can't manage this session's recordings",
                        },
                    )
                if fake.fail_times.get(path):
                    fake.fail_times[path] -= 1
                    return self._reply(500, {"success": False, "error": "down"})
                if self.command == "GET" and path.endswith("/recordings"):
                    return self._reply(200, {"recordings": []})
                if path == "/api/recordings/upload-url":
                    key = f"recordings/abc/{json.loads(body)['filename']}"
                    return self._reply(
                        200,
                        {
                            "upload_url": f"{fake.url}/bucket/{key}",
                            "storage_key": key,
                            "content_type": "audio/flac",
                        },
                    )
                if path.startswith("/bucket/"):
                    fake.objects[path.removeprefix("/bucket/")] = body
                    return self._reply(200, {})
                if path == "/api/recordings":
                    return self._reply(201, {"success": True, "recording_id": 77})
                if path.endswith("/listen-log"):
                    return self._reply(200, {"success": True})
                return self._reply(404, {})

            do_GET = do_POST = do_PUT = _handle

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def paths(self):
        return [(c[0], c[1]) for c in self.calls]

    def call(self, method, path):
        return next(c for c in self.calls if c[0] == method and c[1] == path)


@pytest.fixture
def ceol():
    f = FakeCeol()
    yield f
    f.server.shutdown()


def write_stream(d, seconds, states=(), taps=()):
    """A stream's folder as the Listener leaves it: audio.flac, states, taps."""
    os.makedirs(d, exist_ok=True)
    n = int(seconds * SR)
    y = (0.1 * np.sin(np.arange(n) * 2 * np.pi * 440 / SR)).astype(np.float32)
    sf.write(os.path.join(d, "audio.flac"), y, SR, subtype="PCM_16", format="FLAC")
    with open(os.path.join(d, "states.jsonl"), "w") as f:
        for s in states:
            f.write(json.dumps(s) + "\n")
    with open(os.path.join(d, "taps.jsonl"), "w") as f:
        for tp in taps:
            f.write(json.dumps(tp) + "\n")
    return n


START = "2026-11-02T20:00:00+00:00"


def test_a_stream_is_filed_as_the_nights_recording(ceol, tmp_path):
    d = str(tmp_path / "s1")
    n = write_stream(
        d,
        20,
        states=[{"t_ms": 4000, "top": []}, {"t_ms": 8000, "top": []}],
        taps=[{"t_ms": 6000, "action": "this", "tune_id": 5}],
    )
    rec = NightRecording(120, "tok", START, "Downtown Session, Mon · Nov 2, 2026")
    rec.took_audio(0)
    assert rec.file(d, ceol.url, sleep=lambda s: None) == 77

    assert ceol.paths() == [
        ("POST", "/api/recordings/upload-url"),
        ("PUT", "/bucket/recordings/abc/ceol-listen-2026-11-02.flac"),
        ("POST", "/api/recordings"),
        ("PUT", "/api/recordings/77/listen-log"),
    ]
    # as the person listening; the bucket gets no token
    assert ceol.call("POST", "/api/recordings")[2] == "Bearer tok"
    assert (
        ceol.call("PUT", "/bucket/recordings/abc/ceol-listen-2026-11-02.flac")[2]
        is None
    )
    stored = ceol.objects["recordings/abc/ceol-listen-2026-11-02.flac"]
    assert stored[:4] == b"fLaC"
    body = json.loads(ceol.call("POST", "/api/recordings")[4])
    assert body == {
        "session_instance_id": 120,
        "storage_key": "recordings/abc/ceol-listen-2026-11-02.flac",
        "started_at": START,
        "duration_ms": int(1000 * n / SR),
        "label": "Downtown Session, Mon · Nov 2, 2026 (Ceol website)",
    }
    log = [
        json.loads(x)
        for x in ceol.call("PUT", "/api/recordings/77/listen-log")[4]
        .decode()
        .splitlines()
    ]
    assert [(x["at_ms"], x["dir"], x["msg"]["type"]) for x in log] == [
        (4000, "in", "state"),
        (6000, "out", "tap"),
        (8000, "in", "state"),
    ]
    # filed: the service keeps nothing
    assert rec.filed and not os.path.exists(d)


def test_audio_before_the_first_real_sample_is_not_kept(ceol, tmp_path):
    # a stream resumed on a service that no longer had it: a skip, then audio
    d = str(tmp_path / "s2")
    n = write_stream(d, 30, states=[{"t_ms": 8000}, {"t_ms": 24000}])
    rec = NightRecording(120, "tok", START)
    rec.took_audio(10 * SR)
    rec.file(d, ceol.url, sleep=lambda s: None)

    body = json.loads(ceol.call("POST", "/api/recordings")[4])
    assert body["started_at"] == "2026-11-02T20:00:10+00:00"
    assert body["duration_ms"] == int(1000 * (n - 10 * SR) / SR)
    assert "label" not in body  # no title: the web app names it
    stored = next(iter(ceol.objects.values()))
    tmp = tmp_path / "got.flac"
    tmp.write_bytes(stored)
    assert sf.info(str(tmp)).frames == n - 10 * SR
    log = [
        json.loads(x)
        for x in ceol.call("PUT", "/api/recordings/77/listen-log")[4]
        .decode()
        .splitlines()
    ]
    assert [x["at_ms"] for x in log] == [14000]


def test_a_stream_too_short_to_be_a_night_is_not_filed(ceol, tmp_path):
    d = str(tmp_path / "s3")
    write_stream(d, 3)
    rec = NightRecording(120, "tok", START)
    assert rec.file(d, ceol.url, sleep=lambda s: None) is None
    assert ceol.calls == [] and rec.error == "too short"


def test_a_refusal_is_not_retried(ceol, tmp_path):
    d = str(tmp_path / "s4")
    write_stream(d, 20)
    ceol.refuse.add("/api/recordings/upload-url")
    slept = []
    rec = NightRecording(120, "tok", START)
    assert rec.file(d, ceol.url, sleep=slept.append) is None
    assert slept == [] and rec.error.startswith("refused")
    assert os.path.exists(d)  # not filed, not deleted


def test_a_failure_is_retried_without_uploading_twice(ceol, tmp_path):
    d = str(tmp_path / "s5")
    write_stream(d, 20)
    ceol.fail_times["/api/recordings"] = 2
    slept = []
    rec = NightRecording(120, "tok", START)
    assert rec.file(d, ceol.url, sleep=slept.append, retry_s=(1, 2, 3)) == 77
    assert slept == [1, 2]
    assert [p for p in ceol.paths() if p[1] == "/api/recordings/upload-url"] == [
        ("POST", "/api/recordings/upload-url")
    ]
    assert len(ceol.objects) == 1


def test_may_record_asks_the_web_app(ceol):
    assert recording.may_record(ceol.url, "tok", 120) is None
    assert ceol.paths() == [("GET", "/api/session-instances/120/recordings")]
    ceol.refuse.add("/api/session-instances/121/recordings")
    assert "manage" in recording.may_record(ceol.url, "tok", 121)


def test_the_meter_log_is_the_iphones_shape(tmp_path):
    d = str(tmp_path / "s6")
    write_stream(
        d,
        1,
        states=[{"t_ms": 4000, "none": 0.2}],
        taps=[{"t_ms": 2000, "action": "none"}],
    )
    lines = meter_log(d).decode().splitlines()
    assert json.loads(lines[0]) == {
        "at_ms": 2000,
        "dir": "out",
        "msg": {"type": "tap", "t_ms": 2000, "action": "none"},
    }
    assert json.loads(lines[1])["msg"] == {"type": "state", "t_ms": 4000, "none": 0.2}


def test_started_at_needs_an_offset():
    assert (
        NightRecording(1, "t", "2026-11-02T20:00:00").started_at.tzinfo is not None
    )  # now, not a guess
    assert NightRecording(
        1, "t", "2026-11-02T20:00:00Z"
    ).started_at == datetime.datetime(2026, 11, 2, 20, tzinfo=datetime.timezone.utc)


# --------------------------------------------------------------------------- #
# The service: when a night is recorded, and when it is filed
# --------------------------------------------------------------------------- #


class FakeSocket:
    def __init__(self, messages):
        self.scope = {"headers": []}
        self.query_params = {}
        self.inbox = list(messages)
        self.sent = []
        self.closed = None

    async def accept(self):
        pass

    async def close(self, code=1000):
        self.closed = code

    async def receive(self):
        if self.inbox:
            return {"type": "websocket.receive", "text": json.dumps(self.inbox.pop(0))}
        return {"type": "websocket.disconnect"}

    async def send_text(self, text):
        self.sent.append(json.loads(text))


class StubListener:
    closed = False

    def close(self):
        self.closed = True


class StubStream:
    def __init__(self, sid, mode="audio", known=None):
        self.id, self.mode = sid, mode
        self.have = self.heard_t = self.known_tunes = 0
        self.socket = None
        self.last_seen = 0
        self.dir = f"/nowhere/{sid}"
        self.listener = StubListener()
        self.recording = None
        self.recording_error = None


@pytest.fixture
def service(monkeypatch):
    from listen import service

    async def no_steps(stream):
        return None

    filed = []

    def fake_file(self, stream_dir, api_url, sleep=None, retry_s=()):
        filed.append((self.instance_id, stream_dir, tuple(retry_s)))
        self.filed = True
        return 77

    monkeypatch.setattr(service, "TOKEN", "")
    monkeypatch.setitem(service.state, "models", object())
    monkeypatch.setattr(service, "Stream", StubStream)
    monkeypatch.setattr(service, "_step_loop", no_steps)
    monkeypatch.setattr(service, "_app_token_allowed", lambda token: token == "good")
    monkeypatch.setattr(
        recording,
        "may_record",
        lambda api, token, iid: None if iid == 120 else "not yours",
    )
    monkeypatch.setattr(NightRecording, "file", fake_file)
    service.streams.clear()
    service.filed = filed
    yield service
    service.streams.clear()


RECORD = {
    "type": "start",
    "stream_id": "r-061",
    "sample_rate": 22050,
    "token": "good",
    "instance_id": 120,
    "record": True,
    "started_at": START,
    "title": "Downtown",
}


async def _run(service, ws):
    await service.listen(ws)
    if service.filing:
        await asyncio.wait(list(service.filing))


def test_a_start_that_asks_to_record_gets_a_recording(service):
    ws = FakeSocket([RECORD])
    asyncio.run(_run(service, ws))
    assert ws.sent[0]["type"] == "ready" and ws.sent[0]["recording"] is True
    rec = service.streams["r-061"].recording
    assert (rec.instance_id, rec.token, rec.title) == (120, "good", "Downtown")


def test_a_night_they_may_not_record_says_why_and_listens_anyway(service):
    ws = FakeSocket([{**RECORD, "instance_id": 121}])
    asyncio.run(_run(service, ws))
    assert (
        ws.sent[0]["recording"] is False
        and ws.sent[0]["recording_error"] == "not yours"
    )
    assert service.streams["r-061"].recording is None


def test_a_start_without_record_records_nothing(service):
    ws = FakeSocket([{k: v for k, v in RECORD.items() if k != "record"}])
    asyncio.run(_run(service, ws))
    assert ws.sent[0]["recording"] is False and "recording_error" not in ws.sent[0]


def test_stop_files_the_recording(service):
    ws = FakeSocket([RECORD, {"type": "stop"}])
    asyncio.run(_run(service, ws))
    assert ws.sent[-1] == {"type": "done", "have": 0, "recording": "filing"}
    assert service.filed == [(120, "/nowhere/r-061", (30, 60, 120, 240, 480))]
    assert "r-061" not in service.streams


def test_a_shutdown_files_every_open_recording_once(service):
    ws = FakeSocket([RECORD])
    asyncio.run(_run(service, ws))
    stream = service.streams["r-061"]
    asyncio.run(service._file_all_at_shutdown())
    assert service.filed == [(120, "/nowhere/r-061", ())]
    assert stream.listener.closed and not service.streams


def test_a_recording_stream_waits_longer_before_it_is_swept(service, monkeypatch):
    for sid, rec in (("plain", None), ("rec", NightRecording(120, "good", START))):
        s = StubStream(sid)
        s.recording = rec
        s.last_seen = 0
        service.streams[sid] = s
    now = service.IDLE_S + 60
    monkeypatch.setattr(service.time, "time", lambda: now)

    async def one_sweep():
        real_sleep = asyncio.sleep

        async def once(_s):
            if getattr(once, "done", False):
                raise asyncio.CancelledError
            once.done = True
            await real_sleep(0)

        monkeypatch.setattr(service.asyncio, "sleep", once)
        try:
            await service._sweep()
        except asyncio.CancelledError:
            pass
        monkeypatch.setattr(service.asyncio, "sleep", real_sleep)

    asyncio.run(one_sweep())
    assert list(service.streams) == ["rec"]
    assert service.filed == []
