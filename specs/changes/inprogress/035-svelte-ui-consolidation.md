# 035: Svelte UI Consolidation

**Date:** 2026-07-10
**Status:** Steps 1+2+3 BUILT (2026-07-11) — verified locally (pytest 787, vitest 253,
e2e 88/88 desktop+mobile); uncommitted, awaiting user verification. Step 3 scope note:
the tune-detail modal and the app-wide find-tune overlay are now Svelte
(`frontend/src/tunesheet/`, behind the unchanged `window.TuneDetailModal` /
`window.FindTuneOverlay` contracts; legacy `tune_detail_modal.js` deleted).
`TuneSearchComponent.js` remains only on the legacy fallback add pages
(`my_tunes_add`, `session_tune_add`) and the quarantined pill page — it dies with
those pages rather than being consolidated.
**Step 4 also BUILT (2026-07-11):** `/sessions` (serializers.build_sessions_directory_payload
+ `frontend/src/sessionsdir/`) and `/sessions/<path>` (serializers.build_session_detail_payload,
new GET `/api/sessions/<path>/detail` aggregate endpoint with permission flags /
recurrence_readable / session-timezone today, `frontend/src/sessionpage/` — tunes tab with
selection+copy-to, logs tab with add-instance modal, people tab). The tuple-reshaping
hack is dead on both sides. Verified: pytest 787, vitest 284, e2e 88/88 desktop+mobile.
Step 5 (person details, session admin) not started.
**Related:** [024](../024-live-logging-architecture.md) — the in-repo reference implementation
we are extending. Read it first.

---

## Purpose

The app has three different ways of building a screen, and they all coexist:

1. **Jinja + Bootstrap 4.5** — pages rendered on the server (`templates/`).
2. **Vanilla JS** — hand-written browser code bolted on later (`static/js/`).
3. **Svelte 5** — the newest surface (`frontend/src/`, the live logger + add-tune panes).

Each generation reinvented the same primitives, so the same conceptual thing exists several
times over. This spec makes **Svelte the only way interactive UI gets built**, on top of one
component kit and one set of design tokens, with one Flask serializer defining every payload.

**North star:** the end state is the same shape a native app needs — a clean JSON API, a
named component set, and design tokens. A future native port becomes a translation of a
known component vocabulary, not a fresh design pass.

---

## The evidence (audit, 2026-07-10)

Audit of `templates/`, `static/js/`, `static/css/`, `frontend/src/`, `api_routes.py`,
`web_routes.py`.

### UI duplication
- **12+ modal/overlay implementations** across 4 CSS class families. "Slide a panel in from
  the right" is written **5 separate times** (`tune_detail_modal.css:930`,
  `session_instance_modal.css:355`, `my_tunes_mobile.css:1330`, `.mt-add-pane`, `.drawer`).
- **4 tab engines**, 3 different mobile fallbacks (dropdown `<select>` / stay-as-buttons /
  stay-as-links).
- **3–4 parallel tune-search UIs**, each re-implementing the thesession.org fallback,
  paste-a-URL import, and tune-type normalization.
- **6+ close-button conventions** (`.modal-close-btn`, `.modal-close`, `.close`,
  `.instance-modal-close-btn`, `.ft-close`); the "×" is typed as two different Unicode
  chars (U+00D7 and U+2715).
- **4 separate `@keyframes spin`** declarations.

### Already broken today (pre-existing — not caused by this work)
- `static/css/z-index-layers.css` documents a careful stacking scheme and **is loaded by
  zero templates**. Every overlay hardcodes its z-index anyway. `#find-tune-overlay` uses
  `3000`; the toast container uses `10000` — above the `9999` the dead scheme reserves as
  "always on top."
- CSS vars **referenced but defined nowhere**: `--text-muted`, `--primary-dark`,
  `--secondary-dark`, `--already-added-bg`, `--already-added-hover-bg`.
- `session_instance_modal.css` consumes `--modal-bg-secondary` / `--modal-text-muted` /
  `--modal-primary-dark`, defined **only** in `tune_detail_modal.css` — a hidden load-order
  dependency.
- `theme.css` defines both `--primary` and `--primary-color` with the same value; files use
  them interchangeably.
- `session_instance_detail.html:1778` loads `js/dist/sessionRecorder.js`, **which does not
  exist** (404, behind an admin guard).

### The data fork
`web_routes.py` ships **positional tuples** into Jinja; the API ships **dicts**; the browser
reshapes one into the other at runtime. `templates/session_detail.html:2628`:

```js
// Convert API format to match existing tuple format
const newTunes = data.tunes.map(t => [t.tune_id, t.tune_name, t.tune_type, ...]);
```

The comment is a confession. This is the single best justification for the serializer layer.

### API state
- **166 `/api/*` endpoints**; **51%** have an RPC verb in the URL; **31** handlers named
  `*_ajax`. **Four** different endpoints return "the list of sessions."
- **No serializer layer** outside live-logging. 435 inline `cursor.execute` calls in
  `api_routes.py` hand-building dicts.
- **Auth is three mechanisms deep.** 35 handlers use flask_login's `@login_required`, which
  **302-redirects to the HTML login page** instead of returning 401 — a native client would
  receive an HTML page. There is **no `request_loader`**, so the Bearer tokens minted by
  `/api/live/token` are invisible to Flask (only the streaming sidecar validates them).
- `api_login_required` is **defined twice**, byte-identically (`api_routes.py:50-61` and
  `api_person_tune_routes.py:46-56`, aliased to `person_tune_login_required` at `:84`).

### The cure already exists
`live_logging_routes.py` (spec 024) is the target pattern, in production: thin Flask shell →
one `_record_to_dict` serializer → one aggregate `/bootstrap` payload → Bearer token designed
for a future native client. **We extend this pattern; we do not invent it.**

---

## Decisions

Each was put to the user and confirmed.

1. **Flask keeps routing, login, and URLs.** Each page becomes a thin Flask shell that mounts
   a Svelte view. **No SPA, no client-side router, no SvelteKit.** Migrate page by page.
   *Rationale:* Flask already does routing/auth/shareable-URL SEO well; an SPA means
   re-solving all of it at once for no additional payoff toward the native goal.
2. **Interactive surfaces only.** `auth/*`, `help_*`, and plain admin tables **stay Jinja**.
   Converting a working login form is busywork and touches security-sensitive flows for
   nothing.
3. **Keep the current look.** Extract what's in `theme.css` + component CSS into one token
   set; rebuild components to match today's screen. *Rationale:* mixing a redesign into a
   plumbing rewrite destroys your ability to tell broken behavior from broken styling.
   Visual tweaks come later, against one clean component.
4. **Headless component library — Bits UI** — for behavior (focus trap, keyboard nav, a11y,
   click-outside, scroll-lock). It ships **unstyled**, so decision 3 is unaffected. It buys
   precisely what the audit found broken.
5. **Hybrid data flow.** One Flask serializer builds each payload. The JSON API endpoint
   **and** the page shell's embedded JSON blob both call it, so they **agree exactly on
   shape**. Instant paint, no loading flash, and the API stays the single contract a native
   app consumes.
6. **"Clean what we touch" on the API.** As each page migrates, bring its endpoints (reads
   and writes) up to standard. Untouched endpoints stay. A follow-up spec normalizes the rest.
7. **Don't touch the old pill logger.** Quarantine only (see below).

---

## Architecture: how a migrated page works

```
GET /my-tunes
  └─ Flask route (thin shell)
       ├─ calls serializer  →  the SAME dict the API returns
       ├─ renders shell template with  window.__PAGE_DATA__ = {{ payload | tojson }}
       └─ loads the Svelte bundle
            └─ mount(App, { target, props: { data: window.__PAGE_DATA__ } })
                 └─ subsequent reads/writes go to /api/*  (same shapes)
```

**The invariant:** the embedded blob and the API response are produced by **one function**.
If they can drift, the design is wrong.

**Reference to copy:** `templates/live_logging.html:16-22` (`window.__LIVE_CONFIG__` via
`| tojson`), `web_routes.py:4101-4144` (the thin shell route), `live_logging_routes.py:2196`
(`live_bootstrap`, the aggregate payload).

**Note:** `live_logging.html` deliberately does **not** extend `base.html` and is an
always-dark shell. Migrated pages **do** extend `base.html` (they need the header, hamburger,
theme toggle, toasts), so their bundles must be theme-aware.

---

## STEP 1 — Foundation

### 1a. Design tokens

Extend `static/css/theme.css` (which already owns the color tokens — **not** `base.html`;
`specs/current/ui/theming.md:17` is wrong about this and should be corrected).

**Fix what exists:**
- Collapse `--primary` / `--primary-color` (both `#00a1e0` light / `#4da6ff` dark) into one
  name. Keep `--primary`; alias or sweep the other.
- **Define or delete** the phantom vars: `--text-muted`, `--primary-dark`, `--secondary-dark`,
  `--already-added-bg`, `--already-added-hover-bg`.
- Move `--modal-bg-secondary`, `--modal-text-muted`, `--modal-primary-dark` out of
  `tune_detail_modal.css:9-19` into `theme.css`, killing the load-order dependency.

**Add the scales that don't exist** (none of these are tokenized today):

| Group | Today | Target |
|---|---|---|
| **Radius** | 4 / 6 / 8 / 12 / 14px scattered | `--r-sm: 4px`, `--r: 8px`, `--r-lg: 12px`, `--r-pill: 999px` |
| **Shadow** | ~7 distinct rgba literals | `--shadow-sm` (dropdowns), `--shadow-md` (cards), `--shadow-lg` (modals/sheets) |
| **Scrim** | `rgba(0,0,0,.5)` re-declared 4× | `--scrim: rgba(0,0,0,.5)` |
| **Spacing** | raw px/rem everywhere | 4px-based scale: `--sp-1`…`--sp-8` |
| **Motion** | 0.1 / 0.12 / 0.15 / 0.2 / 0.3s | `--dur-quick: .15s`, `--dur: .25s`, `--ease: ease-out` |
| **Z-index** | file exists, **never loaded** | **Load `z-index-layers.css`** (or fold into `theme.css`) and actually use the vars. Retire the `3000` and `10000` outliers. |
| **Breakpoint** | 768 / 767.98 / 900 / 480 / 374 / 1024 / 1025 | **One device breakpoint: 768px.** The logger's **900px is a separate, intentional _content_ breakpoint** for two-pane — document it as such, don't collapse it. |

One `@keyframes spin`, replacing the 4 that exist.

### 1b. Component kit

`frontend/src/lib/` — the shared kit, consumed by every migrated page.

| Component | Bits UI primitive | Replaces |
|---|---|---|
| **Sheet** | `Dialog` (styled as sheet) | tune-detail modal, session-instance modal, add-tune pane, `.deep-modal`, `.mt-add-pane`, attendance drawer |
| **Dialog** | `AlertDialog` | native `confirm()`, `.reconcile`, `.assign-modal`, inline delete-confirms |
| **Popover** | `Popover` / `DropdownMenu` | hamburger dropdown, in-session popup, connection popup, context menu |
| **Toast** | (thin wrapper over existing `window.showMessage`) | `.message`, ephemeral Bootstrap alerts |
| **Card** | — | `.home-card`, Bootstrap `.card` |
| **Chip** | — | tune pills, `.badge-*`, filter pills, instrument badges |
| **Tabs** | `Tabs` | Bootstrap tabs, `data-tab` tabs, URL-nav tabs |
| **List** | — | `.deep-results`, `ul.results` (vertical, ↑/↓ + Enter) |
| **Pager** | — | TunePreview result + setting pagers (horizontal `‹ ›`, "N of M") |
| **SearchField** | — | `TuneSearch.svelte`, `TuneSearchComponent.js`, find-tune overlay, `#tune-search-modal` |

**Rules:**
- **Decisions are Dialogs; everything else is a Sheet.** Sheet-vs-Dialog is about content, not
  screen size. A Sheet holds a task or scrollable detail and may have its own header/tabs/
  footer. A Dialog holds one decision and never scrolls.
- **Sheet responsive rule:** full-screen on mobile (<768px); centered dialog or docked
  right-pane on desktop. One component, one prop — not three implementations.
- **Tabs responsive rule:** desktop tabs, mobile `<select>`. (This already exists in
  `person_details.html` and `admin_tabs.html` — promote it to *the* rule.)
- **Dismiss conventions:** commit a Sheet = **"Done"** (top-right). Abandon = **"Cancel"**
  (top-left) or scrim-tap. Back within a Sheet = **`‹ Destination`**. Destructive = explicit
  verb (**"Delete session"**), never "OK". One `×` glyph (**U+00D7**), one class.
- **Nav paradigm:** browse as a **List** (↑/↓, no "N of M"); inspect as a **Pager**
  (`‹ ›`, "N of M"). This is a rule, not an accident of which component you land in.

**CSS constraint (important).** The live logger's `app.css` **locks body scroll and hardcodes
the dark palette** — that is exactly why `vite.mytunes.config.js` exists as a separate bundle
(see its comment). **The shared kit's CSS must be theme-aware and scroll-neutral**, or it
cannot be shared. Scroll-locking is a Sheet's job while open, not a stylesheet's job globally.

### 1c. Build setup

- **Bump `svelte` `^5.0.0` → `^5.33.0`** (`bits-ui` 2.18.1 peer-requires it).
- `npm i bits-ui` (+ peer `@internationalized/date`).
- Current build: two Vite configs in lib mode, no-hash filenames —
  `vite.config.js` → `static/live/{app.js,app.css}`, `vite.mytunes.config.js` →
  `static/mytunes/{add.js,add.css}`. Add a **third entry for the My Tunes page view**
  following the same pattern; the shared kit is imported by each entry (Vite dedupes within a
  bundle, and the bundles are page-scoped so cross-bundle duplication is acceptable and small).
- Vitest already configured (`vitest.config.js`) — the kit gets unit tests.

### 1d. Serializer layer

Copy the **shape** of `live_logging_routes.py`, but **fix its two real flaws**:

**The reference (verbatim, `live_logging_routes.py:113-145`):** a single `_RECORD_COLS`
column-order constant, a `_RECORD_FROM` join fragment, and a pure `_record_to_dict(row)`
mapper. One place defines the wire format; every endpoint funnels through it (`_reselect`,
`_handle_remove_tune`, `live_bootstrap`).

**Flaw 1 — positional coupling.** `_record_to_dict` reads `row[0]`…`row[19]`, coupled to the
`_RECORD_COLS` string order. The file already carries defensive comments about it
(`live_logging_routes.py:729`: `pos = rec[3]  # order_position (index 3 in _RECORD_COLS)`;
`:2221`). **Do not inherit this.** Use `psycopg2.extras.RealDictCursor` (or `NamedTupleCursor`)
so serializers read by name.

**Flaw 2 — impure serializer.** `_build_person_tune_response`
(`api_person_tune_routes.py:119`) **opens its own DB connection inside the serializer** and
would N+1 if called in a loop. **Serializers must be pure: `(row) -> dict`, no connection.**
Take a cursor only in the *loader* (`_reselect(cur, id)`), never in the mapper.

**The My-Tunes-specific fork to kill.** `_build_person_tune_response` is used by the
**detail** endpoints (`get_person_tune_detail`, `update_person_tune`, `add_my_tune`). The
**list** endpoint `get_my_tunes` uses **neither it nor `PersonTune.to_dict()`** — its `tunes[]`
comes from `person_tune_service.get_person_tunes_with_details()`, which hand-builds dicts on a
totally separate path. **"A tune in my list" and "a tune in the detail modal" are different
shapes produced by different code.** Unifying these is the concrete payoff of Step 2.

### 1e. Global auth fixes

Cheap, and native needs them.

1. **Swap the 35 wrong decorators.** These `api_routes.py` handlers use flask_login's
   `@login_required` (302 → HTML login) and must use `@api_login_required` (401 JSON):

   `update_session_ajax` (1043), `refresh_tunebook_count_ajax` (1253),
   `cache_tune_setting_ajax` (1346), `get_tune_incipit` (1549),
   `update_session_tune_details` (1859), `delete_session_tune` (2030), `add_session_tune`
   (2111), `add_session_tune_alias` (2319), `delete_session_tune_alias` (2422),
   `add_session_instance_ajax` (2483), `get_next_session_instance_suggestion_ajax` (2580),
   `update_session_instance_ajax` (2725), `delete_session_instance_ajax` (2880),
   `mark_session_log_complete_ajax` (3002), `mark_session_log_incomplete_ajax` (3078),
   `add_session_ajax` (3351), `add_tune_ajax` (3473), `delete_tune_ajax` (3653),
   `link_tune_ajax` (3804), `move_set_ajax` (4631), `move_tune_ajax` (4819),
   `add_tunes_to_set_ajax` (4989), `edit_tune_ajax` (5063), `admin_verify_email` (5986),
   `toggle_person_active` (6053), `update_session_player_regular_status` (6805),
   `update_session_player_admin_status` (6872), `update_session_player_details` (6939),
   `delete_session_player` (7076), `leave_session_membership` (7215), `terminate_session`
   (7267), `reactivate_session` (7327), `update_session_instance_tune_details` (11468),
   `run_cache_settings` (11888), `get_cache_settings_stats` (12006).

   *(Line numbers are the decorator line, as of this audit.)* Five of these
   (`update_session_player_*`, `delete_session_player`, `leave_session_membership`) **also**
   carry an inline `is_authenticated` check that is dead code — the decorator fires first.
   Remove the dead branch while you're there.

   **Do NOT change** `@login_required` on HTML page routes in `web_routes.py` — a 302 to login
   is correct there (e.g. `live_logging_screen`, `web_routes.py:4101`).

2. **Add a `request_loader`** to `app.py` so `Authorization: Bearer <user_session id>` works
   against `/api/*`. The token minting already exists (`live_logging_routes.py:2178`,
   `live_issue_token` → `auth.create_session()`); the streaming sidecar already validates it
   (`streaming/service.py:128-150`, cookie-first / bearer-fallback). Flask registers only a
   `user_loader` (`app.py:96-104`) — the one missing piece is the request_loader. Mirror the
   sidecar's validation (`SELECT user_id FROM user_session WHERE session_id = $1 AND
   expires_at > NOW()`).

3. **De-duplicate `api_login_required`** — one definition, imported by both
   `api_routes.py` and `api_person_tune_routes.py`.

### 1f. Quarantine the old pill logger

**We change nothing about how it works.** `templates/session_instance_detail.html` is the
**only** pill-editor template, it's never `include`d or extended, and `base.html` loads **zero**
pill assets — so deleting it later needs no base-layout change.

The risk is purely collateral: these live *next to* the pill code and would die in a naive
`delete static/js/dist/*` sweep, while kept pages still need them.

| Asset | Still needed by |
|---|---|
| `dist/modalManager.js` | `person_details`, `add_session`, `session_admin`, `session_detail`, `admin_people` — **biggest trap** |
| `components/TuneSearchComponent.js` + `css/tune-search.css` | `my_tunes_add`, `session_tune_add` |
| `tune_detail_modal.js` + `.css` | app-wide via `base.html:779` — **and the new Svelte logger calls `window.TuneDetailModal.show()`** (`frontend/src/App.svelte:1438`) |
| `dist/attendance.js` + `css/attendance.css` | `session_instance_players` |

**Action:** move `modalManager.js` and `attendance.js` **out of `static/js/dist/`** into a
clearly-kept location, so `dist/` contains *only* pill-logger code and can be deleted wholesale.
Update the `<script src>` tags in the 5 + 1 templates listed above. **No behavior change.**

**Safe to delete with the logger (later):** the 12 pill modules (`autoSave`, `stateManager`,
`cursorManager`, `pillRenderer`, `pillSelection`, `pillInteraction`, `dragDrop`, `textInput`,
`keyboardHandler`, `undoRedoManager`, `clipboardManager`, `contextMenu`) +
`pages/session_instance_detail.js` + their `src/ts/components/*.ts` sources — **but NOT**
`src/ts/components/modalManager.ts` and **NOT** `src/ts/attendance.ts`.

**Also dead in that template (can go anytime):** `css/attendance.css` at
`session_instance_detail.html:1384` (no attendance markup on the page at all) and the phantom
`js/dist/sessionRecorder.js` at `:1778` (file doesn't exist).

---

## STEP 2 — My Tunes migration

**Why first:** `web_routes.py:3746` is `@login_required def my_tunes(): return
render_template("my_tunes.html")` — **zero server context.** The page is already 100%
API-driven, and **all 18 `/api/my-tunes*` endpoints are already 401-clean** (they use
`@person_tune_login_required` / `@api_login_required`, never the broken flask_login one). So
this converts with **no backend auth work and no new endpoints** — a pure test of the kit and
tokens, with nothing else to blame.

### What must not break — behavior inventory

Every item below exists today and must survive.

**Load**
- Two-phase parallel fetch: `per_page=20` (fast paint) **and** `per_page=2000` (the real list);
  the 2000 always wins via a `fullTunesLoaded` guard (`my_tunes.html:1146-1239`).
  *In the new world the shell embeds the first payload, so phase 1 can become the embed.*
- Deep-link `?ptid=<person_tune_id>` opens the detail Sheet (polls ≤5s for the tune) (`:575`).
- `?show=<tune_id>` / `?added=<name>` / `?already` → scroll to card, position ~⅓ down, 3s
  yellow highlight fade, then strip the params via `replaceState` (`:644-729`).
- `sessionStorage` handoffs: `copyTunesMessage` (from `/me/and/<id>`), `myTunesToast` (from an
  offline add in the app-wide drawer).
- Listens for `mytunes-synced` → refetch (`:583`).

**Search / filter / sort**
- Search: 300ms debounce; client-side over `tune_name` **and** `notes`; **accent-insensitive**
  via `AccentUtils.includes`; **also matches a tune ID or a pasted thesession.org URL**
  (`:494-511`, `:1268-1281`).
- Status filter (All / Learned / Learning / Want To Learn), tune-type dropdown,
  **instrument dropdown (only rendered when the user plays ≥2 instruments)**.
- **Instrument filter dims rather than drops**: non-matching tunes go below a
  "Tunes on other instruments" heading, dimmed — they are *not* filtered out (`:1291-1312`).
- Active-filter pills with per-pill `×`, shown **only while the filter panel is collapsed**.
- **Primary + secondary sort**: choosing a new mode demotes the current one to secondary,
  keeping its direction (`:461-474`). Modes: alpha / popularity / plays / heard. Sort applied
  **both** server-side (`sort=` param) and client-side.
- The type badge on each card **changes meaning with sort mode** — it shows the numeric
  count (tunebook/heard/plays) instead of the tune type (`:1752-1759`).
- All of the above is mirrored into the URL via `replaceState` and restored on load
  (`:1063-1144`).

**Writes (all optimistic, all offline-queued)**
- Tap status badge to cycle: want to learn → learning → learned → want to learn (`:1656`).
- With an instrument filter active, the badge cycles **that instrument's** status and saves a
  per-instrument override; an *auto* instrument set back to the base status stores **no**
  override (snap-back) (`:1687-1717`).
- Heard count `+` with a `Heard count: N → N+1` toast; sent as an **absolute `set_heard`**,
  never a delta, so replays can't double-count (`:1868-1912`).

**Detail Sheet** — currently `window.TuneDetailModal.show({context:'my_tunes', ...})`
(`:1936-1975`). Provides: name-alias edit, roll-up segmented status + per-instrument blocks
with "View By Instrument" expand, heard ±, notes, "Configure This Tune" (setting_id/alias),
notation (incipit ⇄ full, dots ⇄ ABC, abctools launch), Stats/History/Played-With tabs, Remove.
**This is Step 3's job.** For Step 2, keep calling the existing global; convert it next.

**Add pane** — `window.MyTunesAddPane.open({query, instruments, onAdded, onAlready})`
(`frontend/src/mytunes/AddTuneApp.svelte:40-49`). Becomes a normal child component with
`instruments` as a prop and `onAdded`/`onAlready` as callback props (or a shared store the
pane writes to, dropping the `loadTunes()` refetch round-trip).
**⚠️ The same bundle also mounts `SessionTuneAddApp` on `#session-tune-add-root` for the
session-tunes page — do not break that when restructuring `mytunes/main.js`.**

**Offline (do not regress — `specs/current/logic/offline.md`)**
1. `overlayPendingOps()` (`:516-559`): merge queued ops onto the cached list; synthesize
   `person_tune_id = 'pending-<tune_id>'` rows for queued adds; filter out queued removes;
   mark `pending_sync` → render the `pending` badge.
2. **Loose `String(person_tune_id)` comparison** so a pending row is still clickable (`:1944`).
3. Every write goes through `window.MyTunesOffline.submit()`; optimistic UI is **kept** on
   `{queued:true}` (network failure) and **reverted only** on a server rejection.
4. `set_heard` absolute; `set_instrument_status` with `status:null` clears the override.
5. `CeolOffline.sync()` on load (`:572`).
6. `.catch(() => serverTunes)` fallbacks so a bundle/queue failure never blanks the page.
7. **E2E that must keep passing:** `e2e/app/offline.spec.ts` at `:67, :104, :150, :227, :270,
   :493, :537`.

**Op types accepted by `POST /api/my-tunes/ops`** (`api_person_tune_routes.py:883`, one op per
request, idempotent against `UNIQUE(person_id, tune_id)`, auto-remaps merged tune_ids):
`add`, `set_status`, `set_heard` (absolute), `set_notes`, `remove`, `set_instrument_status`.

**Globals this page depends on** (leave in place for Step 2; they get absorbed later):
`window.TuneDetailModal`, `window.TunebookStatus` (⚠️ has an ES-module twin at
`frontend/src/mylist.js` that **must stay in sync**), `window.AccentUtils`,
`window.showMessage`, `window.MyTunesOffline`, `window.CeolOffline`, `window.activeSession`.

### What to delete (dead code found in the audit)

Do not port any of this:
- **An entire second, unreachable legacy modal implementation** inside `my_tunes.html`:
  `displayTuneDetailModalBasic` (:1977), `displayTuneDetailModalFull` (:2071),
  `displayTuneDetailModal` (:2116), `saveModalChanges` (:2452), `removeTuneFromMyTunes` (:2603),
  `incrementHeardCountModal` (:2288), `decrementHeardCountModal` (:2349),
  `incrementHeardCountFromModal` (:2203), `onModalFieldChange` (:2412), `onSettingIdInput`
  (:277), `toggleNameAliasEdit` (:2244), `normalizeString` (:477). **Verified: no call sites.**
- `cycleStatusFilter()` (:1032) — targets `#status-filter-btn`, which doesn't exist.
- The `#status-filter-select` listener (:743) — no such element.
- **Swipe implementation #1** (`setupTuneCardSwipe()`, :758) — gated on
  `data-can-swipe="true"`, which `createTuneCard` never emits. **Inert.**
- **Swipe implementation #3** (`my_tunes_mobile.js:130-194`) — cosmetic ±10px nudge only.
  *(Keep the behavior of **#2**, `initializeSwipeListeners()` :1476 — the real swipe-right-to-
  increment-heard-count.)*
- `swipe-listener.min.js` (:2716) — loaded, never referenced.
- The card's `Key: …` line (:1797, :1818) — `/api/my-tunes` **never returns `tune_key`**, so it
  can never render.
- `my_tunes_mobile.js` search-clear button (:224-270) — injects into `.filter-group`, which
  doesn't exist. Pull-to-refresh in the same file is already disabled (early `return` at :26).

### Known bugs to fix in passing
- **Silent truncation:** the page requests `per_page=2000` and the server caps at 2000
  (`api_person_tune_routes.py:216`). A user with >2000 tunes is **silently truncated** — page 2
  is never requested. Either paginate properly or surface the cap.
- **No resize handler:** `createTuneCard()` emits **entirely different markup** based on
  `window.innerWidth <= 768` **at render time** (:1722-1827), and nothing re-renders on resize.
  Rotating a tablet across the breakpoint leaves the wrong markup. In Svelte this becomes a
  reactive `$derived` — the bug disappears for free.

### The free performance win
There is **no virtualization, no pagination, no lazy rendering**. `renderTunes()` (:1467)
builds one giant `innerHTML` string of **every** filtered card and assigns it — and **every
keystroke, status tap, and heard bump calls `applyFilters()` → a full re-render of the entire
list**. Typical users have 100–800 tunes; heavy users have thousands. A keyed `{#each}` (and a
virtual list if needed) makes this a non-issue. This is the most visible user-facing win of
Step 2.

---

## Later steps (not yet detailed)

3. **Tune-detail modal → one Svelte Sheet.** The keystone: app-wide via `base.html`, and it
   cuts the new logger's `window.TuneDetailModal.show()` back-reference to the oldest
   generation. Same pass folds the 3–4 tune-search implementations into one **SearchField**.
4. **Sessions list, then session detail.** Both need **new aggregate endpoints** — session
   detail's permission flags, `recurrence_readable`, and timezone math exist **only** in the
   Jinja context today (`web_routes.py:596-770`). This is where the tuple-reshaping hack dies.
5. **Person details, session admin.** Same shape, smaller. Person details also needs a new
   page payload (`web_routes.py:2974-3266`, 5 queries, no JSON equivalent).
6. **Delete the pill logger** + its 12 modules, once the beta logger is promoted.

---

## Follow-up (separate spec)

Normalize the **remaining ~130 API endpoints** not covered by "clean what we touch":
one response envelope, one error shape (today `get_session_tunes_grid_ajax` alone returns
**three** different error shapes: `api_routes.py:5391`, `:5411`, `:5424`), correct HTTP status
codes (several endpoints return errors with **HTTP 200** — `:1049`, `:1069`, `:1134`, `:1156`,
`:4025`, `:4069`), REST naming, and collapsing the **four** "list the sessions" endpoints into
one.

---

## Not doing

- No SPA, SvelteKit, or client-side router.
- No visual redesign.
- No rewrite of `auth/*`, `help_*`, or plain admin tables.
- No change to the old pill logger's behavior (quarantine only).
- No change to `@login_required` on HTML page routes (302-to-login is correct there).

---

## Acceptance criteria

**Step 1**
- [ ] `theme.css` owns radius/shadow/scrim/spacing/motion/z-index scales; `--primary-color`
      and the 5 phantom vars are gone; `--modal-*` vars moved out of `tune_detail_modal.css`.
- [ ] `z-index-layers.css` is actually loaded and referenced (no more `3000` / `10000`).
- [ ] `frontend/src/lib/` exports Sheet, Dialog, Popover, Toast, Card, Chip, Tabs, List,
      Pager, SearchField, with Vitest coverage. Kit CSS is theme-aware and scroll-neutral.
- [ ] `svelte@^5.33`, `bits-ui` installed; third Vite entry builds.
- [ ] All 35 auth decorators swapped; `request_loader` added and a Bearer token can call
      `/api/*`; `api_login_required` defined once.
- [ ] `modalManager.js` + `attendance.js` moved out of `static/js/dist/`; the 6 templates
      updated; **no behavior change** (`static/js/dist/` now contains only pill code).

**Step 2**
- [ ] `/my-tunes` renders from an embedded payload produced by **the same serializer** the API
      uses; no loading flash.
- [ ] Every behavior in the inventory above still works. Every dead-code item listed is gone.
- [ ] Offline: all 7 preservation rules hold; `e2e/app/offline.spec.ts` passes unchanged.
- [ ] Filtering/sorting a 1000-tune list no longer re-renders the whole DOM per keystroke.
- [ ] The list shape and the detail shape come from **one** serializer.
- [ ] `#session-tune-add-root` (session-tunes page) still works.
