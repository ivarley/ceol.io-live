-- Stored procedure to merge one person_id into another across all relevant tables
-- This updates main tables but leaves history tables unchanged to preserve audit trail
--
-- Usage:
--   SELECT merge_person_ids(old_id := 123, new_id := 456);
--
-- Returns JSON with summary of changes made to each table

CREATE OR REPLACE FUNCTION merge_person_ids(
    old_person_id INTEGER,
    new_person_id INTEGER
)
RETURNS JSON
LANGUAGE plpgsql
AS $$
DECLARE
    session_person_updated INTEGER := 0;
    session_person_deleted INTEGER := 0;
    session_instance_person_updated INTEGER := 0;
    session_instance_person_deleted INTEGER := 0;
    person_tune_updated INTEGER := 0;
    person_tune_deleted INTEGER := 0;
    person_instrument_updated INTEGER := 0;
    person_instrument_deleted INTEGER := 0;
    result JSON;
BEGIN
    -- Validate inputs
    IF old_person_id IS NULL OR new_person_id IS NULL THEN
        RAISE EXCEPTION 'Both old_person_id and new_person_id must be provided';
    END IF;

    IF old_person_id = new_person_id THEN
        RAISE EXCEPTION 'old_person_id and new_person_id cannot be the same';
    END IF;

    -- Verify both person_ids exist
    IF NOT EXISTS (SELECT 1 FROM person WHERE person_id = old_person_id) THEN
        RAISE EXCEPTION 'old_person_id % does not exist in person table', old_person_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM person WHERE person_id = new_person_id) THEN
        RAISE EXCEPTION 'new_person_id % does not exist in person table', new_person_id;
    END IF;

    -- 1. session_person table
    -- Update records where no conflict exists
    UPDATE session_person
    SET person_id = new_person_id
    WHERE person_id = old_person_id
      AND NOT EXISTS (
        SELECT 1 FROM session_person sp2
        WHERE sp2.session_id = session_person.session_id
        AND sp2.person_id = new_person_id
      );

    GET DIAGNOSTICS session_person_updated = ROW_COUNT;

    -- Delete remaining duplicates (where both old and new person exist for same session)
    DELETE FROM session_person
    WHERE person_id = old_person_id;

    GET DIAGNOSTICS session_person_deleted = ROW_COUNT;

    -- 2. session_instance_person table
    -- Update records where no conflict exists
    UPDATE session_instance_person
    SET person_id = new_person_id
    WHERE person_id = old_person_id
      AND NOT EXISTS (
        SELECT 1 FROM session_instance_person sip2
        WHERE sip2.session_instance_id = session_instance_person.session_instance_id
        AND sip2.person_id = new_person_id
      );

    GET DIAGNOSTICS session_instance_person_updated = ROW_COUNT;

    -- Delete remaining duplicates
    DELETE FROM session_instance_person
    WHERE person_id = old_person_id;

    GET DIAGNOSTICS session_instance_person_deleted = ROW_COUNT;

    -- 3. person_tune table
    -- Update records where no conflict exists
    UPDATE person_tune
    SET person_id = new_person_id
    WHERE person_id = old_person_id
      AND NOT EXISTS (
        SELECT 1 FROM person_tune pt2
        WHERE pt2.tune_id = person_tune.tune_id
        AND pt2.person_id = new_person_id
      );

    GET DIAGNOSTICS person_tune_updated = ROW_COUNT;

    -- Delete remaining duplicates
    DELETE FROM person_tune
    WHERE person_id = old_person_id;

    GET DIAGNOSTICS person_tune_deleted = ROW_COUNT;

    -- 4. person_instrument table
    -- Update records where no conflict exists
    UPDATE person_instrument
    SET person_id = new_person_id
    WHERE person_id = old_person_id
      AND NOT EXISTS (
        SELECT 1 FROM person_instrument pi2
        WHERE pi2.instrument = person_instrument.instrument
        AND pi2.person_id = new_person_id
      );

    GET DIAGNOSTICS person_instrument_updated = ROW_COUNT;

    -- Delete remaining duplicates
    DELETE FROM person_instrument
    WHERE person_id = old_person_id;

    GET DIAGNOSTICS person_instrument_deleted = ROW_COUNT;

    -- Build result JSON
    result := json_build_object(
        'success', true,
        'old_person_id', old_person_id,
        'new_person_id', new_person_id,
        'tables_updated', json_build_object(
            'session_person', json_build_object(
                'updated', session_person_updated,
                'deleted', session_person_deleted
            ),
            'session_instance_person', json_build_object(
                'updated', session_instance_person_updated,
                'deleted', session_instance_person_deleted
            ),
            'person_tune', json_build_object(
                'updated', person_tune_updated,
                'deleted', person_tune_deleted
            ),
            'person_instrument', json_build_object(
                'updated', person_instrument_updated,
                'deleted', person_instrument_deleted
            )
        ),
        'total_records_affected',
            session_person_updated + session_person_deleted +
            session_instance_person_updated + session_instance_person_deleted +
            person_tune_updated + person_tune_deleted +
            person_instrument_updated + person_instrument_deleted
    );

    RETURN result;

EXCEPTION
    WHEN OTHERS THEN
        -- Re-raise the exception with context
        RAISE EXCEPTION 'Error merging person_ids: %', SQLERRM;
END;
$$;

-- Add helpful comment
COMMENT ON FUNCTION merge_person_ids(INTEGER, INTEGER) IS
'Merges all references from old_person_id to new_person_id in session_person, session_instance_person, person_tune, and person_instrument tables. History tables are left unchanged to preserve audit trail. Returns JSON summary of changes.';
