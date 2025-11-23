# Logic Layer

Business logic, services, workflows, external integrations.

## Overview

- **Routes**: `web_routes.py` (HTML pages), `api_routes.py` (JSON endpoints)
- **Auth**: Flask-Login session management
- **Services**: Modular logic in dedicated files
- **External**: thesession.org API, SendGrid email

## Components

### [Authentication](auth.md)
User registration, login, password reset, email verification

### [Session Management](session-logic.md)
Automatic instance creation, recurrence pattern handling

### [Tune Services](tune-logic.md)
Search, linking to thesession.org, popularity tracking, alias management

### [Attendance System](attendance.md)
Check-in workflows, role-based permissions, instrument tracking (Feature 001)

### [External APIs](external-apis.md)
thesession.org integration, SendGrid email service

### [Active Sessions](active-sessions.md)
Real-time tracking of currently happening sessions (see also [Active Sessions Cron](../services/active-sessions-cron.md))

## Key Locations

- `web_routes.py` - All HTML page handlers
- `api_routes.py` - All JSON API endpoints
- `auth.py` - User model and auth logic
- `session_instance_auto_create.py` - Recurrence handling
- `active_session_manager.py` - Active session tracking
- `api_person_tune_routes.py` - Person/tune relationship endpoints
