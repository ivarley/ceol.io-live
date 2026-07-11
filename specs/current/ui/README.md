# UI Layer

Frontend presentation, user interactions, visual design.

## Overview

Two ways of building a screen, by design (spec 035):

- **Svelte 5 pages** — every interactive page is a thin Flask/Jinja shell that
  embeds a serializer payload (`window.__PAGE_DATA__`) and mounts a page-scoped
  Svelte bundle: `/my-tunes`, `/sessions`, `/sessions/<path>`, `/me`,
  `/admin/people/<id>`, `/admin/sessions/<path>`, plus the live logger and the
  app-wide tune-detail sheet. Source in `frontend/src/`, built to
  `static/<page>/`.
- **Jinja + Bootstrap 4.5** — non-interactive surfaces stay server-rendered:
  `auth/*`, `help_*`, plain admin tables, home, the legacy fallback add pages,
  and the quarantined pill logger.

Styling: custom CSS on CSS variables (`static/css/theme.css` is the single
token source). Data flow: embedded first-paint payload, then `fetch` to
`/api/*` — the embed and the API share one serializer, so they can't drift.

## Components

### [Svelte Pages](svelte-pages.md)
Thin shell + `__PAGE_DATA__` + page-bundle architecture; the how-to for adding/changing a page; the `frontend/src/lib/` component kit

### [Templates & Pages](templates.md)
HTML structure, base layouts, thin shells vs. full Jinja pages

### [Session Logging UI](session-logging.md)
**Quarantined/deprecated** word-processor pill editor (original single-user, bulk-save logger) — replaced by the live logger

### [Live Logging](../logic/live-logging.md)
Real-time multi-user logger (Feature 024) — Svelte 5 PWA, incremental ops over SSE, no explicit save. Bundle under `static/live/`, source in `frontend/`

### [Dark Mode & Theming](theming.md)
CSS custom properties, theme switching, FOUC prevention

### [AJAX Patterns](ajax.md)
Serializer layer, API auth decorators, Bearer tokens, error handling, loading states

### [UI Styles](styles.md)
Standard form controls, search boxes, CSS variables

## Key Locations

- `templates/base.html` - Base layout: navigation, theme switching, and the app-wide tune-detail sheet bundle (`static/tunesheet/sheet.js` → `window.TuneDetailModal` / `window.FindTuneOverlay`)
- `frontend/src/` - Svelte sources (page dirs + `lib/` kit); one Vite config per bundle
- `serializers.py` - One function per page/API payload (the embed==API invariant)
- `templates/session_instance_detail.html` - Quarantined legacy pill editor (spec 035 Step 6 deletes it)
- `templates/admin_*.html` - Plain admin tables (still Jinja)
- `static/` - CSS, images, and the built bundles (gitignored; rebuilt on deploy)
