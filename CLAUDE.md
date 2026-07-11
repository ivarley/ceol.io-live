# CLAUDE.md

Irish music session tracker. Flask/PostgreSQL web app for tracking live music sessions and tunes.

## Work Process

The high level view of the system is documented in the /specs directory. Before beginning work on any task, read any specs that are relevant to the task.

## Quick Reference

**Stack**: Flask 3.1 + PostgreSQL + Svelte 5 (interactive pages) + Jinja2 shells + Bootstrap 4.5 (legacy pages)
**Entry**: `app.py` | **Routes**: `web_routes.py` (HTML), `api_routes.py` + `api_person_tune_routes.py` (JSON)
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
- [Dark Mode & Theming](specs/current/ui/theming.md) - CSS variables, theme switching
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

```bash
# First time setup
make install              # Install Python/JS dependencies
make setup-test-db        # Create local database with seed data
cp .env.test .env         # Use test environment config

# Run the app
flask --app app run --debug  # http://127.0.0.1:5001

# Database management
make reset-test-db        # Drop and recreate database
make seed-test-db         # Refresh seed data only
make test                 # Run all tests
```

See [scripts/LOCAL_DEVELOPMENT.md](scripts/LOCAL_DEVELOPMENT.md) for detailed setup instructions.

**Test login**: `ian` / `password123` (admin) or `sarah_fiddle` / `password123` (regular user)

## Key Files

- `app.py:52` - Flask app init; `app.py:106` - Bearer-token request_loader; API URL rules bound here
- `web_routes.py` - ~3600 lines, all HTML page routes (migrated pages are thin shells calling serializers)
- `api_routes.py` - ~12700 lines, JSON API endpoints; `api_person_tune_routes.py` - my-tunes/person-tune APIs
- `serializers.py` - page/API payload builders (pure mappers, RealDictCursor loaders)
- `api_auth.py` - API auth decorators + `@public_api` marker
- `auth.py:13` - User model and authentication
- `database.py:253` - DB connection, `database.py:270` - History tracking
- `frontend/` - Svelte sources (`src/<page>/`, kit in `src/lib/`), one Vite config per bundle; `frontend/tests/` Vitest; `e2e/` Playwright
- `schema/schema.md` - Complete database documentation
