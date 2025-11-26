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
- **Frontend**: Bootstrap 4.5, Jinja2 templates, vanilla JavaScript
- **Authentication**: Flask-Login with email verification
- **Deployment**: Render.com
- **External APIs**: thesession.org (tune data), SendGrid (email)

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (see .env.example)
export PGHOST=localhost
export PGDATABASE=ceol
export PGUSER=your_user
export PGPASSWORD=your_password
export SECRET_KEY=your_secret_key

# Run development server
flask --app app run --debug --port 5001
```

## Project Structure

```
├── app.py              # Flask app initialization
├── web_routes.py       # HTML page routes
├── api_routes.py       # JSON API endpoints
├── auth.py             # User authentication
├── database.py         # Database connection and utilities
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, images
└── schema/             # Database schema and migrations
```

## Documentation

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.

## License

Private project.
