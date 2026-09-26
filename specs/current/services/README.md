# Services Layer

Internal services and background jobs running as separate processes.

## Overview

Services that run independently from the main Flask app, either as separate Render services or scheduled cron jobs.

## Components

### [ABC Renderer](abc-renderer.md)
Microservice for converting ABC notation to PNG images (Node.js + abcjs)

### [Active Sessions Cron](active-sessions-cron.md)
Scheduled job tracking which sessions are currently happening (runs every 15 minutes). Local testing walkthrough: [Cron Testing](active-sessions-cron-testing.md)

### [thesession.org Merge Sync](thesession-merge-sync.md)
Weekly job that diffs local tune ids against thesession.org's data dump and auto-applies upstream merges (spec 031)

### Streaming Service (Feature 024)
Async Python sidecar (Starlette + asyncpg, `streaming/service.py`) holding the live-logging SSE connections. Downstream fan-out only — Flask owns all writes; this service relays `session_event` rows via Postgres `LISTEN/NOTIFY`. Architecture: [Live Logging](../logic/live-logging.md).

## Deployment

Services live in the Render dashboard; `render.yaml` mirrors them as
documentation and creates nothing. The full set:
- **ceol.io-live**: Web service (Python, `gunicorn app:app`) — the app
- **abc-renderer**: Web service (Node.js)
- **ceol-io-streaming**: Web service (Python, `uvicorn streaming.service:app`) — live-logging SSE sidecar (Feature 024)
- **ceol-io-active-sessions**: Cron job (Python) — the *only* cron job

Scheduled work that has no service of its own, because a cron service costs money
and one cron can carry more than one job:
- **thesession.org merge sync** (spec 031) — runs at the end of
  `ceol-io-active-sessions`, gated to Mondays 06:00 UTC. See
  [thesession.org Merge Sync](thesession-merge-sync.md).
- **Recording ingest sweep** (spec 050) — runs inside `ceol.io-live` from
  gunicorn's `post_fork` and on a 10-minute tick, because every event that
  interrupts an ingest is followed by a worker boot.
