# Live Logging (Feature 024)

Real-time, multi-user session logging screen — the production build of the
[021 prototype](../../changes/021-simplified-session-screen.md). Multiple people log the same session instance at
once and see each other's changes live, with no explicit "save". This is the **new live
logger**, distinct from the older single-user bulk-save desktop logger documented in
[Session Logging UI](../ui/session-logging.md).

**Status**: Phases 0–2 built & validated (walking skeleton → full op vocabulary + schema
delta → presence/typing). Phase 3 (offline / IndexedDB / service worker) is in progress.
The audio socket is documented but **not implemented** (out of scope here).

Full design and rationale: [`specs/changes/024-live-logging-architecture.md`](../../changes/024-live-logging-architecture.md).

## Architecture

Two processes, split by direction of data flow (§A4):

- **Flask app (`ceol-io`)** — the sync, server-authoritative **referee**. Owns *all*
  writes. Handles the upstream `POST` ops and serves the screen shell + bootstrap/search
  endpoints.
- **Streaming service (`ceol-io-streaming`)** — a separate async Python sidecar
  (Starlette + asyncpg, `streaming/service.py`), mirroring the abc-renderer sidecar
  pattern. Holds long-lived **SSE** connections and is downstream fan-out **only**.

```
client EventSource  ──SSE──>  streaming service
                                 ↑  LISTEN session_instance_<id>
client  ──POST op──>  Flask referee  ──pg_notify(id only)──>  Postgres
                                 │  (event row written in same txn)
                                 └──> streaming re-reads session_event row, pushes to subscribers
```

- **Transport** (§A3): SSE downstream, plain `POST` upstream. No WebSockets, no polling.
- **Fan-out** (§A4): Postgres `LISTEN/NOTIFY` (no Redis). The Flask referee appends a
  `session_event` row in the same transaction as the mutation, then
  `pg_notify('session_instance_<id>', event_id)`; the streaming service re-reads that row
  by id and pushes it.
- **Two connections, not one** (§A5): the SSE event stream and the upstream op POSTs are
  independent — the screen keeps reading even while a write is in flight.
- **Auth** (§D, §H): reuses the existing web stack — the Flask-Login session cookie
  (shared across subdomains so the sidecar receives it) **or** a bearer token (a
  `user_session` id, issued at `POST /api/live/token` — the native-client hedge). Both
  resolve to a `user_id`. Logging is flat: any authenticated user can log.

## Source of truth & the event feed (§B)

- `session_instance_tune` stays the **canonical current state**.
- `session_event` is an append-only, per-instance **delivery/replay log**. Its
  `event_id` (BIGSERIAL) doubles as the SSE `Last-Event-ID` cursor for gap recovery /
  catch-up. This is *not* an audit table — see [History](../data/history.md).

## Operation vocabulary (§C)

All writes are incremental, intent-based ops `POST`ed to
`/api/live/instances/<id>/ops` and refereed by `live_op` in `live_logging_routes.py`:

`add_tune`, `remove_tune` (soft tombstone), `change_tune`, `set_confidence`, `set_break`,
`attribute_set_starter`, `edit_notes`, `attendance_add` / `attendance_remove` /
`attendance_create_person`, `mark_complete` / `mark_incomplete`.

Each op carries a client-generated `op_id` (UUID) for idempotent retry. A rejected op
returns `{rejected, reason}` rather than throwing (§E).

## Presence & typing (§F, ephemeral)

Presence and typing indicators are **in-memory in the streaming service and never
persisted** — they ride the SSE stream (typing signals are `POST`ed to
`/live/instances/<id>/typing`). Per-person palette **color** *is* persisted, but in its
own `session_logger_color` table keyed by `(session_id, person_id)` so a casual logger
doesn't get inflated into a member/attendee. (The original `session_instance_person.arrival_seq`
column was superseded by this table and is now unused.)

## Local vocabulary cache (§G, migration 025)

The screen ships each client a "local vocabulary" (`GET /api/live/instances/<id>/vocabulary`)
it indexes for instant, zero-network exact-match logging. Two tiers, both leader-tunable
from the session admin **Local Cache** tab: `session.live_cache_session_limit` (N — this
session's own top tunes) and `session.live_cache_global_limit` (M — globally popular
tunes not already in N). Defaults 200 / 25, mirroring the `LOCAL_VOCAB_*` fallbacks in
`live_logging_routes.py`.

## Endpoints

**Flask referee / shell** (registered in `app.py`, handlers in `live_logging_routes.py`;
screen shell in `web_routes.py:live_logging_screen`):

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/live/instances/<id>` | Svelte screen shell (`templates/live_logging.html`) |
| GET  | `/live/sw.js` | Service worker (scoped to `/live/`) |
| GET  | `/api/live/instances/<id>/bootstrap` | Initial snapshot |
| GET  | `/api/live/instances/<id>/vocabulary` | Local-cache vocabulary (N + M) |
| POST | `/api/live/instances/<id>/ops` | Referee op endpoint (all writes) |
| POST | `/api/live/token` | Issue bearer token (`user_session` id) |
| GET  | `/api/live/instances/<id>/people` `…/people/search` | Attendee lookups |
| GET  | `/api/live/instances/<id>/tune/<tune_id>` `…/match` `…/deep-search` `…/incipit/<tune_id>` | Tune detail / linking / search / ABC |

**Streaming sidecar** (`streaming/service.py`):

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Health check |
| GET  | `/live/instances/<id>/events` | SSE stream (downstream fan-out + presence) |
| POST | `/live/instances/<id>/typing` | Ephemeral typing signal |

## Frontend (§H)

Svelte 5 + Vite PWA, built to a self-contained bundle under `static/live/`
(`app.js` / `app.css`) and isolated to this screen (not the base Bootstrap layout).
Source in `frontend/` (`frontend/src`). The shell template passes `session_instance_id`,
`current_person`, and `STREAMING_BASE_URL` to the bundle, which then fetches the bootstrap
snapshot and opens the SSE stream.

## Schema delta (§I)

See [Schema Reference](../data/schema.md) and [Session Model](../data/session-model.md).
Built migrations: `schema/024_session_event.sql`, `schema/024_live_logging_delta.sql`,
`schema/025_session_local_cache_limits.sql`.

- **New** `session_event` (append-only feed; `event_id`, `op_id`, `op_type`, `payload` JSONB).
- **New** `corroboration` (per-user assertions about a tune record; keyed `(record_id, user_id)`).
- **New** `session_logger_color` (permanent per-session palette color).
- **`session_instance_tune` +cols**: `source`, `confidence`, `played_start`/`played_end`
  (audio-only, nullable), `logged_timestamp`, `client_device_id`, `deleted` (tombstone).
- **`session` +cols**: `live_cache_session_limit`, `live_cache_global_limit`.

## Deployment

`ceol-io-streaming` web service in `render.yaml`
(`uvicorn streaming.service:app`). Flask reaches it via the `STREAMING_BASE_URL` env var;
the session cookie is shared across subdomains (`SESSION_COOKIE_DOMAIN`) so the sidecar
authenticates the SSE connection.

## Related

- [Spec 024](../../changes/024-live-logging-architecture.md) - Full architecture & phases
- [Session Logging UI](../ui/session-logging.md) - The older single-user bulk-save logger
- [Session Model](../data/session-model.md) - Underlying tune-log tables
- [History](../data/history.md) - Why `session_event` is not an audit table
