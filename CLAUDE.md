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

### Session Attendance Tracking (Feature 001)

- Track who attends each session instance with attendance status (yes/maybe/no)
- One-click check-in for regular attendees
- Search and add previous attendees or create new people
- Track instruments played by each person
- Role-based viewing permissions (regulars/admins can view, admins can edit)

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

## Deployment & Infrastructure

- **Hosting**: Render.com with automatic Flask app detection
- **Database**: PostgreSQL hosted on Render (separate service)
- **Production Server**: Gunicorn (auto-configured by Render)
- **Domain**: ceol.io with SSL/TLS termination

## External Integrations

### thesession.org API

- **Purpose**: Tune metadata lookup and validation
- **Usage**: Found in 15+ files across templates and API routes
- **Integration Points**: Tune search, metadata sync, popularity tracking
- **Data Format**: JSON responses with tune details, recordings, discussions

### SendGrid Email Service

- **Purpose**: Password reset emails, account verification
- **Configuration**: Via SENDGRID_API_KEY environment variable
- **Default Sender**: ceol@ceol.io
- **Templates**: Custom HTML email templates for user communications

## Development Workflow

### Local Development

```bash
# Start development server with debug mode
flask --app app run --debug

# Default local server: http://127.0.0.1:5001
```

### Database Operations

- **Backup**: `scripts/backup_database.py` - Creates timestamped SQL dumps
- **Restore**: `scripts/restore_database.py` - Restores from backup files
- **Maintenance**: `scripts/refresh_tunebook_counts.py` - Updates popularity metrics
- **Schema**: All DDL files in `schema/` directory with comprehensive documentation

**Note**: Comprehensive pytest framework with fixtures for unit, integration, and functional tests.

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

#### Attendance API Endpoints (Feature 001)

- **GET** `/api/session_instance/{id}/attendees` - Get attendance list
- **POST** `/api/session_instance/{id}/attendees/checkin` - Check in a person
- **POST** `/api/person` - Create new person with instruments
- **GET/PUT** `/api/person/{id}/instruments` - Manage person's instruments
- **DELETE** `/api/session_instance/{id}/attendees/{person_id}` - Remove attendance
- **GET** `/api/session/{id}/people/search` - Search people for a session

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

## UI/UX Implementation Patterns

### Dark Mode System

- **Implementation**: CSS custom properties with `[data-theme="dark"]` attribute switching
- **Storage**: Theme preference stored in localStorage
- **FOUC Prevention**: Inline script in base.html prevents flash of unstyled content
- **Logo Switching**: Automatic logo variant switching (logo1.png ↔ logo1-dark-transparent.png)

### Responsive Design

- **Framework**: Bootstrap 4.5.2 with extensive customization
- **Approach**: Mobile-first responsive design
- **Breakpoints**: Standard Bootstrap breakpoints with custom CSS variables
- **Layout**: Fluid container system with sidebar navigation

### AJAX-Heavy Frontend

- **Pattern**: Most user interactions use AJAX calls to `/api/` endpoints
- **Error Handling**: Consistent JSON error responses with user-friendly messages
- **Loading States**: Visual feedback during async operations
- **Real-time Updates**: Dynamic content updates without page refreshes

### Session Logging UI

- **Standard Version**: Traditional form-based tune entry and editing
- **Beta Version**: Word-processor-like interface with drag & drop, copy/paste, undo functionality
- **Set Management**: Visual grouping of consecutive tunes played together

## Data Model Key Concepts

### Session Architecture

- **session**: Regular recurring music sessions (location, timing, players)
- **session_instance**: Specific date/time occurrences of a session
- **session_instance_tune**: Individual tunes played during a session instance
- **Relationship**: One session has many instances; one instance has many tunes

### Tune Management System

- **Tune Linking**: Connect session tunes to thesession.org database entries
- **Local Aliases**: Session-specific alternate names for tunes
- **Popularity Tracking**: Tunebook counts from thesession.org API
- **Type Categorization**: Jig, reel, hornpipe, etc. with validation

### User & Authentication Model

- **User Roles**: Regular users vs admin capabilities
- **Session Management**: Server-side sessions with configurable expiration
- **Email Verification**: Two-step registration with email confirmation
- **History Tracking**: Comprehensive audit trail for all data changes

### Set Management

- **Sets**: Groups of tunes played consecutively without breaks
- **Ordering**: Precise tune ordering within sets and across session
- **Movement**: Drag-and-drop reordering with API persistence

## Performance Considerations

### Database Optimization

- **Connection Handling**: Database connection management via get_db_connection()
- **History Tables**: Separate audit tables to avoid bloating main tables
- **Indexing**: Optimized indices for session/tune lookups and popularity queries

### External API Management

- **thesession.org Integration**: Rate limiting and caching considerations for API calls
- **Lazy Loading**: Tune metadata fetched on-demand rather than bulk operations
- **Error Resilience**: Graceful degradation when external APIs unavailable

### Frontend Performance

- **AJAX Patterns**: Minimize full page reloads through targeted API calls
- **Asset Management**: Optimized CSS/JS delivery with proper caching headers
- **Mobile Optimization**: Touch-friendly interfaces with minimal bandwidth usage
