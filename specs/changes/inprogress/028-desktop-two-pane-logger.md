# 028: Desktop Two-Pane Layout (Live Logger)

## Purpose

The live logger (Feature 024) is mobile-first: one `main { max-width: 640px }` column with a bottom
composer, and tune search lives behind a full-screen modal. On a desktop browser that wastes the
horizontal space. This change adds a **wide-screen two-pane layout**: the log stays in a center
column and a **persistent right pane** hosts tune search + the "next tune" suggestion, so search is
always visible instead of modal-gated.

Phase 1 (this spec) is the responsive shell + persistent pane. **Deferred** to later phases:
keyboard navigation/shortcuts, multi-select + copy/paste of sets, and a full reactive-state
`store.svelte.js` extraction.

Rather than fork search between mobile and desktop, this change **extracts the deep-search body**
(name/ABC search over the local catalog, thesession.org remote search, and paste-URL import) **into
one shared `<TuneSearch>` component** rendered in both the mobile modal and the desktop pane — one
search, no divergence.

## Current state (verified)

- `frontend/src/App.svelte` — the monolith. Deep-search modal markup at ~2689-2794; state
  (`deepQuery`, `deepMode`, `deepType`, `deepFilterOpen`, `deepResults`, `deepLoading`, `deepSeq`,
  `tsSearched`, `tsSearching`, `tsResults`, `tsPasteUrl`, `tsPasteError`, `DEEP_TYPES`) and handlers
  (`openDeep` 1521, `onDeepInput` 1532, `setDeepMode`/`setDeepType`/`toggleDeepFilters`,
  `runThesessionSearch` 1600, `pickDeep` 1560, `deepLogAsIs` 1567, `pickRemote` 1611,
  `pasteThesession` 1617, `parseThesessionId` 1588, `deepKey` 1576, `closeDeep`).
- **Every terminal action is the same shape:** `closeDeep(); clearEntry(); addOptimistic(payload,
  name)` — differing only in `payload` (`{tune_id,…}` / `{name}` / `{thesession_id, tune_id,…}` /
  `{thesession_id: id, name:'#id'}`). This collapses to a single `onAdd(payload, name)` callback.
- `frontend/src/logstate.js` (14 pure exports: `computeOrdered`, `segmentByBreaks`, `cursorPos`,
  `remapAnchors`, `normName`, `setLabel`, …) and `frontend/tests/*` (Vitest + characterization +
  `e2e/live/`) are the test foundation from `c607b77`/`178da6d` — the safety net for this refactor.
- `frontend/src/client.js` exports `deepSearch` and `thesessionSearch`. `Incipit.svelte`
  renders notation lazily.
- Layout CSS (`frontend/src/app.css`): `main` is a `100dvh` flex column, `html,body{overflow:hidden}`,
  `.topnav` sticky, `.sets` the sole scroller, `.dock` pinned. `deep-*` result-card classes are
  global (an unscoped component reuses them). No media queries drive layout today; a `visualViewport`
  handler only kicks in below 480px.
- No backend change is required.

---

## A. Extract `frontend/src/TuneSearch.svelte` (shared search body)

Move the deep-search **body** (search field + By-name/By-ABC tabs + type filters + local results +
the "From thesession.org" remote section + paste-URL import) and its search state/logic out of
`App.svelte` into a component that **owns its search state** and calls back for terminal actions.

- **Props:** `config`, `initialQuery` (seed — the composer text for the modal, `''` for the pane),
  `preferType` (the set's type, for result ranking), `displayStatus` (gate remote search
  online-only), `variant: 'modal' | 'pane'` (modal shows the "Done" header + autofocuses),
  `onAdd(payload, name)`, `onClose` (modal only).
- **Owns:** `deepQuery` (init from `initialQuery`), `deepMode`, `deepType`, `deepFilterOpen`,
  `deepResults`, `deepLoading`, `deepSeq`, the `ts*` remote state, `DEEP_TYPES`; and the search logic
  (`runSearch`/`onDeepInput` → `deepSearch`, `runThesessionSearch` → `thesessionSearch`,
  `setDeepMode`/`setDeepType`/`toggleDeepFilters`, `parseThesessionId`, `resetThesession`,
  `deepKey`). On mount, if `initialQuery` is non-empty, run the initial search (replaces `openDeep`'s
  seeding).
- **Calls back** on pick / log-as-is / remote-pick / paste via the single `onAdd(payload, name)`,
  building the same payloads the current handlers build. Reuses the existing global
  `deep-card` / `deep-remote` / `Incipit` markup verbatim.

## B. `App.svelte` — render `<TuneSearch>` in the modal + add the terminal callback

- Replace the inline modal body (2689-2794) with, inside the existing `{#if deepOpen}` shell:
  `<TuneSearch variant="modal" initialQuery={input} preferType={cursorSetType()} {displayStatus}
  {config} onAdd={(p, n) => { closeDeep(); logTune(p, n) }} onClose={closeDeep} />`.
- Add `function logTune(payload, name) { clearEntry(); addOptimistic(payload, name);
  queueMicrotask(() => inputEl?.focus()) }` — the shared terminal path. Delete the migrated
  deep-search state + handlers from `App.svelte` (keep `openDeep`/`closeDeep`/`deepOpen`, which only
  gate the modal shell now).

## C. Responsive shell + `<SidePane>` (wide only)

- Add `let winW = $state(window.innerWidth)`, `<svelte:window bind:innerWidth={winW} />`,
  `const wide = $derived(winW >= 900)`, and `class:wide={wide}` on `<main>`.
- New `frontend/src/SidePane.svelte`, rendered `{#if wide}` as a child of `main`: a persistent
  **suggestion card** on top (the `nextSuggestion`, with Add + dismiss) then
  `<TuneSearch variant="pane" initialQuery="" … onAdd={logTune} />`. Props from App: `config`,
  `suggestion={nextSuggestion}` (795), `canEdit`, `preferType`, `displayStatus`, `onAdd={logTune}`,
  `onAddSuggestion`, `onDismissSuggestion={dismissNext}` (817).
- `app.css` wide branch — **grid-areas over existing children, no DOM restructuring**:
  ```
  main.wide { max-width: 1200px; display: grid; column-gap: 16px;
    grid-template-columns: minmax(0,1fr) 360px;
    grid-template-rows: auto auto 1fr auto;
    grid-template-areas: "top top" "msgs pane" "list pane" "dock pane"; }
  main.wide .topnav { grid-area: top; }
  main.wide .feed-msgs { grid-area: msgs; }
  main.wide .sets { grid-area: list; }
  main.wide .dock { grid-area: dock; }
  main.wide .sidepane { grid-area: pane; overflow-y: auto; min-height: 0; }
  ```
  `.sets` and `.sidepane` become two independent scrollers; the dock stays pinned;
  `html,body{overflow:hidden}` is untouched. Mobile never mounts the pane (the grid never activates),
  so the phone layout is byte-for-byte unchanged.

## D. Behavior summary

| Situation | Result |
|---|---|
| Viewport ≥ 900px | Two-pane grid: log center, persistent pane right (suggestion + search) |
| Viewport < 900px | Unchanged mobile layout; search stays the full-screen modal |
| Pane result picked | `logTune` → `addOptimistic` at the current cursor (same placement as `pickDeep`) |
| Modal (any width) | Same `<TuneSearch>` component, `variant="modal"` — remote/import behavior intact |
| Read-only View mode | Pane still renders; add actions disabled via `canEdit` (suggestion is null in View) |

---

## Files touched

- `frontend/src/App.svelte` — swap the modal body for `<TuneSearch>`; add `logTune`, `winW`/`wide`,
  `class:wide`, render `<SidePane>`; delete the migrated deep-search state/handlers. (Rebuild
  `static/live/`.)
- New: `frontend/src/TuneSearch.svelte`, `frontend/src/SidePane.svelte`.
- `frontend/src/app.css` — wide grid branch + `.sidepane` / suggestion-card styles (results reuse the
  global `deep-*` classes).
- `frontend/tests/App.characterization.test.js` — add `thesessionSearch: vi.fn(async () => [])` to the
  `client.js` mock (the pane mounts a `<TuneSearch>` at jsdom's 1024px width → `wide` is true); add a
  `.sidepane` present/absent assertion.
- `e2e/live/live-logger.spec.ts` — desktop-viewport pane-present / mobile-viewport pane-absent smoke.
- Docs — `specs/current/ui/session-logging.md` (or the 024 UI notes): the wide two-pane layout.
- Reuse (no change): `addOptimistic`, `clearEntry`, `cursorSetType()`, `nextSuggestion`, `dismissNext`;
  `deepSearch`/`thesessionSearch` (`client.js`), `Incipit.svelte`, `logstate.js`. No backend change.

## Verification

- **Frontend unit/component:** `cd frontend && npm test`. The characterization test guards the
  modal → `<TuneSearch>` swap (render parity); existing `.tune-row`/`.set`/`.set-label` assertions
  must still pass, plus the new `.sidepane` present-when-wide / absent-when-narrow assertion.
- **Extraction safety:** `npm run build`, then manually smoke the **modal** at phone width (local
  search, "Search on thesession.org", paste-URL import, log-as-is) to confirm the modal's search
  behavior is unchanged.
- **Desktop e2e:** `make test-e2e` — at ≥900px `.sidepane` visible with the search field; at mobile
  width absent. Read-only (no seed mutation).
- **Manual:** `flask --app app run --debug`, open `/live/instances/90`; widen past 900px → pane appears
  with suggestion + search; picking a pane result adds a tune at the cursor and it appears in a second
  client via SSE; narrow → pane gone, modal path intact.

## Deferred (later phases)

- **Keyboard navigation / shortcuts** — focus search, arrow between tunes, Esc, toggle edit; a
  roving-tabindex/combobox pass that also refines the result-list a11y currently `svelte-ignore`d.
- **Multi-select + copy/paste of sets** — a `selection` model + paste-at-cursor as a burst of
  `add_tune`/`set_break` ops (no backend op needed); shared later with a mobile select/reorder mode.
- **Reorder** — needs one additive backend `move` op (relational anchors → `_position_for`); no
  remove+add.
- **Full `store.svelte.js` extraction** — move the reactive collections + op machinery out of
  `App.svelte`. The `<TuneSearch>`/`<SidePane>` split and `logstate.js` are the seams these build on.

## Open decisions

- **Pane suggestion vs. composer suggestion:** the pane shows `nextSuggestion` persistently while the
  composer dropdown also pins it when focused. Phase 1 keeps both (minor duplication); a later pass may
  suppress the composer's pinned row when `wide`.
- **Pane width:** 360px fixed vs. a clamp (e.g. `clamp(320px, 28vw, 420px)`); start fixed, tune with
  real content.
- **View-mode pane:** render the pane (search browsable, add disabled) vs. hide it entirely in
  read-only View. Plan renders it; revisit if it reads as noise.
