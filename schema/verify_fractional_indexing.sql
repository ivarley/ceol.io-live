-- Verification script for fractional indexing migration
-- Run this against production to verify consistency before removing order_number

-- 1. Check for any NULL order_positions
SELECT 'NULL order_position check' as check_name,
       COUNT(*) as null_count,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as result
FROM session_instance_tune
WHERE order_position IS NULL;

-- 2. Check total row counts
SELECT 'Total rows' as metric,
       COUNT(*) as count
FROM session_instance_tune;

-- 3. Verify ordering consistency between order_number and order_position
-- This compares the rank of each tune when sorted by order_number vs order_position
WITH ordered_by_number AS (
    SELECT session_instance_tune_id, session_instance_id,
           ROW_NUMBER() OVER (PARTITION BY session_instance_id ORDER BY order_number) as num_rank
    FROM session_instance_tune
),
ordered_by_position AS (
    SELECT session_instance_tune_id, session_instance_id,
           ROW_NUMBER() OVER (PARTITION BY session_instance_id ORDER BY order_position) as pos_rank
    FROM session_instance_tune
),
mismatches AS (
    SELECT n.session_instance_tune_id, n.session_instance_id, n.num_rank, p.pos_rank
    FROM ordered_by_number n
    JOIN ordered_by_position p USING (session_instance_tune_id)
    WHERE n.num_rank != p.pos_rank
)
SELECT 'Ordering consistency check' as check_name,
       COUNT(*) as mismatch_count,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as result
FROM mismatches;

-- 4. If there are mismatches, show details (limited to first 20)
WITH ordered_by_number AS (
    SELECT session_instance_tune_id, session_instance_id, name, order_number,
           ROW_NUMBER() OVER (PARTITION BY session_instance_id ORDER BY order_number) as num_rank
    FROM session_instance_tune
),
ordered_by_position AS (
    SELECT session_instance_tune_id, order_position,
           ROW_NUMBER() OVER (PARTITION BY session_instance_id ORDER BY order_position) as pos_rank
    FROM session_instance_tune
)
SELECT n.session_instance_id, n.name, n.order_number, p.order_position,
       n.num_rank as rank_by_number, p.pos_rank as rank_by_position
FROM ordered_by_number n
JOIN ordered_by_position p USING (session_instance_tune_id)
WHERE n.num_rank != p.pos_rank
LIMIT 20;

-- 5. Check for duplicate order_positions within the same session instance
SELECT 'Duplicate order_position check' as check_name,
       COUNT(*) as duplicate_count,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END as result
FROM (
    SELECT session_instance_id, order_position, COUNT(*) as cnt
    FROM session_instance_tune
    GROUP BY session_instance_id, order_position
    HAVING COUNT(*) > 1
) dups;

-- 6. Check for any order_positions that exceed recommended length
SELECT 'Long order_position check (>10 chars)' as check_name,
       COUNT(*) as long_count,
       MAX(LENGTH(order_position)) as max_length
FROM session_instance_tune
WHERE LENGTH(order_position) > 10;

-- 7. Sample data from a recent session instance to visually verify
SELECT 'Sample data from recent session instance:' as info;
SELECT sit.session_instance_tune_id, sit.order_number, sit.order_position, sit.name
FROM session_instance_tune sit
JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
WHERE si.date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY si.date DESC, sit.order_position
LIMIT 30;

-- 8. Check session instances modified in the last 2 weeks (since fractional indexing deploy)
SELECT 'Session instances modified since deploy' as check_name,
       COUNT(DISTINCT session_instance_id) as session_count,
       COUNT(*) as tune_count
FROM session_instance_tune
WHERE last_modified_date >= '2026-01-01'::date;  -- Adjust date to match deploy date
