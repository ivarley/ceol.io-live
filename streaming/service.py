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
import asyncio
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


def event_channel(session_instance_id):
    """Must match live_logging_routes.event_channel on the Flask side."""
    return f"session_instance_{int(session_instance_id)}"


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


# --- Routes ---------------------------------------------------------------


async def health(request):
    return JSONResponse({"ok": True})


async def cors_preflight(request):
    headers = _cors_headers(request)
    headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    headers["Access-Control-Allow-Headers"] = "Authorization, Last-Event-ID"
    return Response(status_code=204, headers=headers)


async def events(request):
    """SSE stream for one session instance: replay-then-live (spec 024 §B)."""
    uid = await authenticate(request)
    if uid is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=_cors_headers(request))

    session_instance_id = int(request.path_params["session_instance_id"])
    channel = event_channel(session_instance_id)

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
        queue: asyncio.Queue = asyncio.Queue()
        listen_conn = await pool.acquire()

        def on_notify(conn, pid, chan, payload):
            try:
                queue.put_nowait(int(payload))
            except (TypeError, ValueError):
                pass

        await listen_conn.add_listener(channel, on_notify)
        try:
            yield b": connected\n\n"

            # 1) REPLAY everything after the client's cursor; note the high-water mark.
            rows = await listen_conn.fetch(
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

            # 2) GO LIVE — drain notifies, skipping anything already replayed.
            while True:
                try:
                    eid = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield b": ping\n\n"
                    if await request.is_disconnected():
                        break
                    continue
                if eid <= replayed_through:
                    continue
                row = await listen_conn.fetchrow(
                    "SELECT op_type, payload::text AS payload FROM session_event WHERE event_id = $1",
                    eid,
                )
                if row is None:
                    continue
                yield _sse(eid, row["op_type"], row["payload"])
                if await request.is_disconnected():
                    break
        finally:
            await listen_conn.remove_listener(channel, on_notify)
            await pool.release(listen_conn)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_cors_headers(request))


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
    print(f"[streaming] live-logging SSE service up on :{PORT}")
    yield
    await pool.close()


app = Starlette(
    routes=[
        Route("/health", health),
        Route("/live/instances/{session_instance_id:int}/events", events, methods=["GET"]),
        Route("/live/instances/{session_instance_id:int}/events", cors_preflight, methods=["OPTIONS"]),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
