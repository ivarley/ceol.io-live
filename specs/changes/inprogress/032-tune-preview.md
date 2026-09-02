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
- **Preview content** (`TunePreview.svelte`), top to bottom: title with the tune type
  inline next to it; a **facts line** carrying the two deciding signals in color —
  session history in gold ("♪ Played here 2× — last: …", or a muted "Not played here
  yet") and popularity with an accent-emphasized count ("**1300** tunebooks") — plus the
  ★ on-your-list badge (the old "in this session" badge was redundant with the play
  count and is gone); "Also known as" aliases (clamped to 3 lines with a "More …"
  expander, re-measured when the backfill grows them); the **settings pager ABOVE the notation**
  (‹ › left/right-justified, single-line ellipsized "Setting n of N · #id · key · ★ this
  session's") so paging settings never moves the bar — only the notation below changes;
  then the notation block with the **tune-detail modal's anatomy** — content on top,
  `notes`/`abc` mode tabs bottom-left (notes default), a `thesession` link bottom-right
  (no abc-tools), clicking the image or ABC flips **incipit ⇄ full**; and an import note
  for remote tunes.
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
  on its far right; tapping it jumps straight into that tune's preview. The preview's nav
  list is the quick results themselves, so the header reads "3 of 8" for the 3rd match and
  ‹ › page the other matches; "‹ Results" lands on the normal deep-search results seeded
  from the composer text (no keyboard re-autofocus on the way back). Logging from the
  jumped preview follows the same `previewAction → onAdd → log at cursor` path.
- **Desktop routing — the deep search IS the side pane; NOTHING opens in a centered
  modal.** On wide screens (≥900px) every deep-search entry point routes to the pane:
  the composer's "🔍 Search …" row seeds the pane's search from the composer text and
  focuses it; the quick-result 🔍 and the paste-URL flows open their preview in the pane
  (`SidePane.seedSearch`/`openPreview` → TuneSearch's runtime `seed`/`openExternalPreview`
  exports). Mobile keeps the full-screen modal, which gets the same jumps via the
  `initialPreview={items, index, settingId?, reseedId?}` mount prop. A second jump while a
  pane preview is already open remounts it (`{#key externalPreview}` — otherwise the new
  items mutate under the old component's index), and TunePreview animates `in:` only, so a
  swap replaces instantly instead of stacking two flying previews.
- **Keyboard (desktop pane):** ↑/↓ walk cards (unchanged), **Enter opens the preview** (was:
  add immediately), Enter again confirms — the fast path is Enter-Enter; **⌘/Ctrl+Enter** adds
  skipping the preview (the ＋ rail's keyboard twin); ←/→ step results in the preview; Esc backs
  out. The composer type-ahead is untouched.
- **Confirm:** one primary action, context-labeled — "＋ Log This Tune" (live logger) /
  "＋ Add This Tune" (both add panes, which then continue to their configure phase). A
  confirmed add **clears the search** (query + results), same end state as the composer.
- **Paste-a-URL** (composer paste-detect AND the deep-search paste field) jumps straight
  into that tune's preview instead of logging blind. A `?setting=`/`#setting` deep link in
  the URL lands the pager on that setting and **counts as chosen** (overriding the
  session-setting landing); it survives the backfill when the setting isn't imported yet
  (`TunePreview initialSettingId` / `pendingSetting`). Meanwhile the search underneath
  re-seeds with the tune's REAL name — the session's local alias first — via
  `reseedFromThesession` (cache-backed, no double fetch), so Back lands on its results,
  not a URL-string search. The preview's confirm sends the same `add_tune{thesession_id}`
  payload as before (offline still queues).
- **Setting id always visible + always saved:** the pager reads "Setting 2 of 4 · #13030 ·
  Ddor" and the `thesession` link deep-links the setting currently showing
  (`?setting=NNN#settingNNN`). `session_tune.setting_id` is ALWAYS populated — the tune's
  default (lowest setting_id) when nothing was chosen — on every enrollment path
  (`_enroll_session_tune`, `add_session_tune`, `insert_session_instance_tune`, shared
  `default_setting_id` helper) plus a backfill for existing rows
  (`schema/032_default_session_tune_setting.sql`). Consequence for precedence: "session
  already has an override" now means a NON-default setting — an auto-filled (or
  explicitly-default) value is replaced by a chosen setting; only a non-default preference
  pushes later choices down to per-row overrides.
- **Toggle stays live mid-render:** the "rendering notation…" spinner (and the
  no-image state) are buttons — clicking mid-fetch flips incipit ⇄ full immediately
  (imgSeq guards the stale response; the abandoned render still finishes and caches).
- **Search polish:** the desktop pane widened to 440px (log column absorbs the
  difference); an **× inside the search field's right edge** cancels out of search mode
  (same `reset()` an add performs); and while the settings **backfill is in flight**, the
  pager's › slot shows a subtle spinner that becomes the arrow if/when more settings
  land (`backfilling` flag around the fetch, seq-guarded; a failed backfill just
  restores the disabled arrow).
- **Filter layout:** the filters toggle sits to the RIGHT of the search input (same
  row); the expandable panel holds the By name / By ABC mode buttons and a styled
  **tune-type droplist** (replacing the chip grid). With the panel closed, active
  filters — mode AND type — show as clearable ✕ pills. The mobile deep modal starts
  **below the fixed app header** (top: 42px + safe-area, z-index under the header) so
  Done never overlaps the hamburger.
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

## Addendum (2026-07-14): optional `footer` snippet

`TunePreview` grew an optional `footer` snippet prop `(item, previewData,
chosenSettingId)` that REPLACES the default `.pv-action` button (threaded
through `TuneSearch` as `previewFooter`; default null = today's button, so the
live logger and session-tunes pane are unchanged). When a footer is set, the
bare-Enter shortcut no-ops (the form owns its own confirm). The My Tunes add
pane uses it to host `AddTuneForm` — its configure phase folded into the
preview, and the ＋ rail became an instant defaults-add.

## Addendum (2026-07-26): paste a link ANYWHERE you can type a tune name

The rule is now uniform: any box that takes a tune name (or ABC) also takes a
thesession.org URL / tune id, and a `?setting=`/`#setting` deep link rides
through to the scope that surface writes. Before this, only the live composer's
paste-detect and the deep search's *secondary* paste box (buried under "Search
on thesession.org") did it — the legacy vanilla `TuneSearchComponent`'s
`enableTuneIdPaste` had covered the main box, and the Svelte rewrite dropped it.

- **`TuneSearch.svelte` main field** (live pane/modal + both add panes): a link
  in the box suppresses the local name search (nothing can match it) and offers
  `🔗 Open tune #NNN`; a real PASTE jumps into the preview immediately, as does
  Enter, a seeded `initialQuery`, and `seed()`. Only a paste auto-jumps —
  `inputType` starting `insertFrom` (falling back to a ≥8-char jump for IMEs
  that omit it) — because typing a URL by hand parses at `.../tunes/8` and would
  yank you into the wrong tune mid-keystroke. All of it funnels through one
  `jumpToPasted(raw)`, shared with the old paste box.
- **Hamburger "Find a tune"** (`FindTune.svelte`, logged-out included): resolves
  links server-side (below). Not in the catalog yet ⇒ not a typo — the empty
  state offers the My Tunes add pane at `/my-tunes?add=1&q=<raw link>` (logged
  out: the thesession.org page). The offline bundle is a NAME index, so it is
  never consulted for a link.
- **`GET /api/tunes/search`** treats an id / tunes URL as a pointer: exact tune,
  merge redirects followed, `query_tune_id` echoed (empty `tunes` beside it =
  "not imported yet"). The 2-char minimum no longer applies to a link.
- **Page search boxes** hand off rather than resolve: My Tunes' filter box gains
  an `Add Tune #NNN` action in its empty state (session tunes already had `Add
  Tune`), and both carry the raw link into the pane, which jumps on the seeded
  query. Filter-only lists (session admin's tune tab) keep plain id matching.
- **Scopes, verified end to end** (stubbed thesession.org): personal ⇒
  `person_tune.setting_id`; session ⇒ `session_tune.setting_id` (prefilled in
  the pane's Advanced field); instance ⇒ session preference when the tune was
  just enrolled, `session_instance_tune.setting_override` once the session
  already prefers a different non-default setting (spec 032's precedence,
  unchanged — the paste path just feeds it a chosen setting).
- **A tune you already have** is the paste path's blind spot: a link resolves to a
  synthetic result carrying no `on_list` flag, so the My Tunes pane offers the full add
  form for a tune that's been on the list for years. `POST /api/my-tunes` answers 409
  there, and used to drop the whole configured add on the floor — the chosen setting
  and the typed notes with it. It now applies the EXPLICIT parts to the existing row and
  reports them as `applied` in the 409 body (`{"setting_id": <id>}` / `{"notes": true}`):
  the setting lands even over an existing one (an explicit, cheap-to-redo choice), notes
  only fill an empty field (free text is lossy to overwrite). The pane forwards `applied`
  to `onAlready`, and the landing toast says "Already on your list — set your setting to
  #NNN" instead of the bare "already on your list".
- Frontend: `parseThesessionId`/`parseThesessionSettingId` moved from
  `logstate.js` (live-only) to `shared/parse.js`, re-exported for the logger.
  `window.CEOL_AUTHED` (base.html + live_logging.html) tells app-wide bundles
  with no page payload whether anyone is signed in.
- Tests: `frontend/tests/tunesearch.test.js` (paste vs. type, seeded query, no
  name search for a link), 3 more in `findtune.test.js`, 5 in
  `tests/integration/test_my_tunes_search.py` (URL/bare id/merge-follow/
  unimported/short-query).
