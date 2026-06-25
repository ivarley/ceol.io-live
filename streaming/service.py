#!/usr/bin/env python3
"""
Live logging — the async streaming service for spec 024 (Phase 0).

A separate Python async sidecar (Starlette + asyncpg) that holds the long-lived
SSE connections, mirroring the abc-renderer sidecar pattern (spec 024 §A4). The
sync Flask app stays unchanged and owns all writes; this service is downstream
fan-out ONLY:

  client EventSource  --SSE-->  this service
                                  |  LISTEN session_instance_<id>
  Flask referee  --pg_notify-->  Postgres  (id-only NOTIFY)
                                  |  re-read session_event row by event_id
                                  push to subscribed clients

Auth reuses the existing web stack (spec 024 §H): the Flask-Login session cookie
(same-origin web path) OR a bearer token (a user_session id; the future
native-client hedge). Both resolve to a user_id; Phase 0 only requires "is this
an authenticated user", not per-instance authorization (logging is flat, §D).

Run locally:
  venv/bin/python -m streaming.service        # or: streaming/service.py
Serves on STREAMING_PORT (default 8080).
"""

import os
import json
import time
import asyncio
import itertools
from contextlib import asynccontextmanager
import asyncpg
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from flask.sessions import SecureCookieSessionInterface
from starlette.applications import Starlette
from starlette.responses import JSONResponse, StreamingResponse, Response
from starlette.routing import Route

# --- Config ---------------------------------------------------------------

PORT = int(os.environ.get("STREAMING_PORT", 8080))
SECRET_KEY = os.environ.get("FLASK_SESSION_SECRET_KEY", "dev-secret-key-change-in-production")
KEEPALIVE_SECONDS = 15

pool: asyncpg.Pool = None

# One global LISTEN channel for the whole feed (must match live_logging_routes).
# A single dedicated listener connection fans out to all clients via the in-memory
# PRESENCE registry — so SSE clients never each hold a DB connection (which capped
# concurrent clients at the pool size and caused new connects to hang on acquire).
LIVE_EVENT_CHANNEL = "live_session_events"

# A throwaway Flask app purely so we can reuse Flask's exact session-cookie
# deserialization (itsdangerous signer + tagged-JSON serializer). We never run it.
_cookie_app = Flask(__name__)
_cookie_app.secret_key = SECRET_KEY
_cookie_serializer = SecureCookieSessionInterface().get_signing_serializer(_cookie_app)


def _dsn():
    return "postgresql://{user}:{pw}@{host}:{port}/{db}".format(
        user=os.environ.get("PGUSER", ""),
        pw=os.environ.get("PGPASSWORD", ""),
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        db=os.environ.get("PGDATABASE", ""),
    )


async def _dispatch_op(instance_id, event_id):
    """Read a committed event once and fan it out to every connected client's queue.
    Called from the single global NOTIFY listener — clients do no per-event DB read."""
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT op_type, payload::text AS payload FROM session_event WHERE event_id = $1",
            event_id,
        )
    if row is None:
        return
    for st in list(PRESENCE.get(instance_id, {}).values()):
        st["queue"].put_nowait(("op", event_id, row["op_type"], row["payload"]))


def _on_global_notify(conn, pid, channel, payload):
    """asyncpg NOTIFY callback (sync): payload is '<instance_id>:<event_id>'."""
    try:
        inst_s, eid_s = payload.split(":", 1)
        instance_id, event_id = int(inst_s), int(eid_s)
    except (ValueError, AttributeError):
        return
    if PRESENCE.get(instance_id):  # only bother if someone's listening
        asyncio.create_task(_dispatch_op(instance_id, event_id))


# --- Auth -----------------------------------------------------------------


def _user_id_from_cookie(request):
    """Decode the Flask-Login session cookie -> user_id, or None."""
    raw = request.cookies.get("session")
    if not raw:
        return None
    try:
        data = _cookie_serializer.loads(raw)
    except Exception:
        return None
    uid = data.get("_user_id")
    try:
        return int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None


async def _user_id_from_bearer(request):
    """Validate `Authorization: Bearer <user_session id>` -> user_id, or None."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT user_id FROM user_session
            WHERE session_id = $1 AND expires_at > (NOW() AT TIME ZONE 'UTC')
            """,
            token,
        )


async def authenticate(request):
    """Return an authenticated user_id (cookie first, then bearer), or None."""
    uid = _user_id_from_cookie(request)
    if uid is not None:
        return uid
    return await _user_id_from_bearer(request)


def _cors_headers(request):
    """Echo the request Origin so EventSource(withCredentials) works cross-origin."""
    origin = request.headers.get("origin")
    headers = {"Cache-Control": "no-cache"}
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return headers


# --- Presence (ephemeral, in the streaming service's memory; spec 024 §F) ----
# Presence ≡ an open authenticated SSE connection. It never touches the DB and is
# never replayed (sent as `event: presence` WITHOUT an `id:`, so it doesn't advance
# Last-Event-ID; a reconnect gets a fresh snapshot).
#
# A person's COLOR, however, IS persisted — per (session, person), not per instance
# — in session_logger_color (spec 024 §F). On first appearance at any instance of a
# session, a person is assigned the least-used palette index among everyone who's
# logged at that session; that index is permanent, so a regular is the same color
# week to week and colors survive streaming restarts / deploys. The roster still
# ships the index in the `arrival_seq` field, so the client (palette[idx]) is
# unchanged. (Color != attendance != membership: the color row is its own table, so
# assigning it never mints a session_person/attendance row — see the migration.)

# Must match the client's PALETTE length in App.svelte (8 colors).
PALETTE_SIZE = 8

# instance_id -> { conn_id: {queue, person_id, arrival_seq, name} }
PRESENCE = {}
# instance_id -> { person_id: color_idx }  (cache of the persisted color; avoids a DB
# hit on every typing signal / roster build; populated on connect, never shrinks)
_COLORS = {}
_conn_ids = itertools.count(1)


async def _session_color(instance_id, person_id):
    """Stable per-(session, person) palette index, get-or-assign. Persisted so it's
    consistent across instances (weeks) and survives restarts. The DB is authoritative:
    a plain SELECT covers the common already-assigned path (no lock), and only a first
    assignment takes a per-session advisory lock so concurrent first-time joiners can't
    both grab the same "least-used" index. The in-memory cache (_COLORS) is refreshed
    here but never short-circuits this, so it can't drift from the DB on connect."""
    if person_id is None:
        return 0
    async with pool.acquire() as c:
        sid = await c.fetchval(
            "SELECT session_id FROM session_instance WHERE session_instance_id = $1",
            instance_id,
        )
        if sid is None:
            return 0
        idx = await c.fetchval(
            "SELECT color FROM session_logger_color WHERE session_id = $1 AND person_id = $2",
            sid, person_id,
        )
        if idx is None:
            async with c.transaction():
                # Serialize assignment per session so two simultaneous joiners don't both
                # compute the same "least-used" index before either has inserted.
                await c.execute("SELECT pg_advisory_xact_lock($1)", sid)
                idx = await c.fetchval(
                    "SELECT color FROM session_logger_color WHERE session_id = $1 AND person_id = $2",
                    sid, person_id,
                )
                if idx is None:
                    rows = await c.fetch(
                        "SELECT color FROM session_logger_color WHERE session_id = $1", sid
                    )
                    counts = [0] * PALETTE_SIZE
                    for r in rows:
                        counts[r["color"] % PALETTE_SIZE] += 1
                    idx = min(range(PALETTE_SIZE), key=lambda i: counts[i])
                    await c.execute(
                        "INSERT INTO session_logger_color (session_id, person_id, color) "
                        "VALUES ($1, $2, $3) ON CONFLICT (session_id, person_id) DO NOTHING",
                        sid, person_id, idx,
                    )
                    # Re-read in case we lost a race despite the lock (defensive).
                    idx = await c.fetchval(
                        "SELECT color FROM session_logger_color WHERE session_id = $1 AND person_id = $2",
                        sid, person_id,
                    )
    _COLORS.setdefault(instance_id, {})[person_id] = idx
    return idx


def _roster(instance_id):
    """One entry per present person (the same person on two devices = one entry)."""
    by_person = {}
    for st in PRESENCE.get(instance_id, {}).values():
        e = by_person.get(st["person_id"])
        if e is None:
            by_person[st["person_id"]] = {
                "person_id": st["person_id"], "arrival_seq": st["arrival_seq"],
                "name": st["name"], "devices": 1,
            }
        else:
            e["devices"] += 1
    return sorted(by_person.values(), key=lambda e: e["arrival_seq"])


def _broadcast_presence(instance_id):
    roster = _roster(instance_id)
    for st in list(PRESENCE.get(instance_id, {}).values()):
        st["queue"].put_nowait(("presence", roster))


# --- Typing (ephemeral, in memory; spec 024 §F) ----------------------------
# A typing signal is a lightweight "X is composing here" reservation, POSTed
# straight to this service (no DB, no NOTIFY). The service owns the 10s-inactivity
# timeout and clear-on-commit; clients refresh it while typing and clear it on
# submit/blur. Like presence, it rides SSE WITHOUT an id: and is never replayed.
TYPING = {}  # instance_id -> { person_id: {name, arrival_seq, anchor, ts(monotonic)} }
TYPING_TTL = 10  # seconds of inactivity before a typing signal expires


def _typing_list(instance_id):
    return sorted(
        ({"person_id": pid, "name": e["name"], "arrival_seq": e["arrival_seq"], "anchor": e["anchor"]}
         for pid, e in TYPING.get(instance_id, {}).items()),
        key=lambda x: x["arrival_seq"],
    )


def _broadcast_typing(instance_id):
    lst = _typing_list(instance_id)
    for st in list(PRESENCE.get(instance_id, {}).values()):
        st["queue"].put_nowait(("typing", lst))


async def _typing_sweeper():
    """Expire typing signals after TYPING_TTL of inactivity (the service is the
    authority for the timeout, §F), re-broadcasting instances that changed."""
    while True:
        await asyncio.sleep(2)
        now = time.monotonic()
        for instance_id, t in list(TYPING.items()):
            stale = [pid for pid, e in t.items() if now - e["ts"] > TYPING_TTL]
            for pid in stale:
                t.pop(pid, None)
            if stale:
                _broadcast_typing(instance_id)


async def _resolve_person(user_id):
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT p.person_id, p.first_name, p.last_name FROM user_account ua "
            "JOIN person p ON ua.person_id = p.person_id WHERE ua.user_id = $1",
            user_id,
        )
    if not row:
        return {"person_id": None, "name": ""}
    return {"person_id": row["person_id"], "name": (row["first_name"] or "").strip()}


# --- Routes ---------------------------------------------------------------


async def health(request):
    return JSONResponse({"ok": True})


async def cors_preflight(request):
    headers = _cors_headers(request)
    headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    headers["Access-Control-Allow-Headers"] = "Authorization, Last-Event-ID, Content-Type"
    return Response(status_code=204, headers=headers)


async def typing(request):
    """Upstream ephemeral typing signal (spec 024 §F). POSTed straight here — no DB,
    no NOTIFY. Body: {typing: bool, anchor: <after_record_id|null>}."""
    uid = await authenticate(request)
    if uid is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=_cors_headers(request))
    instance_id = int(request.path_params["session_instance_id"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    person = await _resolve_person(uid)
    pid = person["person_id"]
    t = TYPING.setdefault(instance_id, {})
    if body.get("typing"):
        # A typer is by definition connected, so their color is already cached from
        # connect; fall back to a lookup only on the rare miss.
        seq = _COLORS.get(instance_id, {}).get(pid)
        if seq is None:
            seq = await _session_color(instance_id, pid)
        t[pid] = {
            "name": person["name"],
            "arrival_seq": seq,
            "anchor": body.get("anchor"),
            "ts": time.monotonic(),
        }
    else:
        t.pop(pid, None)
    _broadcast_typing(instance_id)
    return JSONResponse({"ok": True}, headers=_cors_headers(request))


async def events(request):
    """SSE stream for one session instance: replay-then-live (spec 024 §B)."""
    uid = await authenticate(request)
    if uid is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=_cors_headers(request))

    session_instance_id = int(request.path_params["session_instance_id"])

    # EventSource auto-sends Last-Event-ID on reconnect. On the FIRST connect it
    # can't set that header, so the bootstrap high-water mark rides in as a query
    # param. Use the max so reconnects (header) and first connect (query) both work.
    def _as_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    last = max(
        _as_int(request.headers.get("last-event-id")),
        _as_int(request.query_params.get("last_event_id")),
    )

    async def gen():
        # One in-memory queue per connection carries both message kinds:
        #   ("op", eid, op_type, payload)  fanned out by the single global listener
        #   ("presence", roster)           from the in-process presence broadcaster
        # No per-connection DB connection is held — only a brief pool.acquire for the
        # initial replay — so concurrent clients are bounded by memory, not the pool.
        queue: asyncio.Queue = asyncio.Queue()

        person = await _resolve_person(uid)
        seq = await _session_color(session_instance_id, person["person_id"])
        conn_id = next(_conn_ids)
        PRESENCE.setdefault(session_instance_id, {})[conn_id] = {
            "queue": queue, "person_id": person["person_id"],
            "arrival_seq": seq, "name": person["name"],
        }
        try:
            yield b": connected\n\n"

            # 1) REPLAY everything after the client's cursor; note the high-water mark.
            #    Registered in PRESENCE *before* this, so live ops dispatched during
            #    replay queue up and are de-duped below by replayed_through.
            async with pool.acquire() as c:
                rows = await c.fetch(
                    """
                    SELECT event_id, op_type, payload::text AS payload
                    FROM session_event
                    WHERE session_instance_id = $1 AND event_id > $2
                    ORDER BY event_id
                    """,
                    session_instance_id,
                    last,
                )
            replayed_through = last
            for r in rows:
                replayed_through = r["event_id"]
                yield _sse(r["event_id"], r["op_type"], r["payload"])

            # Announce arrival: a fresh roster to me + everyone else on this instance,
            # and hand the new client the current typing state.
            _broadcast_presence(session_instance_id)
            queue.put_nowait(("typing", _typing_list(session_instance_id)))

            # 2) GO LIVE — drain the queue (ops + presence), skipping replayed ops.
            #    On client disconnect, Starlette cancels this generator (-> finally).
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield b": ping\n\n"  # idle keepalive
                    continue
                if msg[0] == "presence":
                    yield _presence_event(msg[1])  # no id: -> not a resume cursor
                elif msg[0] == "typing":
                    yield _typing_event(msg[1])     # no id: either
                elif msg[0] == "op":
                    _, eid, op_type, payload = msg
                    if eid <= replayed_through:
                        continue
                    yield _sse(eid, op_type, payload)
        finally:
            # Sync cleanup so a leave is always broadcast, even if the cancellation
            # that got us here interrupts anything awaited.
            PRESENCE.get(session_instance_id, {}).pop(conn_id, None)
            _broadcast_presence(session_instance_id)  # tell the rest I left

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_cors_headers(request))


def _presence_event(roster):
    """Frame a presence snapshot. No `id:` -> doesn't advance Last-Event-ID (§F)."""
    return f"event: presence\ndata: {json.dumps({'roster': roster})}\n\n".encode()


def _typing_event(typers):
    """Frame a typing snapshot. No `id:` either."""
    return f"event: typing\ndata: {json.dumps({'typing': typers})}\n\n".encode()


def _sse(event_id, op_type, payload_json):
    """Frame one SSE message. `id:` advances the client's Last-Event-ID cursor.

    All ops ride a single `op` event so the client needs one handler; op_type and
    event_id are folded into the data alongside the referee's payload.
    """
    try:
        data = json.loads(payload_json) if payload_json else {}
    except (TypeError, ValueError):
        data = {}
    data["op_type"] = op_type
    data["event_id"] = event_id
    body = json.dumps(data)
    return f"id: {event_id}\nevent: op\ndata: {body}\n\n".encode()


# --- Lifespan / app -------------------------------------------------------


@asynccontextmanager
async def lifespan(app):
    global pool
    pool = await asyncpg.create_pool(_dsn(), min_size=1, max_size=10)
    # One dedicated, long-lived connection LISTENs the whole feed and fans every
    # committed event out to the in-memory client queues (spec 024 §A4).
    listener = await pool.acquire()
    await listener.add_listener(LIVE_EVENT_CHANNEL, _on_global_notify)
    sweeper = asyncio.create_task(_typing_sweeper())
    print(f"[streaming] live-logging SSE service up on :{PORT} (listening '{LIVE_EVENT_CHANNEL}')")
    try:
        yield
    finally:
        sweeper.cancel()
        await listener.remove_listener(LIVE_EVENT_CHANNEL, _on_global_notify)
        await pool.release(listener)
        await pool.close()


app = Starlette(
    routes=[
        Route("/health", health),
        Route("/live/instances/{session_instance_id:int}/events", events, methods=["GET"]),
        Route("/live/instances/{session_instance_id:int}/events", cors_preflight, methods=["OPTIONS"]),
        Route("/live/instances/{session_instance_id:int}/typing", typing, methods=["POST"]),
        Route("/live/instances/{session_instance_id:int}/typing", cors_preflight, methods=["OPTIONS"]),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
