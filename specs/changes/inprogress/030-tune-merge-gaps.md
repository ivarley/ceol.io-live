# Spec 030: Tune Merge Gaps — Name Preservation, New Tables, Read-Path Redirects

## Overview

Feature 016 built the tune-merge mechanism: `tune.redirect_to_tune_id` tombstone,
the `merge_tune_ids()` stored procedure, and the admin preview/confirm UI at
`/admin/tunes/merge`. This spec fixes what 016 doesn't cover — tables added since
(`person_tune_instrument`, `recording_tune_segment`), name/alias preservation so a
merge doesn't rename tunes out from under people, and the read-path/live behavior
for permalinks and already-open browser windows.

## Motivating example

A tune known locally as "Sonny Riordan's" was merged on thesession.org into
"The Blue Ribbon" (which lists Sonny Riordan's as an alternate title). After
running the local merge, the tune vanished from the user's tunebook *by name* —
it was now filed under "The Blue Ribbon", a name they'd never used. The identity
should migrate; the familiar name should stay.

## Decisions (interview outcomes)

1. **Keep the 016 design.** Tombstone + stored proc + admin preview/confirm UI
   stay as-is; this spec fills gaps.
2. **Name preservation.** When the old and new tunes' canonical names differ,
   every *migrated* row that has no existing name override gets the old tune's
   name written into its override slot:
   - `person_tune.name_alias`
   - `session_tune.alias`
   - `session_instance_tune.name`
   Rows that already have an override keep it untouched. Additionally, the old
   tune's name is inserted into `session_tune_alias` (against the new tune_id)
   for every session that had the old tune, skipping duplicates
   (`UNIQUE (session_id, alias)`).
3. **Conflict merges: survivor wins entirely.** When the target row already
   exists (person or session already has the new tune), the old row is deleted
   and nothing is inherited — no alias copy, and the old row's
   `person_tune_instrument` overrides are dropped with it (matching the existing
   policy where the survivor's learn_status/notes/heard_count win wholesale).
4. **New table coverage.**
   - `person_tune_instrument`: composite FK to `person_tune(person_id, tune_id)`
     gains `ON UPDATE CASCADE` (today the proc's `UPDATE person_tune SET tune_id`
     throws an FK violation when override rows exist). Clean moves carry the
     overrides along; conflict deletes cascade them away (survivor wins).
   - `recording_tune_segment`: plain `UPDATE ... SET tune_id = new` (no unique
     constraints involved).
   - Both appear in preview counts and the result JSON.
5. **Permalinks (read paths).**
   - Path routes `/sessions/<path>/tunes/<old_id>` and `/admin/tunes/<old_id>`
     issue an HTTP **301** to the same URL with the new id.
   - Read APIs the tune-detail modal fetches (`GET /api/sessions/<path>/tunes/<id>`,
     `GET /api/sessions/<path>/<date_or_id>/tunes/<id>`, `GET /api/admin/tunes/<id>`)
     **follow the redirect server-side** and return the new tune's data plus
     `"redirected_from": <old_id>`. The client fixes the URL bar via
     `replaceState` and shows a small "this tune was merged into X" notice.
   - `/my-tunes?ptid=` links use `person_tune_id`, which survives clean moves.
     A ptid deleted by a conflict merge degrades gracefully (notice, param
     dropped) instead of erroring.
6. **Open windows.**
   - **Live logger: real push.** After the merge commits, the admin endpoint
     emits synthetic `change_tune` events (via the existing `emit_change_tune`
     helper) into `session_event` for each affected non-deleted
     `session_instance_tune` row — but only for instances with a `session_event`
     in the last 24 hours (instances that plausibly have SSE listeners; emitting
     for all history would bloat the feed). Clients already handle `change_tune`
     from other users: the row relinks in place, display name intact.
   - **Everything else heals on next interaction** — no polling, no new channels.
7. **Stale writes remap.** Write ops referencing a redirected tune_id proceed
   transparently against the new id, with `remapped_from: <old_id>` noted in the
   response, instead of rejecting with `tune_redirected`-style errors. Rationale:
   after a merge, a stale-id write has exactly one sensible meaning, and offline
   op queues (my-tunes ops, live logger tail) replay hours later with nobody
   watching for an error dialog. Existing "already exists" idempotent handling
   composes with the remap. Sites converted:
   - `live_logging_routes._handle_add_tune` (direct `tune_id` from a stale
     typeahead cache; the `thesession_id` path already remaps)
   - `live_logging_routes._handle_change_tune` (relink to a stale id)
   - `api_routes.py` session-tune add (`~:3596`), bulk log save (`~:7498`),
     and the beta add-tune helper (`~:441`)
   - `api_person_tune_routes.py` add already remaps (kept as the model).
8. **Admin UX.** The preview step:
   - verifies the redirect against thesession.org — server-side
     `GET https://thesession.org/tunes/<old_id>` (no follow); confirmed if it
     redirects to `<new_id>`. Non-blocking: confirmed → green note; mismatch,
     no redirect, or network failure → prominent warning, admin may proceed
     (legitimate for local-only duplicates or merging ahead of thesession).
   - shows the new counts: instrument overrides moved/dropped, recording
     segments, and how many alias fills each table will get.
9. **No undo.** Preview/confirm + the thesession check are the guard rails;
   history tables (all mutations flow through existing triggers) are the
   recovery path. Un-tombstoning (`UPDATE tune SET redirect_to_tune_id = NULL`)
   is documented as a manual SQL escape hatch for "marked the wrong tune";
   it does not restore moved rows.

## Implementation map

| Piece | Where |
|-------|-------|
| FK `ON UPDATE CASCADE` + expanded `merge_tune_ids()` | `schema/030_tune_merge_gaps.sql`, mirrored in `schema/full_schema.sql` |
| Preview counts, thesession verification, post-commit live events | `api_routes.py` admin merge endpoint (`/api/admin/tunes/migrate`) |
| 301s | `web_routes.py` `session_handler` (tune_id arm) + `admin_tune_detail` |
| `redirected_from` on reads | `api_routes.py` / `api_person_tune_routes.py` GET endpoints used by the tune-detail modal |
| Client heal (URL fix + notice) | `static/js/tune_detail_modal.js` |
| Write remaps | `live_logging_routes.py`, `api_routes.py` |
| Live push | reuse `live_logging_routes.emit_change_tune` from the merge endpoint |

## Name-fill semantics (proc detail)

Let `old_name` / `new_name` be `tune.name` of the two ids. Alias filling happens
only when `old_name IS DISTINCT FROM new_name`. Within the merge transaction,
*for rows being migrated* (not conflict-deleted, not already overridden):

```sql
-- session_instance_tune: fill display name BEFORE the id flip
UPDATE session_instance_tune SET name = old_name
  WHERE tune_id = old AND name IS NULL AND record_type = 'tune';
-- person_tune / session_tune: fill override on the clean-move rows as they flip
UPDATE person_tune SET tune_id = new, name_alias = COALESCE(name_alias, old_name) WHERE ...no conflict...;
UPDATE session_tune SET tune_id = new, alias = COALESCE(alias, old_name) WHERE ...no conflict...;
-- session_tune_alias: old name stays findable in every session that had the old tune
INSERT INTO session_tune_alias (session_id, tune_id, alias, created_by_user_id)
SELECT session_id, new, old_name, user FROM (sessions that had old)
ON CONFLICT (session_id, alias) DO NOTHING;
```

(Exact ordering in the proc: capture names → SIT name fill → id flips with
alias fills on moved rows → conflict deletes → alias inserts → recording
segments → tombstone.)

## Testing

1. Clean merge with per-instrument overrides — overrides follow, no FK error.
2. Conflict merge (person has both) — survivor untouched, old row + overrides gone.
3. Name fill on all three tables when names differ; no fill when names match;
   existing overrides never overwritten.
4. `session_tune_alias` gains old name per affected session; duplicate alias skipped.
5. `recording_tune_segment` rows move.
6. Read APIs return `redirected_from`; path routes 301.
7. Write ops with old id remap (`remapped_from` in response) and enrollment uses new id.
8. Synthetic `change_tune` events emitted only for recently-active instances.
9. thesession verification states: confirmed / mismatch / unreachable.
