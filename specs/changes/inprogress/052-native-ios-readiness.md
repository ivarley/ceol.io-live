# 052: Native iOS Readiness — first-pass assessment

**Date:** 2026-09-21
**Status (2026-09-26):** the web side is ready for a first native version cut.
Section A (API / auth) **BUILT 2026-09-21**, and A6 finished 2026-09-26 when the web
bundles moved onto `/api/tunes/*` and the 21 alias rules were deleted. Section B (web UI
reshaping) **BUILT**: stages 0-6 of §B8, B3-B21, and the §B5 fixture files. What is left
is app work or waits for the app: the AASA Team ID and Universal-Link handling (A7),
push (A9), and the legacy error-envelope rewrite below. Section C unchanged; §D is
annotated with what is done.

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
sites are conformed at runtime, not rewritten; the AASA file needs the real Team ID;
Universal-Link handling in the app itself is app work. (The web bundles calling the old
search trees was on this list until 2026-09-26 — see A6.)

**Section B had a clickable prototype, and has a staged plan (2026-09-22).**
The prototype (`mockups/tabbar/`, served at `/mockups/tabbar/`) was the interaction
sketch for the reshaping — four tabs, session-centric Home, inline filters, the tune
sheet. It settled several questions the first draft of §B left open; those answers are
folded into B1–B4 below, which is why it has been deleted: the real thing is built and
a second, diverging answer to the same questions is a liability rather than a
reference. **§B8 is the stage-by-stage conversion plan.** Stages 0-5 of that plan are
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

**DONE 2026-09-26: the aliases are gone.** `client.js` builds `/api/tunes/*` URLs from a
`searchScope` (`{instance}` on the live screen, `{session: path}` on the add-to-session
pane, `{}` on the Add-to-My-Tunes pane) in place of `searchBase`; `TuneSheet` reads
setting images from `/api/tunes/settings/<id>/image`; the 21 rules and their handlers are
deleted, and the tests that called them call the one family. Two small behaviour changes
for the live screen, both on thesession-search: results now carry `on_list` (the alias
passed no person), and it shares the family's 30/min limit, which is per user once signed
in. The main service worker bypasses `/api/tunes/*?instance=` the way it already bypassed
`/api/live/*`, so the logger's searches still never land in the page-data cache. A web
page left open across the deploy calls a removed URL until it reloads — search fails
quietly (empty results), nothing is lost.

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

### B5. The live logger is the real port cost — prepare its logic, not its controls — **DONE 2026-09-26**

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

**Built.** A `<module>.fixtures.json` beside each of `logstate.js`, `fracindex.js`,
`offline.js`, `shared/abcquery.js`, `shared/segments.js`, and `tunesheet/namematch.js`
(which gained cases for its exported functions beside its calibration sets): 433 cases
over 41 functions, plus pinned constants. One deliberately dumb runner,
`frontend/tests/fixtures.test.js`, maps each case's named `input` onto the function's
`params` and compares the result as JSON — the same thing the Swift runner will do. A
guard test fails if an export has no cases and is not listed under `_not_fixtured` with
a reason, so a new export cannot skip the net. Convention written up in
`specs/current/ui/svelte-pages.md`. Each file's `_readme` lists what a port must match
exactly: UTF-16 code-unit string comparison, stable sorts, JS's whitespace set, NFD (not
NFKD), dice scores as exact doubles, absent-vs-null keys, ids that are int or `temp-…`.

The one refactor: `offline.js` split its pure cores out of the IndexedDB functions
(`queueOrder`, `normMatchQuery`, `matchCacheKey`, `matchCacheRows`) so they could be
fixtured; behaviour and write order unchanged.

**What the fixtures turned up, and what was done** (2026-09-26, each now a fixture case):
- `fracindex`: requests with no answer returned a key on the wrong side of `after` —
  `before >= after`, and an `after` that is `before` plus only `'0'`s (`(null,'0')` gave
  `'0V'`). JS fell back to append on the first where the Python raised. **Both now refuse
  both, in the same cases**; `validate_position` rejects a trailing `'0'`. Client code calls
  a new `optimisticBetween`, which falls back to append, so the logger never throws
  mid-gesture over a provisional key. Neither side ever mints a key ending in `'0'`, and
  none of the local seed's 835 positions does. **Not yet checked against production**:
  the Render connection was down; `SELECT count(*) FROM session_instance_tune WHERE
  order_position ~ '0$'` should be 0 there too.
- `mergeStable`: a server row without `in_session_tune` cleared the local value; it now
  keeps it (a server `false` still wins). A duplicated server-only tune is appended once.
- Two name normalizers disagreed: the offline match cache kept accents and folded fewer
  quotes. It now uses `normName` then `stripThe`, so offline "Sligo Maid" finds a cached
  "Sligo Maíd". Old cache entries are just never hit again; the next online lookup
  rewrites them (no IndexedDB version bump, which would also drop the op queue).
- `computeCursorSlots` / the logger: the open set's end seam vanished while its last
  tune was optimistic — for the whole time a queued offline tune waited. The end needs
  no anchor, so it now renders (and is a cursor slot) either way. The start seam keyed on
  a temp id is deliberate: `remapAnchors` resolves it on send.
- `remapAnchors` now remaps `record_ids` arrays too, dropping temp ids that never
  persisted and skipping the op if none are left.
- `formatClock`: no more `-0:00`, and it rounds the magnitude, so halves round away from
  zero on both sides, as Swift's `.rounded()` does.

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

**Committed 2026-09-26.** A 2025 `.gitignore` line (`design/*`) had kept both files out
of git, so the source existed on one disk only and a fresh checkout failed 17 of this
section's tests. `design/tokens.json` and `design/Tokens.swift` are now excepted from it.

### B7. Things that need no change

Desktop-only constructs (`desktop="dock"` sheets, the `.mt-add-pane` split pane, spec 028's
two-pane logger, hover states, ⌘Enter) simply don't port. The <768px paths are the spec
for iOS. The tune-detail drawer's payload-derived variants, the Seg/Chip/Dialog
conventions, and the id-keyed live-ops protocol port as-is.

### B9. Add-a-session becomes a sheet — **DONE 2026-09-24**

`/add-session` was the last screen still shaped like a document. It opened with a
36px two-line heading, an intro paragraph and a bulleted lesson in what the input
box accepts — and the input box accepts all three of those things already, because
`parseSessionInput` sorts a name from an ID from a URL without being told. Measured
on an iPhone 13 viewport (664px): the field started at **y=538**, and the "Next"
button rendered at 598–635 against a tab bar starting at 613. Eighty-one percent of
the first screen was preamble, and the primary action arrived half-hidden behind the
navigation.

The fix is not styling. Adding a session is **adding a row to the sessions list**, so
it is a sheet presented over that list: you are standing where the result appears,
and Cancel leaves the list exactly as it was. That is what the "+" in the sessions
toolbar does now.

**Shape.** Two stacked sheets, `frontend/src/addsession/`:

- `AddSessionSheet.svelte` — find it. A `SearchField` at the top, results as `Row`s
  (name, place, chevron; "Already added" as a trailing chip), and a permanent row at
  the foot for a session that is not on thesession.org. That escape hatch used to be
  a hyperlink inside a sentence, which made the only route for those sessions the
  least visible thing on the screen.
- `DetailsSheet.svelte` — review and commit. Grouped-table sections, label left and
  value right, presented `back="Back"` over stage 1 so a wrong pick costs one tap
  instead of a retyped query.

**Three rules this stage settled**, each with a test:

1. **Offer, do not guess.** Search runs as you type (450ms), and a pasted link
   resolves on its own because it is unambiguous. Bare digits do not: a pause while
   typing `1247` settles the debounce on `124`, and opening session 124 on that basis
   would be a wrong answer delivered confidently. Those become a row you tap.
2. **An error waits for you.** The old one cleared itself after five seconds — long
   enough to start reading and not long enough to finish.
3. **A hidden field cannot own an error.** Everything whose default is already right
   (web address, venue phone and website, first-met date, thesession link, type, the
   60-minute active window, the three people-tracking flags) folds behind Advanced —
   nine fields on the main path instead of twenty. So validation has to open Advanced
   when the thing you got wrong is inside it, or the message points at a control that
   is not on the screen.

**The URL stays.** `/add-session` → `/sessions?add=1` (carrying `?acu=false`, which
the admin sessions list uses to pre-uncheck "Add me as"). Help, the hamburger and the
admin list all link to it and people have it bookmarked. The sheet clears the query
parameter once it opens, so reloading after Cancel does not reopen what you dismissed.

**What went.** `templates/add_session.html`, `frontend/src/addsessionpage/`,
`vite.addsessionpage.config.js` — nine bundles are eight. `GET /api/add-session`
survives as the sheet's own payload, fetched on open rather than embedded in the
sessions-list payload: 44 timezone options on every `/sessions` load, to be read on
almost none of them. The create POST on the same rule stays login-gated.

Every field id is unchanged. The layout is a rewrite; the behaviour is not, and the
generated web address, the refused unusable paths and the refused tune URL are pinned
by the same assertions as before.

### B10. One accent was doing two jobs — **DONE 2026-09-24**

The green behind a selected filter or a tune-type chip was `--primary` (#65b464),
the same token used for link and icon text. White on it measures **2.54:1**, well
under AA, and it read exactly like the washed-out green a phone uses for the
messages it does not want you to like.

One token could not do both jobs, and the numbers say why:

| | white text on it | as text on `--bg-color` |
|---|---|---|
| `--primary` #65b464 | **2.54:1** ✗ | 6.85:1 ✓ |
| `--primary-fill` #4a8049 | **4.69:1** ✓ | 3.71:1 ✗ |

A colour light enough to read *as* text on a dark page is too light to sit *behind*
white text. So the accent splits:

- **`--primary`** — accent TEXT, links, icons, thin borders that stand alone.
- **`--primary-fill` #4a8049** — any surface carrying white text. It is the logo
  green exactly: `logo3-1.png` is one flat `#4a8049`, so a selected chip and the
  wordmark in the header are now the same colour.
- **`--primary-fill-hover` #437342** — 10% darker. Note `--primary-dark` (#3d863c)
  is *lighter* than the fill, so reusing it would have brightened on hover.

143 declarations moved: 105 backgrounds, 38 borders that outline one of those
backgrounds, and 3 `accent-color` (the browser draws a white tick on that fill, so
it is the same case). `color:` was left alone throughout — that is the other half
of the split.

The rule is enforced in `tests/unit/test_design_tokens_052.py`, which greps the
stylesheets rather than the token file, because the token file is not where this
gets broken. It was checked by breaking it: reverting one chip to `--primary` fails
the test and names the file and line.

### B11. Focus rings are for the keyboard — **DONE 2026-09-24**

Clicking almost anything drew a wide pale halo: Bootstrap's reboot has
`button:focus { outline: 5px auto -webkit-focus-ring-color }`, and `:focus`
includes mouse clicks. Measured on a clicked filter button: the element reports
`:focus-visible = false` and the ring paints anyway, 4px of `rgb(144,194,226)`.

`:focus-visible` is the distinction the browser already makes — keyboard arrival
yes, click no — so the ring moves onto it. **Removing rings outright was never an
option**; it would make the app unusable without a mouse. Both halves are tested.

Three sources, all fixed at origin rather than papered over:

1. Bootstrap's reboot. Now `button:focus:not(:focus-visible)`. The first cut used
   `button:focus { outline: none }`, which out-specifies a bare `:focus-visible`
   rule (0,1,1 beats 0,1,0) and silently took the keyboard ring with it.
2. The app's own "focus indicators for keyboard navigation" in
   `my_tunes_mobile.css` and `attendance.css` — the comments said keyboard, the
   selectors said `:focus`. They load after `theme.css` and tie on specificity, so
   a global override could not have reached them.
3. Two `rgba(0,123,255,.25)` focus glows left over from the blue accent, still
   glowing on click in `attendance.css` and `sessionadminpage/page.css`.

Then one ring, defined once at the end of `theme.css`: `2px solid var(--primary)`
with a 2px offset. `--primary`, not `--primary-fill` — it is a line on the page,
not a surface behind white text (§B10).

**The `<select>` exception.** Browsers deliberately match `:focus-visible` on a
*clicked* select, because arrow keys and type-ahead work the moment it has focus.
Defensible, and still a ring that appeared because you tapped something. CSS
cannot tell those apart, so `static/js/input_modality.js` records how focus last
arrived (`data-input-modality` on `<html>`) and the stylesheet defers to it. Keys
that do not move focus are ignored, or typing into a box you clicked would light
it up under your cursor. If the script never loads the attribute is absent, the
rule never matches, and selects ring on click as the browser intended.

`e2e/focus/focus-rings.spec.ts` covers all four: click draws nothing, Tab draws
the accent, a clicked select draws nothing, and the modality flips back on the
first Tab — that last one guards the real hazard, a latch that leaves a keyboard
user with no visible focus at all. Verified by reverting the reboot rule and
watching the first test fail.

### B12. The profile screen — **DONE 2026-09-24**

`/me` opened with `<h1>Profile: Ian Varley</h1>` — 36px of a 664px screen spent
telling you your own name, on the one page where you already know it, under a tab
bar that already says Me. Below it sat two Bootstrap cards with grey header bars,
and inside those, twenty facts as bold grey `Label:` stacked over a dimmer value.
The hierarchy was upside down: the word "Name" was brighter than your name. 1,619px
of scroll.

It is grouped tables now — label left, value right, so each row reads as a sentence
("Location  Austin, TX") — and **1,081px**, a third shorter with nothing removed
that anyone needed.

**What changed, and why each one:**

- **The heading became an identity header**: initials, name, and one quiet line of
  context (`@ian · Austin, TX, USA`), with Edit at the trailing edge. That is where
  iOS puts you at the top of Settings, and it puts Edit next to the thing it edits
  — the old button floated above the first card, anchored to nothing.
- **City / State / Country became one Location row.** Three rows were saying one
  thing.
- **Created, last login and active status moved behind a Details row** on `/me`.
  Nobody checks when they signed up. An admin looking at somebody else gets them
  outright: the same facts are evidence there and noise here.
- **Email verified only appears when it is a problem.** "✓ Verified" on every visit
  says nothing; "Not verified" is worth a row.
- **The duplicate Save/Cancel pair at the bottom of the page went.** They existed
  because the page was long; it is short now, and the header carries them.
- **Display and edit are the same rows.** Entering edit mode turns values into
  inputs in place rather than swapping in a differently-shaped form, so the screen
  you were reading is the screen you are editing.

**Two bugs found by measuring rather than looking:**

1. `.kit-group-head` rendered at 24px in the old docs grey — `.docs-article h3` is
   (0,1,1) and a bare class is (0,1,0). Fixed with the `:root` prefix that
   `specs/current/ui/theming.md` documents for exactly this.
2. `.tab-content` still drew a three-sided rounded box around the whole page: the
   panel that used to hang off the tab strip, which went in §B1. It had been
   framing nothing for a while, plus adding a second 16px gutter.

The row styles live in `frontend/src/lib/grouped.css`, shared rather than copied,
because this is the second screen to want them after the add-a-session sheet
(§B9). **Follow-up:** `DetailsSheet.svelte` still carries its own scoped copy of
the same rules. It should adopt the shared sheet, but it ships scoped styles that
would need re-verifying, and it is not what this change was for.

### B13. One logger, and two lists that match — **DONE 2026-09-24**

**The tune-logger preference is gone.** `beta_live_logging` let a signed-in user drop
back to the legacy pill editor; the live logger is the only logger now, so a setting
offering one option was a question with no answer. Removed: the profile row, the
`POST /api/users/<id>/beta-logging` endpoint and its route, the `User` attribute, the
`SELECT` column in `auth.py` (and the index shift after it — `hashed_password` moved
from 21 to 20), and the field in the person payload. The routing branch in
`session_instance_detail` is unconditional: everyone lands on the live screen, signed
out included, where it renders read-only.

Two things deliberately **not** done, because they are separable and larger than the
ask:

- The `user_account.beta_live_logging` **column stays.** Stop reading a column first,
  drop it once nothing deployed can still want it.
- The **legacy pill editor is now unreachable** —
  `templates/session_instance_detail.html` (~1,970 lines) plus the branch that rendered
  it. That deletion is spec 035 Step 6 and wants its own change.

**The two list pages match.** Sessions and Tunes sit one tap apart on the tab bar, so
anything that changes size between them reads as the page redrawing itself. Measured
and closed:

| | Tunes was | Sessions was | now |
|---|---|---|---|
| row height | 39px | 56px | 39px (padding 15px→8px, line-height 1.5→1.2) |
| name | 18px / 500 | 16px / 400 | 18px / 500 |
| right-hand meta | 12px | 12.8px | 12px |
| count line | 12px, 4px below | 14px, 8px below | 12px, 4px below |
| count text | "10 tunes" | "Showing 3 sessions in your list." | "3 sessions in your list" |

The toolbars were already identical (§B8 Stage 1) — this is the rest of the page
catching up with them.

**The grouped-table rules are shared.** `DetailsSheet.svelte` carried its own scoped
copy of the rules `/me` was using from `frontend/src/lib/grouped.css` — the follow-up
§B12 recorded. It imports the shared sheet now and is **182 lines shorter**, with the
`.as-*` names replaced by the `kit-*` ones. What stays local is the sheet's own
furniture: the recurrence editor, the generated web address, the buffer row, the
footer. `grouped.css` also grew one rule, `.kit-field > label`, so an editable row does
not have to name its own label column.

### B14. The tab bar reaches the logger; the session page needs no back — **DONE 2026-09-25**

**The rule.** A screen gets a back control only when the active tab does not already
land where back would go. One level below a tab root, the tab *is* back — and it is
already highlighted as active, which is exactly what "you are inside this section,
tap to return" looks like on a phone. So the session page gets nothing, and the `⮐`
that used to hang off the end of its `<h1>` is deleted: 0.6em, border-grey, aligned
to nothing, too small to hit, and a second worse way of saying what the tab bar
already says.

**The logger has the tab bar now, in view mode only.** It was the one phone screen
without one — not a decision, just the screen §B8 Stage 5 had not reached. The
original reason for caution was real: a bar pinned to the bottom would sit on the
composer. That is true while you are *writing* a log and false the rest of the time,
so the bar is there while you read one and hides while you write. Reading a log is an
ordinary screen of the app; logging one is the full-screen task it has always been.

- `live_logging.html` renders `tab_bar.html` and carries `has-tab-bar`, so the
  existing `body.has-tab-bar .hamburger-menu { display: none }` rule takes the
  hamburger off this screen too — the last phone surface that still had one for a
  signed-in user.
- `App.svelte` toggles `body.logging-edit` from `mode`, because the bar is rendered
  by the Jinja shell and lives outside the component.

**One bug, caught by a test rather than by looking.** The first cut reserved the
bar's height on `.sets`, the scroller. But the logger's `main` is a flex column, the
scroller is only its middle, and below it sits `.dock` holding "✎ Edit log" — which
stayed exactly where it was, under the bar, with the bar swallowing its taps. The
screen looked perfect and the button did nothing. The reservation belongs on the flex
column, which moves both. `e2e/mobile/tab-bar-logger.mobile.spec.ts` asserts the gap
is non-negative *and* clicks the button, because the geometry is only a proxy.

**Still open:** the logger is two levels below the Sessions tab, so tapping Sessions
skips the session it belongs to. It keeps its `⮐` for now. A proper back control
there is the remaining design decision, along with the signed-out case — a signed-out
visitor has no Me and no Tunes, so they still get the hamburger, on every page.

### B15. The logger's hidden drawer becomes a tray — **DONE 2026-09-25**

Tapping the logger's header band expanded a panel of details in place. Nothing said
the band was a control — it looks like a title — so the panel was a drawer nobody
could be expected to find, holding the date, the name, attendance, recordings, the
roster, notes and the complete/re-open switch.

It is a **drawer** now, sliding down from under the session band. Everything in it
already had the shape of a grouped table — label, value, an action on the right — so
it becomes one: the same `lib/grouped.css` rows as `/me` (§B12) and the
add-a-session sheet (§B9). Third consumer, no new row CSS.

A drawer rather than a modal Sheet, for two reasons. The header stays put — the ceol
bar and the session name both — so you never lose your place on the screen you are
standing on. And the Sheet version had a bug that made its own buttons look broken:
"Mark complete" opens a Dialog at the modal tier (1910) while the Sheet sat at the
sheet tier (2040), so the confirmation rendered BEHIND the panel. A plain drawer at
z-35 lets every dialog land on top of it. The chevron turns to point down.

**The band does not move.** The first cut hid the summary line while the drawer was
open, on the grounds that the drawer repeats the date. That shortened the band, which
walked the avatars, the help icon and the chevron down the screen on every open — a
header that jumps is more distracting than a date that appears twice. The summary
stays, and a test snapshots the icons' positions before and after and requires them
equal. (It has to wait for the log to load first: the band grows as the date line and
the avatars arrive, so an early snapshot measures loading-vs-loaded.)

**It slides out from behind the header; it does not unroll, and it does not pass
over.** Svelte's `slide` animates height, so the panel grew a row at a time. A
one-line custom transition moves it as a single piece — `translateY(-100%)` to `0`.

Getting it BEHIND the band is a z-index story worth writing down, because the obvious
fix does nothing. `.topnav` wraps the ceol bar and the session band in a stacking
context at **z-30**, so a z-index on `.topbar` is scoped inside that context and
cannot lift the band above anything outside it. The drawer had to go **under 30**
instead: it is z-25, which still covers the unlayered log and still sits far below
the recordings panel (91) and the dialog tier (1910+).

The test for this samples `elementFromPoint` at the band's centre six times DURING
the animation, because mid-slide is the only moment the two overlap — a settled
screenshot looks correct either way. Verified by putting the drawer back at z-35 and
watching it fail.

**The second stacking bug, which the first fix did not reach.** The recordings panel
still opened underneath. `main` carries an identity transform — `matrix(1,0,0,1,0,0)`,
not `none` — which is enough to make it a stacking context, so that panel's z-index
of 91 could never rise above a drawer sitting OUTSIDE `main` at z-35, however much
larger 91 is. The drawer is rendered inside `main` now. Worth remembering: an
identity transform is invisible and still changes what z-index means.

**Phone modals are cards, not screens.** The kit Sheet is full-screen below
768px, which overstates what is happening when the content is a label, a text box and
Save — and it buries the drawer you opened it from. `Sheet` gained `compact`: the
centred-card treatment the desktop sheet already had, at every width. The name and
date editors use it, and so does `PersonPicker` — attendance is a list you consult,
and taking the screen for it buries whatever you opened it from.

Two things about that rule. It is **phone-only** (`max-width: 767.98px`): above that
the existing desktop rules already give a card or a docked pane, and compact must not
override a deliberate `dock`. And it needs **both classes**
(`.kit-sheet.kit-sheet-compact`) — a single class ties with the base `inset: 0` and
loses on source order, which pinned the card to the top-left corner and then
translated it off screen.

**It is also where back-to-the-session finally belongs.** The logger sits two levels
under the Sessions tab, so the tab alone lands on the list; the last group in the
tray is the missing level. That replaces the `⮐` hanging off the end of the title —
0.7em, muted, aligned to nothing. Two taps for a rare action, in a place you can
find, beats one tap on a glyph you cannot.

**What went with it.** The old panel had to close itself the moment you touched
anything else, with exceptions for the date sheet portalling out of the header and
for an unsaved notes draft. Tapping the band closes it now, so all of that went; only
the connection popover still needs the outside-click handler.

**The drawer's top edge is measured, not guessed** — the band is taller when a log
carries its own name. It is measured in `toggleExpand`, BEFORE `expanded` flips: read
it afterwards and the first frame paints at `top: 0`, covering the very band it hangs
from and swallowing the tap that closes it again.

**Two layout problems, both found by measuring rather than looking:**

1. Every row carried a bordered action button, which cost ~90px of a 390px line — so
   the VALUE was what got truncated: "Still log…", "none uploade…". The actions are
   text now, like the ones on `/me`.
2. Label-left/value-right stops working when the value is a *list*. A five-name
   attendance list wrapped into a ragged ribbon in the leftover column. `grouped.css`
   gained `.kit-field-stack`: label and action on the first line, value across the
   full width beneath. Date uses it too — "Fri · Sep 25, 2026 · 8:00pm-11pm" does not
   fit beside an action, and the year is the first thing a truncation eats.

`e2e/mobile/tab-bar-logger.mobile.spec.ts` asserts no row in the tray is clipped at
phone width, by comparing `scrollWidth` to `clientWidth` across every label and value
— the check that would have caught both of the above before a screenshot did. It also
asserts the drawer's top equals the band's bottom, and that a dialog opened from
inside it is the element actually under your finger (`elementFromPoint`), because
"visible" was true of the broken version too.

That describe block runs **serially**. Every test in it drives the same live instance,
and the logger is genuinely multi-user: one browser entering edit mode joins the
roster and streams presence to the others, so a parallel sibling can be reading
"Logging: …" while this one changes it. In parallel they failed about half the time,
and the failure said nothing about the feature.

The unit tests moved with it: the Sheet portals to `document.body`, so assertions
that reached into the component's own tree had to reach into the document instead.
One of them caught a real slip — I had folded the attendance count into the label
("Attended 5"), and a test that reads labels expecting labels was right to object.

### B16. One chevron, drawn — **DONE 2026-09-25**

Everything that pointed somewhere was a typographic character: `›` and `‹` (single
angle QUOTATION marks), `▸ ▾` (geometric triangles), `←`. Punctuation makes a poor
icon. It inherits the font's metrics, so its stroke weight never matches the UI
around it; it sits on a text baseline instead of being optically centred; and it
renders differently per font and platform. The tune drawer's disclosure caret was a
**9px `▸`**, which is where that ends up.

`frontend/src/lib/Chevron.svelte` is the one arrow now: a single stroked path, 2px,
square box, matching the tab-bar icons. **19 call sites** converted across the kit
(`Sheet`'s back button, `PersonPicker`), the grouped rows (`/me`, add-a-session, the
logger drawer), the disclosures (Schedule, Advanced, Details, tune config,
SessionTuneAdd's Advanced), the four My Tunes dropdown carets, the steppers in
`TunePreview`, and the logger's date nudge.

Direction is a **class**, not an inline transform, so a caller can still rotate it
with its own CSS — and the CSS that used to carry `font-size`, `line-height` and a
rotation for each of these lost all three, because a drawn icon has no baseline to
fight and the component owns its own direction.

Two things worth remembering:

- **Svelte's scoped CSS does not reach a class passed into a child component.** The
  add-a-session sheet styled `.as-chev` in its own `<style>`, and the moment that
  class went onto a `<Chevron>` the rule was dead — the compiler said so. Those rows
  use the shared `.kit-chev` from `grouped.css` instead.
- A drawn chevron in a **square** box cannot change the size of its own rect when it
  rotates, which is what the logger's band needed: the glyph version nudged the help
  icon 6px every time the drawer opened.

**Deliberately not converted:** the `▸` on the logger's starter pill (`▸ Ian V`).
That is a play marker meaning "started this set", not navigation — a triangle is the
right semantic there, and it is not pretending to be a chevron.

**Still outstanding:** the four `← Back to X` links on legacy templates, one of them
`javascript:history.back()`, which breaks on a deep link. They are on pages the phone
IA has not reached yet.

### B17. The signed-out phone, and the last back link — **DONE 2026-09-25**

**Signed out gets a tab bar too.** Four tabs, once §B18 gave Tunes a public home:
Home · Sessions · Tunes · About. It began as three — it was signed-in only, for a reason that
held at the time: `/my-tunes` and `/me` both redirect to login, so a four-tab bar
would have been two tabs and two rejections. The answer was not to offer a tab that
apologises but to give it somewhere real to go. Either way it is what finally takes
the hamburger off phones entirely (`body.has-tab-bar` is now unconditional, so the existing
hide-the-hamburger rule covers every page).

`/about` is where the signed-out hamburger's list went: a sentence about what Ceol
is, "Log in or register", "How Ceol works", and a row pointing at thesession.org.
Signed in, the first row becomes your profile instead. Share needed no row — it has
been a header control since §B1. **Find-a-tune is not carried over**: it was never a
page, only an overlay, and the catalogue is thesession.org's, which the last row
links to directly.

`grouped.css` moved from `frontend/src/lib/` to `static/css/` and is linked by
`base.html` and the logger shell rather than imported by four components. /about is
three rows; it should not need a Svelte bundle to get the app's list shape. The
action-row rule (`a.kit-field > .kit-field-label` takes the full width) moved with
it, from the profile page's CSS where it had been stranded — which is why About's
labels wrapped to two lines on the first pass.

**The last `javascript:history.back()` is gone.** `/me/and/<id>` — tunes in common,
reached from a session's People tab — now takes `?from=<session path>` and renders a
row naming that session. A session PATH rather than a URL, so the only thing that can
come out of it is `/sessions/<a session that really exists>` and there is no redirect
to validate; an unknown or malformed origin simply yields no row. This matters
because the app is `display: standalone`: an installed visitor has no browser Back,
and a shared link has no history at all.

**Deleted:** `templates/user_sessions.html`, zero references anywhere.

**Left alone, with reasons:**
- `/sessions/<path>/players` is **orphaned** — its only inbound links are the dead
  pill editor and the admin test-links page. It dies with them in spec 035 Step 6.
- The `← Back to X` links in `session_bulk_import.html` and `session_admin_person.html`
  are admin, which is a desktop-first sub-app with breadcrumbs of its own.

One process note: the first cut of the back link 500'd, because `common_tunes.html`
already had an `extra_css` block and Jinja refuses a second. The route catches
`Exception` broadly and renders an error page, so the browser check reported "no back
row" rather than "this page is broken" — the failure looked like a feature not
working. Worth remembering that a broad except turns a crash into a wrong answer.

### B18. A public Tunes tab — **DONE 2026-09-25**

`/my-tunes` is your tunebook and needs an account, which is why the signed-out bar
started at three tabs. `/tunes` is the tradition's: **the 100 most common tunes by
thesession.org tunebook count**, with search over everything past them, and nothing
on it that would need a login — no add-to-my-tunes, no learn status. Tapping a row
opens the tune drawer, whose feed has been `@public_api` all along.

**It is a separate endpoint from the one that already existed**, and that is the
point. `/api/tunes/popular` is login-gated and *personalised*: it joins `person_tune`
to report which of the popular tunes are in YOUR tunebook, so My Tunes can cache them
for offline adding. This one answers a different question for a different audience,
so it is `/api/tunes/top` and returns four columns and no personal data. A test
asserts exactly those four keys, and that `/api/tunes/popular` still 401s.

Two things the build got wrong first, both worth recording:

- **The new handler was shadowed.** `get_popular_tunes` already existed in
  `api_person_tune_routes.py`, `app.py` imports both modules, and the later import
  won — so the "public" endpoint answered 401 and the URL map carried the rule twice.
  Same-named handlers across route modules fail silently like this.
- **Borrowing `my_tunes_mobile.css` did not work.** On a phone a tune row there is a
  three-column grid with a 20px learn-status column and `display: contents` on the
  meta — a shape built for a row this page does not have, and the count and type chip
  landed on top of the name. The page carries its own ~20 lines instead, matched to
  the other lists by measurement: 8px padding, 18px/500 name at line-height 1.2, 12px
  muted meta.

No new bundle: it is a list and a search box, so it is a Jinja page with the embed
that `GET /api/tunes/top` returns (spec 035's rule holds) and about 60 lines of
vanilla JS. The rows are real `<button>`s, so keyboard access needs no invented roles.

### B19. A page wider than the phone breaks the tab bar — **DONE 2026-09-25**

Reported as "the footer scrolls on admin > people". The footer was fine.

`/admin/people` came to **522px on a 390px screen**. A page wider than the device
makes the browser widen the LAYOUT viewport and zoom the whole thing out, and
`position: fixed` pins to that wider viewport — so the tab bar stops sitting on the
bottom edge and appears to scroll. The symptom and the cause were on opposite ends of
the page.

The culprit was the two `<select>` filters in the toolbar. A select's intrinsic width
is its longest option ("Site Users Only"), and **a flex item will not shrink below its
intrinsic width without `min-width: 0`** — so the row could not fit however much the
search box gave up. The mobile block even said "keep on same line", which is fine at
tablet width and impossible at 390 with five controls.

`e2e/mobile/no-horizontal-overflow.mobile.spec.ts` asserts `scrollWidth <=
clientWidth` across **every phone surface**, not just the one that broke — the check
is cheap and the failure mode is this indirect. Elements inside a deliberate
horizontal scroller (`.table-responsive`, the logger's `.sets`) are exempt, because a
data table on a phone has to scroll somehow. A scan of all 14 phone pages found this
was the only one.

Two things the fix taught, both by reverting halves of it:

- `flex-wrap` was **not** what fixed it — the `min-width: 0` on the selects was. The
  first version of the comment credited the wrap, and removing the wrap alone left
  the page fitting fine. The wrap earns its place only on narrower screens.
- The guard bites: restoring the original toolbar rules fails with
  "/admin/people is 522px wide on a 393px screen".

### B20. The public Tunes tab reaches thesession.org — **DONE 2026-09-25**

`/tunes` searched only Ceol's own catalogue, so a visitor looking for a tune we have
not imported got "no tunes match that name" about a tune that plainly exists. It can
reach past us now, on an explicit tap.

**One endpoint relaxed, not a new one.** `GET /api/tunes/thesession-search` was
`@api_login_required`; it is `@public_api` now. It already supported being called
unscoped — `_resolve_search_scope` returns `(None, "personal")` with no
`?session=`/`?instance=`, and the core takes `session_id=None, person_id=None` — so
signing out simply means the hits carry no `on_list` flag. Same "current_user is
personalisation only" shape as `get_sessions_with_today_status`.

**`/api/tunes/deep-search` stays gated.** It reports what is on YOUR list, which is
not a thing a visitor has.

**The UI is a button, not a keystroke.** That endpoint proxies an external site and
its own docstring says it runs on explicit user action only. So: local search stays
debounced-as-you-type against our own table, and a "Also search thesession.org"
control appears once you have typed something. Hits we already hold are dropped (they
are in the list above); hits we do not open on thesession.org in a new tab and say so
on the row, because there is no local tune for the drawer to show.

**Worth knowing: `page.route` does not see requests a service worker handles.** The
first cut of these tests stubbed both searches and silently hit the real
thesession.org anyway — slow, and the opposite of deterministic. The tests set
`serviceWorkers: "block"`, and that line is load-bearing rather than tidiness.

**Not done: rate limiting.** This is now the second public endpoint that proxies
thesession.org (`search_sessions_ajax`, which backs /add-session, has been one for a
while and carries its own "TODO tighten?"). There is no limiter in the app — only a
`429: "rate_limited"` code in `api_auth.py` with nothing raising it. Both endpoints
should get one; it is a single piece of work covering both rather than something to
bolt onto this change.

### B21. Notation for visitors, without becoming an open proxy — **DONE 2026-09-25**

Notation is not stored on a tune; it lives on a **cached setting** fetched from
thesession.org. A tune with none showed a drawer with no notation area — and for a
signed-out visitor, no way to ask for any, because
`POST /api/tunes/<id>/settings/cache` was `@api_login_required`. In the local seed
that is 66 of 216 tunes; in production it is rarer, but it is the first impression a
visitor gets when it happens.

**A shared in-app secret would not have worked**, and it is worth writing down why:
anything the browser can send, a reader of our own page source can send too. A
constant embedded in the app stops casual scripting and nothing else.

**What guards it instead is a per-tune, signed, expiring token** (`notation_token.py`):

- minted only by `GET /api/tunes/<id>/detail`, the drawer's own feed, and only when
  that tune has no cached notation and the viewer is signed out;
- signed with the app's `SECRET_KEY` (via `itsdangerous`, already a Flask dependency),
  so it cannot be forged or edited to name a different tune;
- valid for 15 minutes.

The property that matters is not secrecy — it is **cost**. A token unlocks one tune,
so back-filling a thousand tunes through Ceol means first making a thousand requests
to Ceol to collect a thousand tokens. That is exactly what calling thesession.org
directly would have cost, so the reason to use us as a proxy disappears. The signature
is only how that is enforced.

A signed-in caller needs no token; their session is their authority, and the payload
mints none for them — a second credential for the same permission is a second thing
to look after.

`tests/integration/test_notation_token_052.py` pins the bounds: a token works on its
own tune, is refused on any other, refused when tampered, refused when expired, and
refused when signed with another deployment's key. Those tests assert the mocked
thesession.org was never called, because "401" and "401 after fetching anyway" look
identical from outside.

**Still outstanding: rate limiting** (§B20). This removes the open-proxy *shape* from
three endpoints' worth of thesession.org access; it does not cap volume, and there is
still no limiter in the app.

**Also found, not fixed:** `/tunes?tune=<id>` opens the drawer but never fetches — the
deep link renders the shell and no request goes out. Clicking a row works. Worth a
look on its own.

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

Remaining on this page: **tab counts** — since built (`1f4b882`; the payload carries
`total_logs_count` and `total_people_count`, the latter null for a viewer who may not see
the roster, and both are in `native-surface.yaml`). Counts are NOT
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

#### Stage 6 — Push/pop slide transitions — **DONE 2026-09-26**

**Built as proposed, with a direction rule.** `static/css/page_transitions.css` opts
every `base.html` page into cross-document View Transitions below 768px when motion is
allowed; `static/js/page_transitions.js` decides in `pagereveal`. Direction comes from
the URL hierarchy, not history: a destination UNDER the current screen is a push (slides
in from the right), one ABOVE it is a pop, anything else is skipped — which makes a
tab-bar switch instant, as on iOS. The session page's tab suffix (`/tunes`, `/logs`,
`/people`) is stripped first, so a night opened from the Logs tab is still "under" its
session; Home (`/`) is a tab, not everyone's parent. The header and tab bar carry their
own `view-transition-name`, so only the page slides. Needs `navigation.activation` to
know where it came from (Chrome, Safari 26); without it the transition is skipped.
Verified in Google Chrome at phone width: push on entering a session, pop on Back, no
transition on a tab switch.

**Test caveat.** Playwright's bundled Chromium never paints the page on the far side of
a cross-document view transition — even two static pages with nothing but
`@view-transition` hang, while installed Chrome does not. So the mobile e2e project runs
with `reducedMotion: 'reduce'` (which turns the transitions off), and
`e2e/mobile/page-transitions.mobile.spec.ts` runs in the installed Google Chrome and
skips where there is none. The direction rule itself is unit-tested in
`frontend/tests/pagetransitions.test.js`.

The original plan:


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
4. ~~**The web reshaping (§B)** — stage-by-stage plan in §B8~~ — **DONE**, stages 0-6.
5. ~~**Fixture tests for the pure client logic** (B5)~~ — **DONE 2026-09-26.**
6. **Universal Links + web handoff** (A7) when the app exists; **push** (A9) after.

Explicitly **not** recommended now: a global REST URL rename (035's call stands), rewriting
existing Svelte pages, or promoting/deleting the pill logger as a prerequisite (035 Step 6
is independent — the native client never sees it either way).
