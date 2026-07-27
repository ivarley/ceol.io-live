-- =============================================================================
-- 045 session_tune.manually_added — protect hand-curated repertoire from the
--     live logger's auto-cleanup
-- =============================================================================
-- Logging a tune enrolls it into the session's repertoire as a side effect
-- (spec 025). Deleting that play now un-enrolls it again, so a search-add-then-
-- delete no longer leaves a permanent orphan in the session's tune list.
--
-- The auto-cleanup must never touch a row a person put there ON PURPOSE. Those
-- rows are otherwise indistinguishable from an auto-enrollment — both are a bare
-- (session_id, tune_id) with the tune's default setting — so this column marks
-- them explicitly. It is set TRUE by the deliberate paths only:
--
--   * add_session_tune            — the add-tune pane on the session tunes page
--   * update_session_tune_details — "we play this in Ador here" (spec 037)
--   * copy_tunes_to_destination   — admin bulk copy of a repertoire
--
-- Play-driven enrollment (live logger _enroll_session_tune, the legacy save and
-- link paths) leaves it FALSE, which is what makes a row cleanup-eligible.
--
-- ROLLOUT (manual, prod):
--   psql "$DATABASE_URL" -f schema/045_session_tune_manually_added.sql
--
-- Idempotent.
-- =============================================================================

ALTER TABLE session_tune
ADD COLUMN IF NOT EXISTS manually_added BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN session_tune.manually_added IS
    'TRUE = a person added/curated this repertoire entry on purpose; exempt from the play-delete auto-cleanup (spec 045)';

-- Keep the audit table structurally parallel. Nullable (no default) — a history
-- snapshot mirrors whatever the live row held.
ALTER TABLE session_tune_history
ADD COLUMN IF NOT EXISTS manually_added BOOLEAN;

-- ---------------------------------------------------------------------------
-- Backfill: protect the pre-existing hand-added rows.
--
-- Every automatic enrollment happens alongside a play — the old logger's save,
-- the link paths, the live logger's add, and the 025 backfill all derive the
-- session_tune row FROM a session_instance_tune row. So a repertoire entry with
-- no play record of any kind (not even a tombstoned one) cannot have been
-- auto-enrolled: someone put it there by hand. Those get protected.
--
-- Rows carrying curation (a session alias, a session key, or session_tune_alias
-- entries) are protected too, whatever their origin — the auto-cleanup checks
-- for those separately at delete time, but marking them here makes the intent
-- durable and readable in the data.
--
-- Deliberately conservative in the protect direction: a false TRUE only means a
-- stale row survives (today's status quo), while a false FALSE would delete
-- someone's curated entry.
-- ---------------------------------------------------------------------------
UPDATE session_tune st
SET manually_added = TRUE
WHERE NOT st.manually_added
  AND (
        NOT EXISTS (
            SELECT 1
            FROM session_instance_tune sit
            JOIN session_instance si
              ON si.session_instance_id = sit.session_instance_id
            WHERE si.session_id = st.session_id
              AND sit.tune_id = st.tune_id
        )
     OR st.alias IS NOT NULL
     OR st.key IS NOT NULL
     OR EXISTS (
            SELECT 1 FROM session_tune_alias sta
            WHERE sta.session_id = st.session_id AND sta.tune_id = st.tune_id
        )
  );
