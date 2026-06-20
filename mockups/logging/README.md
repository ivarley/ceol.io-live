# Session Logging — Prototype (Feature 021)

A **clickable, mobile-first prototype** of a redesigned live-session tune-logging
screen for ceol.io. Pure HTML/CSS/JS with **dummy data and no backend** — it's
for getting the *interactions and feel* right before building the real thing.

Full design rationale and decisions: **`specs/changes/021-simplified-session-screen.md`**.

## Where it runs
- **On prod:** `https://ceol.io/mockups/logging/`
- **Locally:** `python3 serve.py` (no-cache static server on :8021) or just open `index.html`.
- **Installable PWA:** in mobile Safari → Share → *Add to Home Screen* (runs full-screen/standalone).

## ⚠️ Start with the 🧪 menu
The headline features — **multi-user, audio, and offline** — are invisible until you
trigger them. Tap the **🧪 flask icon** (top bar, left of the hamburger) to simulate:
- Sarah logs / starts a set / ends a set; her **mic** logs a tune
- **typing** indicators (one or several people at once)
- **merge** (you + Sarah log the same tune)
- a player **joins/leaves**
- **toggle offline** (then keep logging, and reconnect to sync)
- **clear session** (see the empty state)

This menu is **prototype-only** — it does not exist in the real product.

## Gestures that aren't obvious
- **Tap the field** → search + log a tune (stay-hot for logging a whole set).
- **Tap a tune** → its actions (Info / Before / After / Edit / Remove).
- **Tap a seam** (gap between tunes, or between sets) → insert there; the armed seam
  also offers **Split** (within a set) / **Join** (between sets) on its right edge.
- **Tap the set's type label** (e.g. "Jigs") → who started the set (and logged-by + time).
- **Tap the header** (session name) → expand counts / notes / attendance / who's logging.
- **🎤** → start the audio recorder (tap again for its control panel).
- Bottom-right **Done** → read-only "view" mode; **✎ Edit log** → back to logging.

## What's real vs faked
- **Real (in this prototype):** all the UI/interaction logic — sets, entry/search,
  editing, split/join, details drawer, confidence markers, presence colors, typing
  reservations that re-anchor, corroboration merge, offline queue/reconnect, undo.
- **Faked / stubbed:** all data is dummy and in-memory (refresh = reset); no network,
  no persistence, no real audio recognition; "Search deeper" By-ABC/Filters tabs,
  notes, and the deep search are partial; multi-user/offline are driven by the 🧪 menu.

## Known limitation
The header **jumps-and-settles when the iOS keyboard opens**. This was proven
unfixable in pure web (iOS animates the visual viewport itself) — see spec §41. A
native wrapper is the only true fix.
