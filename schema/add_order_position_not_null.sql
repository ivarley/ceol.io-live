-- Migration: Add NOT NULL constraint to order_position column
--
-- Prerequisites:
-- 1. migrate_to_fractional_indexing.sql has been run
-- 2. verify_fractional_indexing.sql shows no issues
-- 3. All code paths now generate order_position on insert
--
-- This migration should be run after verifying production data is consistent.

BEGIN;

-- Verify no NULL values exist before adding constraint
DO $$
DECLARE
    null_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO null_count
    FROM session_instance_tune
    WHERE order_position IS NULL;

    IF null_count > 0 THEN
        RAISE EXCEPTION 'Cannot add NOT NULL constraint: % rows have NULL order_position. Run migrate_to_fractional_indexing.sql first.', null_count;
    END IF;

    RAISE NOTICE 'Verification passed: no NULL order_position values found';
END $$;

-- Add NOT NULL constraint to main table
ALTER TABLE session_instance_tune
ALTER COLUMN order_position SET NOT NULL;

-- Verify the constraint was added
DO $$
DECLARE
    is_nullable VARCHAR;
BEGIN
    SELECT c.is_nullable INTO is_nullable
    FROM information_schema.columns c
    WHERE c.table_name = 'session_instance_tune'
      AND c.column_name = 'order_position';

    IF is_nullable != 'NO' THEN
        RAISE EXCEPTION 'NOT NULL constraint was not added correctly';
    END IF;

    RAISE NOTICE 'NOT NULL constraint added successfully to order_position column';
END $$;

COMMIT;

-- Note: The history table (session_instance_tune_history) intentionally keeps
-- order_position nullable since historical records from before the migration
-- may not have this value.
