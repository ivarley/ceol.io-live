-- Fix duplicate order_position values
-- This regenerates order_position for all affected session instances

-- First, find all session instances with duplicate order_positions
WITH duplicates AS (
    SELECT session_instance_id, order_position, COUNT(*) as cnt
    FROM session_instance_tune
    GROUP BY session_instance_id, order_position
    HAVING COUNT(*) > 1
),
affected_instances AS (
    SELECT DISTINCT session_instance_id FROM duplicates
)
SELECT session_instance_id FROM affected_instances ORDER BY session_instance_id;

-- Regenerate positions for affected session instances
-- Uses order_number as the source of truth since it's still correct
-- Generates positions: V, W, X, Y, Z, a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y, z, z0, z1, ...

DO $$
DECLARE
    alphabet CONSTANT TEXT := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
    start_idx CONSTANT INT := 32; -- 'V' is at index 31 (0-indexed), we use 1-indexed here
    inst_id INT;
    tune RECORD;
    new_position TEXT;
    position_idx INT;
BEGIN
    -- Find all affected session instances
    FOR inst_id IN (
        SELECT DISTINCT sit.session_instance_id
        FROM session_instance_tune sit
        WHERE sit.session_instance_id IN (
            SELECT session_instance_id
            FROM (
                SELECT session_instance_id, order_position, COUNT(*) as cnt
                FROM session_instance_tune
                GROUP BY session_instance_id, order_position
                HAVING COUNT(*) > 1
            ) dups
        )
        ORDER BY sit.session_instance_id
    )
    LOOP
        RAISE NOTICE 'Fixing session_instance_id: %', inst_id;

        position_idx := 0;

        -- Update each tune in order
        FOR tune IN (
            SELECT session_instance_tune_id, order_number
            FROM session_instance_tune
            WHERE session_instance_id = inst_id
            ORDER BY order_number
        )
        LOOP
            -- Generate position: V, W, X, Y, Z, a, b, ... , z, z0, z1, ...
            IF position_idx < (62 - start_idx) THEN
                -- Still in single-character range (V through z)
                new_position := SUBSTRING(alphabet FROM (start_idx + position_idx) FOR 1);
            ELSE
                -- Need to extend: z0, z1, z2, ... zV, zW, ... zz, zz0, ...
                new_position := 'z' || SUBSTRING(alphabet FROM ((position_idx - (62 - start_idx)) % 62 + 1) FOR 1);
            END IF;

            UPDATE session_instance_tune
            SET order_position = new_position
            WHERE session_instance_tune_id = tune.session_instance_tune_id;

            position_idx := position_idx + 1;
        END LOOP;
    END LOOP;
END $$;

-- Verify the fix
SELECT 'After fix - Duplicate check:' as status;
SELECT 'Duplicate order_position check' as check_name,
       COUNT(*) as duplicate_count,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as result
FROM (
    SELECT session_instance_id, order_position, COUNT(*) as cnt
    FROM session_instance_tune
    GROUP BY session_instance_id, order_position
    HAVING COUNT(*) > 1
) dups;

-- Show fixed data for verification
SELECT 'Fixed session instance 345:' as status;
SELECT session_instance_tune_id, order_number, order_position, name
FROM session_instance_tune
WHERE session_instance_id = 345
ORDER BY order_position;
