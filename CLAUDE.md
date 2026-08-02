# CLAUDE.md

## What Ceol is for

Ceol.io is a companion to thesession.org for players of Irish traditional music: it tracks the tunes you know and are learning, the sessions you play at, and what was actually played at each of those sessions. thesession.org holds the world's tune data; Ceol holds the social layer — what is really played, where, and by whom.

The user-facing version of this lives at `/help` (`templates/help.html`). Keep the two in step.

## Work Process

The high level view of the system is documented in the /specs directory. Before beginning work on any task, read any specs that are relevant to the task.

## Quick Reference

**Stack**: Flask 3.1 + PostgreSQL + Svelte 5 (interactive pages) + Jinja2 shells + Bootstrap 4.5 (legacy pages)
**Entry**: `app.py` | **Routes**: `web_routes.py` (HTML), `api_routes.py` + `api_person_tune_routes.py` (JSON), `live_logging_routes.py` (live-logging ops)
**Payloads**: `serializers.py` — one function per payload; the page shell's embedded `__PAGE_DATA__` and the API return the same dict (spec 035)
**API auth**: `api_auth.py` — `@api_login_required` / `@api_admin_or_self_required` / `@public_api`; Bearer tokens via `app.py` request_loader
**Frontend**: `frontend/src/<page>/` + shared kit `frontend/src/lib/` → Vite builds to `static/<page>/` (gitignored, rebuilt on deploy); how-to: [Svelte Pages](specs/current/ui/svelte-pages.md)
**Deploy**: Render.com (Gunicorn) | **DB**: `database.py` | **Auth**: `auth.py` (Flask-Login)

## Documentation Structure

### [UI Layer](specs/current/ui/README.md)
Frontend, templates, interactions, theming
- [Svelte Pages](specs/current/ui/svelte-pages.md) - Thin shell + `__PAGE_DATA__` + page bundle; how to add/change a page; the component kit
- [Templates & Pages](specs/current/ui/templates.md) - HTML structure, base layouts, shells vs. Jinja pages
- [Session Logging UI](specs/current/ui/session-logging.md) - QUARANTINED legacy pill editor (spec 035 Step 6 deletes it)
- [Theming](specs/current/ui/theming.md) - CSS variables (dark-only palette)
- [AJAX Patterns](specs/current/ui/ajax.md) - Serializer layer, API auth decorators, Bearer tokens

### [Data Layer](specs/current/data/README.md)
Database schema, models, persistence
- [Core Schema](specs/current/data/schema.md) - Tables, relationships, constraints
- [Session Model](specs/current/data/session-model.md) - Sessions, instances, recurrence
- [Tune Model](specs/current/data/tune-model.md) - Tunes, aliases, settings, linking
- [People & Attendance](specs/current/data/people-model.md) - Users, persons, attendance tracking
- [History & Audit](specs/current/data/history.md) - Audit trail tables and functions

### [Logic Layer](specs/current/logic/README.md)
Business logic, services, external integrations
- [Authentication](specs/current/logic/auth.md) - Login, registration, email verification
- [Session Management](specs/current/logic/session-logic.md) - Auto-creation, recurrence handling
- [Tune Services](specs/current/logic/tune-logic.md) - Search, linking, popularity tracking
- [Attendance System](specs/current/logic/attendance.md) - Check-in, roles, permissions (Feature 001)
- [Live Logging](specs/current/logic/live-logging.md) - Real-time multi-user session logging (Feature 024)
- [Offline Support](specs/current/logic/offline.md) - Service worker, offline bundle, tune-list op-queue, connection indicator
- [External APIs](specs/current/logic/external-apis.md) - thesession.org, SendGrid
- [Active Sessions](specs/current/logic/active-sessions.md) - Real-time session tracking

### [Services Layer](specs/current/services/README.md)
Internal services, microservices, background jobs
- [ABC Renderer](specs/current/services/abc-renderer.md) - Node.js microservice for ABC → PNG
- [Active Sessions Cron](specs/current/services/active-sessions-cron.md) - 15-min job tracking live sessions
- [thesession.org Merge Sync](specs/current/services/thesession-merge-sync.md) - Weekly job auto-applying upstream tune merges (Feature 031)
- [Streaming Service](specs/current/logic/live-logging.md) - Async SSE sidecar for live logging (Feature 024)

## Feature Index

- **Session Tracking**: [Data](specs/current/data/session-model.md) | [Logic](specs/current/logic/session-logic.md) | [UI](specs/current/ui/svelte-pages.md)
- **Attendance (Feature 001)**: [Data](specs/current/data/people-model.md) | [Logic](specs/current/logic/attendance.md)
- **Tune Management**: [Data](specs/current/data/tune-model.md) | [Logic](specs/current/logic/tune-logic.md)
- **Per-Instrument Tune Status**: [Data + UI](specs/current/data/people-model.md) (`person_tune_instrument` overrides, `person_instrument.is_auto`, canonical instruments in `instruments.py`)
- **User System**: [Data](specs/current/data/people-model.md) | [Logic](specs/current/logic/auth.md)
- **Audio Recording (Feature 022)**: [Spec](specs/changes/022-session-audio-recording.md)
- **Live Logging (Feature 024)**: [Logic](specs/current/logic/live-logging.md) | [Spec](specs/changes/024-live-logging-architecture.md)
- **Offline Support**: [Logic](specs/current/logic/offline.md)
- **Svelte UI Consolidation (Feature 035)**: [UI](specs/current/ui/svelte-pages.md) | [Spec](specs/changes/inprogress/035-svelte-ui-consolidation.md) — `/my-tunes`, `/sessions`, `/sessions/<path>`, `/me`, `/admin/people/<id>`, `/admin/sessions/<path>` migrated to Svelte shells

## Development

Run the app with [`./start`](start). It is idempotent and brings up everything the app needs from any state — Postgres, the venv, the webpack and Vite bundles, `.env`, the seeded local database, and the live-logging streaming sidecar — then runs the Flask dev server.

```bash
./start                   # run the app: http://localhost:3232
./start --reset-db        # drop and reseed the local database first
```

Two things `./start` gets right that a bare `flask run` does not:

- **`localhost`, not `127.0.0.1`.** The session cookie is host-scoped and the streaming sidecar authenticates with that same cookie, so mixing the two spellings kills live updates and nothing else — a miserable thing to debug. The e2e suite uses `localhost` too.
- **The streaming sidecar has to be running.** Without it live logging still accepts ops and catch-up on reconnect fills the gap, but nothing arrives live, which reads as "the logger is broken".

Port 3232 (not Flask's default) because another local app owns 5001 on this machine; override with `PORT`.

```bash
make install              # Python test/dev deps — ./start installs runtime deps only
make test                 # pytest + npm test + frontend Vitest
make test-e2e             # Playwright
make lint                 # flake8 + black --check
make format               # black
make reset-test-db        # drop and recreate the local database
make seed-test-db         # refresh seed data only
make help                 # every target
```

See [scripts/LOCAL_DEVELOPMENT.md](scripts/LOCAL_DEVELOPMENT.md) for detailed setup instructions.

**Test login**: `ian` / `password123` (admin) or `sarah_fiddle` / `password123` (regular user)

## Key Files

**Request handling**
- [`app.py`](app.py) - Flask app construction, Flask-Login setup, the Bearer-token `request_loader`, template filters, and the `add_url_rule` block that binds every route imported from the route modules
- [`web_routes.py`](web_routes.py) - every HTML page route; migrated pages are thin shells that call a serializer
- [`api_routes.py`](api_routes.py) - the bulk of the JSON API
- [`api_person_tune_routes.py`](api_person_tune_routes.py) - my-tunes / person-tune JSON API
- [`live_logging_routes.py`](live_logging_routes.py) - the live-logging referee: the server-authoritative op endpoint and its op vocabulary (spec 024)
- [`serializers.py`](serializers.py) - page/API payload builders; one function per wire shape, shared by the page shell's `__PAGE_DATA__` and the API (spec 035)
- [`api_auth.py`](api_auth.py) - API auth decorators and the `@public_api` marker

**Data and auth**
- [`database.py`](database.py) - connection handling, the history/audit writer, and shared query helpers
- [`auth.py`](auth.py) - User model, login, registration, email verification
- [`models/`](models) / [`services/`](services) - the few pieces that have been pulled out of the route modules (person-tune, person merge, thesession sync, merge scanning)
- [`schema/schema.md`](schema/schema.md) - complete database documentation

**Domain utilities**
- [`active_session_manager.py`](active_session_manager.py) - which session instances are currently live, and who is at them
- [`recurrence_utils.py`](recurrence_utils.py) / [`session_instance_auto_create.py`](session_instance_auto_create.py) - recurrence patterns, and creating upcoming instances from them
- [`timezone_utils.py`](timezone_utils.py) - UTC storage, per-session and per-user display conversion
- [`session_path.py`](session_path.py) / [`session_fields.py`](session_fields.py) - validation shared by both session write paths
- [`instruments.py`](instruments.py) - the canonical instrument vocabulary
- [`fractional_indexing.py`](fractional_indexing.py) - CRDT-compatible list ordering for tune sets
- [`recording.py`](recording.py) - session audio: S3 upload/download and chunking
- [`email_utils.py`](email_utils.py) - SendGrid delivery

**Frontend and out-of-process**
- [`frontend/`](frontend) - Svelte sources (`src/<page>/`, shared kit in `src/lib/`), one Vite config per bundle; `frontend/tests/` is Vitest
- [`templates/`](templates) - Jinja2: page shells for Svelte pages, full pages for the legacy ones
- [`streaming/`](streaming) - async SSE sidecar for live logging (Starlette + asyncpg), deployed separately
- [`jobs/`](jobs) - Render cron jobs: active-session tracking, thesession.org merge sync
- [`abc-renderer/`](abc-renderer) - Node.js microservice, ABC notation → PNG
- [`e2e/`](e2e) - Playwright specs; [`spike/`](spike) - standalone exploration scripts, deliberately excluded from pytest collection
