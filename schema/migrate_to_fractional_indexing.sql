-- Migration: Add fractional indexing (order_position) to session_instance_tune
--
-- This adds a VARCHAR column for CRDT-compatible ordering alongside the existing
-- integer order_number. The order_position uses base-62 strings (0-9, A-Z, a-z) that
-- allow insertion between any two positions without renumbering.
--
-- Uses COLLATE "C" to ensure byte-order sorting (0-9 < A-Z < a-z).
--
-- Run this migration in a transaction and verify before committing.

BEGIN;

-- Step 1: Add order_position column to main table (nullable initially)
-- COLLATE "C" ensures consistent byte-order sorting regardless of database locale
ALTER TABLE session_instance_tune
ADD COLUMN IF NOT EXISTS order_position VARCHAR(32) COLLATE "C";

-- Step 2: Add order_position column to history table
ALTER TABLE session_instance_tune_history
ADD COLUMN IF NOT EXISTS order_position VARCHAR(32) COLLATE "C";

-- Step 3: Create a function to generate fractional positions from integers
-- Uses base-62 alphabet: 0-9, A-Z, a-z (sorted by ASCII byte value)
-- Position sequence: V,W,...,z, zV,...,zz, zzV,...,zzz, etc.
-- Note: Extensions use midpoint 'V' (not '0') to leave room for insertions
CREATE OR REPLACE FUNCTION generate_fractional_position(order_num INTEGER)
RETURNS VARCHAR(32) AS $$
DECLARE
    alphabet VARCHAR(62) := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
    start_idx INTEGER := 31;  -- 'V' is at index 31 (0-indexed)
    first_range INTEGER := 31;  -- V-z (31 positions)
    second_range INTEGER := 31;  -- zV-zz (31 positions)
    third_range INTEGER := 31;  -- zzV-zzz (31 positions)
    pos INTEGER;
BEGIN
    IF order_num IS NULL OR order_num < 1 THEN
        RETURN 'V';
    END IF;

    IF order_num <= first_range THEN
        -- V(1) through z(31)
        RETURN SUBSTRING(alphabet FROM start_idx + order_num FOR 1);
    END IF;

    pos := order_num - first_range;

    IF pos <= second_range THEN
        -- zV(32) through zz(62)
        RETURN 'z' || SUBSTRING(alphabet FROM start_idx + pos FOR 1);
    END IF;

    pos := pos - second_range;

    IF pos <= third_range THEN
        -- zzV(63) through zzz(93)
        RETURN 'zz' || SUBSTRING(alphabet FROM start_idx + pos FOR 1);
    END IF;

    pos := pos - third_range;

    IF pos <= 31 THEN
        -- zzzV(94) through zzzz(124)
        RETURN 'zzz' || SUBSTRING(alphabet FROM start_idx + pos FOR 1);
    END IF;

    -- Beyond 124, use zzzzVN format (very rare, >100 tunes in a session)
    RETURN 'zzzz' || SUBSTRING(alphabet FROM start_idx + 1 FOR 1) || (pos - 31)::text;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Step 4: Populate order_position for existing data
-- Generate positions that maintain the same ordering as order_number
UPDATE session_instance_tune
SET order_position = generate_fractional_position(order_number)
WHERE order_position IS NULL;

-- Step 5: Create index for ordering queries
CREATE INDEX IF NOT EXISTS idx_sit_order_position
ON session_instance_tune(session_instance_id, order_position);

-- Step 6: Verification queries (run these to check migration success)

-- Check that all rows have order_position
DO $$
DECLARE
    null_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO null_count
    FROM session_instance_tune
    WHERE order_position IS NULL;

    IF null_count > 0 THEN
        RAISE EXCEPTION 'Migration incomplete: % rows have NULL order_position', null_count;
    END IF;
END $$;

-- Verify ordering matches between order_number and order_position
-- This checks that sorting by order_position gives the same result as order_number
DO $$
DECLARE
    mismatch_count INTEGER;
BEGIN
    WITH ordered_by_number AS (
        SELECT session_instance_tune_id, session_instance_id,
               ROW_NUMBER() OVER (PARTITION BY session_instance_id ORDER BY order_number) as num_rank
        FROM session_instance_tune
    ),
    ordered_by_position AS (
        SELECT session_instance_tune_id, session_instance_id,
               ROW_NUMBER() OVER (PARTITION BY session_instance_id ORDER BY order_position) as pos_rank
        FROM session_instance_tune
    )
    SELECT COUNT(*) INTO mismatch_count
    FROM ordered_by_number n
    JOIN ordered_by_position p USING (session_instance_tune_id)
    WHERE n.num_rank != p.pos_rank;

    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Migration verification failed: % rows have mismatched ordering', mismatch_count;
    END IF;

    RAISE NOTICE 'Verification passed: order_position ordering matches order_number';
END $$;

-- Show sample data
SELECT
    session_instance_id,
    order_number,
    order_position,
    name
FROM session_instance_tune
WHERE session_instance_id = (
    SELECT session_instance_id
    FROM session_instance_tune
    GROUP BY session_instance_id
    HAVING COUNT(*) > 5
    LIMIT 1
)
ORDER BY order_position
LIMIT 20;

-- Count total migrated rows
SELECT
    COUNT(*) as total_rows,
    COUNT(order_position) as rows_with_position,
    COUNT(*) - COUNT(order_position) as rows_missing_position
FROM session_instance_tune;

COMMIT;

-- After verification is complete and code is deployed, run this to make NOT NULL:
-- ALTER TABLE session_instance_tune ALTER COLUMN order_position SET NOT NULL;
