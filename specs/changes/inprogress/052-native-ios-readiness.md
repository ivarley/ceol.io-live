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

**Section B has a clickable prototype and a staged plan (2026-09-22).**
`mockups/tabbar/` (served at `/mockups/tabbar/`) is the interaction prototype for the
reshaping — four tabs, session-centric Home, inline filters, the tune sheet. It settled
several questions the first draft of §B left open; those answers are folded into B1–B4
below, and **§B8 is the stage-by-stage conversion plan**. Nothing in §B is built yet.

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

**Prototype: [`mockups/tabbar/`](../../../mockups/tabbar/README.md)** (`/mockups/tabbar/`) —
clickable, phone-first, dummy data. It is a *guide, not a spec*: it covers a dozen screens
and says nothing about admin, the live logger, attendance, bulk selection, merge/copy-to,
the offline indicator, or the add-tune configure step. Where it and this document
disagree, the prototype is newer.

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

**Home · Sessions · Tunes · Me** — four, settled in the prototype (the first draft
proposed five, with Search as its own tab).

- Add A Session → "+" inside Sessions. Share → the system share sheet (`/share?url=`
  remains the web fallback). Help/Admin/Log Out → inside Me.
- **Search is not a tab.** It is the search field at the top of Tunes, which reaches the
  whole catalogue: on the "All" filter, your matching tunes stay where they are and a
  `Not on your list` divider appears *below* them with catalogue matches; on
  Know/Learning/Want it simply filters that list. This replaces the `FindTuneOverlay`
  bolted to the hamburger without spending a tab on it.
- **Home's icon is the C from the wordmark** (`static/images/android-chrome-192x192.png`),
  greyed by a CSS mask at rest and full-colour when active; the wordmark itself
  (`logo3-1.png`) sits top-left on Home in place of a title.
- Building this as a bottom tab bar on the web's <768px layout now (a) validates the IA
  with real users before it's baked into a binary, and (b) forces Home to become a real
  payload (A2).

### B2. Home as a Svelte page

Follows from A2 and B1; `build_home_payload` already exists. The prototype's ordering,
which differs from today's page:

1. **Today** — present *only* when a session is on today. The whole card opens that
   session's log; one green **View** button does the same. It carries the live/finished/
   starts-at chip, the venue, who is there, and the running tally ("18 tunes logged so
   far"). **More than one session today (a festival) is a horizontal scroll-snap strip**
   with the next card peeking and page dots — not a stack, because at a festival the
   thing you need to see is *that there are three*.
2. **This week** (calendar icon), 3. **Learning** (notes icon), 4. **Pick up where you
   left off** (pencil icon) — the unfinished log and the half-placed recording.

The payload already carries everything except the per-instance "logged so far" tally and
the people-here count; both exist elsewhere (`live_bootstrap`, `active_session_manager`)
and need folding into `build_home_payload` when this is built.

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

### B8. The staged conversion plan

Ordered by **blast radius, not by visibility**. Three things make a stage risky here:
how many pages it touches, whether it disturbs the DOM contract the Playwright suite
pins (spec 035's discipline), and whether it changes navigation.

**Two standing hazards, true of every stage:**

- **The mobile safety net is thin.** `e2e/mobile/core.mobile.spec.ts` is four smoke
  tests on a Pixel 5 (`testMatch: /\.mobile\.spec\.ts/`), against 88 desktop tests.
  Mobile is where all of this work lands.
- **`static/css/my_tunes_mobile.css` is 1,767 lines** loaded by three templates
  (`my_tunes.html`, `session_detail.html`, `admin_tunes.html`) and referenced from
  `sessionpage/page.css` and `mytunespage/TuneCard.svelte`. It is the de-facto mobile
  stylesheet. **Every stage should delete from it, never add to it**; a stage that grows
  it has gone wrong.

---

#### Stage 0 — Widen the mobile e2e net — **DONE 2026-09-22**

**What.** Mobile specs for the screens stages 2–6 touch: the session page's three tabs
(filter, search, scroll), My Tunes filtering and the status Seg, the tune drawer opening
and a status change persisting, Home's blocks.
**Why first.** Pure addition; nothing ships. It is the only thing that makes stages 4–6
safe to attempt, and it is the one step I would argue against skipping.
**Done when.** The mobile project runs ~15–20 specs instead of 4, all green before any
UI changes.

**Built:** the `mobile` project now runs **24 specs across 5 files** (was 4 in 1);
26 tests including setup, all green.

| File | Pins |
|---|---|
| `core.mobile.spec.ts` (unchanged) | the four original smoke tests |
| `sessions.mobile.spec.ts` | tabs are VISUAL on a phone and switch; Tunes search narrows; the filter panel expands from its toggle; Logs lists instances + its tune filter; People roster + search |
| `my-tunes.mobile.spec.ts` | controls render; the status filter works WITHOUT opening the panel; the panel expands; notation search marks `abc-only` hits; the add pane opens via `?add=1` |
| `tune-drawer.mobile.spec.ts` | opens from a My Tunes card and from a session tune row; notation renders; a status change persists to the server |
| `home.mobile.spec.ts` | greeting + counts; **the page and `GET /api/home` agree** (the embed==API invariant Stage 4 formalizes); this week renders or says so; every hamburger destination is listed (the inventory Stage 5 must not shrink) |

Three deliberate choices, so the later stages don't have to rewrite this file:

- **Behaviour, not markup.** The specs assert what a surface *does*. The one structural
  assertion is Home's page-vs-API agreement, because that is precisely what Stage 4
  establishes and the thing most likely to rot unnoticed.
- **A no-sideways-scroll assertion on all three scrolling pages.** One `scrollWidth`
  check each. This is the regression a right-aligned trailing element (Stage 2) causes,
  and it is invisible in a screenshot.
- **The hamburger inventory is recorded in `home.mobile.spec.ts`**, so Stage 5's tab bar
  is checked against a list rather than against recollection. That test changes meaning
  in Stage 5 — deliberately, and it is why it exists.

New fixture: `SCRATCH_TUNES.mobileDrawerStatus` (tune 208), the drawer spec's own row,
so it can never race a parallel worker.

**Pre-existing failures, NOT introduced here** (verified by running the same specs on a
clean tree): 5 in `e2e/live/*` — Playwright's `webServer` starts Flask but not the
spec-024 streaming sidecar, so anything asserting live SSE fan-out cannot pass — plus 4
that fail on a clean tree for their own reasons: `profile.spec.ts` (My Sessions tab,
Tunes tab, the empty-session review sheet) and `my-tunes.spec.ts` (the preview form in
the add pane's footer). **Worth a look before Stage 2 touches those pages.**

#### Stage 1 — The three missing kit primitives, adopted by nobody

**What.** `frontend/src/lib/` gains:
- **`Row.svelte`** — lead / (title + subtitle) / trailing. **Flex, not grid**: the
  prototype's first cut used `grid-template-columns: auto 1fr auto` with
  `.lead:empty { display: none }`, and a hidden lead pushed the body into column 1 and
  the trailing chip into the stretchy column, so status chips sat beside the text instead
  of at the right margin. Flex with `margin-left: auto` on the trailing element has no
  such failure mode. Worth pinning in a test.
- **`Toolbar.svelte`** — one line: `SearchField` + optional filter / sort / add buttons,
  with the **filter panel expanding beneath it** (a notch pointing back at the button
  that opened it). Open/close is a class toggle on live nodes so both directions animate.
- **`SectionHeader.svelte`** — title + optional icon + optional "See all".

**Why here.** Pure addition; no page imports them yet. Vitest only.
**Done when.** Three components, their tests, and `lib/README.md` updated. Zero diff in
`static/` output for existing pages.

#### Stage 2 — Visual conformance, one page per commit

**What.** Adopt `Row` and `SectionHeader`; right-align trailing status; make the counts
in tab labels faint (`Tunes · 96` with the number muted) and **add a count to People,
which lacks one**; section icons.
**Why here.** No behaviour changes. Keep the legacy ids/classes per spec 035 so existing
selectors keep passing; each commit is independently revertible.
**Done when.** Per page: desktop + mobile e2e green, and a measurable deletion from
`my_tunes_mobile.css`.

#### Stage 3 — One toolbar everywhere

**What.** The session page's Tunes / Logs / People tabs each get a `Toolbar`: search on
every tab, a filter panel (tune type / complete-or-year / role), `+` on Tunes. My Tunes
gets the sort control **moved out of the page header and into the toolbar row**.
**Why here — and why this is the best value in the plan.** My Tunes *already ships this
pattern*: `filters-container` → `filter-panel-toggle` → `filter-panel` with a
`clear-filters-btn`, in `mytunespage/App.svelte` (~line 598ff). This stage generalizes
proven production code rather than inventing a pattern. It also kills the
filter-as-bottom-sheet idea the prototype briefly tried: **a control at the top of the
screen must not open a panel at the bottom of it**. (On iPhone a popover anchored to a
button adapts into a bottom sheet by default, so "popover" is not the escape hatch
either — inline expansion is the answer on both platforms.)
**Done when.** All four tab surfaces use one component; the bespoke filter markup in
`sessionpage/TunesTab.svelte` and the `.filter-*` block in `my_tunes_mobile.css` are
gone; mobile e2e green.

#### Stage 4 — Home becomes a Svelte page

**What.** `templates/home.html` → thin shell + `frontend/src/homepage/`, rendering
`build_home_payload` (already written, already the `/api/home` body). Content per B2.
**Why here.** Self-contained: one route, one serializer that exists, and the page is
currently simple Jinja. It must precede the tab bar — a tab bar whose first tab is the
old Home is a menu in a different place.
**Done when.** `/` and `GET /api/home` render from one payload; the festival strip works
at 400px; `test_home_continue_tagging_050.py` still passes.

#### Stage 5 — The tab bar, behind a flag

**What.** A bottom tab bar in `base.html` at <768px: Home / Sessions / Tunes / Me. Help,
Admin, Share and Log Out move into Me *first*; the hamburger stays alive until Me has
absorbed them, then dies.
**Why here, and why flagged.** This is the only stage that touches every page, and
`e2e/mobile/core.mobile.spec.ts` currently asserts "hamburger menu opens on mobile" —
that test changes meaning here, which is exactly why Stage 0 exists.
**Done when.** Flag on: four tabs, no hamburger, every hamburger destination reachable.
Flag off: today's behaviour, byte-identical. Both paths green in e2e.

#### Stage 6 — Push/pop slide transitions

**What.** `/sessions` → `/sessions/<path>` slides in from the right; Back slides it out.
**The honest caveat.** The prototype fakes this with a hash router and absolutely
positioned screens. The real app does a **server round trip** between those URLs, so the
prototype's mechanism does not port. The cheap answer is **cross-document View
Transitions** — `@view-transition { navigation: auto; }` plus a named transition on the
content area: Chrome and Safari animate it, Firefox ignores it, no SPA router, no
JS. If that degradation is unacceptable, **drop this stage** rather than reaching for a
client-side router; the slide is polish and a router is an architecture change that
spec 035 deliberately avoided ("No SPA, no client-side router").
**Done when.** The transition runs in Chrome/Safari, is absent and harmless in Firefox,
and no navigation behaviour changed.

#### Anytime — independent of the sequence

- **Toast diet (B4).** Trim success toasts to the cases where the effect is off-screen.
  In the prototype exactly one survives: adding a tune to My Tunes from a catalogue
  search result, because the change lands on a list you are not looking at. Low risk,
  many small call sites, blocks nothing.
- **Person page → sections (B3).** Six tabs behind a `<select>` become a profile screen
  with sections and "See all" drill-downs. Self-contained to one page; retires the one
  kit behaviour with no iOS counterpart.
- **Design tokens as data (B6).**

#### Already done — no work

The **tune drawer**. The prototype's sheet was built to look like today's drawer on
purpose (type pill · title · ×, "Log to …" when a session is live, notation first, then
My List / Details / History / Played With). It rises to ~94% height on a phone; that is
the only change, and it is a Sheet prop.

#### What the prototype does not cover

Decide these per page as the stages reach them; do not assume the prototype settled them:
admin (session admin, people admin, recordings, activity), the live logger itself,
attendance/check-in, the session-tune add's configure step (alias/setting/key), the
non-modal `.mt-add-pane`, bulk selection (spec 029), tune merge and copy-to, the
connection/offline indicator, the in-session badge, per-instrument status, My Tunes
pagination, the tunebook sync pane, and the auth/help pages.

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

1. ~~**Auth handshake + `me` + `app-config`** (A1, A8)~~ — **DONE 2026-09-21.**
2. ~~**ISO JSON provider + envelope + raw-beside-display audit** (A3, A4)~~ — **DONE.**
3. ~~**Native surface + OpenAPI + contract test** (A5), with A6 folded in~~ — **DONE.**
4. **The web reshaping (§B)** — now has its own stage-by-stage plan: **see §B8**. Its
   Stage 4 (Home) and Stage 5 (tab bar) are what item 4 of this list used to be.
5. **Fixture tests for the pure client logic** (B5) — can start any time, independent of
   §B8; must be done before the Swift logger. **This is the highest-leverage prep work
   in this document** and nothing blocks it.
6. **Universal Links + web handoff** (A7) when the app exists; **push** (A9) after.

Explicitly **not** recommended now: a global REST URL rename (035's call stands), rewriting
existing Svelte pages, or promoting/deleting the pill logger as a prerequisite (035 Step 6
is independent — the native client never sees it either way).
