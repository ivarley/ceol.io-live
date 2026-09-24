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
below, and **§B8 is the stage-by-stage conversion plan**. Stages 0-5 of that plan are
built: the kit primitives exist, the session page's three tabs are converted, Home is a
Svelte page rendering the same payload `GET /api/home` returns, and the phone navigation
is the four-tab bar rather than the hamburger.

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

### B3. Retire `Tabs mobileSelect` — **DONE 2026-09-23**

Person page and session admin collapsed 5+ tabs into a `<select>` on phones. There is no
iOS idiom for that, so a page navigated by one could not be ported, only redesigned.

**The `<select>` is gone from the kit entirely** — not switched off, deleted, along with
the `mobileSelect`, `selectId`, `selectClass` and `selectLabel` props. Too many tabs for
the width now **scroll sideways**, which both platforms do. The person page's six tabs
overflow 400px by ~140px and push.

One trap worth recording: the scroll rule disables **shrinking only** (`flex-shrink: 0`),
not the whole shorthand. `flex: 0 0 auto` would also cancel any grow a page had set, and
`.kit-tabs .kit-tab` outranks a page's own `.tab-button` — it flattened the session page's
three evenly-divided tabs on the first attempt.

**And then most of the person page went (2026-09-24).** The sections turned out to be
the same data wearing a different frame, so four of the five are gone and their jobs are
done where they belong:

| Was a section on /me | Is now |
| --- | --- |
| Sessions | `/sessions` already listed them. Its one unique control, **leaving a session**, moved to that session's own role sheet — where you are when you decide to leave |
| Attended | the Logs tab's **"Attended"** filter, offered only when signed in, on the session it is about |
| Tunebook | **My Tunes with an added-date range** in the filter panel, which is what it was |
| Logged | deleted |

Nothing was lost checking: granting somebody session-admin, the other control that
section carried, already lives on `/admin/sessions/<path>/people/<id>`.

**Share left too.** It gives a link and a QR for the page you are looking at, so parking
it on `/me` made it mean "share your profile" half the time. It is a header button now,
present on every screen, opening a sheet with the QR first (that is how you hand a link
to somebody across a table), then Copy link, then the system share sheet where one
exists. Its QR is fetched on open, not on page load, because the button is on every page.

What is left of /me is your profile and Admin / Help / Log Out — which is what a Me
screen is for.

**The earlier restructure (2026-09-23)**, after the tabs-plus-account-list
combination was called out as two menus on one screen. The tab strip is gone: `/me` is
your details, then a list of sections to open, then the account actions — every row the
same shape. Opening one is a drill-down with a back link, on the existing `?tab=` URLs,
so every link that already pointed at a section still lands there.

Rows buy something tabs could not: a line under each saying what is in it, phrased for
whose profile it is ("Sessions you belong to" / "Sessions they belong to").

**The panes stay MOUNTED**, shown and hidden as before. Rendering only the open one
inside an `{#if}` read better and quietly undid the lazy-load contract — leaving a
section destroyed its component, so returning refetched. The unit test that pins
"loads exactly once" caught it.

### B4. Toast diet — **DONE 2026-09-23**

`toast()` fired on most successful saves. iOS convention is that obvious success is
silent and only errors interrupt.

Of 23 success toasts, **7 are gone** — the ones where the change was already visible
where you were looking, or where the page moved on before you could read it:

| Removed | Because |
| --- | --- |
| "X added to session" | the refetch puts them in the list in front of you |
| "X archived. / restored." | the row leaves the filter you are on, or returns to it |
| "Heard count: 2 → 3" | said beside a card that had just changed from 2 to 3 |
| "Session instance deleted" | you confirmed it and the row is gone |
| add-instance success | the next line navigates to the instance it just made |
| profile activate/deactivate | a reload follows a second later and destroys the toast |
| "X has been created" (people admin) | the refetch updates the row you are looking at |

**The 16 that stay, and the line between them.** Anything whose effect is off-screen or
invisible: copy-to-another-session, people merged, verification email sent, live-logger
mode switched, the offline notices, and the landing toasts that explain a redirect you
did not ask for. Permission changes stay too — "X can now see this session's people"
reports something the screen does not show, unlike archiving, which is the list moving.

**Form saves stay, deliberately, against the letter of the rule.** Session details,
recurrence and cache settings all save and leave you sitting on the same form. There is
no row to update and no view to pop, so removing the toast leaves a Save button with no
feedback at all, which reads as broken rather than as quiet. On iOS these would confirm
by popping the view; until the web does something equivalent, the toast is doing real
work. Two component imports became dead and went with the calls.

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

### B6. Design tokens as data — **DONE 2026-09-23**

`design/tokens.json` is the source: 111 tokens in three groups (Bootstrap palette and
theme surfaces, the spec-035 scales, the z-order tiers), comments included.
`scripts/build_tokens.py` renders it into the `:root` block of `static/css/theme.css`
and into `design/Tokens.swift`. `make tokens` regenerates, `make tokens-check` fails if
they have drifted.

**Written back INTO theme.css between markers**, not emitted as a separate stylesheet.
theme.css is loaded by every template plus the live logger's own shell, so a new file
would have to be added to each of them in the right order; rewriting a marked region
changes nothing about how the CSS loads. The lift was verified value-for-value: 110
custom properties before, the same 110 after, none added, none changed.

**The check is a test, because this is the kind of drift nothing else notices.** A
colour that diverges between the two clients throws no error and fails no build — the
app just stops matching itself on a device nobody is looking at.
`tests/unit/test_design_tokens_052.py` regenerates and compares, and also pins that the
z-order tiers keep their relative order (a toast under a sheet is the sort of thing
found during a demo).

**Not everything crosses.** Font stacks, multi-part shadows and `rgba()` scrims have no
useful Swift form, and CSS breakpoints describe the web's responsive layout where iOS
has size classes — `--breakpoint-xs` is also literally `0`, which the first cut read as
a z-order and emitted as one. They are listed by name in the Swift file rather than
dropped silently, so nobody hunts for a token the generator quietly declined to emit.

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

**Config fix that came with this:** the `chromium` project had no `testIgnore`, so every
`*.mobile.spec.ts` ran under BOTH projects — 24 phone specs replayed at a desktop
viewport, where their assertions are meaningless or wrong (visual tabs vs the `<select>`,
"no sideways scroll at 400px" measured at 1280px, a filter panel laid out differently
above 768px). The four original smoke tests were loose enough to survive it, which is why
nobody noticed. `chromium` now carries `testIgnore: /\.mobile\.spec\.ts/`, so the suite
is 149 tests (123 desktop + 24 mobile + 2 setup) instead of 173 with 24 duplicated.

**Also fixed: the 9 pre-existing desktop failures** (confirmed pre-existing by running
them on a clean tree first). None were product bugs; all were tests that had drifted from
the app, plus one missing process. Worth recording because three of them would otherwise
have been re-diagnosed during Stage 2-3:

| Failure | Cause | Fix |
|---|---|---|
| `profile.spec.ts` ×2 | spec 034 renamed the tab **"My Sessions" → "Sessions"**, and the tunebook tab reads **"Tunebook"**, not "Tunes". Pane ids (`#sessions`, `#tunes`) never changed. | Update the expectations |
| `profile.spec.ts` ×1 | the add-session validation message no longer lists **Path** — it is generated from name + city (`SessionSheet.svelte`), so only Name/City/State/Country are required | Update the expectation |
| `my-tunes.spec.ts` ×1 | **the test raced its own debounce.** Opening the add pane fires an empty deep-search (browse mode, ~30 popular tunes), so a card with the tune's name can already be on screen when `fill()` returns: `toBeVisible()` passed against a *browse* result, the click opened a preview, and ~150ms later the debounced query search landed, replaced `deepResults`, and took the preview down with it — "element was detached from the DOM". Whether it failed depended on whether that tune happened to be in the browse list. | A `searchPane()` helper that waits for the response carrying the query. Also stubbed the thesession.org backfill so these tests stop making a live third-party call mid-assertion |
| `live-logger.spec.ts` ×4 | **instance 90's log is `log_complete_date` in the seed.** A complete log is read-only for everyone — the viewbar shows "✓ This session has been fully logged" where the edit affordance would be, and completion actively locks edit mode — so there is no "✎ Edit log" button on it at all, and four tests were clicking one. | Moved those four to **throwaway instances**, the pattern `live-logger-bulk.spec.ts` already used. Helpers extracted to `e2e/support/live.ts` and both specs now share them |
| `live-logger-bulk.spec.ts` ×1 | the SSE sidecar was not running: Playwright started Flask only | `playwright.config.ts` now starts **both** processes |

The sidecar one is worth spelling out, because the failure mode is not "no live
updates". An SSE connection the sidecar cannot authenticate is served **anonymously**,
and an anonymous payload has its people stripped — so records arrive with no `actor`,
the change lands correctly, and only the attribution toast is missing. A mismatched
`FLASK_SESSION_SECRET_KEY` between Flask and the sidecar produces exactly that, and it
reads as a UI bug. (I hit this myself while diagnosing: started the sidecar with the
wrong secret, saw the test still fail, and briefly concluded the sidecar was not the
cause.) Both processes read `.env`, which is what keeps them in step.

**One real product fragility surfaced and NOT fixed** (it is product code, outside this
stage): the add pane's preview footer can be torn out from under a tap. A late
`deepResults` replacement destroys the open preview, and a late settings backfill
re-renders the footer. A person can tap a status and have it swallowed. The test no
longer races it; the UI still can. Worth addressing when Stage 3 touches the add pane.

#### Stage 1 — The three missing kit primitives, adopted by nobody — **DONE 2026-09-22**

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

**Built.** `Row`, `Toolbar`, `SectionHeader` in `frontend/src/lib/`, exported from
`index.js`, documented in `lib/README.md`, and registered in the kit's export-surface
smoke test. 136 kit tests, 820 frontend tests, clean vite build. Nothing imports them.

Two notes for the stages that adopt them:

- **Testing Row's layout.** jsdom does not apply a component's scoped `<style>`, so
  `getComputedStyle` cannot see it. Structure (no empty lead element; trailing is the
  last child, with and without a lead) is asserted against the DOM; the two rules the
  component turns on — flex-not-grid, and `min-width: 0` on the body — are asserted
  against its own `<style>` block. Crude, but it pins the contract at unit speed, and
  the real-browser behaviour is already covered by Stage 0's no-sideways-scroll checks.
- **Toolbar deliberately owns only the chrome.** The host owns `open`, the filter state
  and the sort menu. That keeps the filter state where the page's URL sync and payload
  already live, and means adopting it in Stage 3 is a markup change, not a state
  rewrite.

#### Stage 2 — Visual conformance, one page per commit — **MOSTLY DONE 2026-09-22**

**Status.** All three session tabs render through `Row`: People and Tunes were verified
pixel-identical to the previous build at 400px and 1280px, and Logs was rebuilt as one
list (its three table layouts collapsed into rows under sticky group headers). **Not
done: the faint counts in the tab labels, and the count on People** — both need
`build_session_detail_payload` to carry logs and people counts, which it does not,
because those two tabs load their data lazily inside themselves.

**What.** Adopt `Row` and `SectionHeader`; right-align trailing status; make the counts
in tab labels faint (`Tunes · 96` with the number muted) and **add a count to People,
which lacks one**; section icons.
**Why here.** No behaviour changes. Keep the legacy ids/classes per spec 035 so existing
selectors keep passing; each commit is independently revertible.
**Done when.** Per page: desktop + mobile e2e green, and a measurable deletion from
`my_tunes_mobile.css`.

**First adoption: the session page's People tab (2026-09-22).** Picked as the least
risky surface on the page — 4 e2e references against the Tunes tab's 50, and no
selection-mode machinery (spec 029) to disturb. Verified **pixel-identical**: 0
differing pixels at 400px and at 1280px, same row heights (75 / 62) and the same 8px
trailing inset. The only DOM change is `div` → `button`, because a row that does
something should be a control.

Two things learned on first contact, both folded back into the kit:

- **Row needed a `body` snippet.** `.person-info` lays name / badges / instruments
  INLINE on desktop and stacked under 768px — a shape `title` + `subtitle` cannot
  express. Rather than flatten it (a redesign, not conformance), `body` hands the
  body's layout back to the page while Row keeps the three-slot frame. This is
  exactly what Stage 1's "adopted by nobody" was for: the gap surfaced before four
  pages had been built on the wrong shape.
- **`.person-row` was declaring the very grid Row exists to avoid** —
  `grid-template-columns: auto 1fr auto`. Harmless here (the person icon always
  renders, so the columns are always filled) but one conditional lead away from the
  bug. Deleted; the layout now comes from Row.

**Second: the Tunes tab (2026-09-22).** Also pixel-identical (0 differing pixels at
400px and 1280px, same row heights 41 / 49, same 8px meta inset), and selection mode
verified unchanged against the pre-change build: checkboxes tick, the row click still
opens the drawer, and the drawer does not leak through a checkbox press.

It forced a second addition to Row, `as`. This row carries its own checkbox, and
**interactive content inside a `<button>` is invalid HTML** — browsers disagree about
whether the inner control ever sees the click — so it must stay a div. That is a rule
rather than a preference, and it means the "a row that does something is a control"
default cannot be universal. Rows like this are no less accessible than before, but no
more either; giving them keyboard reach needs a real control INSIDE the row, which is a
redesign rather than a port.

`.tune-row` was another `auto`-shaped grid (`1fr auto`), saved only by both children
always rendering and by explicit `grid-column` assignments. Those are gone too.

**The Logs tab: taken deliberately as a VISUAL change (2026-09-22), not conformance.**
It was three near-identical render paths — a multi-year `<table>`, a compact
single-year `<ul>`, and a day-grouped `<table>` for festivals — differing only in what
labels a group and what leads a row. `view` already handed all three the same
`sortedKeys` / `byKey`, so they collapsed into ONE list with two ternaries.

The shape now: a flat list of `Row`s under a **sticky group header that stays tappable
to collapse**. A regular session leads each row with a date block (weekday over
day-of-month) and titles it with the log's own name or its date; a festival day names
itself in the header, so its rows carry no date block at all and lead with the room,
with the time in the subtitle. Both put time and tune count in the subtitle.

**Why not fully flat, as the mockup implied.** The seed's biggest session has 14 logs,
which would have made flat look fine and proved nothing. A weekly session five years
deep is ~260 logs and eight years is ~400: sticky headers tell you where you are, but
collapsing is what gets you to 2019. Kept as it was — in-memory only, so it resets on
reload.

**Two things found while doing it.** `.year-view-link` ("view N logs") had no handler
anywhere and its CSS set `opacity: 0; pointer-events: none`, revealed by a `.visible`
class nothing ever added: invisible and inert, so deleted rather than ported. And the
subtitle separator has to be `{' · '}` rather than literal whitespace, because Svelte
trims text at a block boundary and the two facts run together.

**Pinned chrome (2026-09-22).** The tab strip and the active tab's toolbar are now
sticky under the fixed site header; the session's title, address and schedule scroll
away. Pinning those too was asked for and measured first: the hero is 291px, which on
an 800px phone leaves 377px of list (~6 rows) against 668px (~11) with only the tabs
pinned. The mockup did not pin it either — only its app bar and tab bar were fixed.

`Add` moved from the current year's section header into the Logs toolbar, so it is
reachable from 2019 as easily as from this week.

Three things this cost, all worth recording:

- **`top: 0` is wrong on this site.** The site header is `position: fixed` at 42px, so
  anything sticking at 0 slides underneath and is never seen — which looks exactly
  like sticky being broken. `--site-header-h` now names it (theme.css).
- **The offsets are measured, not hard-coded** (`sessionpage/sticky.js` publishes each
  layer's height via ResizeObserver). A toolbar wraps at narrow widths and the Tunes
  filter panel grows every time it opens, so a magic number would be wrong within a
  day.
- **Only Logs publishes its toolbar height.** All three tabs stay MOUNTED across
  switches so their state survives, so three writers to one shared variable meant
  whichever hidden pane reported last won — and a hidden pane measures 0.

**One toolbar on all three tabs (2026-09-22).** Search, a `+`, and a filter button
whose panel expands beneath the line — the same controls, icons and skin everywhere.
Logged/All (Logs) and Members/Visitors/Archived (People) moved into their filter
panels: they are filters, and they were each taking a third of a phone's toolbar to
say so. The `?` help link is gone from all three; it was competing with the controls
for the narrowest row on the page.

The kit `Toolbar` grew four things to make this a port rather than a rewrite:

- **A pluggable `search` snippet.** Two of the three tabs need it — the Logs filter is
  a combobox whose dropdown positions against its own wrapper, and the Tunes field
  carries a tail of autocomplete/spellcheck attributes. Toolbar's job is the LINE and
  the panel; which control does the searching is the page's business.
- **Legacy hooks** (`filterId`, `panelId`, `addId`, `buttonClass`) so `#filter-panel`,
  `#filter-panel-toggle` and the `.filter-panel-toggle` skin survive untouched.
- **`addHref`**, because the session-tunes `+` is a real URL you can open in a new tab
  while the other two are actions.
- **The app's own filter glyph** as the default icon, so a converted toolbar is
  indistinguishable from the hand-rolled ones it replaced.

Deleted on the way: `panelAnim` and `toggleFilterPanel` (the Toolbar animates the panel
by toggling a class on live nodes, so the hand-rolled opening/closing classes and their
timers are dead), `.logs-add-btn`, and the `.help-icon` rules.

**One behaviour genuinely changed**, and a test had to say so: the panel now stays in
the DOM and collapses, where the old Tunes panel was conditionally rendered. That is
what lets CLOSING animate rather than just vanishing.

Remaining on this page: **tab counts**. Counts are NOT
free — `total_tunes_count` is in the payload but the logs and people counts load
lazily inside their own tabs, so a count on Tunes alone would be worse than none.
That needs `build_session_detail_payload` to carry all three, which is server work
and belongs with Stage 3 rather than a visual pass.

#### Stage 3 — One toolbar everywhere — **DONE 2026-09-22**

**Status.** The session page's three tabs share one `Toolbar`: search, a filter button
whose panel expands beneath the line, and `+`. The Logged/All and Members/Visitors/
Archived segmented controls moved into that panel, the help icons are gone, and Add moved
out of the Logs year header into the toolbar so it survives scrolling. The tabs and the
toolbar are pinned under the fixed site header, which needed `--site-header-h` and a
measured `--logs-toolbar-h` rather than magic numbers.

The three toolbars are verified identical at 400px and 1280px — position, size, font and
padding — by `e2e/support/toolbars.ts`, called from both the phone and desktop suites.
Getting there meant deleting two containers' leftover `display: flex`, a stray inline
`padding-left` on the Logs pane, 20px of pane padding on Tunes and People, and a second
skin on the People search box that set 14px where the shared class sets the 16px that
stops iOS zooming on focus.

**My Tunes is on it too now.** All four surfaces use one `Toolbar`. Converting it
deleted `panelOpen`, `panelAnim` and a pair of 300ms timers: the panel was inside an
`{#if}`, and a node that does not exist cannot animate out, so closing had to keep it
mounted for the length of the transition and then remove it. Toolbar toggles a class on
live nodes, so both directions animate for nothing. Two consequences worth knowing: the
panel now sits directly beneath the toolbar row rather than below the status segment,
which is the point of the component (it attaches to the button that opened it), and it
stays in the DOM when shut — four tests asserted its *absence* and now assert that it is
closed, which is what they always meant.

**The `.filter-*` block in `my_tunes_mobile.css` stays**, contrary to the "done when"
below. It is no longer this page's private skin: it is the shared one all four toolbars
wear via `styled={false}`. Deleting it would mean restyling the session tabs, which were
verified pixel-identical on adoption. One component with one skin is the outcome that
was wanted; the file it lives in is a rename, not a deletion, and not worth the churn.

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

#### Stage 4 — Home becomes a Svelte page — **DONE 2026-09-22**

**Status.** `templates/home.html` is a thin shell embedding `build_home_payload`, and
`frontend/src/homepage/` renders it in the prototype's order: Today, This week,
Learning, Pick up where you left off. The two in-progress cards became one section,
merged and sorted by last edit, because each holds at most three rows and two headings
above two single rows was most of what they were.

`_load_home_upcoming_sessions` gained what the Today card needs — `end_time`,
`location_name`, `is_active`, `tunes_logged`, `people_here` — as scalar subqueries, not
joins, for the reason spelled out in `tests/integration/test_home_today_052.py`. The
payload also carries `viewer.first_name` now; the greeting used to read `current_user`
in Jinja, and a native Home screen should not need `/api/me` to say hello. Both
additions are in `specs/api/native-surface.yaml`.

**Today is a subset of `upcoming_sessions`, not its own list.** A second list would be a
second chance to disagree about a night, and the disagreement would show as a card
saying one thing above a row saying another.

**The rules live in `frontend/src/homepage/logic.js`** — which nights are today, whether
one is live, what the tally says, what order the unfinished work comes back in — as pure
functions with 34 tests against payload fixtures. That is §B5's highest-leverage prep
work done for one screen: a SwiftUI Home has to make the same decisions, and this is what
makes "do the two agree?" a question you can answer.

**Seeded, because it could not otherwise be reached.** Two instances dated
`CURRENT_DATE`. The live one with the log and the people is **Downtown, not Mueller**:
the live logger suggests the next tune from the session's own history, so a set seeded at
Mueller gave the composer a suggestion it did not have, which opened its dropdown on an
empty input and turned ArrowUp into "move the highlight" rather than "leave the box" —
failing a keyboard test on an unrelated instance.

**Not done.** `test_home_continue_tagging_050.py` does NOT still pass unchanged, contrary
to the "done when" below: it read the rendered HTML for the card's heading and its
`/admin/recordings/<id>/segment` link, and the link is now built in the client from
`recording_id`. The seven rules it pins are unchanged and now asserted against the
payload instead. The old assertions were testing Jinja's ability to print JSON.

**What.** `templates/home.html` → thin shell + `frontend/src/homepage/`, rendering
`build_home_payload` (already written, already the `/api/home` body). Content per B2.
**Why here.** Self-contained: one route, one serializer that exists, and the page is
currently simple Jinja. It must precede the tab bar — a tab bar whose first tab is the
old Home is a menu in a different place.
**Done when.** `/` and `GET /api/home` render from one payload; the festival strip works
at 400px; `test_home_continue_tagging_050.py` still passes.

#### Stage 5 — The tab bar — **DONE 2026-09-22**

**Not behind a flag.** The plan called for one; the decision was to skip it and take a
`git revert` as the rollback instead. What the flag would have bought was a dual-path
e2e run; what it cost was a second code path through every page's navigation for as long
as it lived. The tests were rewritten to assert the new behaviour rather than both.

**Status.** `templates/tab_bar.html` + `static/css/tab_bar.css`, included from
`base.html` below 768px for signed-in users: Home, Sessions, Tunes, Me. Home wears the C
from the wordmark as a CSS **mask**, so one file greys with its neighbours at rest and
takes the accent when active rather than needing a second asset.

**Where the other five hamburger items went** — the whole safety argument, since nine
items had to fit four slots:

| Was in the menu | Is now |
| --- | --- |
| Me | its own tab |
| My Tunes | the Tunes tab |
| My Sessions | the Sessions tab |
| Admin, Help, Share, Log Out | the **Account section on `/me`** (`personpage/AccountSection.svelte`) |
| Add A Session | the **"+" on `/sessions`** |
| Find a tune | the Tunes tab's add pane, which runs the same deep catalogue search the overlay did |

Me absorbed its four FIRST, as the plan required: a destination in neither place is a
feature quietly deleted, and nothing else in the suite would have noticed.
`e2e/mobile/home.mobile.spec.ts` now walks to every one of them the way a person on a
phone would.

**The hamburger is hidden, not deleted.** It is still the navigation above 768px, and
still the navigation for signed-out visitors on a phone — they have no Me and no Tunes,
so a four-tab bar would be two tabs and two rejections. `e2e/app/navigation.spec.ts`
still checks the menu on desktop.

**Two details worth keeping.** The hide/reserve rules key off a `has-tab-bar` class that
`base.html` sets from the same condition the bar renders under, NOT off `:has(.tab-bar)`
— if `:has()` were ever unsupported that would fail *open*, showing both navigations at
once. And the live logger never gets a bar, because `live_logging.html` has its own
shell; a bar pinned to the bottom of that screen would sit on the composer.

**One thing it broke and fixed.** Adding "+" to the sessions toolbar left the search box
162px of a 360px row, about twelve characters. The Mine/All filter's padding gave the
room back.

**B1's catalogue search is built (2026-09-23).** On the All filter, typing on My Tunes
searches the whole catalogue and anything you do not already have appears below a
`Not on your list` divider; tapping a row opens the add pane for it. On a status filter
it does not appear, because there the question is "which of MY tunes match".

Two decisions worth keeping. "Not yours" is decided in the client against the list the
page already holds, not by passing `person_id` to `/api/tunes/search` — that endpoint
answers for whatever `person_id` it is given, and this page has no business asking about
anybody but its viewer. And it waits for the list to finish loading, because offering to
add a tune you already own, on the grounds that the page had not loaded it yet, is the
one wrong answer the section can give. Both rules are pure functions in
`mytunespage/logic.js` with tests, for the same reason as Home's.

"No tunes found" now reads "None of your tunes match" when the section has results, and
the empty state's Add Tune button steps aside: the rows below name the tunes and adding
one is a tap on the row it belongs to.

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
