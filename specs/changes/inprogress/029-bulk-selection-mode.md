# 029 — Bulk Selection Mode (select / move / copy / paste / delete / assign)

The live logger (Feature 024/021/028) gains a **selection mode** for bulk operations on
tunes: multi-select, copy/paste (clipboard-compatible with the old pill logger), bulk
delete with undo, bulk starter assignment, and drag-to-move of contiguous blocks with
full set-break preservation. Works on mobile and desktop; every mutation is an op on
the existing op→event→SSE pipeline, so all changes stream to other connected clients
in near real time.

## A. Entering / leaving selection mode

- **Entry point**: a checklist toggle button (☑) on the right edge of the pull-down
  filter bar (the bar hidden above the fold, revealed by scrolling to the top).
  Tapping it must NOT focus the filter input.
- Available in **both edit and view mode**. View-mode selection is copy-only: no grab
  bars, no Paste/Delete/Assign — the selection bottom bar shows just Copy and Done.
- The button is accent-filled while selection mode is on; tapping it again exits
  (identical to Done / Esc).
- **State hygiene on entry**: row-action popup, set trays, and starter picker close;
  an in-progress tune edit (`editingId`) is cancelled (composer disappears); a
  `resolving` placeholder settles on its own. Selection starts EMPTY every time.
  The cursor seam carries over unchanged. Typing-indicator broadcast stops.
- **On exit** (Done, toggle, Esc): selection + shift anchor clear; bottom bar reverts
  to the underlying mode. Selection mode is pure client UI state — never synced.
- The internal rich clipboard SURVIVES exiting selection mode (session lifetime), so
  copy → Done → re-enter → Paste works.
- Multiplayer feedback (activity toasts, remote flashes) keeps running in selection
  mode — if someone deletes a tune out from under your selection, the toast explains
  the row (and selection count) dropping.

## B. Selecting

- Tapping a tune row toggles selection (replaces the normal row-action popup while in
  selection mode). Non-contiguous selections OK. Tapping a seam still moves the
  cursor and never alters the selection.
- Selected rows: translucent accent wash (~18%) + 1.5px accent inset ring + ✓ badge
  where the ⓘ button normally sits. Theme-variable based (works in dark mode).
- **Shift-click range select** (desktop): the last-tapped row is the anchor;
  shift-click selects everything between anchor and target inclusive (across breaks).
  Anchor resets when the selection empties.
- **Select all / None** quiet-text row pinned directly under the filter bar, only in
  selection mode. With filter text active, "Select all" = all *visible* (matching)
  tunes; "None" always clears everything.
- Temp / resolving / queued-offline / removing rows are **not selectable** (no settled
  server id → no bulk op could address them).
- Remote deletion of a selected tune silently drops it from the selection. Remote
  *moves* don't affect selection (ids are stable).
- **Filter composition**: selection mode and the pull-down filter compose. Selection
  persists across filter changes/clears. Copy/Delete/Assign act on selected ids
  regardless of visibility. **Positional** actions (grab bars, Paste) are unavailable
  while filter text is active (no seams exist in searchMode); they return when the
  filter clears, selection intact.

## C. Bottom bar (selection mode)

`"N selected" · Copy · Paste · Delete · Assign · Done` (view mode: Copy · Done).
Copy/Delete/Assign disabled at zero selection. Delete uses the danger red. Paste is
dimmed-but-tappable when the internal clipboard is empty (see E). Done exits.

### Keyboard shortcuts (selection mode only, focus not in an input)

Cmd/Ctrl+C copy · Cmd/Ctrl+V paste · Delete/Backspace bulk delete ·
Cmd/Ctrl+A select all (filter-aware) · Esc exit. No Cmd+X (drag is the honest move
tool; cut+paste would mint new record ids). No shortcut to *enter* selection mode.

## D. Copy / Paste (old-logger clipboard compatible)

**Copy** (any selection, incl. non-contiguous; groups by set):
- Internal rich clipboard (in-memory): array of sets of `{tune_id, name, tune_type}`.
- System clipboard: **plain text** — one line per set (sets with ≥1 selected member),
  selected tune names comma-separated. Exactly the old pill logger's format
  (`pillSelection.ts` copySelectedPills), so old-logger paste, notes apps, etc. work.
- Copy never touches the server; clipboards are not multiplayer state.

**Paste** (edit-mode selection mode, filter clear; targets the active cursor seam,
which always exists — defaults to `end`):
1. Read system clipboard text. If byte-identical to the plain text of our last Copy →
   the clipboard wasn't replaced → paste the **internal rich data** (explicit tune_id
   links survive; improvement over the old logger, which re-matches even its own copies).
2. Else if it parses as a JSON array → old-logger pill format: map
   `{tuneId, tuneName}` → `add_tune {tune_id, name}`, line structure → `set_break`s.
3. Else plain text: lines = sets, commas = tunes → `add_tune` by name; the server's
   existing matcher links what it can (same as typing the names).
- Paste = a sequence of ordinary `add_tune` + `set_break` ops anchored at the seam —
  to other clients it looks like fast logging. Splice semantics follow the same weld
  law as move (F): breaks between pasted sets are recreated; edges weld unless the
  target is an inter-set seam.
- **Starter attribution does NOT travel** through copy/paste (pasted tunes are new
  performance records; preserving attribution is what move is for).
- Nothing usable in the clipboard → non-destructive notice ("Nothing to paste").

## E. Bulk delete + undo (new ops: `remove_tunes`, `restore_tunes`)

- Delete fires ONE atomic `remove_tunes` op `{record_ids}` — a loop over the existing
  single-remove soft-tombstone logic in one transaction, one event, one remote toast.
- Client shows "Deleted N tunes — **Undo**" toast (~8s). Undo sends `restore_tunes`
  `{record_ids}` → flips `deleted` back on ids still tombstoned (idempotent wrt a
  concurrent individual delete). Tombstones keep their `order_position`, so restore
  reappears exactly in place. Both stream to everyone; no confirm dialog.
- **Direction note**: this is deliberately the first brick of a general undo pattern —
  ops declare inverse ops (delete↔restore, move↔move-back). No undo stack yet.

## F. Move (drag) — new op `move_tunes`

### Interaction
- Grab bar on the right edge of every tune row (~44px touch zone, ⠿ glyph), rendered
  only in edit-mode selection mode with no filter active. `touch-action:none` on the
  handle only — handle drags immediately (no long-press); rest of the row scrolls.
- Pointer events (down → setPointerCapture → move → up), NOT HTML5 DnD (unusable on
  mobile). ~6px slop before lift.
- **What drags**: (1) grabbed row selected + in a contiguous run of selected tunes →
  the whole run (contiguity is over the tune sequence; intervening BREAKS don't
  interrupt a run and travel with it). (2) grabbed row selected but run is just
  itself → that row. (3) grabbed row NOT selected → just that row; the existing
  selection is completely untouched (no auto-select side effects).
- Ghost follows the pointer: single row shows the name; multi shows "6 tunes · 2 sets".
  Source rows dim in place.
- **Drop zones** = existing seams; nearest eligible seam to pointer-y lights up and
  **thickens** (2px → ~6px accent-yellow bar, ~120ms ease). Other eligible seams show
  faint dashes during the drag. Ineligible (no-op) = seams interior to or immediately
  bounding the dragged block. Hit-testing by y-interval, not elementFromPoint.
- Autoscroll within ~48px of list top/bottom edges, speed proportional to proximity.
- Cancel: pointercancel / Esc / release with no eligible seam → settle back, no op.
- Drop: optimistic local reorder via fracindex `generateBetween` (same exclude-the-
  block pred/succ rule as the server), then ONE `move_tunes` op. The landing seam
  becomes the active cursor seam. Selection unchanged; still in selection mode.

### Server semantics (`move_tunes {record_ids, after_record_id|before_record_id|null,
new_set: bool}`)
- Validates all ids are live tunes of this instance; **re-sorts the block by current
  order_position** (never trusts client order — stale/offline clients can't scramble).
  If the block went non-contiguous server-side, moved rows re-pack contiguously at the
  destination in current relative order; interlopers stay behind. Deterministic.
- **Interior breaks travel**: any break record positioned between the first and last
  moved tune moves with the block (client sends only tune ids). 14 tunes in 4 sets
  dragged to the start is still 14 tunes in 4 sets.
- **Weld law** (one rule everywhere): breaks move with the block; whatever becomes
  adjacent — at the source gap or at the block's edges at the destination — merges.
  - Intra-set seam drop of `[A B | C D]` into `[P Q ⌄ R S]` → `[P Q A B] | [C D R S]`.
  - Inter-set seam / closed-end drop (`new_set: true`): block lands as its own set(s);
    the server supplies the boundary break(s) needed so both neighbors stay separated
    — atomically in the same transaction (never a separate client-chained op).
  - Source remnants merging (took the tail of set A + all of set B → A-front and
    B-successor join) is accepted; one Split tap undoes it if unwanted.
- **Cleanup invariant**: after any move, no empty sets — back-to-back/leading/trailing
  orphan breaks created by the move are deleted in the same transaction.
- **Fractional index care** (see also §C of 024): destination pred/succ are computed
  EXCLUDING the moving rows (else keys interleave with about-to-vacate positions);
  N keys are generated sequentially (`k1=between(pred,succ)`, `k2=between(k1,succ)`…);
  tombstoned rows still occupy positions (don't filter deleted from neighbor scans —
  matches `_position_for`); anchor inside the block → deterministic rejection;
  vanished anchor → degrade to append (matches add_tune §C; offline replay stays
  applicable, reconcile machinery covers the surprise); anchors remap via tempToReal.
  No uniqueness constraint exists on (instance, order_position) — collisions would be
  a SILENT ordering bug, hence the exclusion rule above. The add_tune concurrency
  race (no FOR UPDATE on neighbor scans) is inherited unchanged; out of scope.
- **`started_by` is NEVER touched by a move.** Per-tune values are durable user
  claims; the set-level starter is *derived* (first non-null in the set — existing
  `setStarterName` rule). A misdrop into another set then re-drag-out loses nothing.
  Only explicit acts stamp: the set tray picker and bulk Assign. (The old save path's
  majority-propagation reading mixed sets differently is pre-existing; not our bug.)
- Event carries all reselected changed records (moved tunes, moved/created/deleted
  breaks) — one event, one remote application, one toast ("Sarah moved 6 tunes").

## G. Assign (bulk starter)

- Enabled at ≥1 selected. Opens the existing starter-picker UI (filter box, checked-in
  attendees, "— Clear —", "＋ Add a player") as a modal.
- Fires one existing `attribute_set_starter` op per **set containing ≥1 selected tune**
  (anchored on that set's first tune id). Stamps EVERY tune in each affected set —
  selecting one tune from a set assigns the whole set (started_by means the set).
- Afterward: modal closes, selection KEPT, still in selection mode, notice
  "Assigned N sets to X" (cheap to correct a mis-pick).

## H. Multiplayer summary

Everything mutating is an op → session_event → SSE broadcast → `byId` application:
- `move_tunes`, `remove_tunes`, `restore_tunes`: new op types → new cases in the
  client apply-event switch + activity toast texts. Remote flash on arrived blocks.
- Paste/Assign reuse existing op types — zero new remote handling.
- Offline: all queue in IndexedDB and replay through the reconcile machinery.

## I. Tests (red/green TDD)

1. **pytest** (`tests/integration/test_live_logging_ops.py` pattern): `move_tunes` —
   within set, across sets, inter-seam `new_set` with break creation, multi-set block
   with interior breaks, source-remnant merge + orphan-break cleanup, anchor-inside-
   block rejected, vanished anchor → append, server re-sorts stale client order,
   started_by untouched, idempotent replay. `remove_tunes` — bulk tombstone, partially
   already-deleted, atomicity. `restore_tunes` — round-trip, concurrent-delete
   idempotency, order preserved.
2. **Vitest** (pure helpers in `frontend/src/logstate.js` / new `selection.js`):
   contiguous-run computation (across breaks), eligible-drop-seam computation,
   optimistic block fracindex assignment (exclude-block rule), clipboard serialization
   (records → lines/commas) and paste parsing (3-case resolution), select-all-under-
   filter, shift-range computation.
3. **Playwright** (`e2e/live/`): enter/exit both entry points; tap/shift/all/none
   selection; Copy → Paste at a seam (assert clipboard text format); bulk Delete →
   Undo → restore; Assign via modal; mouse drag on grab bar (assert seam thickening +
   final order); filter+selection composition; view-mode copy-only bar; two-context
   multiplayer (second context sees move/delete/assign via SSE + toasts); mobile
   viewport variant of select→drag→drop.

## Out of scope

Full undo stack (direction noted in E); cut; view-mode paste/delete/assign; rebalancing
fractional indexes; fixing the add_tune neighbor-scan race; carrying starter through
paste; old-logger UI changes of any kind.
