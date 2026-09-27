# Authentication

User registration, login, password management, email verification.

## Key Files

- `auth.py` - User model, session management, permissions
- `web_routes.py` - Registration, login, logout, password reset routes (HTML + the spec-013 JSON login steps)
- `api_app_routes.py` - the native auth handshake, `/api/me`, `/api/app-config` (spec 052)
- `email_utils.py` - SendGrid integration

## User Model

**Location**: `auth.py:13-105`

- Properties: user_id, person_id, username, is_system_admin, email_verified, timezone
- Methods: get_by_id(), get_by_username(), check_password(), create_user()

## Authentication Flow

**Email-first login** (`templates/auth/login.html`, `POST /api/auth/check-email`
→ `web_routes.check_email_api`). The person types an address; the answer is one of:
- `password_login` — an account with a password: show the password field.
- `magic_link_sent` — a passwordless account: a 15-minute login link is emailed.
  Clicking it also sets `email_verified` (the click proves the address).
- `registration_started` — no account for this address. **Nothing is created
  yet** (migration 056): `auth.start_pending_registration` records a
  `pending_registration` row (email, token, 24-hour expiry, the session's
  `referred_by_person_id`) and `email_utils.send_registration_email` sends a
  "create your account" link to `/verify-email/<token>`. The page says "We don't
  have an account for <email> yet. We've sent a link to create one." with a "Try a
  different email" link, so a mistyped address is noticed rather than turned into
  a phantom account. Entering the same address again (any case) refreshes the
  same row: the expiry is extended and the token kept while still valid, so an
  earlier email's link keeps working; an expired token is replaced.

**Clicking the registration link** (`verify_email`, or `POST /api/auth/exchange`
for the app) calls `auth.complete_pending_registration(token)`, in one transaction:
- If an account for that address now exists (made some other way since the link
  was sent), nothing is created, the pending row is deleted, and the person is
  sent to log in (web: redirect to `/login` with a note; API: 409 `account_exists`).
- Otherwise it takes over an accountless `person` whose `email` matches (someone
  an admin added to a roster), or creates a blank person (name and location come
  from profile setup), creates a passwordless `user_account` with
  `email_verified = TRUE`, retires `person.email`, and deletes the pending row.
  The unique index on `LOWER(user_account.user_email)` backs this up if two
  clicks race.
- The person is logged in and continues as before: `/auth/set-password`
  (optional) → `/auth/setup-profile` while the name or location is missing
  (`needs_profile_setup`) → home.

**Resend verification** (`/resend-verification`, `POST /api/auth/resend-verification`):
an unverified `user_account` gets a new verification token; otherwise, if the
address has a pending registration, it is refreshed and its link resent. Unknown
addresses get the generic "if an unverified account exists" answer and nothing is
created.

**Legacy form registration** (`/register`, `web_routes.register`): username,
password and name up front. It still creates the person and an unverified
`user_account` immediately, and the account's own `verification_token` is
consumed by the same `/verify-email/<token>` route. Password login refuses these
accounts until verified. Links emailed by the login page before migration 056
(when it still created the account up front) also take this path.
- Links to existing person if email matches, creates new person otherwise
- Referrer tracking via `?referrer=<person_id>` URL parameter (stored in the Flask
  session by `app.py`, copied to the pending registration or the new account)

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
  `request_loader` (`app.py`) accepts `Authorization: Bearer
  <user_session id>` on any route (the streaming sidecar validates the same
  tokens).
- **Native handshake (spec 052, `api_app_routes.py`)**: a caller sending
  `X-Ceol-Client: ios/<version>` gets a Bearer token (a `user_session` id) from
  `POST /api/auth/login-password` or `POST /api/auth/exchange {token}` (the
  magic-link and email-verification tokens, delivered as Universal Links), and
  no cookie. `POST /api/auth/logout` revokes it. `GET /api/me`,
  `GET|PUT /api/me/profile`, `POST /api/auth/set-password`,
  `POST /api/auth/resend-verification` and `POST /api/auth/web-session` (a
  one-time `/auth/login/<token>?next=` link for opening the web signed in)
  complete the set. `establish_session()` there is the single login-recording
  path; `web_routes.login_password_api` delegates to it. Full table:
  [AJAX Patterns](../ui/ajax.md#the-native-handshake-api_app_routespy-spec-052).
- **Account deletion (spec 054)**: `POST /api/me/delete-account {confirm_email}`
  deletes the account and its private data immediately (`services/account_deletion.py`),
  kills every token, and signs the caller out. The person's name stays on rosters. See
  [People & Attendance](../data/people-model.md#account-deletion-spec-054).
- `auth.needs_profile_setup(person_id)` (missing name or no location) drives
  both the web redirect to `/auth/setup-profile` and the API's `next` field.
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
- `pending_registration` - An address that asked to register on the login page but has not clicked its link; no person or account exists for it yet (migration 056)
- `user_session` - Active sessions with expiry
- `login_history` - Audit trail (LOGIN_SUCCESS, LOGIN_FAILURE, LOGOUT, PASSWORD_RESET)

## Related

- [People Model](../data/people-model.md) - User/person relationship
- [External APIs](external-apis.md) - SendGrid email
