# 025: Session Repertoire Enrollment — Live Logger Fix + Backfill

## Purpose

The old logger enrolls every **linked** tune played into `session_tune` (the session's
repertoire) as a side effect of saving. The new live logger does **not**. Result: tunes logged
through the live logger that weren't already in a session's repertoire are silently missing from
`session_tune`. This spec (1) fixes the live logger to enroll linked tunes going forward, and
(2) backfills the rows already missed.

## Problem detail (verified)

- **Old logger enrolls:** `save_session_instance_tunes_ajax` (`api_routes.py:7212`) collects
  every linked tune in the saved list and, at `api_routes.py:7356-7362` / `7405-7419`, does
  `INSERT INTO session_tune (session_id, tune_id, alias, setting_id, created_by_user_id) …
  ON CONFLICT (session_id, tune_id) DO NOTHING` for any not already present. So logging a tune
  that's in the ceol DB but new to this session grows the repertoire.
- **New logger does not:** `live_logging_routes.py` has **zero** `session_tune` writes;
  `_handle_add_tune` (`live_logging_routes.py:337-386`) only inserts `session_instance_tune`.
- **No safety net:** the only triggers on `session_tune` maintain `last_modified_date`
  (`schema/create_tune_tables.sql:47`). Nothing backfills it from plays.

## Impact

`session_tune` is the session repertoire and feeds:
- the **known-tunes fast-match vocabulary** — tier A of `compute_session_vocabulary`
  (`live_logging_routes.py:1262`, `FROM session_tune st`), which powers instant local matching
  and ranking in the live logger;
- the **"in session" / "on your list"** flags in `live_deep_search` / `live_match`
  (`live_logging_routes.py:1033`);
- the session **repertoire / tune-list** views and next-tune suggestions.

So sessions logged (wholly or partly) via the new logger have an incomplete repertoire: tunes
played there don't rank in fast-match, don't flag as in-session, and don't appear in the tune
list — silently, because logging itself still works.

## Goals

1. **Forward fix** — the live logger enrolls linked tunes into `session_tune`, matching the old
   logger, for every path that establishes a tune↔instance link.
2. **Backfill** — retroactively enroll all already-played linked tunes.
3. Idempotent, history-tracked, no regressions.

---

## A. Forward fix (`live_logging_routes.py`)

Add a small helper and call it from the two ops that establish a link:

```python
def _enroll_session_tune(cur, session_id, tune_id, user_id):
    """Enroll a linked tune into the session's repertoire (idempotent), mirroring the old
    logger's save path (api_routes.py:7405). No-op for unlinked/break rows and merged tunes."""
    if not tune_id:
        return
    # Skip merged/redirect tunes (old logger refuses to add these): only canonical tunes.
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
    row = cur.fetchone()
    if not row or row[0] is not None:
        return
    cur.execute(
        """INSERT INTO session_tune (session_id, tune_id, created_by_user_id)
           VALUES (%s, %s, %s)
           ON CONFLICT (session_id, tune_id) DO NOTHING""",
        (session_id, tune_id, user_id),
    )
    if cur.rowcount > 0:
        save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id), user_id=user_id)
```

Call sites:
- **`_handle_add_tune`** (`live_logging_routes.py:337-386`): after the tune is resolved and the
  `session_instance_tune` row is inserted, if the final record is **linked** (`tune_id` not
  null), call `_enroll_session_tune`. The handler must know `session_id`; it already fetches it
  in the name-resolution branch (line 350) — hoist that lookup so it's available whenever a
  `tune_id` is present (from a tap or a name match).
- **`_handle_change_tune`** (`live_logging_routes.py:405+`): when a change sets a **new**
  `tune_id` (a relink, not an unlink), enroll that tune_id the same way.

Explicitly **not** enrolled: unlinked rows (`tune_id NULL`), `break` rows, and merged/redirect
tunes (guarded above). Corroborations (`_corroborate`) add no new tune and need no enrollment —
the original add already enrolled it.

**Deferred refinement:** the old logger also stores the user's per-session alias in
`session_tune.alias`. This fix enrolls with `alias NULL` (the per-instance display name lives on
`session_instance_tune`). Capturing a differing logged name as the `session_tune.alias` is a
follow-up, not required to close the data gap.

## B. Backfill (one-off migration, reviewed before it runs)

Idempotent bulk heal covering gaps from **any** source, not just the live logger:

```sql
INSERT INTO session_tune (session_id, tune_id)
SELECT DISTINCT si.session_id, sit.tune_id
FROM session_instance_tune sit
JOIN session_instance si USING (session_instance_id)
JOIN tune t ON t.tune_id = sit.tune_id
WHERE sit.tune_id IS NOT NULL
  AND sit.record_type = 'tune'
  AND sit.deleted = FALSE
  AND t.redirect_to_tune_id IS NULL
ON CONFLICT (session_id, tune_id) DO NOTHING;
```

Requirements:
- **Dry-run first:** print the count of rows the insert *would* add (the same SELECT wrapped in
  `SELECT COUNT(*)`, or reported via `cur.rowcount` in a transaction that is rolled back) and
  pause for review before committing.
- `created_by_user_id` is nullable (tests insert without it), so backfilled rows leave it NULL;
  `alias` / `setting_id` NULL. History rows for the backfill are optional — recommend writing
  `session_tune_history` INSERTs in batch for auditability (attributed to a system/admin id), but
  acceptable to skip as a documented bulk heal.
- Excludes: unlinked plays, `break` rows, deleted/tombstoned rows, merged/redirect tunes.
- **Idempotent** (`ON CONFLICT DO NOTHING`) — safe to re-run; a second run adds 0.
- Deliver as a runnable script under `scripts/` (following existing migration/script
  conventions) and/or a `schema/0XX_*.sql`; include the review/count step alongside.

---

## Files touched

- `live_logging_routes.py` — new `_enroll_session_tune` helper; call from `_handle_add_tune`
  and `_handle_change_tune`; hoist the `session_id` lookup in `_handle_add_tune`.
- `scripts/` backfill script (+ optional `schema/` SQL) with the dry-run count.
- `tests/integration/test_live_logging_ops.py` — see Verification.
- Docs: note repertoire enrollment in `specs/current/logic/live-logging.md` and
  `specs/current/data/session-model.md` / `tune-model.md`.

## Verification

- **Integration tests (new):** posting an `add_tune` op for a linked tune creates the
  `session_tune` row; a second identical add creates no duplicate and doesn't error; an
  unlinked add creates **no** `session_tune` row; a `change_tune` relink enrolls the new
  tune_id; a merged/redirect tune is not enrolled.
- **Backfill:** on a prod-like copy, run the dry-run count, apply, then re-run (expect 0 new).
  Spot-check a session that was logged only via the live logger — its played tunes now appear in
  the repertoire and in the `known_tunes` vocabulary.
- **Regression:** existing live-logging op tests pass (`make test`).

## Edge cases / decisions

- Merged/redirect tunes excluded (guard on `redirect_to_tune_id`), matching the old logger.
- `break` rows, unlinked rows, and deleted rows excluded from both fix and backfill.
- Alias capture into `session_tune.alias` deferred (enroll `alias NULL`).
- Backfill `created_by_user_id` left NULL (column is nullable); confirm whether you'd prefer a
  system/admin attribution.

## Relationship to other work

This is a prerequisite for the (separately specced) **thesession remote-search / import**
feature in the live logger: once 025 lands, that feature needs **no** `session_tune` code of its
own — an imported-then-logged tune enrolls through this same fix.
