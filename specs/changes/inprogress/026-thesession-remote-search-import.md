# 026: thesession.org Remote Search & Import (Live Logger)

## Purpose

Close a parity gap: the new live logger can't add a tune that exists on thesession.org but isn't
in our DB yet. Add two paths, both of which import the tune into the local catalog and log it
**linked**:

1. **On-demand remote search** in the deep-search "Find a tune" modal — when the within-system
   matches aren't what you want, run the *same* query against thesession.org.
2. **Top-level paste** — paste a thesession URL or tune ID straight into the tune box and it
   resolves + logs in place.

Depends on **025** (repertoire enrollment): because `_handle_add_tune` already enrolls linked
tunes into `session_tune` (`live_logging_routes.py:410`), an imported-then-logged tune enrolls
automatically — this spec needs no `session_tune` code of its own.

## Current state (verified)

- Deep-search modal (`App.svelte`, `deepOpen` ~2625) and `live_deep_search`
  (`live_logging_routes.py:988+`) search the **local** catalog only.
- Top-level tune box uses the **resolving-placeholder** machinery: `commit()` (`App.svelte:1333`)
  drops a pending row at the cursor, resolves it (unique match / disambiguate / unmatched), then
  settles.
- `add_tune` op → `_handle_add_tune` (`live_logging_routes.py:357`), dispatched via `HANDLERS`
  (654) in `live_op` (673); **idempotent by `op_id`** (dedup at 699 before the handler runs).
  It resolves a tune by `tune_id` (tap) or by `name` (typed → `find_matching_tune`), else logs
  unlinked. It already fetches `session_id` (367) and enrolls linked tunes (410).
- Offline: ops queue in IndexedDB and replay on reconnect via `flush()` (`App.svelte:1055`),
  serially in timestamp order.
- Import logic exists **only** in `link_tune_ajax` (`api_routes.py:3472+`): fetch
  `thesession.org/tunes/<id>?format=json`, INSERT `tune`, `cache_default_tune_setting` (434).
- thesession search precedent: `search_sessions_ajax` (`api_routes.py:2779`) proxies
  `sessions/search?q=&format=json`. The **tunes** search API (`tunes/search?q=&format=json`)
  supports both name and **ABC/incipit** queries (e.g. `q=fdd cAA` → "My Darling Asleep") and a
  `type=` filter; each hit carries only `id, name, alias, url, member, date, type` (no notation,
  no tunebook count).

---

## A. Backend — shared fetch + two importers (`api_routes.py` / `live_logging_routes.py`)

**As built** — the transaction model forced a split (see the box below). `api_routes.py` gains:

```python
class TuneImportError(Exception):
    """thesession.org import failed (404 / timeout / bad data). Carries an HTTP status."""
    def __init__(self, message, status=502):
        super().__init__(message); self.message = message; self.status = status

def _fetch_thesession_tune(tune_id):
    """GET tune #tune_id from thesession.org and return the validated JSON dict.
    Raises TuneImportError on 404 / non-200 / timeout / invalid payload. SHARED."""

def _import_tune_from_thesession(cur, tune_id, user_id):
    """Legacy path: _fetch + INSERT tune + save_to_history + cache_default_tune_setting
    (renders PNGs synchronously). Returns (name, tune_type)."""
```

`link_tune_ajax`'s inline import block (was `api_routes.py:3472-3534` + its `requests` `except`
handlers) is refactored to call `_import_tune_from_thesession`, preserving its existing alias /
`session_tune` / `session_instance_tune` writes and JSON error shape — legacy behavior unchanged.

> **Why two importers (not one shared with the op).** `cache_default_tune_setting` opens its
> **own** DB connection to insert `tune_setting` (FK → `tune`) and swallows its own errors. That
> only works when the `tune` row is already visible to a separate connection — true on the legacy
> path (no explicit transaction) but **false inside `live_op`'s `BEGIN`** (the new `tune` row is
> uncommitted, so a separate connection can't see it → the setting insert would silently FK-fail).
> So the live path uses its own in-transaction importer, `_import_tune_for_live`
> (`live_logging_routes.py`): it `_fetch`es, then INSERTs the `tune` **and** its default
> `tune_setting` (ABC only) on the **op's cursor**, and lets notation PNGs render **lazily** via
> `_ensure_incipit` on first view (the live logger already renders notation lazily everywhere).
> No image rendering happens inside the op, so the transaction isn't held open on the renderer.

## B. Backend — import folds into the `add_tune` op (`live_logging_routes.py`)

Extend `_handle_add_tune` with an optional `data['thesession_id']`. Resolution priority becomes
**thesession_id → tune_id → name**:

- `_parse_thesession_id` coerces `thesession_id` (int, numeric string, or a tunes URL) to an int.
  The "needs tune_id or name" guard now also accepts `thesession_id` (else a paste-only add is
  rejected); when `thesession_id` is present the name→tune matching is skipped.
- Look up the local `tune`:
  - **Exists, not a redirect** → use it (`tune_id = thesession_id`).
  - **Is a redirect** (`redirect_to_tune_id` set) → follow to the canonical id and use that (see
    Open decisions — alternative is to reject).
  - **Not local** → `_import_tune_for_live(cur, id, user_id)` inside the op txn (FK-safe against
    `session_instance_tune.tune_id → tune.tune_id`; see the box in §A for why this is a live-
    specific importer, not `_import_tune_from_thesession`). On success set `tune_id` + canonical
    `name`.
    - On `TuneImportError` (fake/deleted id, thesession down) → **do not fail the op**: fall
      through to logging **unlinked** with a placeholder name (`data.get('name')` or `f"#{id}"`),
      and include `import_failed: true` + `import_message` in the op response so the client settles
      the placeholder as an unmatched row (never interrupts).
- Then continue into the existing insert path. `session_id` is already fetched and the spec-025
  enrollment covers the imported tune — **no extra enrollment code**.

Idempotency: `live_op` dedups by `op_id` before dispatch, so a retried POST (e.g. lost ack after
a slow import) returns the cached event without re-importing (verified by test).

**Latency note:** this op POST does a thesession fetch synchronously (~0.3-1s); notation PNGs are
NOT rendered in the op (lazy, per §A). The client `sendOp` timeout is 10s (`client.js`); a rare
timeout re-queues the op, and the retry finds the tune already local and completes fast.

## C. Backend — thesession search proxy (online-only read)

New `GET /api/live/instances/<id>/thesession-search?q=&type=` (`api_login_required`), mirroring
`search_sessions_ajax` (`api_routes.py:2779`) but for `tunes/search?q=&format=json&perpage=N`.
Returns `{success, results:[{tune_id, name, alias, tune_type, url, on_list?, in_session?}]}`.
- Map `id → tune_id`, `type → tune_type` (title-cased to match local).
- Flag each result that is **already local** and/or **already in this session** (one query
  against `tune` + `session_tune`) so the client can dedup/annotate.
- Pass the modal's active `type` filter through, lowercased.
- Timeout / non-200 → `{success:false}` (client treats as empty). Register the route in `app.py`
  next to the other `/api/live/...` rules.

Results carry no notation or tunebook count, so remote cards show name/alias/type only.

## D. Frontend — `client.js`

- `thesessionSearch(config, q, type)` → GET the proxy; returns `[]` on any failure.
- Remote/paste adds send `thesession_id` (not `tune_id`) in the `add_tune` payload, plus an
  optimistic `name`/`tune_type` for the placeholder row; the server resolves the real `tune_id`.

## E. Frontend — deep-search modal (`App.svelte`, ~2625-2692)

- A **"Search on thesession.org"** button at the **end of the within-system results**. Shown in
  name/mixed **and** ABC modes (the API supports ABC search); **hidden when offline**. Runs only
  on explicit tap — never per keystroke.
- On tap: `thesessionSearch(deepQuery, deepType)`, render results in a **"From thesession.org"**
  section **below** the local results. **Dedup by tune_id:** drop remote hits whose `tune_id` is
  already in the local `deepResults` (leave them up top). Show `alias` on remote cards.
- Tap a remote card → close modal, `addOptimistic({ thesession_id: r.tune_id, name: r.name,
  tune_type: r.tune_type }, r.name)` at the cursor (identical placement to `pickDeep`). The op
  carries `thesession_id`; the server imports if needed; the optimistic row shows the known title
  and settles on ack.
- Inside that section, a **"Have a link? Paste a thesession.org URL or tune ID"** field → parse
  URL/ID → same `addOptimistic({ thesession_id })`.

## F. Frontend — top-level paste detection (`App.svelte`)

- Detect when the tune-box input is a thesession URL or bare numeric ID (regex). When detected,
  suppress normal name/ABC search and show a **single special result row** — "＋ Add … from
  thesession.org". Optionally pre-fetch the title to display it; if the fetch hasn't returned,
  the row shows `#<id>`.
- Tap the row, or press Enter, → fold into the existing resolving-placeholder flow: drop a pending
  row, send `add_tune{ thesession_id }`, settle **linked** on the op response, or **unmatched**
  if `import_failed`. Pressing Enter before any title pre-fetch returns still follows through
  (intent is clear).
- **Offline works for free:** the `add_tune{ thesession_id }` op simply queues and replays on
  reconnect via `flush()`, serially — the server imports at replay time, fake ids settle
  unmatched. The pending row shows `#<id>` until reconnect resolves it. No new offline machinery.

## G. Behavior summary (edge cases)

| Situation | Result |
|---|---|
| Remote pick / paste, tune not local | Server imports within the op, logs linked, enrolls repertoire (025) |
| Tune already local | Server links directly (no import) |
| Fake / deleted id | Op logs **unlinked** (`#id`), `import_failed` → unmatched row, no interrupt |
| Merged/redirect id | Follow to canonical and log it (Open decisions) |
| Offline paste | Op queues; reconnect `flush()` imports + settles serially |

---

## Files touched

- `api_routes.py` — extract `_import_tune_from_thesession` + `TuneImportError`; refactor
  `link_tune_ajax`.
- `live_logging_routes.py` — extend `_handle_add_tune` (thesession_id branch, reusing 025's
  session_id + enrollment); new `thesession-search` proxy endpoint.
- `app.py` — register the search proxy route.
- `frontend/src/client.js` — `thesessionSearch`; `thesession_id` in the add payload.
- `frontend/src/App.svelte` — modal button + "From thesession.org" section + paste field;
  top-level paste detection wired into the resolving-placeholder flow. (Rebuild `static/live/`.)
- Docs — `specs/current/logic/live-logging.md` (op vocabulary: `add_tune` gains `thesession_id`;
  new search endpoint; offline note) and `specs/current/logic/external-apis.md` (`tunes/search`
  + `tunes/<id>` consumers via the shared helper).

## Verification

- **Op-level (integration):** `add_tune{thesession_id}` for a tune not local → `tune` row +
  cached notation created, `session_instance_tune` linked, `session_tune` enrolled; same op
  retried by `op_id` → no duplicate/import; `thesession_id` for a fake id → unlinked row +
  `import_failed`; redirect id → canonical logged; already-local id → linked, no re-import.
- **Search proxy:** returns thesession hits with `on_list`/`in_session` flags; ABC query returns
  incipit matches; type filter honored.
- **Frontend (e2e):** modal "Search on thesession.org" appends a deduped remote section; tapping a
  card logs the tune linked at the cursor and it appears in a second client via SSE; pasting a URL
  in the tune box drops a pending row that settles linked; a fake URL settles unmatched without
  interrupting; offline paste stays pending and resolves on reconnect.
- **Regression:** old logger's link-tune still imports (shared helper); `make test`.

## Open decisions

- **Merged/redirect pasted id:** follow to canonical and log it (recommended, friendlier for
  paste) vs. reject with a message like legacy `link_tune`.
- **Top-level title pre-fetch:** whether to pre-resolve the title for the special row (needs a
  by-id lookup that hits thesession for non-local tunes) or just show `#<id>` until the op settles.
  Pre-fetch is optional polish; the op response is authoritative either way.
- `perpage` for the search proxy (suggest 20-30).
