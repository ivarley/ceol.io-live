-- =============================================================================
-- 031 Scan for Merged Tunes
-- =============================================================================
-- Because tune.tune_id IS the thesession.org tune id, tunes merged upstream go
-- stale silently: we keep logging against the old id while thesession.org
-- 301-redirects it. The scan (services/tune_merge_scan_service.py) HEADs every
-- non-tombstoned tune id against thesession.org and records the interesting
-- outcomes here; the admin merge page renders them as a punchlist for manual,
-- one-by-one merging through the existing spec-030 preview/confirm flow.
--
--   * tune_merge_scan         one row per scan; progress cursor + heartbeat so
--                             a killed thread can be detected (stale heartbeat)
--                             and resumed from cursor_tune_id. "Latest scan
--                             only": starting a new scan deletes prior rows.
--   * tune_merge_scan_result  only interesting hits (merged / deleted / error);
--                             200s are not stored. No FK on tune_id: the row
--                             must survive its tune being merged (that's how
--                             the punchlist knows the item is done).
--   * tune_merge_ignore       admin dismissals, keyed by (tune_id, target);
--                             deliberately OUTSIDE the scan rows so they
--                             survive scan wipes. NULL target = dismissed
--                             deleted-upstream (404) row.
--
-- Idempotent.  See specs/changes/inprogress/031-scan-merged-tunes.md.
-- =============================================================================

CREATE TABLE IF NOT EXISTS tune_merge_scan (
    scan_id             SERIAL PRIMARY KEY,
    status              VARCHAR(16) NOT NULL CHECK (status IN ('running', 'completed', 'cancelled')),
    cursor_tune_id      INTEGER,            -- last checked id; resume point
    total_count         INTEGER NOT NULL,   -- snapshot of ids to check at start
    checked_count       INTEGER NOT NULL DEFAULT 0,
    merged_count        INTEGER NOT NULL DEFAULT 0,
    deleted_count       INTEGER NOT NULL DEFAULT 0,
    error_count         INTEGER NOT NULL DEFAULT 0,
    started_by_user_id  INTEGER REFERENCES user_account(user_id),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    heartbeat_at        TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    finished_at         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tune_merge_scan_result (
    scan_id         INTEGER NOT NULL REFERENCES tune_merge_scan(scan_id) ON DELETE CASCADE,
    tune_id         INTEGER NOT NULL,       -- no FK: see header
    result_type     VARCHAR(16) NOT NULL CHECK (result_type IN ('merged', 'deleted', 'error')),
    target_tune_id  INTEGER,                -- final id after following redirect chain (merged only)
    target_name     TEXT,                   -- thesession's canonical name for the target
    target_aliases  JSONB,                  -- thesession's alternate titles for the target
    detail          TEXT,                   -- http status / error message
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (scan_id, tune_id)
);

CREATE TABLE IF NOT EXISTS tune_merge_ignore (
    tune_id             INTEGER NOT NULL,
    target_tune_id      INTEGER,            -- NULL = dismissed deleted-upstream row
    created_by_user_id  INTEGER REFERENCES user_account(user_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Pair uniqueness including the NULL-target case (portable across PG < 15,
-- which lacks UNIQUE NULLS NOT DISTINCT).
CREATE UNIQUE INDEX IF NOT EXISTS idx_tune_merge_ignore_pair
    ON tune_merge_ignore (tune_id, target_tune_id) WHERE target_tune_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_tune_merge_ignore_deleted
    ON tune_merge_ignore (tune_id) WHERE target_tune_id IS NULL;
