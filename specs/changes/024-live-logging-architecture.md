# 024: Live Logging Architecture (the real build of 021)

**Date:** 2026-06-21
**Status:** Proposed — resolves the §M technical agenda of
[021-simplified-session-screen.md](021-simplified-session-screen.md)
**Related:** [021](021-simplified-session-screen.md) (UX design + prototype),
[022](022-session-audio-recording.md) (audio capture, Stage 1),
[023](complete/023-set-break-records.md) (set breaks as records — shipped),
[015-fractional-indexing.md](015-fractional-indexing.md)

## Purpose

Feature 021 designed the *interaction model* for a new live session-logging screen and
shipped a clickable prototype (`mockups/logging/`). Its §M listed eight unsolved
engineering questions; this spec resolves them and defines the real build. 021 remains
the UX design doc; this is the architecture + build plan. Audio is explicitly **not**
built here (see §Audio).

## North Star

The architecture assumes, from day one, **multiple distinct clients concurrently
contributing tunes and metadata to one shared session instance** — multiple human
loggers on different devices, and (later) an audio recognizer, all as **peer clients of
one server-authoritative API**. Getting concurrency right is the point of the exercise,
not a later bolt-on. This was a deliberate rejection of a "single-user first, add
collaboration later" architecture.

The build is sequenced (see §Phases) but the *architecture* is multi-user throughout.

---

## A. Sync Model

### A1. Incremental, eager, intent-based writes — no "save"

There is no save action and no bulk-array save. Every *definite intent* writes
immediately and incrementally as its own atomic operation. Mid-typing is ephemeral and
unwritten; the write happens at the moment of commitment (a tune is matched/committed, a
set ended, a row edited). The existing bulk `save_session_instance_tunes_ajax` is **not**
extended for this screen.

### A2. Server-authoritative referee on Postgres + fractional indexing — no CRDT library

There is always a server, so we do not need convergence-without-authority (the only thing
a CRDT buys that fractional indexing doesn't already give us). The ceol.io server is the
single referee: clients send intent-ops; the server applies them — assigning
`order_position`, running domain merge/conflict rules, persisting — then broadcasts the
authoritative result. The domain merge rules (§H30/§H31 of 021) are bespoke and built by
hand either way, so a generic CRDT would be pure overhead and a foreign runtime.

Local ops are **optimistic**: rendered immediately as pending, confirmed on server ack
(the §39 settle-flash).

### A3. Transport: SSE down, POST up

The two directions have opposite shapes, so they use different mechanisms:

- **Upstream (client → server): plain `POST`.** Each intent-op is a self-contained,
  idempotent request the server acks. No persistent socket needed; over HTTP keep-alive /
  HTTP/2 there is no per-message latency penalty versus WebSockets at our message rate.
- **Downstream (server → client): SSE.** A one-way `EventSource` stream carrying other
  clients' committed ops, presence, and typing. Native auto-reconnect + `Last-Event-ID`
  gives gap recovery for free — the same primitive the offline-replay story needs.

WebSockets were rejected (we don't need duplex; they add framing + worker complexity).
Polling was rejected (presence/typing would lag the poll interval).

### A4. Serving topology

The main Flask app stays **synchronous and unchanged** (all existing routes + the new
op-POST endpoints). A **separate Python async streaming service** (Starlette/FastAPI +
`asyncpg` + an SSE helper) holds the long-lived SSE connections — mirroring the existing
ABC-renderer-as-sidecar pattern. Python (not Node) so it reuses the Flask-Login
session-cookie validation and DB conventions.

Fan-out is **Postgres `LISTEN/NOTIFY`** — no Redis, no new infra. The op's transaction
issues `NOTIFY` on a per-instance channel carrying **only the `event_id`**; the streaming
service `LISTEN`s, re-reads the event row, and pushes to subscribed clients. Ephemeral
presence/typing live in the streaming service's **memory** (single instance for now;
horizontal scaling would reintroduce a cross-instance pub/sub need — fine for a long
time at this app's concurrency).

### A5. Two device connections, not one

Each logging device will eventually hold **two** long-lived server connections: the SSE
stream and (when audio ships) a streaming audio upload (022). Both multiplex over one
HTTP/2 connection browser-side; server-side they belong to the async streaming service,
not the sync app.

---

## B. Source of Truth & the Event Feed

`session_instance_tune` stays the **canonical current state** — so every existing read
path (view-a-session, stats, popularity, desktop logger, history) keeps working. Ops
apply as ordinary INSERT/UPDATE/DELETE against it.

Alongside it, a slim append-only **`session_event`** table is the *change feed*:

| Column | Notes |
|--------|-------|
| `event_id` | `BIGSERIAL PRIMARY KEY` — **globally** monotonic, doubles as the SSE `Last-Event-ID` cursor |
| `session_instance_id` | FK, indexed |
| `op_type` | the op |
| `payload` | `JSONB` |
| `created_by_user_id` | actor (audit) |
| `server_ts` | receipt time |

- **Write path:** in the *same transaction* as the mutation, append the event row and
  `NOTIFY`. Truth and feed cannot diverge.
- **Resume / catch-up (one path):** a reconnecting `EventSource` sends `Last-Event-ID: N`;
  the service replays `WHERE session_instance_id = X AND event_id > N ORDER BY event_id`,
  then goes live. Same code serves live gap-recovery and offline catch-up.
- **Distinct from audit history.** `session_event` is an ordered delivery/replay log;
  the existing `*_history` tables are permanent column-level audit. Kept separate.
- The only ordering with **domain** meaning is `order_position` (tune/break order).
  `event_id` is purely a delivery/resume cursor; mutation order is plumbing.
- Retention: keep for the instance's lifetime (a few hundred events); prune closed
  instances later if ever needed.

---

## C. Operation Vocabulary

Every op carries a client-generated **`op_id` (UUID)** — the universal idempotency key
(online and offline): a retried POST whose ack was lost is safely deduped.

**Tune ops**
- `add_tune` — relational anchor (`after_record_id` / `before_record_id`, or "append to
  open set") + tune ref (id or raw name) + source + (audio) confidence + `op_id` +
  `logged_timestamp` + `client_device_id`. **Server assigns `order_position`** and set
  membership.
- `remove_tune` — soft **tombstone** (`deleted=true`), not a hard delete (so undo restores
  the same identity, offline "Restore" works, and removal-beats-edit is representable).
- `change_tune` — **identity-preserving** relink / rename / unlink / key / setting on a
  stable `session_instance_tune_id`.
- `set_confidence` — generalizes Confirm (`→100/human-verified`); trivially invertible.

**Set ops** (per 023, breaks are `record_type='break'` records in `session_instance_tune`)
- `set_break` — insert/remove a positioned break record. End-set / Split / Join all reduce
  to placing or removing a break (incl. a trailing break = "open set closed").
- `attribute_set_starter` — `started_by_person_id` (stays per-tune; 023 chose records over
  a set entity).

**Instance-metadata ops** (ride the same per-instance feed): `edit_notes`,
`attendance_add` / `attendance_remove` / `attendance_create_person`, `mark_complete` /
`mark_incomplete`.

**Server-generated events** (in the feed, not client-submitted): `corroborate/merge`
(§H30 — collapse duplicate, credit earliest, bump confidence) and conflict notices (§E).

**Undo** is not a separate op category — it emits the **inverse op** as a new mutation
(`add`↔`remove`, `set_break`↔remove-break, `set_confidence(x)`→`set_confidence(prev)`).
A private undo *stack* is impossible under concurrency; compensating ops are just
well-ordered mutations the referee handles normally (§J40 4s toast = emit the inverse).

### Positioning rule (foundational)

**Ops carry relational anchors; the server computes the authoritative `order_position`;
the client's position is provisional (local render only).** This is what makes both live
concurrent inserts and offline mid-set inserts converge. Anchor fallback when a neighbor
was removed: surviving neighbor → enclosing set → best-effort append, mess made visible,
never dropped silently.

---

## D. Identity, Attribution & Permissions

- **`person` is the universal identity; `user_account` is a subset** (login + permission)
  that hangs off a person (`user_account.person_id` is NOT NULL UNIQUE). **Everything in
  the UI is person data** (names, initials, colors); a user_account is never surfaced.
- **Attribution = person; authorization = user.** Principle: **store a `user_id` for
  "who performed this action"** (the existing `created_by_user_id` / `last_modified_user_id`
  audit columns already do this — the logger's person is *derived*, not stored
  redundantly); **store a `person_id` only when the named person isn't necessarily the
  actor** (`started_by_person_id`; attendance). Audio attributes to the device-owner's
  person with `source='audio'`.
- **Permissions:** logging is already guarded only by `@login_required` today (no
  admin/regular check — verified). The new screen keeps that: **any authenticated user
  may log and edit any entry; flat collaborative editing; nothing on this screen is
  admin-gated** (notes, attendance, started-by, mark-complete included). Safety net =
  attribution + undo + conflict rules, not access control. (Session-*level* management —
  creating instances, regular/admin membership — stays admin, but this screen doesn't do
  it.)

---

## E. Conflict Resolution

Composes from the referee + soft-delete decisions; little new infra:

1. **Two concurrent edits to one row** → server serializes → **last-write-wins** (last to
   commit). Everyone gets the authoritative state via the feed.
2. **Removal beats a concurrent edit (§H31)** → an edit op targeting a `deleted=true` row
   is **rejected as a no-op**; removal stands.
3. **Notices** ("Sarah also changed this" / "...removed the tune you were editing") need
   **no per-recipient channel**: the affected client renders the notice from its **own
   op-ack** (which carries a rejection reason — `superseded_by`, `target_deleted`);
   observers just see the normal authoritative feed event. The only new surface is the
   op-POST "rejected + reason" response variant.

### Reconciliation doctrine — *predictability over cleverness*

When intent is ambiguous, prefer a deterministic, explainable rule a human can fix in two
taps over a heuristic that's usually-right-but-surprising. Three tiers:
1. **Hard invariants (never violated):** sets stay contiguous (never interleave tunes into
   someone else's set, §I37); identical inputs → identical order on every device.
2. **Known domain merges (attempted):** same tune/slot → corroborate; same-set variations
   → align where shared tunes make it unambiguous (naive append + manual cleanup is an
   acceptable fallback).
3. **Nonsense (made visible, never guessed):** two unrelated logs collide → append both as
   separate sets, surface the mess, make it cheap to clean by hand. Never silently pick or
   destroy.

**Online ordering is solved by serialization** (the referee's order *is* the truth, seen
by all within ~100ms). The genuinely hard cases are quarantined to **offline-reconnect**.

---

## F. Presence & Typing (ephemeral)

- Live entirely in the **streaming service's memory** — never DB, never `session_event`,
  never replayed. Ride the same SSE connection as distinct event types **without an
  `id:`** (so they don't advance `Last-Event-ID`; reconnect gets a fresh snapshot).
- **Upstream ephemeral signals POST directly to the streaming service** (not the main
  app/DB) — no durable write, no NOTIFY.
- **Presence ≡ an open authenticated SSE connection.** Connect → registered present;
  drop (detected via keepalive) → removed and broadcast. No explicit join/leave op. (This
  gives §I33 "others' presence drops when you go offline" for free.)
- **Typing = a position reservation**, stored as `{person, relative-anchor}` in
  `order_position` space, so it re-anchors (slides) when a tune is inserted at/before it.
  The service is authoritative for the 10s-inactivity timeout and clear-on-commit.

### Color & arrival

- Store **`arrival_seq INT`** (monotonic per-instance by first arrival) on
  `session_instance_person`, **not** a color — the UI infers color from the ordinal
  (`palette[seq mod N]`, wrap in the UI; palette changes need no migration). Distinct +
  stable for the instance's life; survives reconnects *and* streaming-service restarts.
- Claimed on first SSE connect via `INSERT … ON CONFLICT DO NOTHING` (lowest unused seq).
- **Attendance auto-marks `yes`** only when a person enters **edit mode** *and* the
  instance is within its live window + grace (reuse `active_session_manager`). Outside
  that, or in view-only mode, connecting touches nothing. A manual override exists
  ("logging, but not here in person"). Connecting alone never asserts attendance.

---

## G. Offline & Reconnect

- **Local store = IndexedDB**: (1) the op queue (pending ops), (2) a local snapshot of the
  instance, (3) the offline tune cache for matching — bounded, weighted toward **this
  session's tunes played more than once / recently**, then global-popular; a true miss
  falls back to "log unlinked, link later."
- **Offline changes are visible as queued** (§I34): inserts/edits "⏳ queued" (dashed);
  deletes "⏳ removing" (struck-through, with Restore). Pending states are
  **client-local only** — never server columns. The server stores only committed truth +
  the `deleted` tombstone.
- **Reconnect** replays the queue in offline order, each op idempotent by `op_id`, with
  **local→server ID remapping** (an offline tune inserted after another offline tune
  resolves its anchor once the first syncs). Placement follows the doctrine: your offline
  *sets* insert whole, by time, **never interleaved** (§I37); partial-overlap alignment is
  not built. Edits to rows that changed/vanished resolve per §E.
- **Reconnect outcome is a spectrum:**
  - Minor/clean → the lightweight "X synced, Y added while away" toast (§I36).
  - **Major divergence, or reconnecting after the instance is `log_complete`** → a
    dedicated **reconciliation review screen**: a set-by-set diff (matched / theirs-only /
    yours-new) walking the user through what to contribute. Common enough (someone logs a
    whole session offline, reconnects to find it already logged) to warrant real UI.
- No hard offline-duration guard; the queued count is surfaced (§I33 banner).

---

## H. Frontend

- **Clean-slate build on Svelte + Vite** — a self-contained bundle Flask serves, isolated
  to this screen. The prototype's `app.js` is a **reference only** (not ported); the
  desktop logger is untouched. Reactive stores map onto the model: server-truth records,
  the optimistic op queue, presence. (We deliberately did *not* reuse the existing
  TS/webpack desktop-logger code — it grew too complex — nor hand-roll rendering.)
- **Entry:** opt-in via a **"Use beta logger"** user setting; when on, the instance's log
  link routes here. Not a device-sniffed replacement.
- **Bootstrapping:** a thin Flask shell template inlines a bootstrap JSON snapshot
  (current person, instance metadata, initial segmented records, presence roster, SSE URL
  + `Last-Event-ID` high-water mark), then the client opens SSE for the delta.
- **Auth rides the existing Flask-Login session cookie** (same-origin) for both SSE and
  POSTs. The streaming service + op endpoints **also accept a bearer token** from the
  start (cheap insurance for a future true-native client; cookie remains the web path).
- **PWA:** Vite-PWA service worker — **shell assets cache-first, all dynamic routes (API,
  op-POST, SSE) network-only** (a SW must never cache/intercept the stream or queue).
  Installable manifest retained. Data lives in IndexedDB, not the SW cache.
- **Native shell deferred.** The iOS keyboard jump (021 §41) is provably unfixable in pure
  web (only a WKWebView that resizes the layout viewport fixes it). The beta ships PWA-only
  and accepts that floor. The op/event API is treated as a **versioned, documented
  contract** so any future client (incl. a WKWebView wrapper *or* true-native UI)
  implements against a stable surface — the expensive server architecture is
  native-agnostic by construction.

---

## I. Schema Delta (summary)

On `session_instance_tune` (canonical state; `record_type` already shipped in 023):
`source`, `confidence`, `played_start`, `played_end` (audio-only), `logged_timestamp`,
`client_device_id`, `deleted` tombstone.

New tables: `session_event` (§B); a tune **corroboration** child table
(`record_id, user_id, source, confidence, client_asserted_ts` — keyed by user, person
derived). On `session_instance_person`: `arrival_seq`.

Audio-only columns (`source`/`confidence`/`played_*`) are added now (nullable) so the
audio task plugs in without a later migration; human ops never write `played_*`.

---

## J. Audio — out of scope here (documented socket only)

Audio is a **separate future task**. This build does not implement the recorder or any
recognition. It only guarantees the socket:
- A recorder (driving 022's existing capture — **022's Stage-1 capture must be finished
  first**, a prerequisite for *that* task, not this build) is just another client.
- A recognizer (on-device *or* server — deferred; both are clients) POSTs `add_tune` /
  `set_break` ops with `source='audio'`, `confidence` (revisable; ≤70% → amber pill +
  Confirm/Edit row, §G26), and `played_start`/`played_end` sourced from 022's per-chunk
  wall-clock times. Audio can also end a set ("hears a pause", §G25) = a `set_break` op.
- Attribution is the device-owner's person; the 🎤 is a label, never its own identity.

---

## K. Build Phases

The architecture is multi-user throughout; phases are assembly/verification order. We
**derisk the novel infra first** (the streaming service + SSE + `LISTEN/NOTIFY` don't
exist in the codebase today) via a walking skeleton, then widen.

- **Phase 0 — Walking skeleton.** Implement *only* `add_tune`, through the entire real
  pipeline: Svelte `POST` → referee assigns position + writes `session_event` + `NOTIFY`
  (one txn) → streaming service `LISTEN` → SSE → **a second browser sees it live (~100ms)**.
  Proves the scariest, newest integration on day one; multi-user is real immediately.

  > **The streaming triangle is already spike-validated** (2026-06-21) against the real
  > `ceol_test` Postgres on the real stack (asyncpg + Starlette): one-txn insert+`pg_notify`,
  > id-only NOTIFY with row re-read, asyncpg `LISTEN` → SSE fan-out to already-connected
  > clients, and `Last-Event-ID` replay-then-live with correct dedupe. Reference impls (throwaway):
  > `spike/sse_spike_async.py` (real stack) and `spike/sse_spike.py` (threaded, has a browser UI).
  > Phase 0 turns that proven triangle into the real `session_event` table + `add_tune` endpoint
  > on sync-Flask, the streaming service with cookie **and** bearer-token auth, and the minimal
  > Svelte shell. Deps `asyncpg`/`starlette`/`uvicorn` were pip-installed into `venv` for the
  > spike but are **not yet pinned in requirements** — pin them when Phase 0 begins.
  >
  > **✅ Built & end-to-end validated (2026-06-21).** The full pipeline runs on the real stack:
  > - `schema/024_session_event.sql` (+ mirrored into `full_schema.sql`) — the `session_event` feed.
  > - `live_logging_routes.py` — the referee: `add_tune` op (one txn: `session_instance_tune` +
  >   `session_event` + `pg_notify`, server-assigned `order_position` via fractional indexing) and a
  >   `bootstrap` snapshot endpoint; both `@api_login_required`. Wired in `app.py`
  >   (`/api/live/instances/<id>/ops/add_tune`, `/bootstrap`, `/live/instances/<id>` screen).
  > - `streaming/service.py` — Starlette + asyncpg sidecar: per-instance `LISTEN session_instance_<id>`,
  >   `Last-Event-ID` (header **or** `?last_event_id=` query) replay-then-live, **cookie** auth (decodes
  >   the Flask-Login session cookie) **and** **bearer** auth (validates a `user_session` id), CORS for
  >   cross-origin `EventSource(withCredentials)`.
  > - `frontend/` — clean-slate Svelte 5 + Vite bundle → `static/live/`; thin shell
  >   `templates/live_logging.html`. Idempotent upsert by `session_instance_tune_id`.
  > - `requirements.txt` pins `asyncpg`/`starlette`/`uvicorn`; `render.yaml` adds the
  >   `ceol-io-streaming` web service + the frontend build step.
  > - E2E check `spike/test_phase0_e2e.py`: POST→referee→NOTIFY→SSE delivery in ~30ms; anon SSE 401;
  >   bearer auth + replay verified.
  >
  > **Run locally:** `venv/bin/python -m streaming.service` (sidecar, :8080) + `flask --app app run`
  > (:5001); build the client with `cd frontend && npm install && npm run build`; open
  > `/live/instances/<id>` in two browsers.
- **Phase 1 — Full op vocabulary + data delta.** The remaining ops, the schema columns,
  corroboration table, `arrival_seq`, `op_id` idempotency, token auth, the bootstrap shell.

  > **✅ Built & end-to-end validated (2026-06-21).**
  > - `schema/024_live_logging_delta.sql` (+ mirrored into `full_schema.sql`, `save_to_history`):
  >   `source`/`confidence`/`played_*`/`logged_timestamp`/`client_device_id`/`deleted` on
  >   `session_instance_tune`; `op_id` (UNIQUE) on `session_event`; new `corroboration` table;
  >   `arrival_seq` (UNIQUE per instance) on `session_instance_person`. `full_schema.sql`
  >   re-validated by a clean from-scratch load.
  > - `live_logging_routes.py` rewritten as a **generic op endpoint**
  >   (`POST /api/live/instances/<id>/ops`, body `{op_type, op_id, …}`) with a dispatch table,
  >   one-txn atomic apply, and **`op_id` idempotency** (cached-ack dedup + UNIQUE-violation race
  >   handling). Ops: `add_tune`, `remove_tune` (soft tombstone), `change_tune`
  >   (relink/rename/unlink/key/setting), `set_confidence` (+ records a corroboration),
  >   `attribute_set_starter`, `set_break` (insert/remove), `edit_notes`,
  >   `mark_complete`/`mark_incomplete`. Rejections return a `{rejected, reason}` ack (§E;
  >   `target_deleted` = removal-beats-edit). Bootstrap now returns segmented `sets`, notes,
  >   and completion state.
  > - Streaming service: all ops ride a single `event: op` (op_type folded into the data).
  > - `frontend/`: generic `sendOp`, single SSE handler dispatching by `op_type`, set-segmented
  >   render with per-tune remove/confirm + End-set controls.
  > - E2E `spike/test_phase1_e2e.py`: every op over SSE, op_id dedup (no double-apply), and
  >   removal-beats-edit rejection. Existing pytest suite unchanged (119 pre-existing failures,
  >   same with/without this work).
  >
  > **Phase 1 tail — also built & validated (2026-06-22):**
  > - **Attendance ops** `attendance_add` / `attendance_remove` / `attendance_create_person` —
  >   reuse the existing DB helpers (which carry the `active_session_manager` side effects); the
  >   attendance write commits on its own connection, then the feed event is appended (metadata,
  >   so the slight non-atomicity is fine; `op_id` still guards double-apply).
  > - **Name→tune matching + corroborate/merge detection** (§H30): `add_tune` resolves a typed
  >   name to a `tune_id` via the existing `find_matching_tune` (matching takes priority; tapping a
  >   typeahead result instead sends `tune_id` directly; ambiguous/unknown names stay unlinked).
  >   Then an append whose tune is already live in the open set collapses into the earliest row —
  >   identity = the resolved `tune_id` when linked, else an identical normalized raw name among
  >   the also-unlinked rows (so two people typing the same unmatched text still merge; mid-typing
  >   never hits the stream, so only committed entries collide). Records a corroboration, bumps
  >   confidence (two distinct corroborators → 100/verified), and emits a server-generated
  >   `corroborate` event via an op_type override instead of a duplicate row.
  > - **Bearer-token issuance**: `POST /api/live/token` (cookie-authed) mints a `user_session`-id
  >   bearer the streaming service already accepts — round-trip verified.
  > - E2E `spike/test_phase1_tail.py` covers all three.
  >
  > Genuinely out of Phase 1 (future): partial-overlap offline reconciliation, By-ABC search.
- **Phase 2 — Presence + typing + reconnect resume.** The ephemeral channel,
  color-from-`arrival_seq`, `Last-Event-ID` gap recovery, settle / go-to-end polish,
  conflict notices.
- **Phase 3 — Offline.** IndexedDB stores, service worker, queue + pending UI, reconnect
  replay + reconciliation + the post-completion review screen.

(Audio = separate task, after the above; gated on finishing 022.)

## Open / deferred (not blockers)

- Exact op/event JSON payload schemas (specified during Phase 0/1).
- Deep-search "By ABC" / filter tabs (021 §K) — reuse existing `/api/tunes/search` for the
  beta; By-ABC deferred.
- On-device vs server recognition; the recognizer itself (audio task).
- Native WKWebView wrapper; horizontal scaling of the streaming service (single instance
  suffices for now).
