-- Add redirect_to_tune_id column to tune table
-- When set, indicates this tune has been merged into another tune on thesession.org
-- The old tune record is preserved for audit purposes but should not be used

ALTER TABLE tune ADD COLUMN IF NOT EXISTS redirect_to_tune_id INTEGER REFERENCES tune(tune_id);

-- Prevent redirect chains: a tune cannot redirect to another redirect
CREATE OR REPLACE FUNCTION check_tune_redirect_chain()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.redirect_to_tune_id IS NOT NULL THEN
        -- Check that target tune is not itself a redirect
        IF EXISTS (
            SELECT 1 FROM tune
            WHERE tune_id = NEW.redirect_to_tune_id
            AND redirect_to_tune_id IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'Cannot redirect to a tune that is itself a redirect (tune_id: %)', NEW.redirect_to_tune_id;
        END IF;

        -- Check for self-redirect
        IF NEW.tune_id = NEW.redirect_to_tune_id THEN
            RAISE EXCEPTION 'A tune cannot redirect to itself';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_check_tune_redirect_chain ON tune;
CREATE TRIGGER trigger_check_tune_redirect_chain
    BEFORE INSERT OR UPDATE ON tune
    FOR EACH ROW
    WHEN (NEW.redirect_to_tune_id IS NOT NULL)
    EXECUTE FUNCTION check_tune_redirect_chain();

-- Index for quickly finding redirected tunes
CREATE INDEX IF NOT EXISTS idx_tune_redirect_to ON tune(redirect_to_tune_id) WHERE redirect_to_tune_id IS NOT NULL;

-- Stored procedure to merge one tune_id into another across all relevant tables
-- This updates main tables but leaves history tables unchanged to preserve audit trail
--
-- Usage:
--   SELECT merge_tune_ids(old_tune_id := 123, new_tune_id := 456, changed_by_user_id := 1);
--
-- Returns JSON with summary of changes made to each table

CREATE OR REPLACE FUNCTION merge_tune_ids(
    old_tune_id INTEGER,
    new_tune_id INTEGER,
    changed_by_user_id INTEGER DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
AS $$
DECLARE
    tune_setting_updated INTEGER := 0;
    session_tune_updated INTEGER := 0;
    session_tune_deleted INTEGER := 0;
    session_tune_alias_updated INTEGER := 0;
    session_tune_alias_deleted INTEGER := 0;
    session_instance_tune_updated INTEGER := 0;
    person_tune_updated INTEGER := 0;
    person_tune_deleted INTEGER := 0;
    result JSON;
BEGIN
    -- Validate inputs
    IF old_tune_id IS NULL OR new_tune_id IS NULL THEN
        RAISE EXCEPTION 'Both old_tune_id and new_tune_id must be provided';
    END IF;

    IF old_tune_id = new_tune_id THEN
        RAISE EXCEPTION 'old_tune_id and new_tune_id cannot be the same';
    END IF;

    -- Verify both tune_ids exist
    IF NOT EXISTS (SELECT 1 FROM tune WHERE tune_id = old_tune_id) THEN
        RAISE EXCEPTION 'old_tune_id % does not exist in tune table', old_tune_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM tune WHERE tune_id = new_tune_id) THEN
        RAISE EXCEPTION 'new_tune_id % does not exist in tune table', new_tune_id;
    END IF;

    -- Verify old tune is not already a redirect
    IF EXISTS (SELECT 1 FROM tune WHERE tune_id = old_tune_id AND redirect_to_tune_id IS NOT NULL) THEN
        RAISE EXCEPTION 'old_tune_id % is already a redirect', old_tune_id;
    END IF;

    -- Verify new tune is not a redirect (prevent chains)
    IF EXISTS (SELECT 1 FROM tune WHERE tune_id = new_tune_id AND redirect_to_tune_id IS NOT NULL) THEN
        RAISE EXCEPTION 'new_tune_id % is a redirect - cannot redirect to a redirect', new_tune_id;
    END IF;

    -- 1. tune_setting table - just update tune_id, setting_id is globally unique
    UPDATE tune_setting
    SET tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id;

    GET DIAGNOSTICS tune_setting_updated = ROW_COUNT;

    -- 2. session_instance_tune table - update tune_id
    -- No unique constraint on (session_instance_id, tune_id), so just update
    UPDATE session_instance_tune
    SET tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id;

    GET DIAGNOSTICS session_instance_tune_updated = ROW_COUNT;

    -- 3. session_tune_alias table - update where no conflict
    -- Unique constraint on (session_id, alias), so we need to handle conflicts
    UPDATE session_tune_alias
    SET tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM session_tune_alias sta2
        WHERE sta2.session_id = session_tune_alias.session_id
        AND sta2.tune_id = new_tune_id
        AND sta2.alias = session_tune_alias.alias
      );

    GET DIAGNOSTICS session_tune_alias_updated = ROW_COUNT;

    -- Delete remaining duplicates
    DELETE FROM session_tune_alias
    WHERE tune_id = old_tune_id;

    GET DIAGNOSTICS session_tune_alias_deleted = ROW_COUNT;

    -- 4. session_tune table - update where no conflict
    -- Unique constraint on (session_id, tune_id)
    UPDATE session_tune
    SET tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM session_tune st2
        WHERE st2.session_id = session_tune.session_id
        AND st2.tune_id = new_tune_id
      );

    GET DIAGNOSTICS session_tune_updated = ROW_COUNT;

    -- Delete remaining duplicates (where both old and new tune exist for same session)
    DELETE FROM session_tune
    WHERE tune_id = old_tune_id;

    GET DIAGNOSTICS session_tune_deleted = ROW_COUNT;

    -- 5. person_tune table - update where no conflict
    -- Unique constraint on (person_id, tune_id)
    UPDATE person_tune
    SET tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM person_tune pt2
        WHERE pt2.person_id = person_tune.person_id
        AND pt2.tune_id = new_tune_id
      );

    GET DIAGNOSTICS person_tune_updated = ROW_COUNT;

    -- Delete remaining duplicates
    DELETE FROM person_tune
    WHERE tune_id = old_tune_id;

    GET DIAGNOSTICS person_tune_deleted = ROW_COUNT;

    -- 6. Mark old tune as redirect
    UPDATE tune
    SET redirect_to_tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id;

    -- Build result JSON
    result := json_build_object(
        'success', true,
        'old_tune_id', old_tune_id,
        'new_tune_id', new_tune_id,
        'tables_updated', json_build_object(
            'tune_setting', json_build_object(
                'updated', tune_setting_updated
            ),
            'session_instance_tune', json_build_object(
                'updated', session_instance_tune_updated
            ),
            'session_tune_alias', json_build_object(
                'updated', session_tune_alias_updated,
                'deleted', session_tune_alias_deleted
            ),
            'session_tune', json_build_object(
                'updated', session_tune_updated,
                'deleted', session_tune_deleted
            ),
            'person_tune', json_build_object(
                'updated', person_tune_updated,
                'deleted', person_tune_deleted
            )
        ),
        'total_records_affected',
            tune_setting_updated +
            session_instance_tune_updated +
            session_tune_alias_updated + session_tune_alias_deleted +
            session_tune_updated + session_tune_deleted +
            person_tune_updated + person_tune_deleted
    );

    RETURN result;

EXCEPTION
    WHEN OTHERS THEN
        -- Re-raise the exception with context
        RAISE EXCEPTION 'Error merging tune_ids: %', SQLERRM;
END;
$$;

-- Add helpful comment
COMMENT ON FUNCTION merge_tune_ids(INTEGER, INTEGER, INTEGER) IS
'Merges all references from old_tune_id to new_tune_id in tune_setting, session_tune, session_tune_alias, session_instance_tune, and person_tune tables. Marks the old tune with redirect_to_tune_id. History tables are left unchanged to preserve audit trail. Returns JSON summary of changes.';
