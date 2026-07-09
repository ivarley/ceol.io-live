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
- **Settings backfill:** the local catalog usually holds only the setting an import brought
  over, so after a local tune's preview opens, the client background-fetches
  `thesession-preview/<id>?full=1` (which skips the local short-circuit) and appends the
  settings thesession has beyond the local ones (dedup by `setting_id`; thesession aliases
  merge into "Also known as" too). Backfilled settings render ephemerally via `render-abc`
  (no `tune_setting` row); offline or thesession-down, the local settings simply stand.
  The response is cached per id, so stepping away and back is instant.
- **Result steppers:** ‹ › in the preview header page through the whole result list (local
  results, then remote) so candidates can be compared without bouncing back. Back/Esc returns
  with query, results, and scroll intact.
- **🔍 on composer quick results:** each type-ahead row on the log page carries a magnifier
  on its far right; tapping it opens the deep-search modal JUMPED straight into that tune's
  preview. The preview's nav list is the quick results themselves, so the header reads
  "3 of 8" for the 3rd match and ‹ › page the other matches; "‹ Results" lands on the normal
  deep-search results seeded from the composer text (no keyboard re-autofocus on the way
  back). Implemented as a TuneSearch `initialPreview={items, index}` prop (App builds the
  items from `visibleResults`); logging from the jumped preview follows the same
  `previewAction → onAdd → close modal + log at cursor` path.
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
- **Session's setting surfaced** (the setting-level parallel of the tune-level "in this
  session" badges): with a session scope, (1) the search card's incipit shows the SESSION'S
  preferred setting when its image is cached (else the usual lowest-cached fallback — never
  a mismatched lazy render), (2) the preview's pager OPENS on that setting
  (`session_setting_id` in the tune-preview response; landing there is not a "choice"), and
  (3) it's badged "★ this session's" in the pager label. My Tunes scope is unchanged.
- **Chosen setting (logging with it):** a setting counts as CHOSEN only when the user works
  the pager in that preview (merely opening — which lands on setting 1 — expresses no
  preference). The confirm then sends `setting_id` in the `add_tune` op. Server side
  (`_maybe_apply_chosen_setting`): the setting is **imported into `tune_setting` if it isn't
  local** (fetched from thesession.org inside the op transaction, like the tune import), then
  - **no session-level override yet** (`session_tune.setting_id` NULL, incl. just-enrolled) →
    it becomes the session's **preferred setting**;
  - **session already prefers a different setting** → it applies to **this row only**
    (`session_instance_tune.setting_override`);
  - **same as the existing preference** → no-op (`setting_applied: 'already'`).
  A duplicate append that collapses into a **corroboration** still applies the chosen setting
  (to the corroborated row); a setting that can't be imported never fails the op
  (`setting_failed` in the ack). One-tap adds (＋ rail, ⌘Enter, composer) send no setting_id.
  In the **add panes**, a chosen setting prefills the Advanced "Setting" field (visible and
  editable) and rides their existing submit paths — `POST /api/sessions/<path>/tunes` now also
  fetches+caches a not-yet-local setting, matching `POST /api/my-tunes`.

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
- The pager shows ALL of thesession's settings via the backfill, and logging with one
  chosen imports it and applies it (session preference / row override — see "Chosen
  setting" above).
- The pane's "usually next" card remains visible above a pane preview; harmless but could be
  hidden later if it reads oddly.
