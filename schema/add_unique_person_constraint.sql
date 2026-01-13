-- Migration: Add unique constraint on person_id in user_account
-- This ensures one user account per person

-- First, identify and handle any duplicate person_ids
-- Keep the account with the most recent login activity (or most recent creation if no logins)

BEGIN;

-- Show any duplicates before we fix them
DO $$
DECLARE
    dup_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT person_id FROM user_account GROUP BY person_id HAVING COUNT(*) > 1
    ) dups;

    IF dup_count > 0 THEN
        RAISE NOTICE 'Found % person(s) with multiple accounts. Resolving...', dup_count;
    END IF;
END $$;

-- Delete duplicate accounts, keeping the one with most recent activity
-- Uses user_session.last_accessed to determine which account is active
DELETE FROM user_account ua
WHERE ua.user_id IN (
    SELECT user_id
    FROM (
        SELECT
            ua2.user_id,
            ua2.person_id,
            ROW_NUMBER() OVER (
                PARTITION BY ua2.person_id
                ORDER BY
                    COALESCE(
                        (SELECT MAX(last_accessed) FROM user_session us WHERE us.user_id = ua2.user_id),
                        ua2.created_date
                    ) DESC
            ) as rn
        FROM user_account ua2
        WHERE ua2.person_id IN (
            SELECT person_id FROM user_account GROUP BY person_id HAVING COUNT(*) > 1
        )
    ) ranked
    WHERE rn > 1  -- Keep only the first (most recently active) account
);

-- Now add the unique constraint
ALTER TABLE user_account
ADD CONSTRAINT user_account_person_id_unique UNIQUE (person_id);

COMMIT;

-- Verify the constraint was added
SELECT
    conname as constraint_name,
    contype as constraint_type
FROM pg_constraint
WHERE conrelid = 'user_account'::regclass
AND conname = 'user_account_person_id_unique';
