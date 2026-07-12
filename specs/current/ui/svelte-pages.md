# Svelte Pages

How every interactive page is built (spec 035). Flask keeps routing, login, and
URLs; each page is a **thin Jinja shell** that embeds a serializer payload and
mounts a **page-scoped Svelte 5 bundle**. No SPA, no client-side router.

## The pattern

```
GET /my-tunes
  └─ Flask route (web_routes.py, thin shell)
       ├─ calls the serializer  →  the SAME dict the API returns
       ├─ renders the shell with  window.__PAGE_DATA__ = {{ payload | tojson }}
       └─ loads the page bundle (static/<page>/page.js)
            └─ main.js: mount(App, { target, props: { pageData: window.__PAGE_DATA__ } })
                 └─ subsequent reads/writes go to /api/*  (same shapes)
```

**The invariant:** the embedded blob and the API response come from **one
function** in `serializers.py`. If they can drift, the design is wrong.
First paint needs no fetch — no loading flash.

## Migrated pages

| Page | Shell template | Serializer (`serializers.py`) | Aggregate API | Bundle source | Output |
|---|---|---|---|---|---|
| `/my-tunes` | `my_tunes.html` | `build_my_tunes_payload` | `GET /api/my-tunes` | `frontend/src/mytunespage/` | `static/mytunespage/` |
| `/sessions` | `sessions.html` | `build_sessions_directory_payload` | `GET /api/sessions/with-today-status` | `frontend/src/sessionsdir/` | `static/sessionsdir/` |
| `/sessions/<path>` | `session_detail.html` | `build_session_detail_payload` | `GET /api/sessions/<path>/detail` | `frontend/src/sessionpage/` | `static/sessionpage/` |
| `/me`, `/admin/people/<id>` | `person_details.html` | `build_person_details_payload` | `GET /api/me/details`, `GET /api/admin/people/<id>/details` | `frontend/src/personpage/` | `static/personpage/` |
| `/admin/sessions/<path>` (+ tab wrappers) | `session_admin.html` | `build_session_admin_payload` | `GET /api/admin/sessions/<path>/admin-detail` | `frontend/src/sessionadminpage/` | `static/sessionadminpage/` |

Plus three non-page bundles:

- **`frontend/src/tunesheet/` → `static/tunesheet/sheet.js`** — the app-wide
  tune-detail sheet + "Find a tune" overlay, loaded on every page by
  `base.html` (`{% block tune_detail_modal %}`). Installs the legacy-compatible
  `window.TuneDetailModal` and `window.FindTuneOverlay` globals; idempotent
  (guards against double mount). The drawer **derives its own variant**: one
  payload endpoint — `GET /api/tunes/<id>/detail` (`?session=` / `&instance=`
  for the session/instance scope; `serializers.build_tune_detail_payload`, the
  same builder behind the legacy per-session GETs) — carries `viewer`
  (logged_in / is_admin / is_session_admin), the FULL `person_tune_status`
  core shape when on-list, and the scope block; the drawer maps those facts to
  its my-tunes / session / instance / admin / read-only variants. Call sites
  pass identity only: `show({ tuneId, scope?, ptid?, ...callbacks })`, scope
  defaulting from the URL (session pages imply their path, `/admin/tunes`
  implies admin). Old-style configs (context + apiEndpoint + additionalData,
  from the quarantined pill logger, `admin_tunes.html`, `common_tunes.html`)
  map through `normalizeShowConfig` unchanged. Offline, the drawer synthesizes
  the same payload from the cached bundle + op queue (`offlinePayload`).
- **`frontend/src/` (root) → `static/live/`** — the live logger (spec 024), the
  progenitor of this pattern. Its shell (`live_logging.html`) does *not* extend
  `base.html` and embeds `window.__LIVE_CONFIG__` instead.
- **`frontend/src/mytunes/` → `static/mytunes/add.js`** — the add-tune pane.
  Also compiled *into* the mytunespage bundle as a child component; the
  standalone build currently serves `session_detail.html`'s
  `#session-tune-add-root` and is being folded away.

## What stays Jinja

Non-interactive surfaces, deliberately (spec 035 decision 2): `auth/*`,
`help_*`, plain admin tables (`admin_people.html`, `admin_tunes.html`, …),
`home.html`, the legacy fallback add pages (`my_tunes_add.html`,
`session_tune_add.html` — the last users of `TuneSearchComponent.js`), the
attendance page (`session_instance_players.html`), and the **quarantined**
pill logger (`session_instance_detail.html` — dies in spec 035 Step 6, see
[Session Logging UI](session-logging.md)).

## Adding or changing a page — the checklist

1. **Serializer** — add `build_<page>_payload(conn, ...)` to `serializers.py`.
   Follow its module-docstring rules: mappers are **pure** `(row) -> dict`, no
   DB connection ever; rows are read **by name** via
   `psycopg2.extras.RealDictCursor`; loaders take a connection, open their own
   RealDictCursor, and batch (no N+1 in a loop).
2. **API endpoint** — a handler in `api_routes.py` that returns exactly the
   serializer output, registered via `app.add_url_rule` in `app.py`. Every
   `/api/*` handler must be explicitly classified: `@api_login_required`,
   `@api_admin_or_self_required`, an inline admin check — or `@public_api` if
   deliberately anonymous (see [AJAX Patterns](ajax.md)). Never flask_login's
   `@login_required` on an API route (it 302s to the HTML login page).
3. **Thin shell** — a template extending `base.html` whose content block is a
   `<script>window.__PAGE_DATA__ = {{ payload | tojson }};</script>`, a mount
   `<div id="<page>-root">`, and a `{% block extra_js %}` loading the bundle
   (`my_tunes.html` is the cleanest example). The web route in `web_routes.py`
   keeps `@login_required` (302-to-login is correct for HTML) and calls the
   **same** builder.
4. **Bundle** — `frontend/src/<page>/main.js` mounts `App.svelte` on the root
   div with `pageData` from `window.__PAGE_DATA__`; a
   `frontend/vite.<page>.config.js` (copy an existing one: lib mode, ES format,
   fixed `page.js` / `page.[ext]` filenames, `outDir: ../static/<page>`,
   `emptyOutDir`); add `dev:<page>` and append to the `build` script in
   `frontend/package.json`. Gitignore `static/<page>/` — Render's
   `buildCommand` (root webpack build + `cd frontend && npm run build`)
   rebuilds all bundles on deploy, so no `render.yaml` change is needed.
5. **CSS** — page styles belong in the bundle (Step 2 / `my_tunes.html` did
   this right); the Step 4–5 shells still carry `<style>` blocks, a known
   regression to clean up. Bundles under `base.html` must be theme-aware
   (`static/css/theme.css` vars) and scroll-neutral.
6. **Tests** — three layers, all expected:
   - **pytest** for the serializer/endpoint (auth matrix included — see
     `tests/integration/test_person_api_auth.py`).
   - **Vitest** component tests in `frontend/tests/<page>.app.test.js`,
     including a "first paint renders the embedded payload" case.
   - **Playwright e2e** in `e2e/` (see `e2e/README.md`) — which mostly means
     *not breaking* the existing specs.

## The DOM-contract discipline

Migrations keep the **legacy DOM ids/classes** (`#find-tune-overlay`/`.ft-*`,
`.tune-card`, the sessions grid, …) so the existing e2e selectors and page CSS
keep passing unchanged — the e2e suite is the regression harness proving a
port didn't change behavior. Vitest tests pin the contract explicitly (e.g.
`frontend/tests/mytunespage.app.test.js` "legacy DOM contract"). Change the
DOM only deliberately, updating e2e + CSS in the same commit.

## The component kit — `frontend/src/lib/`

The shared kit (spec 035 Step 1b): Sheet, Dialog, Popover, Card, Chip, Tabs,
List, Pager, SearchField, `toast()` — Bits UI primitives underneath for focus
trap / keyboard / a11y. Conventions live in `frontend/src/lib/README.md`;
the load-bearing ones:

- **Decisions are Dialogs; everything else is a Sheet.** Destructive confirms
  use an explicit verb, never "OK".
- Theme-aware, scroll-neutral CSS; `kit-` class prefix; one `×` glyph (U+00D7).
- Device breakpoint 768px, handled inside each component.

**Adoption status:** the visual-consolidation pass is DONE. `Dialog` + `toast`
replaced every native `confirm()`/`alert()` and copied `showMessage`; then one
component per round replaced its lookalikes, each keeping page skins via
class-passthrough props + `styled={false}`:

- **Tabs** — THE tab engine (personpage, sessionpage, sessionadminpage,
  tunesheet); value mode with `onValueChange` URL sync, or navigate mode.
- **SearchField** — every debounced search box (8 sites); Enter flushes the
  debounce; `focus()` export.
- **Chip** — every status badge / count pill / dismissible chip (~20 sites);
  clickable non-dismissible chips render as ONE button.
- **Seg** — all six segmented controls (tune-sheet status 3-ways main +
  per-instrument, add-pane "Add as" + per-instrument, my-tunes status/sort
  filters incl. the `secondary` two-level sort, session sort, both
  history-scope toggles). Controlled: `onSelect` fires on every click,
  including the active option (per-instrument toggle-off relies on it).
- **Sheet** — every remaining hand-rolled modal (copy-to two-step with `back`
  chevron, add-instance ×2, PeopleTab ×3, instrument-config, add-to-session,
  termination) plus the ported vanilla `session_instance_modal.js`
  (now `sessionadminpage/InstanceSheet.svelte`; the static js/css are gone)
  and the "Find a tune" overlay. Unlike the other rounds, Sheet REPLACED the
  bespoke chrome (scrim/frame/Cancel–title–Done header — the spec's dismiss
  conventions); each modal's body content kept its markup and CSS. Commits
  that can fail server-side use footer buttons, not header Done, so the sheet
  stays open for retry.

**Deliberate exceptions:** the tune-detail drawer (already the single shared
implementation; its chrome + live-shell dark scoping stay as-is pending a
future decision), the add pane (`.mt-add-pane` — a NON-modal desktop
split-pane push; a Sheet would focus-trap it), and the live logger's bespoke
controls (search-mode inputs, action-pills).

## Related

- [Templates & Pages](templates.md) — the shells and what stays Jinja
- [AJAX Patterns](ajax.md) — serializer layer, auth decorators, Bearer tokens
- [Live Logging](../logic/live-logging.md) — the spec-024 reference implementation
- `specs/changes/inprogress/035-svelte-ui-consolidation.md` — the migration spec


> Kit adoption update: lib/Tabs is now THE tab engine across personpage, sessionpage, sessionadminpage, and the tunesheet (value mode + onValueChange URL sync, or navigate mode with href tabs); pages keep their existing skins via the class-passthrough props and styled={false}. The mobile `<select>` is a per-host knob (`mobileSelect`: true | false | 'auto' = select only above 4 tabs): personpage and sessionadminpage keep it (it originated there and their tab counts overflow a phone); sessionpage and the tunesheet keep visual tabs on mobile.
