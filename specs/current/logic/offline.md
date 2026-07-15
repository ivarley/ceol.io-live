# Offline Support

How the main app keeps working without a connection. This covers everything **except**
the live logger, which ships its own `/live/`-scoped worker and offline model (see
[Live Logging](live-logging.md), Feature 024). The two are independent by design: separate
service workers, separate op-queues, separate IndexedDB databases.

## Goal

If you've opened the app online at least once, the pages you care about — your tune list,
the sessions list, session pages, tune details with notation, global tune search — keep
working offline, and any changes you make (add a tune, change status, bump heard count) are
queued and replayed automatically when you reconnect. The design principle is **predictable,
not timing-dependent**: one bundle mirrors your data locally, rather than hoping the right
endpoint happened to be cached at the right moment.

## The pieces

### Tier 0 — App shell + navigations (`static/service-worker.js`)

Served from **`/sw.js`** (via a route in `app.py`) so its scope is the whole origin. It
controls every navigation except the live logger (`/live/*` has its own worker that wins by
scope specificity).

- **Network-first, cache fallback — except content-hash versioned assets, which are
  cache-first.** Flask stamps every `url_for('static', …)` URL with `?v=<sha1[:8]>` of the
  file's content (`app.py`, `@app.url_defaults`) and answers v-stamped requests with
  `Cache-Control: public, max-age=31536000, immutable`. Since the URL changes whenever the
  content changes, an exact-URL cache hit can never be a stale build — the same guarantee
  as filename fingerprinting without renaming build outputs — so both service workers serve
  v-stamped `/static/` requests **cache-first** (`cacheFirstVersioned`: exact match incl.
  query; on first fetch of a new version, superseded versions of the same path are pruned).
  This is the site-wide slow-network win: a warm page load waits only for the HTML
  document; all JS/CSS/images come from disk. Unversioned asset requests (and anything a
  page hardcodes) keep network-first — a fixed-name asset served cache-first could strand
  users on a stale build. Offline, both strategies fall back across the version boundary
  (`ignoreSearch`): any cached version of the file beats a broken page.
- **Per-user, version-scoped caches.** Page snapshots and API responses live in
  `ceol-io-pages-<VERSION>-<uid>` / `ceol-io-api-<VERSION>-<uid>`. Bumping `VERSION`
  invalidates stale snapshots on the next load; switching users prunes the other user's
  caches so a shared device can't leak personalized data.
- **Snapshot-on-visit.** Each successfully-fetched page is stored, so revisiting it offline
  renders. Offline navigations to a never-visited page fall back to the shared shell, then to
  the standalone **`/offline`** page (rather than a browser error).
- **Never touched:** `/api/live/*`, `/live/*`, `/logout`, and non-GET requests go straight to
  the network. `/admin` navigations still show the offline page when offline but are never
  snapshotted. The legacy word-processor editor is fetched live but never cached (the server
  marks its response `X-Offline-Exclude`; it is being deprecated and is intentionally out of
  offline support).
- **Two correctness rules** (both learned from breaking the logout e2e test): `handleNav`
  awaits a cache handle *before* firing the navigation fetch (so SW activation settles and
  Chromium doesn't drop the navigation's `Set-Cookie`), and activation stays instant —
  precache runs from a post-load `init` message, never in `install`'s `waitUntil`.

### Tier 1 — API responses

`GET /api/*` is network-first into the per-user API cache, so the AJAX-driven pages have
data offline. Online always returns fresh; offline returns the last response seen. On an
offline cache-miss the worker resolves a **503 JSON** (`{success:false, error:'offline'}`),
not a thrown error, so the page's own `.catch` handles it cleanly and the UI can fall back to
the bundle.

### The offline bundle — one predictable payload

- **`GET /api/offline/bundle`** (`api_person_tune_routes.py`) returns, for the current user:
  - `tunes`: their whole tunebook, each with incipit notation (`incipit_abc` /
    `incipit_image` / `setting_key`, joined from `tune_setting`) plus every field the
    tune-detail drawer renders offline: learn status, heard count, notes, `name_alias`,
    `setting_id`, `learned_date`, `person_tune_id`, `tune_name` + `name`,
    `tunebook_count` + `tunebook_count_cached_date`, `global_play_count`,
    `person_list_count`, `session_play_count`, `instruments`, `instrument_status`.
  - `popular`: the top ~100 catalog tunes (with incipit notation and the same
    tunebook/play/list-count stats) so tunes you don't own yet are searchable and
    viewable offline.
  Only *incipit* notation is bundled — full ABC/images stay online-only to bound the payload.
  **Parity rule**: a bundle `tunes` entry must carry every field the drawer's offline path
  (`offlinePayload` in `frontend/src/tunesheet/logic.js`) maps into the detail payload;
  drift guards in `tests/integration/test_tune_detail_payload.py` (key coverage + values)
  and `frontend/tests/tunesheet.test.js` (same rendered UI online vs offline) enforce it.
- **`window.CeolOffline`** (`static/js/offline_data.js`) mirrors the bundle into IndexedDB
  (`ceol-offline`, stores `tunes` / `popular` / `meta`) on each load (throttled ~5 min) and
  on reconnect. It exposes `getTune(id)`, `getTunes()`, and `searchTunes(q)` (your tunes
  first, then popular).
- **The UI falls back to it when a fetch fails** (the online path is unchanged):
  - Tune-detail drawer → `CeolOffline.getTune()` (renders incipit notation).
  - Global "Find a tune" (`frontend/src/tunesheet/FindTune.svelte`, opened via
    `hamburger_menu.js`) + the Add-to-My-Tunes pane's deep search
    (`offlineDeepSearch` in `frontend/src/client.js`, opted in via the pane's
    `offlineSearchFallback` config) → `CeolOffline.searchTunes()`.
  - Sessions list → the cached `/api/sessions/with-today-status` response.

### Tier 2 — Writes (op-queue)

`window.MyTunesOffline` (`static/js/mytunes_offline.js`) queues tune-list changes when a
write fails offline, keeps the optimistic UI, and replays on reconnect.

- Ops POST to **`/api/my-tunes/ops`**, which is idempotent server-side (`UNIQUE(person_id,
  tune_id)`), so replays are safe with no dedup table. Op types: `add`, `remove`,
  `set_status`, `set_heard`, `set_notes`, `set_instrument_status`.
- Heard count is sent as an **absolute** target, never a delta, so a replayed op can't
  double-count. Ops carry a **monotonic** timestamp so two changes in the same millisecond
  still replay in submit order.
- Queue lives in IndexedDB (`ceol-mytunes`). On drain it fires a `mytunes-synced` window
  event so open views drop their "pending" markers without a manual reload.
- **Pending UI:** the My Tunes list overlays queued ops onto the cached list — a queued add
  shows immediately with a `pending` badge (a synthetic `person_tune_id` of
  `pending-<tune_id>`); status/heard/notes edits show their new values. The tune drawer's
  offline render overlays the same queued ops so reopening a tune reflects an offline change.
- **Adding a tune offline** navigates to My Tunes and shows a non-blocking toast there
  ("…will sync when you are back online"), instead of a blocking `alert`.

### Connection indicator (`static/js/connection_status.js`)

A dot in the header, sharing one visual language with the live logger's own connection
dot (`App.svelte`, `.conn-*` in `frontend/src/app.css`): **orange** = offline (queued
changes waiting), **orange pulsing** = syncing/reconnecting, **green** = caught up / live.
The app-wide dot sits by the hamburger and hides when idle-online. The live logger's dot is
floated in the same spot (beside its shared hamburger) but only appears when a live stream
is actually in play — in **edit** mode, or in an open **view** when at least one other
person is connected and editing live (it's pointless on a solo read or a completed log).
Green here means *connectivity*, never "a session is on now" — that signal is the red
pulsing "Live" label (see [Active Sessions](active-sessions.md)). Connectivity is
detected by a heartbeat (`HEAD /sw.js`) and fetch-failures, **not** `navigator.onLine`
(which is unreliable — it reports false in headless automation and true on a real device that
is actually offline). Tapping the dot shows how long you've been offline (persisted across
page loads) and the pending-change count.

The live logger's dot is tappable too, with a richer popover (it has more independent
failure modes): status headline (connected / connecting / reconnecting / connection
trouble / offline), last stream activity, how long the stream has been down, and the
queued/saving edit counts. Whenever the stream isn't live it actively probes **both**
servers — the Flask app (`HEAD /sw.js`) and the streaming sidecar (`GET /health`,
`no-cors` so the missing CORS headers don't matter) — because they fail independently,
and names the one that's unreachable. The classic local-dev trap (page on `localhost`,
`STREAMING_BASE_URL` on `127.0.0.1` or vice versa: the sidecar responds but the
host-scoped login cookie never reaches it, so SSE 401s forever) is detected explicitly —
both hosts loopback but different — and called out with the fix; the loopback guard means
the hint can never misfire in production.

### Background warm-up (`static/js/prefetch.js`)

`window.CeolPrefetch` warms a small, fixed set of page shells + their assets (home, sessions,
my-tunes, each of the user's session pages) and re-syncs the bundle, a couple of
seconds after load and deduped to ~10 min. The list is fixed and predictable — not
endpoint-guessing. It's gated off under automation (`navigator.webdriver`) so it can't flood
the single-process test server.

### App-wide tune drawer (`templates/base.html`)

The hamburger **Find a tune** is on every page, so the unified tune-detail sheet (the Svelte
bundle `/static/tunesheet/sheet.js`, spec 035 Step 3, which renders its own
`#tune-detail-modal` container and installs `window.TuneDetailModal`) is loaded app-wide by
`base.html` via overridable Jinja blocks (`tune_detail_modal_css` / `tune_detail_modal`).
This means the drawer works offline everywhere without a fragile lazy-load. The entry is
idempotent (guards against double registration) and the container defaults to inline
`display:none` so a page's own `.modal-overlay` CSS can't reveal it. No page overrides the
blocks anymore — `common_tunes` (the last holdout with its own inline modal) now uses the
shared sheet too.

## Verification

E2e coverage lives in `e2e/app/offline.spec.ts` (run online once, go offline, then assert
each surface works without having visited it): My Tunes list + pending overlay, tune drawer
notation, global Find-a-tune → drawer, sessions list, an unvisited session page after
warm-up, the offline add-toast, and the offline-added-tune lifecycle (clickable, notation,
status persists across reopen).

## Key files

- `app.py` — `_static_version` / `_stamp_static_version` / `_immutable_versioned_static`:
  the content-hash `?v=` stamping + immutable caching for static assets.
- `static/service-worker.js` — the `/sw.js` worker (bump `VERSION` on a deploy that changes
  cached assets/snapshots).
- `api_person_tune_routes.py` — `get_offline_bundle` (`/api/offline/bundle`), `my_tunes_op`
  (`/api/my-tunes/ops`).
- `static/js/offline_data.js` — `window.CeolOffline` bundle mirror.
- `static/js/mytunes_offline.js` — `window.MyTunesOffline` write op-queue.
- `static/js/connection_status.js` — header connection/sync indicator.
- `static/js/prefetch.js` — background page/asset/bundle warm-up.
- `templates/base.html` — app-wide tune drawer + offline scripts; `templates/offline.html` —
  the standalone offline page.
