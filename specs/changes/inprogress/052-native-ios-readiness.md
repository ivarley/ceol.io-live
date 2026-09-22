# 052: Native iOS Readiness — first-pass assessment

**Date:** 2026-09-21
**Status:** Section A (API / auth) **BUILT 2026-09-21** — pytest 1359 passed (54 new,
3 existing tests updated). Section B (web UI reshaping) is pending the user's read.
Section C/D unchanged.

**What section A built** (all web-repo work, no frontend change; the web login page
and the Jinja home behave exactly as before):

- **A1 auth handshake** — `api_app_routes.py` (new): `POST /api/auth/login-password`
  returns a Bearer token (and no cookie) to a caller sending `X-Ceol-Client: ios/…`,
  via the shared `establish_session()`; `POST /api/auth/exchange {token}` consumes a
  magic-link OR verification token (the two emailed Universal Links); `POST
  /api/auth/logout` revokes the token; `POST /api/auth/resend-verification`, `POST
  /api/auth/set-password`, `GET /api/me`, `GET|PUT /api/me/profile` (the JSON twin of
  `/auth/setup-profile`), `GET /api/app-config` (streaming URL, per-platform
  `MIN_CLIENT_VERSION_*`, `force_upgrade`). `auth.needs_profile_setup` is shared with
  the web redirect. `User.get_by_id` now loads the password hash, so `has_password()`
  is right on every request — a latent bug: before this, EVERY verified user was
  redirected to set-password (one existing test asserted the buggy behaviour).
- **A2 home** — `serializers.build_home_payload` + `GET /api/home`; `web_routes.home`
  renders the same dict (the five inline queries moved into named loaders on a
  RealDictCursor).
- **A3 envelope** — `api_auth.api_error()` + `DEFAULT_ERROR_CODES`; an
  `after_request` normalizer (`app._normalize_api_errors`) back-fills
  `{success, error, message, code}` on every `/api/*` JSON error. **Deviation from
  the assessment:** the shape is FLAT (`error` and `message` both the human string,
  `code` the machine string), not `error: {code, message}` — the web reads
  `data.error` / `data.message` as strings at ~40 sites and a nested object would
  toast `[object Object]`.
- **A4 dates** — `CeolJSONProvider` in `app.py`: ISO 8601 for date/datetime/time,
  float for Decimal, for `jsonify` and `|tojson`. The raw-beside-display audit found
  every display string already has a raw twin; the rule is now written down in
  `specs/current/ui/ajax.md`.
- **A5 native surface** — `specs/api/native-surface.yaml` (OpenAPI 3.1, 40 operations,
  schemas for the 20 GETs with stable shapes) + `tests/contract/test_native_surface.py`
  (every documented op is a registered, auth-classified rule; live responses validate).
  `jsonschema` + `PyYAML` added to `requirements-test.txt`.
- **A6 search family** — one `/api/tunes/*` tree with `?session=<path>` /
  `?instance=<id>` scope (`tunes_deep_search`, `tunes_thesession_search`,
  `/api/tunes/<id>/preview`, `/api/tunes/<id>/incipit-image` — named so it doesn't
  collide with the older `/api/tunes/<id>/incipit`, `/api/tunes/settings/<id>/image`,
  `/api/tunes/thesession/<id>/preview`, `/api/tunes/render-abc`). The three
  per-page trees (21 rules) stay registered as aliases for the web bundles.
- **A7 deep links** — `GET /api/resolve?path=` (session_handler's rules, incl.
  `/live/instances/<id>` and full URLs); `POST /api/auth/web-session {next}` mints a
  5-minute one-time `/auth/login/<token>?next=` link (`login_with_token` now honours a
  site-relative `next`); `/.well-known/apple-app-site-association` served when
  `IOS_APP_IDS` is set.
- **A8 client id** — `X-Ceol-Client` parsed by `api_auth.current_client()` (cached on
  the WSGI environ, not `g` — `g` leaks across requests under one app context, which
  the test client uses), stored on `user_session.user_agent` and `login_history`.
- **A9 push** — not built, as planned.

**Not done / follow-ups:** the ~400 legacy `jsonify({"success": False, "message"…})`
sites are conformed at runtime, not rewritten; the web bundles still call the old
search trees; the AASA file needs the real Team ID; Universal-Link handling in the app
itself is app work.

---

This is the survey of what the web codebase
would need to change so a native iOS app is a translation of a known API and component
vocabulary rather than a fresh design. Spec 035's north star said exactly this; this spec
audits how far along that road we are and names the remaining work.

**Related:** [035](035-svelte-ui-consolidation.md) (serializer layer, kit, "native port =
translation"), [024](../024-live-logging-architecture.md) (Bearer tokens, SSE sidecar,
op vocabulary), [021](../021-simplified-session-screen.md) (the mobile-first logger
prototype), [013](../013-simplified-login.md) (email-first login).

---

## Where we already are (don't redo this)

The audit found the API layer is much closer to native-ready than a Flask+Jinja app
usually is. Specifically:

| Piece | State | Evidence |
|---|---|---|
| Bearer auth on every `/api/*` route | Done | `app.py` `load_user_from_request` accepts `Authorization: Bearer <user_session id>`; the streaming sidecar validates the same tokens (`streaming/service.py` `authenticate`) |
| API handlers never read the cookie session dict | Verified | zero `session[...]` / `session.get(` reads in `api_routes.py`, `api_person_tune_routes.py`, `live_logging_routes.py`, `recording_routes.py`. The `admin_session_ids` cache written at login is only read by one HTML admin page (`web_routes.py:2390`). A Bearer client cannot hit a hidden cookie dependency in the API. |
| 401 JSON, never 302 | Done | `api_auth.py`; ratchet test `tests/integration/test_api_auth_coverage.py` — all 182 `/api/*` rules classified |
| One serializer per payload, embed == API | Done for 8 pages | `serializers.py`; the page table in `specs/current/ui/svelte-pages.md` |
| Idempotent, client-id'd write ops | Done ×2 | live ops (`op_id`, `/api/live/instances/<id>/ops`, ~18 op types); my-tunes ops (`/api/my-tunes/ops`, 8 op types) |
| Real-time transport a native client can use | Done | SSE + `Last-Event-ID` catch-up (URLSession handles SSE fine); upstream is plain POST |
| Sync primitive for a local store | Done | `GET /api/offline/bundle` — whole tunebook + incipits + top-100 catalog, with drift guards |
| thesession.org proxied server-side | Done | `thesession-search` / `thesession-preview` endpoints; the client never talks to thesession.org |
| Notation as images | Done | ABC renderer sidecar → PNG (`setting-image`, `incipit`, `render-abc`) — no web view needed to show a tune |
| Audio upload | Done | presigned S3 PUT (`recording.py generate_presigned_upload`) — native uploads straight to S3 |
| JSON login endpoints | Partial | `POST /api/auth/check-email`, `POST /api/auth/login-password` exist (spec 013) but **set a cookie and return no token** |
| Component kit with a small vocabulary | Done | `frontend/src/lib/`: Sheet, Dialog, Popover, Tabs, Seg, Chip, List, Pager, SearchField, toast — each has an obvious UIKit/SwiftUI counterpart (see §UI) |

So the "separate API layer" mostly exists. What is missing is the **edge**: the auth
handshake, a handful of screens with no API, envelope/date consistency, duplicated
endpoint trees, and the compatibility discipline a shipped binary needs.

---

## A. API layer — gaps

### A1. Auth handshake (the actual blocker)

Today a token can only be minted by an already-cookie-authenticated browser
(`POST /api/live/token`, `@api_login_required`). A native app has no cookie. Needed:

1. **Token-returning login.** `POST /api/auth/login-password` (and the magic-link
   completion) return `{token, token_type: "Bearer", user: {...}}` when the client asks
   (e.g. `X-Ceol-Client: ios/…` header, or a `?client=native` body flag). The cookie path
   stays for the web. `create_session()` already produces the `user_session` row that
   *is* the token — this is plumbing, not design.
2. **Magic link → app.** `/auth/login/<token>` currently 302s into a cookie session. For
   native: register it as a Universal Link (`apple-app-site-association`), and add
   `POST /api/auth/exchange {login_token}` that consumes the one-time login token and
   returns a Bearer token. Same for `/verify-email/<token>`.
3. **Logout** = `POST /api/auth/logout` revoking the `user_session` row (today `/logout`
   is HTML and clears cookies).
4. **Registration / verification / profile setup are HTML-only.** `register()`
   (`web_routes.py:914`), `resend_verification`, `setup_profile` (`web_routes.py:1757`,
   name/location/timezone/instruments) all read `request.form` and render Jinja. Need JSON
   twins — or, cheaper, make the existing handlers content-negotiate.
5. **`GET /api/me`** — a minimal identity payload: user_id, person_id, name, is_admin,
   timezone, email_verified, `has_password`, flags. Today the viewer's identity only
   arrives embedded in page payloads (`viewer` blocks) and `__LIVE_CONFIG__`.
6. **`GET /api/app-config`** (public) — `streaming_base_url` (today an env var injected
   into the Jinja shell `live_logging.html`), `min_supported_client_version`,
   `force_upgrade`, feature flags. A shipped binary cannot be hot-patched the way a Vite
   bundle can; this endpoint is how the server steers old clients.

### A2. Screens with no API

- **Home** (`web_routes.py home()`, ~200 lines): five inline queries (learning counts,
  suggested tune, this week's sessions, in-progress logs, in-progress recordings) rendered
  straight into `home.html`. It is the native app's first screen. Needs
  `serializers.build_home_payload` + `GET /api/home`, and (independently useful) the web
  home becomes a Svelte page on the same payload.
- **Attendance page** (`session_instance_players`) is Jinja, but its data is already
  available via `/api/session_instance/<id>/attendees*` and the live `attendance_*` ops —
  no new API needed, just note that the native client uses those.
- **Help pages** — leave as web; open in `SFSafariViewController`.
- **Admin** (`/admin/*`, 30 API rules + Jinja tables) — explicitly out of native scope
  for v1. Deep-link to the web with a session handoff (see A7).

### A3. One response envelope

Codable models want one shape. Today there are at least five:

| Shape | Where |
|---|---|
| `{"success": false, "error": "..."}` | `api_auth.py`, ~140 sites in `api_routes.py` |
| `{"success": false, "message": "..."}` | ~274 sites in `api_routes.py` |
| bare `{"error": "..."}` | `check_email_api`, `login_password_api` |
| `{"success": true, "rejected": true, "reason": "date_conflict"}` | live ops (a *business* rejection, deliberately not an HTTP error — keep this idea) |
| raw payload dict, no `success` key | some aggregate GETs (`get_session_detail` returns `jsonify(payload)`; `build_my_tunes_payload` includes `success: true`) |

Proposal, applied to the **native surface** (A5) rather than all 182 rules at once:
errors are always `{"success": false, "error": {"code": "<machine_code>", "message":
"<human>"}}` with a real HTTP status; successes return the payload body itself (no
wrapper — the status code is the wrapper); live-op rejections stay
`{success: true, rejected: true, reason}` since they are a documented protocol. Add
machine-readable `code`s (`not_found`, `forbidden`, `date_conflict`, `offline`…) — the
app switches on codes, not English.

### A4. Dates and display strings

- **Flask's default JSON provider emits `date`/`datetime` as RFC 822** (`Sun, 21 Sep
  2026 00:00:00 GMT`). The serializers are careful (~70 `.isoformat()` calls across the
  API modules), but nothing enforces it. Install a `JSONProvider` that serializes
  `date`/`datetime`/`time` as ISO 8601 so a missed field can't leak the wrong format.
- **Presentation strings ride in payloads** without a raw twin in some places: live
  bootstrap `session_date` is `format_session_date()` output ("Sat · Sep 20, 2026") and
  the raw `instance_date` was added later precisely because of this; `date_label`
  (`strftime("%a %-d %b %Y")` in the recordings list), `recurrence_readable`,
  `timezone_display`, `state_label`. Keeping display strings is fine (they encode server
  rules), but every one needs the raw value beside it: ISO date, IANA tz, recurrence
  rule, state enum. Audit rule: *no field that is only a formatted string*.
- **Session timezone vs user timezone**: payloads sometimes pre-resolve "today" in the
  session's tz (`build_session_detail_payload`). Ship the tz name so the client can do the
  same arithmetic offline.

### A5. Declare the native surface, then freeze it

182 rules include legacy and duplicate families a native client must never see:
the quarantined pill logger's `save_tunes`, `*_grid_ajax`, `/api/sessions/list` +
`/api/my-sessions` + `/api/user/admin-sessions` (035 noted the collapse), the person
`tunes*` endpoints. Rather than a global rename (035 deferred REST renaming; still the
right call), **enumerate the native surface** (~35–40 endpoints):

- auth (A1), `me`, `app-config`, `home`
- `my-tunes` payload + ops; `tunes/search`, `tunes/<id>/detail`, `tunes/<id>/incipit`,
  `tunes/abc-filter`; the search family (A6)
- `sessions/with-today-status`, `sessions/<path>/detail`, `logs`, `logged-tunes`,
  `people`, `join`/`leave`, `add_instance`, `next_instance_suggestion`,
  `session/<id>/active_instance`
- live: `bootstrap`, `vocabulary`, `ops`, `people`, `token`; sidecar `events`, `typing`
- `session-instances/<id>/recordings`, `audio`; `offline/bundle`
- `me/details`, `person/<id>/instruments`, `instrument-auto`, `update`

Then: (a) a **hand-authored OpenAPI 3.1 document** for just that surface, (b) a pytest
**contract test** that hits each endpoint against the seeded DB and validates the response
against its schema (the drift guard, in the spirit of `test_api_auth_coverage.py`), and
(c) generate the Swift models from the OpenAPI doc (`swift-openapi-generator`). Schema
changes on the native surface are **additive-only**; removals wait a deprecation window
measured in app-store months, not deploys.

### A6. Collapse the triplicated tune-search family

Seven endpoints (`deep-search`, `thesession-search`, `incipit/<id>`, `tune-preview/<id>`,
`setting-image/<id>`, `thesession-preview/<id>`, `render-abc`) exist **three times**, once
under each of `/api/live/instances/<id>/`, `/api/sessions/<path>/tunes/`, and
`/api/my-tunes/` — 21 rules — with `client.js searchBase(config)` picking the tree per
page. The tune-detail endpoint already solved this the right way (`/api/tunes/<id>/detail`
with `?session=`/`&instance=` scope). Do the same: one `/api/tunes/*` family with optional
scope params; keep the old trees as aliases for the web until the bundles move over.

### A7. Deep links and the web↔app seam

- **Universal Links** for `/sessions/<path>`, `/sessions/<path>/<date>`,
  `/live/instances/<id>`, `/auth/login/<token>`, `/verify-email/<token>`, `/share?url=`.
  The existing URL scheme (spec 012 "URLs for everything") is an asset here.
- **App → web handoff** for admin/help: `POST /api/auth/web-session` mints a one-time
  login token; the app opens `https://ceol.io/auth/login/<token>?next=/admin/...` in
  `SFSafariViewController`. This is the existing magic-link route, reused.
- The `/sessions/<path>/<date_or_id>` ambiguity resolution ("`oflahertys/2025` is a
  session, not an instance") lives in `web_routes.session_handler`. Native should key by
  ids (`session_id`, `session_instance_id`, both present in the directory/detail payloads)
  and only parse paths when opening a Universal Link — expose that resolution as
  `GET /api/resolve?path=...` so the client never reimplements it.

### A8. Client identification and telemetry

Add `X-Ceol-Client: ios/<build>` (web sends `web/<bundle-hash>`); log it on
`login_history`/`user_session.user_agent` (already stored) and in the op endpoints. Cheap,
and it's what makes `min_supported_client_version` enforceable.

### A9. Push notifications (not a prerequisite — plan the table)

Nothing exists (no APNs/web-push code anywhere). The obvious triggers already have hooks:
`active_session_manager` + the 15-min cron know when a member's session goes live; live
ops know when someone logs at your session; `admin_email_updates` is the email version of
"what's new". Plan `device_token(user_id, platform, token, created, last_seen)` and a
sender in `jobs/`; don't build it before the app exists.

---

## B. UI — what to reshape on the web so the port is a translation

The kit already maps cleanly. This table is the translation dictionary; the point of the
rest of this section is the places where the web *doesn't* follow it yet.

| Kit component | iOS counterpart | Notes |
|---|---|---|
| Sheet (`desktop=center`) | `.sheet` with detents / `UISheetPresentationController` | Cancel-left / title / Done-right is already the iOS modal grammar |
| Sheet (`back` prop) | pushed view inside a `NavigationStack` in the sheet | |
| Dialog (destructive verb) | `.alert` / `.confirmationDialog` with `.destructive` role | already "never OK" — correct |
| Popover | `.contextMenu` / `Menu` (phone), `.popover` (iPad) | |
| Tabs (value mode) | segmented `Picker` (≤3) or a scrolling top tab bar | **not** a `<select>` — see B3 |
| Tabs (navigate mode) | `TabView` tab bar | |
| Seg | `Picker(.segmented)` | 1:1 |
| Chip | capsule `Label`/`Button`, `.tag`-style | 1:1 |
| List (↑↓ Enter) | `List` + `NavigationLink` | keyboard nav is n/a |
| Pager (‹ › N of M) | `TabView(.page)` / swipe | |
| SearchField (debounced) | `.searchable` | debounce belongs in the client |
| toast() | **no native equivalent** for success; use inline state / haptic; errors as banner or alert | see B4 |
| Tune-detail drawer | sheet with `.medium`/`.large` detents | payload-derived variants port directly |
| Hamburger menu | **tab bar** | see B1 |

### B1. Navigation IA: hamburger → tab bar (do this on the web first)

`templates/hamburger_menu.html` has 9 items for a signed-in user: Me, Admin, Find a tune,
My Tunes, My Sessions, Add A Session, Log Out, Share, Help. iOS wants 3–5 tabs. Proposed:

**Home · Sessions · My Tunes · Search · Me**

- Add A Session → "+" inside Sessions. Share → the system share sheet (`/share?url=`
  remains the web fallback). Help/Admin/Log Out → inside Me. Find a tune → its own tab
  (it is the most-used action; a tab is faster than a menu).
- Building this as a bottom tab bar on the web's <768px layout now (a) validates the IA
  with real users before it's baked into a binary, (b) forces Home to become a real payload
  (A2), and (c) makes Search a page (`/search`) rather than an overlay bolted to the
  hamburger via `window.FindTuneOverlay`.

### B2. Home as a Svelte page

Follows from A2 and B1. Content stays what it is (learning counts, suggested tune, this
week's sessions, in-progress logs and recordings), but each block should be a payload
section the app can render as cards.

### B3. Retire `Tabs mobileSelect`

Person page and session admin collapse 5+ tabs into a `<select>` on phones. There is no
iOS idiom for that. The person page (Profile / Sessions / Tune stats / Attended / Logged /
Logins) is over-tabbed; on iOS it would be a profile screen with sections and drill-downs.
Restructure it that way on the web (sections + "See all" links), which also removes the
one kit component with no native counterpart.

### B4. Toast diet

`toast()` fires on most successful saves. iOS convention is that obvious success is
silent (the row updated) and only errors interrupt. Trim success toasts to the cases where
the effect is off-screen (e.g. "Added to My Tunes" from a session page). The web gets
quieter and the port doesn't need a toast system.

### B5. The live logger is the real port cost — prepare its logic, not its controls

`frontend/src/App.svelte` is 4,830 lines of bespoke, mobile-first interaction (seams,
action pills, stay-hot search, presence, typing reservations, corroboration merge, undo,
offline queue). The controls are fine to redesign natively; the risk is the **client-side
rules** — `logstate.js` (ordering, set segmentation, cursor slots, `mergeStable`),
`fracindex.js`, `abcquery.js`, `tunesheet/namematch.js`, `shared/segments.js`,
`offline.js` (queue/replay). These must be reimplemented in Swift and must agree with the
JS byte-for-byte or two clients will disagree about the same log.

Prep: **fixture-driven tests** — JSON cases in / expected JSON out — for each of those
modules, in the pattern `namematch.fixtures.json` already uses. Vitest runs them today;
the Swift package runs the same files. That is the single highest-leverage piece of prep
work in this document.

### B6. Design tokens as data

`static/css/theme.css` is the palette. Emit it from a `tokens.json` (colors, radii,
spacing, type scale, z-order names) and generate both the CSS vars and an Xcode asset
catalog / Swift enum from it. Keeps the two clients on one palette without hand-syncing.
Small, do it whenever.

### B7. Things that need no change

Desktop-only constructs (`desktop="dock"` sheets, the `.mt-add-pane` split pane, spec 028's
two-pane logger, hover states, ⌘Enter) simply don't port. The <768px paths are the spec
for iOS. The tune-detail drawer's payload-derived variants, the Seg/Chip/Dialog
conventions, and the id-keyed live-ops protocol port as-is.

---

## C. Architecture choice: native vs WKWebView

Spec 024 hedged "native/WKWebView". Recommendation: **native SwiftUI for the five tabs
and the logger; web only for admin and help** (via `SFSafariViewController` with the A7
handoff). Reasons: notation is already PNG (no web view needed for the hardest rendering
problem), the payloads are already flat JSON, and the logger's offline/live behaviour is
exactly what a web view does worst. A WKWebView wrapper would ship faster and gain almost
nothing over the installable PWA the 021 prototype already demonstrated.

---

## D. Suggested order

Everything in A and B is web-repo work and can ship incrementally behind the web app.

1. **Auth handshake + `me` + `app-config`** (A1, A8) — nothing else can be tested
   end-to-end from a device without it.
2. **ISO JSON provider + envelope on the native surface + raw-beside-display audit**
   (A3, A4) — cheap, mechanical, and the Swift models depend on it.
3. **Native surface list + OpenAPI + contract test** (A5) — freezes the contract before
   the first Swift file. Fold A6 (search family collapse) into this since it changes URLs.
4. **Home payload + tab-bar IA on the web** (A2, B1, B2) — validates the app's shape
   with real users.
5. **Fixture tests for the pure client logic** (B5) — can start any time; must be done
   before the Swift logger.
6. **Person page restructure, toast diet, tokens.json** (B3, B4, B6) — polish; do
   opportunistically.
7. **Universal Links + web handoff** (A7) when the app exists; **push** (A9) after.

Explicitly **not** recommended now: a global REST URL rename (035's call stands), rewriting
existing Svelte pages, or promoting/deleting the pill logger as a prerequisite (035 Step 6
is independent — the native client never sees it either way).
