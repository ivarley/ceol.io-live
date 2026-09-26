# AJAX Patterns and API Integration

Frontend-backend communication using fetch API for dynamic updates.

## Serializer Layer (`serializers.py`)

One function defines each wire shape (spec 035 §1d). Every producer of that
shape — the JSON API endpoint **and** the page shell's embedded first-paint
payload (`window.__PAGE_DATA__`) — funnels through it, so **embed == API** and
they cannot drift. See [Svelte Pages](svelte-pages.md) for the page table.

Pattern rules (from the module docstring — deliberately different from
`live_logging_routes.py`'s first cut):

- **Mappers are pure**: `(row) -> dict`. No DB connection, ever. Anything that
  needs a query happens in a loader, batched (no N+1 in a loop).
- **Rows are read by name** via `psycopg2.extras.RealDictCursor`, never by
  position, so the column list and the mapper can't silently fall out of sync.
- **Loaders take a connection** and open their own RealDictCursor; callers
  keep owning the connection/transaction.

Current builders: `build_my_tunes_payload`, `build_person_tune_detail`,
`build_tune_detail_payload` (THE tune-drawer feed — `GET /api/tunes/<id>/detail`
plus the legacy per-session tune-detail GETs all delegate to it),
`build_sessions_directory_payload`, `build_session_detail_payload`,
`build_person_details_payload`, `build_session_admin_payload`, plus shared
helpers (`timezone_options`, `recurrence_readable` — also used by
`web_routes._get_session_data`). New payloads go here, not inline in handlers.

## API Auth (`api_auth.py`)

- **`@api_login_required`** — the standard for authenticated `/api/*`
  endpoints: returns **401 JSON**, never flask_login's `@login_required`
  (which 302-redirects to the HTML login page — wrong for fetch and for
  native clients). One definition, imported by `api_routes.py` and
  `api_person_tune_routes.py`.
- **`@api_admin_or_self_required`** — for person-scoped endpoints
  (`person_id` arg): authenticated AND (system admin OR that person);
  401/403 JSON. Guards PII endpoints like `/api/person/<id>/logins`.
- **`@public_api`** — a runtime no-op marker for endpoints that are
  **deliberately** unauthenticated (e.g. the public session logs feed). Its
  purpose is auditability: an `/api/*` handler with neither an auth decorator
  nor `@public_api` is a bug, not a decision. The direction is that **every**
  `/api/*` endpoint ends up explicitly classified one way or the other.

Both real decorators set `_auth_required = True` and `@public_api` sets
`_public_api = True` — machine-checkable markers, so the unclassified
endpoints can be found mechanically (`tests/integration/test_person_api_auth.py`
covers the person-scoped 401/403/self/admin/public matrix). HTML page routes
in `web_routes.py` keep `@login_required` — a 302 to login is correct there.

**Bearer tokens**: a `request_loader` in `app.py` (`load_user_from_request`)
authenticates `Authorization: Bearer <user_session id>` against any `/api/*`
route — the same tokens the streaming sidecar honors. Cookie sessions still
flow through `user_loader`; the request_loader only runs when the cookie is
absent/invalid. Tokens are minted by the native login handshake (below) and,
for the web → sidecar case, by `/api/live/token`.

## The native handshake (`api_app_routes.py`, spec 052)

A client announces itself with **`X-Ceol-Client: <platform>/<version>`**
(`ios/1.2.0 (build 57)`; absent or `web/…` = the browser). `api_auth.current_client()`
parses it; `is_native_client()` is the one switch the login paths branch on. The
string is stored on the `user_session` row (prefixed onto `user_agent`) so a token
traces to an install, and `/api/app-config` compares the version to
`MIN_CLIENT_VERSION_<PLATFORM>` to set `force_upgrade`.

| Endpoint | Auth | What |
|---|---|---|
| `GET /api/app-config` | public | `streaming_base_url`, `min_client_version`, `force_upgrade` (for THIS caller), feature flags |
| `POST /api/auth/check-email` | public | spec 013 step 1: `password_login` / `magic_link_sent` / `registration_started` |
| `POST /api/auth/login-password` | public | web caller: cookie + `redirect`; **native caller: `token` + `token_type: Bearer`, no cookie**. Both: `user`, `next` (`set_password` / `setup_profile` / null), `method` |
| `POST /api/auth/exchange {token}` | public | consumes a magic-link login token **or** an email-verification token (both emailed links are Universal Links for the app) → same body as login |
| `POST /api/auth/resend-verification {email}` | public | quiet 200 either way |
| `POST /api/auth/logout` | bearer/cookie | revokes the presented token (or the cookie's `user_session`) |
| `POST /api/auth/set-password {password}` | bearer | the optional step after a magic-link login |
| `GET /api/me` | bearer | identity block (`user_id`, `person_id`, names, `is_system_admin`, `timezone`, `email_verified`, `has_password`, `needs_profile_setup`) |
| `GET|PUT /api/me/profile` | bearer | the JSON twin of `/auth/setup-profile` (name, location, timezone, instruments; blank clears, absent keeps) |
| `GET /api/home` | bearer | `serializers.build_home_payload` — the same dict the Jinja `/` renders |
| `GET /api/resolve?path=` | public | a ceol.io URL/path → `{kind: session|instance, session, instance}` using `session_handler`'s rules (`oflahertys/2025` is a session, not an instance) |
| `POST /api/auth/web-session {next}` | bearer | mints a 5-minute one-time `/auth/login/<token>?next=…` link so the app can open the web (admin, help) signed in |
| `/.well-known/apple-app-site-association` | public | served when `IOS_APP_IDS` is set; paths in `api_app_routes.UNIVERSAL_LINK_PATHS` |

`establish_session(user, method)` is the one place a successful login is recorded
(user_session row, LOGIN_SUCCESS history, cookie **only** for web callers);
`web_routes.login_password_api` delegates to it. `auth.User.get_by_id` loads the
password hash so `has_password()` is correct on every request, not just at login.

**The native surface** — the endpoints a native client may depend on — is
enumerated in `specs/api/native-surface.yaml` (OpenAPI 3.1) and enforced by
`tests/contract/test_native_surface.py`: every documented operation must be a
registered, auth-classified rule, and the listed GETs' live responses must
validate against their schemas. Changes to that surface are **additive only**.

## Standard Pattern

**Basic Fetch**:
```javascript
fetch('/api/endpoint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
})
.then(response => response.json())
.then(data => {
  if (data.success) showMessage(data.message, 'success');
  else showMessage(data.error, 'error');
})
.catch(error => showMessage('An error occurred', 'error'));
```

In Svelte pages the same calls live in the page's `logic.js` / components,
with `frontend/src/lib/toast.js` wrapping `showMessage`.

**With Loading State**:
```javascript
button.disabled = true;
button.textContent = 'Saving...';
// ... fetch request ...
.finally(() => {
  button.disabled = false;
  button.textContent = 'Save';
});
```

## Key Operations

**Page payloads**: `GET /api/my-tunes`, `GET /api/sessions/with-today-status`, `GET /api/sessions/<path>/detail`, `GET /api/me/details`, `GET /api/admin/sessions/<path>/admin-detail` — aggregate reads, same shape as the page embeds

**My Tunes ops**: `POST /api/my-tunes/ops` - Idempotent, offline-queued writes (see [Offline Support](../logic/offline.md))

**Check-In**: `POST /api/session_instance/<id>/attendees/checkin` - Button disabled, spinner | `partials/attendance_tab.html`

**Tune Search**: `GET /api/tunes/search?q=<query>&mode=name|abc|mixed` - 300ms debounce, dropdown; blends
notation matches for note-shaped queries and flags them `abc_only` | `frontend/src/TuneSearch.svelte`
(Svelte pages), `frontend/src/tunesheet/FindTune.svelte` (hamburger overlay), `TuneSearchComponent.js` (pill page only)

**Notation filter**: `POST /api/tunes/abc-filter {q, tune_ids}` -> `{tune_ids}` - which of THESE tunes match this
notation query. Backs the three client-side list filters (My Tunes, session Tunes tab, admin tunes tab), whose
payloads carry no ABC | `frontend/src/shared/abcfilter.svelte.js`. `@public_api` (session pages are public).

**Save Tunes** (deprecated pill page): `POST /api/sessions/<path>/<date_or_id>/save_tunes` - Bulk save | `session_instance_detail.html`

## Loading States

**Buttons**: Disable + text change ("Saving...")

**Spinner**: `<i class="fas fa-spinner fa-spin"></i>`

**Overlay**: Full-page for long operations

**Svelte pages**: no loading flash on first paint — the shell embeds the payload

## Error Handling

**Response**: `{"success": false, "error": "Message", "message": "Message", "code": "not_found"}`
— see *API Response Conventions* below; `error` and `message` are the same string.

**Client**: Check `data.success`, show `data.error` via `showMessage()` / `toast()`;
a native client switches on `code`.

**Network**: Catch block, generic message

**Status**: 200 (OK), 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 500 (Server)

## Debouncing

**Search**: 300ms delay (legacy inline pattern below; Svelte pages use `lib/SearchField.svelte`'s `debounce` prop)
```javascript
let searchTimeout;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => performSearch(), 300);
});
```

## Patterns

**Optimistic Update**: Update UI first, revert on server rejection (kept on network failure — the op queues offline)

**Form Submit**: Intercept with `preventDefault()`, fetch with JSON

**File Upload**: FormData (don't set Content-Type)

## API Response Conventions

**Success**: the payload itself, with `"success": true` (page-payload GETs return
the bare serializer dict). Live-op *business* rejections are HTTP 200 with
`{success: true, rejected: true, reason}` — a documented protocol, not an error.

**Error** (spec 052 A3): every `/api/*` 4xx/5xx body is

```json
{"success": false, "error": "<human>", "message": "<human>", "code": "<machine>"}
```

`error` and `message` carry the same string because the web reads both
(`data.error || data.message` and vice versa, ~40 sites); `code` is what a native
client switches on (`unauthenticated`, `forbidden`, `not_found`, `conflict`,
`invalid`, `invalid_token`, `date_conflict`, …; defaults per status in
`api_auth.DEFAULT_ERROR_CODES`). Build errors with **`api_auth.api_error(message,
status, code, **extra)`**. The ~400 legacy sites that still hand-roll
`jsonify({"success": False, "message": …})` are made to conform by
`app._normalize_api_errors` (an `after_request` that back-fills missing keys on
JSON error responses under `/api/`), so the guarantee holds across every rule
without a sweep; converting them to `api_error` as they're touched is still the
direction.

**Dates** (spec 052 A4): `app.json` is `CeolJSONProvider` — `date`/`datetime`/`time`
serialize as ISO 8601 (`2026-09-21`, `2026-09-21T01:02:03+00:00`, `23:00:00`),
`Decimal` as float, for `jsonify` AND Jinja's `|tojson`. Flask's stock provider
emitted RFC 822 (`Sun, 21 Sep 2026 00:00:00 GMT`); nothing should rely on that.
Display strings (`session_date`, `recurrence_readable`, `timezone_display`,
`date_label`, `state_label`) always ride beside a raw field (`instance_date`,
`recurrence`, `timezone`, `date`, `group`) — never ship a formatted string alone.

## Key Endpoints

**Routes**: `api_routes.py` + `api_person_tune_routes.py` (JSON APIs, URL rules bound in `app.py`), `web_routes.py` (HTML pages)

**Common**: page payloads, my-tunes ops, check-in, tune search, tune linking, session management
