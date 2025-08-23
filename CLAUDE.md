# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This system provides a mobile and desktop web experience for traditional Irish music players to track their live group musical performances (called "sessions") and the pieces of music ("tunes") they play. It's a Flask-based web application with PostgreSQL database backend, user authentication, and extensive API functionality.

## Architecture

### Core Application Files

- **app.py**: Main Flask application entry point with route registration and configuration
- **web_routes.py**: HTML page route handlers (home, sessions, authentication, etc.)
- **api_routes.py**: JSON API endpoints for AJAX functionality
- **auth.py**: User authentication system with Flask-Login integration
- **database.py**: Database connection utilities and history tracking functions
- **email_utils.py**: Email functionality for password resets and verification

### Database & Schema

- **PostgreSQL database** with comprehensive schema for sessions, tunes, and user management
- **schema/**: SQL schema files for table creation and initial data
- **schema/schema.md**: Detailed database schema documentation
- **scripts/**: Database backup and restore utilities

### Frontend

- **templates/**: Jinja2 HTML templates with base layout and specialized pages
- **static/**: CSS styling and images
- **Mobile-optimized** responsive design
- **dark-mode** ready, all pages support both light and dark mode

## Key Features

### Session Data Tracking

- Track regular music sessions with location, timing, and recurrence patterns
- Record individual session instances (specific dates/times)
- Add and organize logs of tunes played during sessions

### Session Logging

- View and edit modes
- Set management (grouping tunes played consecutively)
- Beta version (session_instance_detail_beta) using a word-processor like UI with drag and drop, copy paste, undo

### Tune Database

- Integration with thesession.org API for tune metadata
- Local tune aliases and session-specific information
- Tune type categorization (jig, reel, hornpipe, etc.)
- Tunebook popularity tracking

### User System

- User registration with email verification
- Password reset functionality via email
- Session-based authentication with configurable expiration
- Admin user capabilities

### API Functionality

- Comprehensive REST API for all major operations
- AJAX-driven frontend for smooth user experience
- Real-time tune searching and linking
- Session data management endpoints

## Development Commands

### Running the Application Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables (see .env file)
# PGHOST, PGDATABASE, PGUSER, PGPASSWORD, etc.

# Run in development mode
flask --app app run

# Or with debug mode enabled
flask --app app run --debug
```

### Production Serving

The application uses Gunicorn for production deployment on Render, which automatically detects the Flask app.

## Key Implementation Details

### Application Structure

- Flask app instantiated in app.py:14 with secret key configuration
- Route registration uses `add_url_rule()` for clean separation of concerns
- Flask-Login integration for user session management (app.py:22-29)
- Environment variable configuration via python-dotenv

### Database Integration

- PostgreSQL connection via psycopg2 (database.py:13-21)
- Comprehensive history tracking for audit trails (database.py:24+)
- Connection pooling handled by database module

### API Design

- RESTful endpoints under `/api/` prefix
- JSON responses for all API calls
- Consistent error handling and status codes
- Integration with external thesession.org API

### Security Features

- bcrypt password hashing
- Email verification for new accounts
- Secure session management with configurable timeouts
- CSRF protection via Flask's built-in mechanisms

### File Locations Reference

- Main routes: web_routes.py (pages), api_routes.py (JSON APIs)
- User model: auth.py:12-70
- Database utilities: database.py
- Templates: templates/ directory with auth/ subdirectory
- Schema documentation and DDL: schema/*
