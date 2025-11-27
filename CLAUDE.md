# CLAUDE.md

Irish music session tracker. Flask/PostgreSQL web app for tracking live music sessions and tunes.

## Quick Reference

**Stack**: Flask 3.1 + PostgreSQL + Bootstrap 4.5 + Jinja2
**Entry**: `app.py` | **Routes**: `web_routes.py` (HTML), `api_routes.py` (JSON)
**Deploy**: Render.com (Gunicorn) | **DB**: `database.py` | **Auth**: `auth.py` (Flask-Login)

## Documentation Structure

### [UI Layer](specs/current/ui/README.md)
Frontend, templates, interactions, theming
- [Templates & Pages](specs/current/ui/templates.md) - HTML structure, base layouts
- [Session Logging UI](specs/current/ui/session-logging.md) - Word-processor-style tune logging
- [Dark Mode & Theming](specs/current/ui/theming.md) - CSS variables, theme switching
- [AJAX Patterns](specs/current/ui/ajax.md) - API integration, loading states

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
- [External APIs](specs/current/logic/external-apis.md) - thesession.org, SendGrid
- [Active Sessions](specs/current/logic/active-sessions.md) - Real-time session tracking

### [Services Layer](specs/current/services/README.md)
Internal services, microservices, background jobs
- [ABC Renderer](specs/current/services/abc-renderer.md) - Node.js microservice for ABC → PNG
- [Active Sessions Cron](specs/current/services/active-sessions-cron.md) - 15-min job tracking live sessions

## Feature Index

- **Session Tracking**: [Data](specs/current/data/session-model.md) | [Logic](specs/current/logic/session-logic.md) | [UI](specs/current/ui/session-logging.md)
- **Attendance (Feature 001)**: [Data](specs/current/data/people-model.md) | [Logic](specs/current/logic/attendance.md)
- **Tune Management**: [Data](specs/current/data/tune-model.md) | [Logic](specs/current/logic/tune-logic.md)
- **User System**: [Data](specs/current/data/people-model.md) | [Logic](specs/current/logic/auth.md)

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

- `app.py:14` - Flask app initialization
- `web_routes.py` - 2960 lines, all HTML page routes
- `api_routes.py` - 9671 lines, all JSON API endpoints
- `auth.py:12-70` - User model and authentication
- `database.py:13-21` - DB connection, `database.py:24+` - History tracking
- `schema/schema.md` - Complete database documentation
