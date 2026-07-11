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

**Bearer tokens**: a `request_loader` in `app.py` (`load_user_from_request`,
`app.py:106`) authenticates `Authorization: Bearer <user_session id>` against
any `/api/*` route — the same tokens minted by `/api/live/token` and honored
by the streaming sidecar. Cookie sessions still flow through `user_loader`;
the request_loader only runs when the cookie is absent/invalid. This is what
a future native client uses.

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

**Tune Search**: `GET /api/tunes/search?q=<query>` - 300ms debounce, dropdown | `frontend/src/TuneSearch.svelte` (Svelte pages), `components/tune_search_input.html` (legacy)

**Save Tunes** (deprecated pill page): `POST /api/sessions/<path>/<date_or_id>/save_tunes` - Bulk save | `session_instance_detail.html`

## Loading States

**Buttons**: Disable + text change ("Saving...")

**Spinner**: `<i class="fas fa-spinner fa-spin"></i>`

**Overlay**: Full-page for long operations

**Svelte pages**: no loading flash on first paint — the shell embeds the payload

## Error Handling

**Response**: `{"success": false, "error": "Message"}`

**Client**: Check `data.success`, show `data.error` via `showMessage()` / `toast()`

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

**Success**: `{"success": true, "message": "...", "data": {...}}`

**Error**: `{"success": false, "error": "...", "code": "..."}`

(Older endpoints vary; normalizing envelopes/status codes is the follow-up
spec to 035. New endpoints follow the shapes above, or return the bare
serializer payload for page-payload GETs.)

## Key Endpoints

**Routes**: `api_routes.py` + `api_person_tune_routes.py` (JSON APIs, URL rules bound in `app.py`), `web_routes.py` (HTML pages)

**Common**: page payloads, my-tunes ops, check-in, tune search, tune linking, session management
