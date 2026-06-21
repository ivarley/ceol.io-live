-- =============================================================================
-- 023 Set Breaks as Explicit Records  (EXPAND step)
-- =============================================================================
-- Makes a set boundary an explicit row in session_instance_tune instead of the
-- implicit `continues_set = false` flag on the first tune of each set.
--
-- A break row: record_type = 'break', tune_id NULL, name NULL, positioned in the
-- normal order_position stream. A set is the run of record_type = 'tune' rows
-- ending at a break (one break per set, including a trailing break that closes
-- the final set).  See specs/changes/023-set-break-records.md.
--
-- ROLLOUT (manual, prod) -- run these in order:
--   1. psql ... -f schema/023_set_break_records.sql      <-- THIS FILE (expand)
--   2. python3 scripts/migrate_023_set_breaks.py         <-- backfill + drop continues_set
--
-- This file is the additive (safe, reversible) half only. It is idempotent.
-- =============================================================================

-- 1. Discriminator column. Existing rows default to 'tune'.
ALTER TABLE session_instance_tune
    ADD COLUMN IF NOT EXISTS record_type VARCHAR(16) NOT NULL DEFAULT 'tune';

-- Mirror onto the history table (nullable, like the other copied columns).
ALTER TABLE session_instance_tune_history
    ADD COLUMN IF NOT EXISTS record_type VARCHAR(16);

-- 2. Replace the name-or-id CHECK so break rows (no tune_id, no name) are legal.
ALTER TABLE session_instance_tune
    DROP CONSTRAINT IF EXISTS session_instance_tune_name_or_id;
ALTER TABLE session_instance_tune
    ADD CONSTRAINT session_instance_tune_name_or_id
    CHECK (record_type = 'break' OR tune_id IS NOT NULL OR name IS NOT NULL);
