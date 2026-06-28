# Services Layer

Internal services and background jobs running as separate processes.

## Overview

Services that run independently from the main Flask app, either as separate Render services or scheduled cron jobs.

## Components

### [ABC Renderer](abc-renderer.md)
Microservice for converting ABC notation to PNG images (Node.js + abcjs)

### [Active Sessions Cron](active-sessions-cron.md)
Scheduled job tracking which sessions are currently happening (runs every 15 minutes)

### Streaming Service (Feature 024)
Async Python sidecar (Starlette + asyncpg, `streaming/service.py`) holding the live-logging SSE connections. Downstream fan-out only — Flask owns all writes; this service relays `session_event` rows via Postgres `LISTEN/NOTIFY`. Architecture: [Live Logging](../logic/live-logging.md).

## Deployment

All services defined in `render.yaml`:
- **abc-renderer**: Web service (Node.js)
- **ceol-io-active-sessions**: Cron job (Python)
- **ceol-io-streaming**: Web service (Python, `uvicorn streaming.service:app`) — live-logging SSE sidecar (Feature 024)
