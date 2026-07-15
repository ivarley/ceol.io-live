# Template Structure and Base Layouts

Flask/Jinja2 template hierarchy and shared components.

## Base Template

**File**: `templates/base.html`

**Provides**:
- HTML structure, header, navigation
- Flash messages (toasts) — `showMessage()` at `base.html:365`
- In-session badge
- PWA features (service worker, pull-to-refresh)
- App-wide offline scripts (`mytunes_offline.js`, `offline_data.js`, `connection_status.js`, `prefetch.js`)
- The app-wide tune-detail sheet (see below)

**Blocks**:
```jinja2
{% block title %}                 <!-- Page title -->
{% block description %}           <!-- Meta description -->
{% block tune_detail_modal_css %} <!-- Override to skip the sheet's stylesheet -->
{% block extra_css %}             <!-- Page CSS -->
{% block content %}               <!-- Main content -->
{% block tune_detail_modal %}     <!-- Override to skip the sheet bundle -->
{% block extra_js %}              <!-- Page JavaScript -->
```

**Usage**: `{% extends "base.html" %}`

### App-wide tune-detail sheet

`base.html:779-782` loads `static/tunesheet/sheet.js` (Svelte, spec 035
Step 3, source `frontend/src/tunesheet/`) on **every** page. The bundle
renders its own hidden `#tune-detail-modal` container and installs
`window.TuneDetailModal` plus the hamburger "Find a tune" overlay
(`window.FindTuneOverlay`). `tunebook_status.js` is loaded alongside it —
remaining consumers use `window.TunebookStatus` directly. The
`tune_detail_modal` / `tune_detail_modal_css` blocks exist so a page could opt
out; today no page does (`common_tunes.html` used to, but now uses the shared
sheet).

The one template that does **not** extend `base.html` is `live_logging.html`
(the live logger's standalone shell, spec 024).

## Thin Svelte shells

The interactive pages are thin shells (spec 035): each embeds
`window.__PAGE_DATA__ = {{ payload | tojson }}` (produced by the **same**
`serializers.py` function its API endpoint returns), provides a mount div, and
loads a page bundle in `{% block extra_js %}`. See
[Svelte Pages](svelte-pages.md) for the full pattern and page table.

- `my_tunes.html` → `#my-tunes-root` + `static/mytunespage/page.js` (the cleanest example — 26 lines)
- `sessions.html` → `#sessions-root` + `static/sessionsdir/page.js`
- `session_detail.html` → `#session-detail-root` + `static/sessionpage/page.js` (also mounts `#session-tune-add-root` for the add pane)
- `person_details.html` → `#person-details-root` + `static/personpage/page.js` (serves both `/me` and `/admin/people/<id>`)
- `session_admin.html` → `#session-admin-root` + `static/sessionadminpage/page.js`
- `add_session.html` → `#add-session-root` + `static/addsessionpage/page.js` (public page; only the create POST is gated)
- `admin_people.html` → `#admin-people-root` + `static/peopleadminpage/page.js` (keeps the Jinja `admin_tabs.html` chrome above the mount)

Several of these shells still carry large page `<style>` blocks; moving that
CSS into the bundles (as `my_tunes.html` already does) is a known follow-up.

## Full Jinja pages (deliberately not migrated)

- **Auth**: `auth/login.html`, `auth/register.html`, `auth/reset_password.html`, …
- **Help**: `help.html`, `help_*.html`
- **Plain admin tables**: `admin_tabs.html`, `admin_sessions_list.html`, `admin_tunes.html`, … (`admin_people.html` is a thin Svelte shell now, see above)
- **Home**: `home.html`
- **Attendance page**: `session_instance_players.html` (+ `partials/attendance_tab.html`, `static/js/shared/attendance.js`)
- **Quarantined**: `session_instance_detail.html` — the legacy pill editor, kept working untouched until spec 035 Step 6 deletes it (see [Session Logging UI](session-logging.md)); now the only consumer of `static/js/components/TuneSearchComponent.js` AND `static/js/shared/modalManager.js`, both of which die with it

The legacy fallback add pages (`my_tunes_add.html`, `session_tune_add.html`) are
deleted: `/my-tunes/add` and `/sessions/<path>/tunes/add` now redirect to their
modern Svelte surfaces with the add pane auto-opened (`?add=1[&q=]` — see
[Svelte Pages](svelte-pages.md)). Likewise `my_tunes_sync.html` is deleted:
`/my-tunes/sync` redirects to `/my-tunes?add=1&sync=1`, which opens the add
pane straight into its tunebook-sync view (`SyncPane.svelte`; the search phase
links to it under the pane header).

## Header

**Logo**: `#logo-img` (`base.html:306`) - Responsive

**In Session Badge**: `#inSessionBadge` (`base.html:327`) - "Live" indicator when a session is on, popup on hover/click

**Hamburger Menu**: `static/js/hamburger_menu.js` + `templates/hamburger_menu.html` - Profile, Admin, My Tunes, Find a tune, Log Out (authenticated) | Log In, Session Logs (unauthenticated)

## Theme

The app is dark-only — no toggle, no `data-theme` attribute.

**CSS**: `static/css/theme.css` - The single token source (colors + radius/shadow/spacing/motion/z-index scales)

**See**: [Theming](theming.md)

## Messages

**Server**: Flask `flash()` → toasts

**Client**: `showMessage(message, type)` (`base.html:365`); Svelte pages reach it via `frontend/src/lib/toast.js`

**Display**: Top-center, auto-hide

## Partials & Components

**Attendance Tab**: `partials/attendance_tab.html` - Reusable attendance UI (`session_instance_players.html`)

**Modals**: `modals/person_edit.html` - Person edit dialog

**Usage**: `{% include 'partials/attendance_tab.html' %}`

## Conventions

**URL Generation**: Always use `url_for()`, never hardcode
```jinja2
<a href="{{ url_for('session_detail', path=session.path) }}">Session</a>
<img src="{{ url_for('static', filename='images/logo.png') }}">
```

**Global Context**: `current_user`, `request`, `session` (Flask session)

**Shell Context**: migrated pages get a single `payload` variable (embedded as
`window.__PAGE_DATA__`); legacy pages get individual variables (`session`,
`session_instance`, `tunes`, `is_admin`, …)

## Responsive & Layout

**Framework**: Bootstrap 4.5 (xs/sm/md/lg/xl breakpoints); Svelte kit components use one 768px device breakpoint

**Z-Index**: `--z-*` variables in `static/css/theme.css` (folded in from the former `z-index-layers.css`)

## PWA

**Service Worker**: `static/service-worker.js`, served as `/sw.js` (see [Offline Support](../logic/offline.md))

**Manifest**: `static/manifest.json`

**Pull-to-Refresh**: PWA-only, in `base.html`

## JavaScript

**Inline**: Base template (menu, badge)

**Page**: `{% block extra_js %}` — Svelte page bundles (`static/<page>/page.js`) on migrated pages

**Shared vanilla**: `static/js/` — e.g. `utils/unaccent.js`, `hamburger_menu.js`, offline scripts; `static/js/shared/` (webpack: `modalManager.js`, `attendance.js` — still used by Jinja pages); `static/js/dist/` (webpack: pill-editor modules **only**, deleted with the pill page)
