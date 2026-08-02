# Ceol.io

Irish traditional music session tracker. A web application for tracking live music sessions, tunes, and attendance at Irish traditional music gatherings.

## Features

- **Session Management**: Create and manage recurring music sessions with location details
- **Tune Logging**: Word-processor-style interface for logging tunes played at sessions
- **Attendance Tracking**: Track who attended which sessions with role management
- **Tune Database**: Link tunes to thesession.org, track popularity and settings
- **User Profiles**: Personal tune lists, session history, and preferences
- **Dark Mode**: Full theme support with CSS variables

## Tech Stack

- **Backend**: Flask 3.1, PostgreSQL, Gunicorn
- **Frontend**: Svelte 5 for the interactive pages, Jinja2 shells around them; Bootstrap 4.5 on the older pages
- **Authentication**: Flask-Login with email verification
- **Deployment**: Render.com
- **External APIs**: thesession.org (tune data), SendGrid (email)

## Local Development

```bash
./start              # http://localhost:3232
./start --reset-db   # drop and reseed the local database first
```

`./start` is idempotent and sets up whatever is missing — Postgres, the venv, the frontend bundles, `.env`, the seeded database, and the live-logging streaming sidecar.

## Documentation

[CLAUDE.md](CLAUDE.md) is the map: what the app is for, where the code lives, and links into `specs/` for the architecture.

## License

Private project.
