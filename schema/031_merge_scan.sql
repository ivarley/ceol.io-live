-- =============================================================================
-- 031 thesession.org merge sync
-- =============================================================================
-- Because tune.tune_id IS the thesession.org tune id, tunes merged upstream go
-- stale silently: we keep logging against the old id while thesession.org
-- 301-redirects it. A weekly job (jobs/sync_thesession_merges.py ->
-- services/tune_merge_scan_service.run_sync) downloads thesession's weekly
-- data dump, finds local tune ids that no longer exist upstream, resolves
-- where they went (settings-trace through the dump, live redirect check for
-- the rest), live-verifies each redirect, and APPLIES the merge automatically
-- via the spec-030 machinery (merge_tune_ids: reference moves, name
-- preservation, history, live-logger relink). The admin merge page renders
-- these tables as a record of what was applied, with a Run Now button.
--
--   * tune_merge_scan         one row per run; counters + heartbeat (a run
--                             whose thread died leaves status 'running' with
--                             a stale heartbeat; the next run just starts).
--   * tune_merge_scan_result  outcomes worth recording, kept ACROSS runs
--                             (applied merges are one-shot — the next run
--                             can't re-detect them, so rows are the record):
--                             'merged' (applied_at set when auto-applied),
--                             'deleted' upstream (informational, recorded
--                             once, first run that noticed), 'error'
--                             (latest attempt only; retried next run).
--                             No FK on tune_id: the row must survive its tune
--                             being merged.
--
-- Idempotent.  See specs/changes/inprogress/031-scan-merged-tunes.md.
-- =============================================================================

CREATE TABLE IF NOT EXISTS tune_merge_scan (
    scan_id             SERIAL PRIMARY KEY,
    status              VARCHAR(16) NOT NULL CHECK (status IN ('running', 'completed', 'cancelled')),
    total_count         INTEGER NOT NULL,   -- local active tunes at run start
    checked_count       INTEGER NOT NULL DEFAULT 0,
    merged_count        INTEGER NOT NULL DEFAULT 0,   -- merges detected this run
    applied_count       INTEGER NOT NULL DEFAULT 0,   -- merges actually applied this run
    deleted_count       INTEGER NOT NULL DEFAULT 0,
    error_count         INTEGER NOT NULL DEFAULT 0,
    started_by_user_id  INTEGER REFERENCES user_account(user_id),  -- NULL = cron
    started_at          TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    heartbeat_at        TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    finished_at         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tune_merge_scan_result (
    scan_id         INTEGER NOT NULL REFERENCES tune_merge_scan(scan_id) ON DELETE CASCADE,
    tune_id         INTEGER NOT NULL,       -- no FK: see header
    result_type     VARCHAR(16) NOT NULL CHECK (result_type IN ('merged', 'deleted', 'error')),
    target_tune_id  INTEGER,                -- final id after resolution (merged only)
    target_name     TEXT,                   -- thesession's canonical name for the target
    target_aliases  JSONB,                  -- thesession's alternate titles for the target
    detail          TEXT,                   -- how it was detected / error message
    applied_at      TIMESTAMPTZ,            -- when the merge was auto-applied (merged only)
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (scan_id, tune_id)
);

-- Record reads ("was this tune already recorded as deleted?") filter by tune.
CREATE INDEX IF NOT EXISTS idx_tune_merge_scan_result_tune
    ON tune_merge_scan_result (tune_id);
