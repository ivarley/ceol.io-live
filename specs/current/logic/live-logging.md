# Live Logging (Feature 024)

Real-time, multi-user session logging screen — the production build of the
[021 prototype](../../changes/021-simplified-session-screen.md). Multiple people log the same session instance at
once and see each other's changes live, with no explicit "save". This is the **new live
logger**, distinct from the older single-user bulk-save desktop logger documented in
[Session Logging UI](../ui/session-logging.md).

**Status**: Phases 0–2 built & validated (walking skeleton → full op vocabulary + schema
delta → presence/typing). Phase 3 (offline / IndexedDB / service worker) is in progress.
The audio socket is documented but **not implemented** (out of scope here).

Full design and rationale: [`specs/changes/024-live-logging-architecture.md`](../../changes/024-live-logging-architecture.md).

## Architecture

Two processes, split by direction of data flow (§A4):

- **Flask app (`ceol-io`)** — the sync, server-authoritative **referee**. Owns *all*
  writes. Handles the upstream `POST` ops and serves the screen shell + bootstrap/search
  endpoints.
- **Streaming service (`ceol-io-streaming`)** — a separate async Python sidecar
  (Starlette + asyncpg, `streaming/service.py`), mirroring the abc-renderer sidecar
  pattern. Holds long-lived **SSE** connections and is downstream fan-out **only**.

```
client EventSource  ──SSE──>  streaming service
                                 ↑  LISTEN session_instance_<id>
client  ──POST op──>  Flask referee  ──pg_notify(id only)──>  Postgres
                                 │  (event row written in same txn)
                                 └──> streaming re-reads session_event row, pushes to subscribers
```

- **Transport** (§A3): SSE downstream, plain `POST` upstream. No WebSockets, no polling.
- **Fan-out** (§A4): Postgres `LISTEN/NOTIFY` (no Redis). The Flask referee appends a
  `session_event` row in the same transaction as the mutation, then
  `pg_notify('session_instance_<id>', event_id)`; the streaming service re-reads that row
  by id and pushes it.
- **Two connections, not one** (§A5): the SSE event stream and the upstream op POSTs are
  independent — the screen keeps reading even while a write is in flight.
- **Auth** (§D, §H): reuses the existing web stack — the Flask-Login session cookie
  (shared across subdomains so the sidecar receives it) **or** a bearer token (a
  `user_session` id, issued at `POST /api/live/token` — the native-client hedge). Both
  resolve to a `user_id`. Logging is flat: any authenticated user can log.

## Source of truth & the event feed (§B)

- `session_instance_tune` stays the **canonical current state**.
- `session_event` is an append-only, per-instance **delivery/replay log**. Its
  `event_id` (BIGSERIAL) doubles as the SSE `Last-Event-ID` cursor for gap recovery /
  catch-up. This is *not* an audit table — see [History](../data/history.md).

## Operation vocabulary (§C)

All writes are incremental, intent-based ops `POST`ed to
`/api/live/instances/<id>/ops` and refereed by `live_op` in `live_logging_routes.py`:

`add_tune`, `remove_tune` (soft tombstone), `change_tune`, `set_confidence`, `set_break`,
`attribute_set_starter`, `edit_notes`, `attendance_add` / `attendance_remove` /
`attendance_create_person`, `mark_complete` / `mark_incomplete`.

Each op carries a client-generated `op_id` (UUID) for idempotent retry. A rejected op
returns `{rejected, reason}` rather than throwing (§E).

### Repertoire enrollment (spec 025)

Logging a **linked** tune enrolls it into the session's repertoire (`session_tune`),
mirroring the old logger's save path. `_enroll_session_tune` (`live_logging_routes.py`)
runs an idempotent `INSERT … ON CONFLICT (session_id, tune_id) DO NOTHING` (+ history)
from `add_tune` (on the final linked record) and from `change_tune` (on a relink to a new
`tune_id`). **Not** enrolled: unlinked rows (`tune_id NULL`), `break` rows, corroborations
(the original add already enrolled), and merged/redirect tunes (`tune.redirect_to_tune_id`
set). This keeps the fast-match vocabulary, "in session" flags, and tune-list views
complete. Backfill for pre-fix gaps: `scripts/backfill_025_session_tune_enrollment.py`.

## Presence & typing (§F, ephemeral)

Presence and typing indicators are **in-memory in the streaming service and never
persisted** — they ride the SSE stream (typing signals are `POST`ed to
`/live/instances/<id>/typing`). Per-person palette **color** *is* persisted, but in its
own `session_logger_color` table keyed by `(session_id, person_id)` so a casual logger
doesn't get inflated into a member/attendee. (The original `session_instance_person.arrival_seq`
column was superseded by this table and is now unused.)

## Local vocabulary cache (§G, migration 025)

The screen ships each client a "local vocabulary" (`GET /api/live/instances/<id>/vocabulary`)
it indexes for instant, zero-network exact-match logging. Two tiers, both leader-tunable
from the session admin **Local Cache** tab: `session.live_cache_session_limit` (N — this
session's own top tunes) and `session.live_cache_global_limit` (M — globally popular
tunes not already in N). Defaults 200 / 25, mirroring the `LOCAL_VOCAB_*` fallbacks in
`live_logging_routes.py`.

## Endpoints

**Flask referee / shell** (registered in `app.py`, handlers in `live_logging_routes.py`;
screen shell in `web_routes.py:live_logging_screen`):

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/live/instances/<id>` | Svelte screen shell (`templates/live_logging.html`) |
| GET  | `/live/sw.js` | Service worker (scoped to `/live/`) |
| GET  | `/api/live/instances/<id>/bootstrap` | Initial snapshot |
| GET  | `/api/live/instances/<id>/vocabulary` | Local-cache vocabulary (N + M) |
| POST | `/api/live/instances/<id>/ops` | Referee op endpoint (all writes) |
| POST | `/api/live/token` | Issue bearer token (`user_session` id) |
| GET  | `/api/live/instances/<id>/people` `…/people/search` | Attendee lookups |
| GET  | `/api/live/instances/<id>/tune/<tune_id>` `…/match` `…/deep-search` `…/incipit/<tune_id>` | Tune detail / linking / search / ABC |

**Streaming sidecar** (`streaming/service.py`):

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Health check |
| GET  | `/live/instances/<id>/events` | SSE stream (downstream fan-out + presence) |
| POST | `/live/instances/<id>/typing` | Ephemeral typing signal |

## Frontend (§H)

Svelte 5 + Vite PWA, built to a self-contained bundle under `static/live/`
(`app.js` / `app.css`) and isolated to this screen (not the base Bootstrap layout).
Source in `frontend/` (`frontend/src`). The shell template passes `session_instance_id`,
`current_person`, and `STREAMING_BASE_URL` to the bundle, which then fetches the bootstrap
snapshot and opens the SSE stream.

**In-log filter (pull-down search).** A filter box that lives as the first child of the
scrolling list, hidden above the fold and revealed by scrolling to the very top (no gesture
handling — the list keeps a `.sets-body { min-height: 100% }` so it always overflows enough
to tuck the bar behind the header, even for a short log; the app nudges scroll past it once
on first paint). Typing filters live, per keystroke: only sets containing a tune whose
**name** matches survive (`displaySegments`), and the matched substring is highlighted in
orange (reusing `suggestionParts`). It is **orthogonal to view/edit mode** — a `searchMode`
flag separate from `mode`, so it works in view, in edit, and on **completed** logs, and
never calls `setMode`/reconnects the stream. While active, all editing chrome is hidden
(`canEdit = !viewing && !searchMode` gates the seams/row-actions/composer) and the dock
shows a single **"Done Searching"** button that clears the filter and re-hides the bar. All
in `App.svelte`; no backend involvement (it filters the already-loaded `byId` records).

**Desktop two-pane layout (spec 028).** At viewport widths ≥ 900px (`winW` via
`<svelte:window bind:innerWidth>`, `main.wide`), the mobile single column becomes a CSS grid:
the log stays in the center column and a persistent right pane (`SidePane.svelte`, 360px)
hosts the "likely next tune" suggestion card plus always-visible tune search — grid areas over
the existing children, no DOM restructuring; `.sets` and `.sidepane` scroll independently and
the dock stays pinned. Below 900px the pane never mounts and the phone layout is unchanged.
The deep-search body (name/ABC catalog search, thesession.org remote search, paste-URL
import — specs 021 §D/026) is extracted into a shared **`TuneSearch.svelte`** rendered by
both the mobile full-screen modal (`variant="modal"`) and the pane (`variant="pane"`); it
owns its search state and calls back on every terminal action via a single
`onAdd(payload, name)` → `App.logTune` (clear composer, `addOptimistic` at the cursor,
refocus). In read-only View mode the pane still renders and search stays browsable; a pick
opens a confirm dialog ("Switch to editing?") that flips to edit mode, logs the tune, and
clears the pane search (same end state as a direct edit-mode add); cancelling keeps the
search. Reading never mutates silently (complete logs get a notice instead — un-complete
from the header first).

**Keyboard nav (spec 028).** A window `keydown` handler (`onWinKey`) plus per-field handlers
give three behaviors keyed off *what has focus*:

- **Type-ahead lists own the arrows when their field is focused.** In the composer, ArrowUp/Down
  move a highlight (`composerHl`) through `composerNavItems` (the pinned suggestion + results, in
  the column-reverse list's visual bottom-to-top order); Enter picks the highlighted row (else
  falls back to the suggestion / commit). In `TuneSearch` (pane *or* modal), ArrowUp/Down move
  `hl` through the result cards and Enter picks the highlighted card. The focused field
  `preventDefault`s so the window handler never double-acts; both expose the highlight via
  `aria-activedescendant` (combobox pattern), styled `.hl`.
- **Escape blurs** whatever field is focused (unless a more specific handler already claimed it —
  the modal closes, a resolving placeholder cancels).
- **With nothing focused ("cursor mode"), the arrows/Enter/Space drive the insertion cursor.**
  ArrowUp/Down step it one slot through `computeCursorSlots(displaySegments, endIsOpen, …)` (pure,
  in `logstate.js`) — the ordered list of every rendered seam (set starts, after-tune seams,
  between-set new-set seams, the end). **Enter** runs the seam's action via `seamActionFor`
  (also pure): a between-sets seam **joins** the two sets, an intra-set after-tune seam **splits**
  there — matching the "Join"/"Split" pills. **Space** drops back into the tune-entry box.
  `moveCursor` deliberately does *not* refocus the composer, so successive arrows keep stepping;
  typing or Space refocuses, Escape blurs.
- **Split/join hold the cursor in place** (`holdCursor`, not `setCursor` — no jump to the end,
  no composer focus). The seam stays put and its mode flips: after a split the held spot is now
  the new between-sets seam (Enter/tap Joins it back); after a join it's the now-intra-set seam
  (Enter/tap Splits it back) — an exact toggle. This is the same for the mouse/touch pills, so
  on mobile the pill just flips Split↔Join in place.
- **Enter on the live yellow end seam ends the set** (`activeSeam === 'end' && endIsOpen` → the
  same `endSet` the "End set" button calls). The closed-end "new set" white line has no action.

**Text-box recall history (spec 028).** The filter box and the search box each keep a page-local
MRU history (`filterHist` in App; `searchHist` in App, `$state` so it stays live across the pane
and modal `TuneSearch` instances that share it via a prop). A term is remembered on an 800ms
idle-debounce after typing (plus on a pick, for search) — so history holds terms you settled on,
not every keystroke (`rememberInHistory`, MRU-dedup). **ArrowUp** recalls older entries, **ArrowDown**
newer (past the newest → empty draft), via the pure `historyStep`. In the filter box (no result
list) the arrows always drive history; **ArrowDown on an empty, non-navigating filter** instead
exits to the top seam. In the search box, ArrowUp recalls only when the box is **empty** (a typed
query's arrows walk the result cards); each recall **fires the search** so the results show
immediately, and `histPos` stays set so further arrows keep cycling. Enter then picks the top/
highlighted result (a recalled query mid-load never falls through to "log as-is").
- **Mode transitions knit the three zones (filter box ↕ cursor ↕ tune-entry box).** Stepping the
  cursor off the **bottom** slot (ArrowDown at the end) focuses the tune-entry box; off the **top**
  seam (ArrowUp) focuses the pull-down filter box. Conversely, ArrowUp in an **empty** tune-entry
  box drops onto the cursor line. **"/"** anywhere (outside a text field) jumps to the search box —
  the persistent pane when wide, else the deep-search modal. Typing **"/" as the first character
  in the (empty) tune-entry box** jumps there too; once the box has text, "/" is literal.

Cursor mode is edit-only (`canEdit`); "/" works in any mode (search is browsable while reading).
The **Log button is disabled while the composer is empty**; **ArrowRight from an empty composer**
hops focus to the "End set" button when it's showing (open set at the live end).

Deferred to later phases: multi-select + copy/paste of sets, reorder, and the full
`store.svelte.js` extraction
([spec 028](../../changes/inprogress/028-desktop-two-pane-logger.md)).

## Schema delta (§I)

See [Schema Reference](../data/schema.md) and [Session Model](../data/session-model.md).
Built migrations: `schema/024_session_event.sql`, `schema/024_live_logging_delta.sql`,
`schema/025_session_local_cache_limits.sql`.

- **New** `session_event` (append-only feed; `event_id`, `op_id`, `op_type`, `payload` JSONB).
- **New** `corroboration` (per-user assertions about a tune record; keyed `(record_id, user_id)`).
- **New** `session_logger_color` (permanent per-session palette color).
- **`session_instance_tune` +cols**: `source`, `confidence`, `played_start`/`played_end`
  (audio-only, nullable), `logged_timestamp`, `client_device_id`, `deleted` (tombstone).
- **`session` +cols**: `live_cache_session_limit`, `live_cache_global_limit`.

## Deployment

`ceol-io-streaming` web service in `render.yaml`
(`uvicorn streaming.service:app`). Flask reaches it via the `STREAMING_BASE_URL` env var;
the session cookie is shared across subdomains (`SESSION_COOKIE_DOMAIN`) so the sidecar
authenticates the SSE connection.

## Related

- [Spec 024](../../changes/024-live-logging-architecture.md) - Full architecture & phases
- [Session Logging UI](../ui/session-logging.md) - The older single-user bulk-save logger
- [Session Model](../data/session-model.md) - Underlying tune-log tables
- [History](../data/history.md) - Why `session_event` is not an audit table
