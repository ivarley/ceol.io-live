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

  client -> {"type": "start", "stream_id": "<uuid>", "sample_rate": 22050,
             "instance_id": <the night, optional>}
            (the same stream_id again after a reconnect resumes the stream).
            With the night, the listener prefers the session's own tunes (those
            logged before it, from the web app with the caller's token), then
            popular ones, then the rest (spec 053, the tiers)
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

Background work (spec 053, "053 files/find-tunes-on-the-server.md"): with
LISTEN_JOB_TOKEN set (the same secret as the web app's), the service asks the
app for queued jobs whenever no stream is open, and finds a night's tunes from
its recording, one job at a time. Live listening comes first: while a stream
is open the job waits between steps, and says so. /health shows the job.

Run locally:  uvicorn listen.service:app --port 8440
"""

import asyncio
import json
import os
import shutil
import socket
import struct
import subprocess
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

NU_PARTLY = 0.5         # a popular tune's discount, as a fraction of an outside tune's (spec 053)
state = {"models": None, "loading": True, "error": None, "started": time.time(), "load_s": None, "job": None}
streams = {}            # stream_id -> Stream


class Stream:
    """One listening phone: a Listener, the next sample expected, chunks that
    arrived ahead of a gap, and the socket currently attached (if any)."""

    def __init__(self, stream_id, mode="audio", session_tunes=None):
        from lab.tools.listen import Listener

        self.id = stream_id
        self.mode = mode              # "audio": the phone streams audio; "heard": it sends notes
        self.dir = os.path.join(STREAM_DIR, stream_id)
        os.makedirs(self.dir, exist_ok=True)
        models = state["models"]
        self.listener = Listener(self.dir, models=models, audio_name="audio.flac", keep_s=KEEP_S,
                                 session_tunes=session_tunes or None, second_tier=models.popular,
                                 nu_partly=NU_PARTLY, audio=mode == "audio")
        self.known_tunes = len(session_tunes or ())
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
        # one whole-corpus index for every session, its own tunes preferred
        models = await asyncio.to_thread(Models, 0, True)
        _name_tunes(models)
        state["load_s"] = round(time.time() - t0, 1)
        t1 = time.time()
        await asyncio.to_thread(_warm, models)
        state["warm_s"] = round(time.time() - t1, 1)
        print(f"listen: models loaded in {state['load_s']}s, warmed in {state['warm_s']}s", flush=True)
        state["models"] = models
    except Exception as e:
        state["error"] = repr(e)
    finally:
        state["loading"] = False


def _warm(models):
    """One listener's first steps on a few seconds of made-up tune, so the first
    phone to connect after a start does not wait while Basic Pitch loads and the
    aligner compiles (a phone switched to this service on 2026-10-10, a minute
    after a deploy, heard nothing for the 33 s it waited)."""
    import tempfile

    from lab.tools.listen import HOP_MS, Listener

    t = np.arange(int(SR * 0.25)) / SR
    notes = [62, 64, 66, 67, 69, 71, 73, 74, 73, 71, 69, 67, 66, 64, 62, 66] * 2   # a D major run, in eighths
    y = np.concatenate([0.3 * np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * t) for m in notes]).astype(np.float32)
    with tempfile.TemporaryDirectory() as d:
        li = Listener(d, models=models, audio_name="warm.wav", keep_s=KEEP_S)
        li.store.append(y)
        for step_t in range(HOP_MS, li.store.duration_ms + 1, HOP_MS):
            li.step(step_t)
        li.close()


@asynccontextmanager
async def lifespan(app):
    from listen.data import ensure_data

    await asyncio.to_thread(ensure_data)
    # Loaded and warmed before the port opens: on a deploy, the old instance keeps
    # every phone until this one can answer at once.
    await _load()
    tasks = [asyncio.create_task(_sweep()), asyncio.create_task(_jobs())]
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
    """-> (allowed, the caller's Ceol app token or None)."""
    auth = dict(scope_headers).get(b"authorization", b"").decode()
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else (query.get("token") or "")
    if not TOKEN and not token:
        return True, None             # local development
    if TOKEN and token == TOKEN:
        return True, None
    ok = bool(token) and await asyncio.to_thread(_app_token_allowed, token)
    return ok, token if ok else None


def _known_tunes(instance_id, token):
    """The tune ids the night's session logged before it (the web app's
    /api/session-instances/<id>/known-tunes), or None if it cannot say."""
    import urllib.request

    try:
        req = urllib.request.Request(f"{CEOL_API_URL}/api/session-instances/{int(instance_id)}/known-tunes",
                                     headers={"Authorization": f"Bearer {token}", "X-Ceol-Client": "listen"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return [int(t) for t in json.loads(r.read()).get("tune_ids", [])]
    except Exception as e:
        print(f"listen: no known tunes for instance {instance_id}: {e!r}", flush=True)
        return None


# --------------------------------------------------------------------------- #
# Background work: finding a night's tunes (spec 053)
# --------------------------------------------------------------------------- #

JOB_TOKEN = os.environ.get("LISTEN_JOB_TOKEN", "")
JOB_POLL_S = 20
JOB_REPORT_S = 5
WORKER = f"{socket.gethostname()}-{os.getpid()}"


LIVE_GRACE_S = 30


def _live():
    """Is a night being listened to? A stream with a phone attached, or one that
    sent audio in the last LIVE_GRACE_S (a phone between reconnects); not one
    left behind by a phone that went away, which the sweep closes later."""
    now = time.time()
    return any(s.socket is not None or now - s.last_seen < LIVE_GRACE_S for s in list(streams.values()))


def _app(path, body):
    """POST to the web app as this service (LISTEN_JOB_TOKEN). -> the JSON reply."""
    import urllib.request

    req = urllib.request.Request(f"{CEOL_API_URL}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {JOB_TOKEN}", "Content-Type": "application/json",
                                          "X-Ceol-Client": "listen"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _fetch_audio(url, work):
    """The recording, decoded to 22,050 Hz mono 16-bit WAV. -> its path."""
    import urllib.request

    src = os.path.join(work, "master")
    with urllib.request.urlopen(url, timeout=120) as r, open(src, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    wav = os.path.join(work, "mono22k.wav")
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", wav],
                   check=True, timeout=3600)
    os.remove(src)
    return wav


class _Job:
    """One job's state as the service holds it, shared by its worker thread and
    the reporter: where it has got to, and the time it has spent waiting for
    live listening."""

    def __init__(self, job):
        self.job = job
        self.id = job["listen_job_id"]
        self.phase, self.progress, self.heard_ms = "fetching", 0.0, 0
        self.stop = False
        self.started = time.time()
        self.paused_since = None
        self.paused_s = 0.0

    def pause(self):
        """True while live listening has the service; counts the time."""
        live = _live()
        now = time.time()
        if live and self.paused_since is None:
            self.paused_since = now
        elif not live and self.paused_since is not None:
            self.paused_s += now - self.paused_since
            self.paused_since = None
        return live

    def paused_total(self):
        return self.paused_s + (time.time() - self.paused_since if self.paused_since else 0.0)

    def report(self):
        paused = self.paused_since is not None
        return {"worker": WORKER, "status": "paused" if paused else "running", "phase": self.phase,
                "progress": round(self.progress, 4), "heard_ms": self.heard_ms,
                "running_s": round(time.time() - self.started - self.paused_total(), 1),
                "paused_s": round(self.paused_total(), 1)}

    def on_progress(self, phase, done, total):
        self.phase = phase
        self.progress = done / total if total else 0.0
        if phase == "listening":
            self.heard_ms = done


def _work(j):
    """The job, start to finish, in a worker thread. -> find_tunes' result."""
    from lab.tools.find_tunes import find_tunes

    work = tempfile.mkdtemp(prefix=f"job-{j.id}-")
    try:
        wav = _fetch_audio(j.job["audio_url"], work)
        keys = {int(k): v for k, v in (j.job.get("keys") or {}).items()}
        return find_tunes(wav, state["models"], j.job.get("session_tunes") or None, keys,
                          progress=j.on_progress, pause=j.pause, cancelled=lambda: j.stop,
                          log=lambda msg: print(f"listen job {j.id}: {msg}", flush=True), nu_partly=NU_PARTLY)
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def _run_job(job):
    from lab.tools.find_tunes import Cancelled

    j = _Job(job)
    state["job"] = {"listen_job_id": j.id, "recording_id": job.get("recording_id"), **j.report()}
    print(f"listen: job {j.id} (recording {job.get('recording_id')}) started", flush=True)

    async def reporter():
        while True:
            await asyncio.sleep(JOB_REPORT_S)
            j.pause()                     # keeps the paused clock right between steps too
            body = j.report()
            state["job"] = {"listen_job_id": j.id, "recording_id": job.get("recording_id"), **body}
            try:
                reply = await asyncio.to_thread(_app, f"/api/listen-jobs/{j.id}/progress", body)
                if reply.get("stop"):
                    j.stop = True
            except Exception as e:
                print(f"listen: job {j.id} progress not sent: {e!r}", flush=True)

    rep = asyncio.create_task(reporter())
    try:
        out = await asyncio.to_thread(_work, j)
        keep = ("tune_id", "name", "start_ms", "end_ms", "p_right", "set", "first_in_set", "outside")
        body = {**j.report(), "drafts": [{k: d.get(k) for k in keep} for d in out["drafts"]],
                "confidence_model": out["confidence_model"], "summary": out["summary"]}
        await asyncio.to_thread(_app, f"/api/listen-jobs/{j.id}/result", body)
        print(f"listen: job {j.id} done: {out['summary']}", flush=True)
    except Cancelled:
        print(f"listen: job {j.id} cancelled", flush=True)
    except Exception as e:
        print(f"listen: job {j.id} failed: {e!r}", flush=True)
        retry = isinstance(e, (OSError, subprocess.SubprocessError))   # fetching or decoding
        try:
            await asyncio.to_thread(_app, f"/api/listen-jobs/{j.id}/fail",
                                    {**j.report(), "error": repr(e)[:2000], "retry": retry})
        except Exception:
            pass
    finally:
        rep.cancel()
        state["job"] = None


async def _jobs():
    """Ask for work whenever the models are loaded and nothing is live."""
    if not JOB_TOKEN:
        return
    while True:
        await asyncio.sleep(JOB_POLL_S)
        if state["models"] is None or _live():
            continue
        try:
            job = (await asyncio.to_thread(_app, "/api/listen-jobs/claim", {"worker": WORKER})).get("job")
        except Exception as e:
            print(f"listen: no job claimed: {e!r}", flush=True)
            continue
        if job:
            await _run_job(job)


async def health(request):
    import resource

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_gb = rss / 1e9 if os.uname().sysname == "Darwin" else rss / 1e6   # bytes on macOS, KB on Linux
    return JSONResponse({"ready": state["models"] is not None, "loading": state["loading"],
                         "error": state["error"], "load_s": state["load_s"],
                         "streams": len(streams), "peak_memory_gb": round(rss_gb, 2),
                         "threads": state.get("threads"), "cpu": state.get("cpu"), "job": state["job"],
                         "uptime_s": int(time.time() - state["started"])},
                        status_code=200 if state["models"] is not None else 503)


async def listen(ws: WebSocket):
    allowed, app_token = await _authorised(ws.scope.get("headers", []), dict(ws.query_params))
    if not allowed:
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
                    known = None
                    if m.get("instance_id") and app_token:
                        known = await asyncio.to_thread(_known_tunes, m["instance_id"], app_token)
                    stream = Stream(sid, mode, known)
                    streams[sid] = stream
                    if mode == "audio":
                        asyncio.create_task(_step_loop(stream))
                stream.socket = ws
                await _send(ws, {"type": "ready", "stream_id": sid, "mode": mode, "have": stream.have,
                                 "heard_t": stream.heard_t, "known_tunes": stream.known_tunes})
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
