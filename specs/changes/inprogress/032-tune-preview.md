# 032: Deep-Search Tune Preview (Look Before You Log)

## Purpose

Tapping a deep-search result used to perform the action immediately (log at cursor / add to
session tunes / add to My Tunes) — but a title alone, especially a thesession.org hit with no
notation, often isn't enough to know it's the right tune. This inserts one state between
*search* and *act*: a **tune preview** with full notation, ABC, alternate titles, settings,
and stats, across all three deep-search surfaces at once (they all share `TuneSearch.svelte`).

Interaction pattern was agreed via an interactive mockup first (mobile screen-push and desktop
pane drill-in — the preview always occupies the **same real estate** as the search, never a
new centered modal).

## Interaction (as built)

- **Split result card:** the card body opens the preview; a slim **＋ rail** on the right edge
  keeps the old one-tap add for tunes you recognize from the incipit. (`.deep-card-split`,
  `.deep-card-body`, `.deep-quick`; the base `.deep-card` keeps its column layout for the add
  panes' picked-card.)
- **Preview content** (`TunePreview.svelte`): name/type/badges; "Also known as" (session
  aliases locally, thesession aliases remotely); a notation block with the **tune-detail
  modal's anatomy** — content on top, `notes`/`abc` mode tabs bottom-left (notes default),
  a `thesession` link bottom-right (no abc-tools), clicking the image or ABC flips
  **incipit ⇄ full**; a **settings pager** (‹ › left/right-justified, "Setting n of N · key");
  an import note for remote tunes; tunebook count + played-here stats.
- **Result steppers:** ‹ › in the preview header page through the whole result list (local
  results, then remote) so candidates can be compared without bouncing back. Back/Esc returns
  with query, results, and scroll intact.
- **Keyboard (desktop pane):** ↑/↓ walk cards (unchanged), **Enter opens the preview** (was:
  add immediately), Enter again confirms — the fast path is Enter-Enter; **⌘/Ctrl+Enter** adds
  skipping the preview (the ＋ rail's keyboard twin); ←/→ step results in the preview; Esc backs
  out. The composer type-ahead is untouched.
- **Confirm:** one primary action, context-labeled — "＋ Log This Tune" (live logger) /
  "＋ Add This Tune" (both add panes, which then continue to their configure phase). A
  confirmed add **clears the search** (query + results), same end state as the composer.
- **Paste-a-URL** now routes through the preview (confirm the fetched title/notation before
  the import) instead of logging blind; the preview's confirm sends the same
  `add_tune{thesession_id}` payload as before.
- **Render-on-demand:** an incipit/full image not yet cached fires a render request and shows
  a spinner; pending renders live in a **module-level registry in `client.js`** keyed
  `settingId:kind`, so the spinner survives navigating to another setting/result and back and
  the modal/pane share in-flight requests.

## Backend (`live_logging_routes.py`, routes in `app.py`)

Four endpoints, each homed three ways like the rest of the search family
(`/api/live/instances/<id>/…`, `/api/my-tunes/…`, `/api/sessions/<path>/tunes/…`):

- `GET …/tune-preview/<tune_id>` — `_tune_preview_core`: all settings with `abc`,
  `incipit_abc` (stored or derived via `extract_abc_incipit`), and any **cached incipit image
  inline**; session aliases (`session_tune.alias` + `session_tune_alias`) and played-here
  stats when a session scope exists; follows merge redirects to the canonical tune.
- `GET …/setting-image/<setting_id>?kind=incipit|full` — `_ensure_setting_image`:
  per-setting sibling of `_ensure_incipit`; renders via the abc-renderer and caches on the
  `tune_setting` row if missing; degrades to `{image: null}` when unrenderable.
- `GET …/thesession-preview/<id>` — already-local ids (following redirects) short-circuit to
  `{is_local, tune_id}` with no network; otherwise `_fetch_thesession_tune` (shared with the
  import path) shaped to name/type/tunebooks/aliases/settings ("!" line breaks unfolded,
  empty-abc settings dropped). **Nothing is imported** — the existing
  `add_tune{thesession_id}` op still does import-on-confirm (spec 026, unchanged).
- `POST …/render-abc` `{abc, key, tune_type, kind}` — ephemeral render for a remote setting's
  notes mode; nothing cached; 20k char cap.

## Frontend

- `frontend/src/TunePreview.svelte` — new; hosted by `TuneSearch.svelte` (content swap with a
  fly transition, both modal and pane variants).
- `frontend/src/TuneSearch.svelte` — split cards, `previewIdx`/`previewItems` state,
  `actionLabel` prop, keyboard changes, paste→preview, `afterAdd` clears preview state.
- `frontend/src/client.js` — `tunePreview`, `settingImage`, `thesessionPreview`,
  `renderRemoteAbc` + the shared image cache/in-flight registry.
- CSS: `.deep-card-split`/`.deep-quick` + `.pv-*`/`.nb-*` in `frontend/src/app.css` (live,
  dark) and scoped under `.mt-add-pane` in `frontend/src/mytunes/mytunes-add.css`
  (site-themed panes). Both bundles rebuilt (`npm run build`).
- Hosts: live logger uses the defaults; `AddTuneApp` / `SessionTuneAddApp` pass
  `actionLabel="＋ Add This Tune"` (their `pick` still returns `false` and swaps to the
  configure phase, which unmounts the search+preview — behavior unchanged).

## Verification

- `tests/integration/test_tune_preview.py` (11 tests): preview shape + settings order +
  inline cached incipit; session aliases/stats vs personal scope; merge-redirect follow;
  404s; setting-image cached/render/missing; thesession-preview local shortcut (asserts **no
  network**), remote shaping, error passthrough; render-abc validation; live-instance home.
- Full backend suite (772) and Vitest suite (137) pass; both bundles build clean.
- E2E (Chrome, app on :5031 with thesession.org stubbed): pane search → preview →
  notes/abc → incipit⇄full → setting 2 render-on-demand spinner → Log This Tune → row lands
  at cursor + search clears; remote search → remote preview (skeleton → aliases/notation/
  import note) → Log → imported + linked + enrolled; modal variant via composer "Search …"
  (Enter opens preview, Esc restores search state); My Tunes pane preview → "＋ Add This
  Tune" → configure phase → added; session-tunes pane preview with session-scoped stats.

## Notes / follow-ups

- The suggestion chip and "log as-is" stay one-tap (nothing to preview).
- Multiple-settings display was already carried by the pager; when remote multi-setting
  import lands someday, the pager is the seam.
- The pane's "usually next" card remains visible above a pane preview; harmless but could be
  hidden later if it reads oddly.
