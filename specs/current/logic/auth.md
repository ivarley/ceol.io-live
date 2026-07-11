# Authentication

User registration, login, password management, email verification.

## Key Files

- `auth.py` - User model, session management, permissions
- `web_routes.py:790-1520` - Registration, login, logout, password reset routes
- `email_utils.py` - SendGrid integration

## User Model

**Location**: `auth.py:13-105`

- Properties: user_id, person_id, username, is_system_admin, email_verified, timezone
- Methods: get_by_id(), get_by_username(), check_password(), create_user()

## Authentication Flow

**Registration** (`web_routes.py:790-983`):
- Links to existing person if email matches, creates new person otherwise
- Email verification required (24-hour tokens)
- Referrer tracking via `?referrer=<person_id>` URL parameter

**Login** (`web_routes.py:986-1104`):
- Blocks login if email not verified
- Creates 6-week session tokens
- Logs all attempts to login_history table

**Password Reset**:
- 1-hour token expiry
- Doesn't reveal if email exists (security)

## Sessions

**Session Management** (`auth.py:177-221`):
- 6-week lifetime (SESSION_LIFETIME_WEEKS = 6)
- Stored in user_session table with IP/user agent
- Token: 32-byte URL-safe string

## API Authentication

- Cookie sessions via flask_login's `user_loader`; additionally a
  `request_loader` (`app.py:106`) accepts `Authorization: Bearer
  <user_session id>` on any route — the tokens minted by `/api/live/token`
  (spec 035; the streaming sidecar validates the same tokens).
- `/api/*` endpoints use the decorators in `api_auth.py`
  (`@api_login_required` 401 JSON, `@api_admin_or_self_required` 401/403,
  `@public_api` marker for deliberately-anonymous endpoints) — see
  [AJAX Patterns](../ui/ajax.md). flask_login's `@login_required`
  (302-to-login) is for HTML page routes only.

## Permissions

**System Admin**: `is_system_admin = TRUE` - access everything

**Session-Level** (`auth.py:287-376`):
- is_session_regular(person_id, session_id) - can view attendance
- is_session_admin(person_id, session_id) - can edit session, manage attendance
- can_view_attendance(user, session_id)
- can_manage_attendance(user, session_id)

**Note**: `api_routes.py` has different can_view_attendance(session_instance_id, person_id) for instance-level checks

## Database Tables

- `user_account` - Login credentials, preferences, tokens
- `user_session` - Active sessions with expiry
- `login_history` - Audit trail (LOGIN_SUCCESS, LOGIN_FAILURE, LOGOUT, PASSWORD_RESET)

## Related

- [People Model](../data/people-model.md) - User/person relationship
- [External APIs](external-apis.md) - SendGrid email
