"""The listening service: a phone streams a session's audio here and gets back,
every 4 s, what tune the detector thinks is playing (spec 053, "listen on the
server"; `specs/changes/inprogress/053 files/listen-on-the-server.md`).

A separate async service, like the live-logging streaming sidecar
(`streaming/service.py`), because its dependencies (three pitch trackers,
PyTorch, numba) and its memory (about 3 GB) must stay off the web app. The
detector is the lab's own (`lab.tools.listen`: `Models` loaded once and
shared, a `Listener` per stream), so what the phone sees is what the lab
measured.

One WebSocket per stream, at /listen:

  client -> {"type": "start", "stream_id": "<uuid>", "sample_rate": 22050}
            (the same stream_id again after a reconnect resumes the stream)
  server -> {"type": "ready", "stream_id", "have": <samples received>}
  client -> binary: 8-byte little-endian uint64 sample offset, then 16-bit
            little-endian mono PCM at 22050 Hz. Chunks may repeat or arrive
            after a gap is refilled; each sample is taken once, in order.
  server -> {"type": "ack", "have": <contiguous samples received>}
  server -> {"type": "state", ...} each 4 s of audio: top tunes with beliefs,
            "not a tune", tune-ness, what is shown, recent history
  client -> {"type": "tap", "action": "this" | "none", "tune_id", "shown"}
  client -> {"type": "stop"}  ->  server -> {"type": "done", "have"}

  client -> {"type": "start", ..., "mode": "heard"}  instead of audio, the
            phone hears for itself (spec 053, "Listening on the phone") and sends
            each 4 s step's notes and features:
            {"type": "heard", "t_ms", "heard_ms", "notes": {tracker: [[t0_ms,
            t1_ms, midi], ...] over the last 24 s}, "features": {...}};
            server -> state, then {"type": "ack", "heard_t": <last step taken>};
            "ready" carries "heard_t" so a reconnect resends only later steps
  client -> {"type": "skip", "to": <sample>}  after an outage longer than the
            phone keeps unsent audio: the gap is filled with silence so the
            detector's clock stays the recording's (the phone's own file is the
            complete recording)

Authentication: `Authorization: Bearer <token>` (or `?token=`). Either the
service's own LISTEN_TOKEN (the test client), or a Ceol app token belonging
to a system admin, checked by asking the web app's /api/me (CEOL_API_URL)
and cached for ten minutes, so this service needs no database credentials.

Run locally:  uvicorn listen.service:app --port 8440
"""

import asyncio
import json
import os
import struct
import tempfile
import time
from contextlib import asynccontextmanager

import numpy as np
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

SR = 22050
TOKEN = os.environ.get("LISTEN_TOKEN", "")
STREAM_DIR = os.environ.get("LISTEN_STREAM_DIR") or os.path.join(tempfile.gettempdir(), "listen-streams")
IDLE_S = 300            # a stream nobody has sent to for this long is closed
KEEP_S = 120            # audio held in memory per stream

state = {"models": None, "loading": True, "error": None, "started": time.time(), "load_s": None}
streams = {}            # stream_id -> Stream


class Stream:
    """One listening phone: a Listener, the next sample expected, chunks that
    arrived ahead of a gap, and the socket currently attached (if any)."""

    def __init__(self, stream_id, mode="audio"):
        from lab.tools.listen import Listener

        self.id = stream_id
        self.mode = mode              # "audio": the phone streams audio; "heard": it sends notes
        self.dir = os.path.join(STREAM_DIR, stream_id)
        os.makedirs(self.dir, exist_ok=True)
        self.listener = Listener(self.dir, models=state["models"], audio_name="audio.flac", keep_s=KEEP_S,
                                 audio=mode == "audio")
        self.heard_t = 0              # heard mode: the last step taken (ms of audio)
        self.heard_lock = asyncio.Lock()  # one step at a time, across a reconnect's two sockets
        self.have = 0                 # contiguous samples taken
        self.ahead = {}               # offset -> samples, waiting for a gap to fill
        self.socket = None
        self.last_seen = time.time()
        self.stepping = False

    def take(self, offset, samples):
        if offset + len(samples) <= self.have:
            return                    # a repeat after a reconnect
        if offset > self.have:
            self.ahead[offset] = samples
            return
        self._append(samples[self.have - offset:])
        while self.have in self.ahead:
            self._append(self.ahead.pop(self.have))
        for k in [k for k in self.ahead if k < self.have]:
            s = self.ahead.pop(k)
            if k + len(s) > self.have:
                self._append(s[self.have - k:])

    def skip_to(self, to):
        """Silence up to `to` (at most an hour), for audio the phone no longer has."""
        gap = min(int(to) - self.have, 3600 * SR)
        if gap > 0:
            self._append(np.zeros(gap, dtype=np.float32))
            self.ahead = {k: v for k, v in self.ahead.items() if k + len(v) > self.have}
            while self.have in self.ahead:
                self._append(self.ahead.pop(self.have))

    def _append(self, samples):
        if len(samples):
            self.listener.store.append(samples)
            self.have += len(samples)


async def _send(ws, msg):
    if ws is not None:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            pass


async def _step_loop(stream):
    """Run the detector for each 4 s of audio as it becomes available, off the
    event loop, and send the meter's state to whichever socket is attached."""
    from lab.tools.listen import HOP_MS

    li = stream.listener
    while li.running:
        if li.store.duration_ms >= li.next_t:
            t = li.next_t
            try:
                await asyncio.to_thread(li.step, t)
            except Exception as e:      # keep listening; say what went wrong
                li.state["status"] = f"error at {t} ms: {e!r}"
            li.next_t += HOP_MS
            with li.lock:
                payload = {"type": "state", **li.state, "heard_ms": li.store.duration_ms}
            await _send(stream.socket, payload)
        else:
            await asyncio.sleep(0.2)


async def _take_heard(stream, m):
    """Heard mode: one step's notes and features from the phone -> the meter's
    state. A step at or before the last one taken is a resend after a
    reconnect and is only acknowledged."""
    from lab.tools.listen import unpack_heard

    t, ctx, feats, heard_ms = unpack_heard(m)
    stream.last_seen = time.time()
    li = stream.listener
    async with stream.heard_lock:
        if t > stream.heard_t:
            try:
                await asyncio.to_thread(li.step_heard, t, ctx, feats, heard_ms)
            except Exception as e:      # keep listening; say what went wrong
                li.state["status"] = f"error at {t} ms: {e!r}"
            stream.heard_t = t
            with li.lock:
                payload = {"type": "state", **li.state, "heard_ms": heard_ms}
            await _send(stream.socket, payload)
    await _send(stream.socket, {"type": "ack", "heard_t": stream.heard_t})


async def _sweep():
    while True:
        await asyncio.sleep(30)
        now = time.time()
        for sid, s in list(streams.items()):
            if s.socket is None and now - s.last_seen > IDLE_S:
                s.listener.close()
                streams.pop(sid, None)


def tune_name(name):
    """A tune's name as people write it. thesession.org's data dump, which the
    detector's indexes were built from, keeps a leading "The" at the end so
    names sort under the noun ("Holly Bush, The": 6,581 of its 23,317 tunes);
    no other word is moved. The phone shows names, so it goes back in front."""
    if name and name.endswith(", The"):
        return "The " + name[: -len(", The")]
    return name


def _name_tunes(models):
    """Every name the detector reports, in place: the repertoire index, and the
    whole corpus's, which is also Models.names."""
    for names in (models.index.tune_names, models.fallback.tune_names):
        for tune_id, name in names.items():
            names[tune_id] = tune_name(name)


async def _load():
    try:
        # Before the models (and torch, numba, ONNX Runtime) load: hold every
        # library to the CPUs the container really has, not the host's count.
        from lab.tools.threads import limit_threads

        n, seen = limit_threads()
        state["threads"], state["cpu"] = n, seen
        print(f"listen: threads held to {n}; cpus seen {seen}", flush=True)

        from lab.tools.listen import Models

        t0 = time.time()
        models = await asyncio.to_thread(Models)
        _name_tunes(models)
        state["models"] = models
        state["load_s"] = round(time.time() - t0, 1)
    except Exception as e:
        state["error"] = repr(e)
    finally:
        state["loading"] = False


@asynccontextmanager
async def lifespan(app):
    from listen.data import ensure_data

    await asyncio.to_thread(ensure_data)
    tasks = [asyncio.create_task(_load()), asyncio.create_task(_sweep())]
    yield
    for t in tasks:
        t.cancel()


CEOL_API_URL = os.environ.get("CEOL_API_URL", "https://ceol.io")
_app_tokens = {}      # token -> (allowed, checked at)


def _app_token_allowed(token):
    """Does this Ceol app token belong to a system admin? The web app says."""
    import urllib.request

    hit = _app_tokens.get(token)
    if hit and time.time() - hit[1] < 600:
        return hit[0]
    allowed = False
    try:
        req = urllib.request.Request(f"{CEOL_API_URL}/api/me",
                                     headers={"Authorization": f"Bearer {token}", "X-Ceol-Client": "listen"})
        with urllib.request.urlopen(req, timeout=10) as r:
            allowed = bool(json.loads(r.read()).get("user", {}).get("is_system_admin"))
    except Exception:
        allowed = False
    _app_tokens[token] = (allowed, time.time())
    return allowed


async def _authorised(scope_headers, query):
    auth = dict(scope_headers).get(b"authorization", b"").decode()
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else (query.get("token") or "")
    if not TOKEN and not token:
        return True                   # local development
    if TOKEN and token == TOKEN:
        return True
    return bool(token) and await asyncio.to_thread(_app_token_allowed, token)


async def health(request):
    import resource

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_gb = rss / 1e9 if os.uname().sysname == "Darwin" else rss / 1e6   # bytes on macOS, KB on Linux
    return JSONResponse({"ready": state["models"] is not None, "loading": state["loading"],
                         "error": state["error"], "load_s": state["load_s"],
                         "streams": len(streams), "peak_memory_gb": round(rss_gb, 2),
                         "threads": state.get("threads"), "cpu": state.get("cpu"),
                         "uptime_s": int(time.time() - state["started"])},
                        status_code=200 if state["models"] is not None else 503)


async def listen(ws: WebSocket):
    if not await _authorised(ws.scope.get("headers", []), dict(ws.query_params)):
        await ws.close(code=4401)
        return
    await ws.accept()
    if state["models"] is None:
        await _send(ws, {"type": "error", "error": "still loading" if state["loading"] else state["error"]})
        await ws.close(code=4503)
        return
    stream = None
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                if stream is None:
                    continue
                data = msg["bytes"]
                offset = struct.unpack("<Q", data[:8])[0]
                pcm = np.frombuffer(data[8:], dtype="<i2").astype(np.float32) / 32768.0
                stream.take(offset, pcm)
                stream.last_seen = time.time()
                await _send(ws, {"type": "ack", "have": stream.have})
                continue
            m = json.loads(msg.get("text") or "{}")
            kind = m.get("type")
            if kind == "start":
                if int(m.get("sample_rate", SR)) != SR:
                    await _send(ws, {"type": "error", "error": f"send {SR} Hz"})
                    continue
                sid = str(m.get("stream_id") or "")
                if not sid:
                    await _send(ws, {"type": "error", "error": "stream_id needed"})
                    continue
                mode = "heard" if m.get("mode") == "heard" else "audio"
                stream = streams.get(sid)
                if stream is not None and stream.mode != mode:
                    await _send(ws, {"type": "error", "error": f"stream {sid} is in {stream.mode} mode"})
                    stream = None
                    continue
                if stream is None:
                    stream = Stream(sid, mode)
                    streams[sid] = stream
                    if mode == "audio":
                        asyncio.create_task(_step_loop(stream))
                stream.socket = ws
                await _send(ws, {"type": "ready", "stream_id": sid, "mode": mode, "have": stream.have,
                                 "heard_t": stream.heard_t})
            elif kind == "heard" and stream is not None and stream.mode == "heard":
                await _take_heard(stream, m)
            elif kind == "skip" and stream is not None:
                stream.skip_to(int(m.get("to", 0)))
                await _send(ws, {"type": "ack", "have": stream.have})
            elif kind == "tap" and stream is not None:
                stream.listener.tap(m.get("action"), m.get("tune_id"), m.get("shown") or ())
            elif kind == "stop" and stream is not None:
                await _send(ws, {"type": "done", "have": stream.have})
                stream.listener.close()
                streams.pop(stream.id, None)
                stream = None
    except WebSocketDisconnect:
        pass
    finally:
        if stream is not None and stream.socket is ws:
            stream.socket = None
            stream.last_seen = time.time()


app = Starlette(routes=[Route("/health", health), WebSocketRoute("/listen", listen)], lifespan=lifespan)
