-- Spec 037: person_tune.key — "I play this in ..."
--
-- A person's key for a tune, mirroring session_tune.key and
-- session_instance_tune.key_override. Nullable; NULL means "no opinion — whatever
-- the setting says". Vocabulary is the app's MUSICAL_KEYS list (frontend
-- logic.js); no CHECK constraint, matching the other two key columns.
--
-- Label only: it does not transpose notation and does not surface outside the
-- tune drawer.

ALTER TABLE person_tune
ADD COLUMN IF NOT EXISTS key VARCHAR(20);

COMMENT ON COLUMN person_tune.key IS 'The key this person plays the tune in; NULL means no preference (use the setting''s key)';

-- Keep the audit table structurally parallel with the table it shadows.
ALTER TABLE person_tune_history
ADD COLUMN IF NOT EXISTS key VARCHAR(20);

-- merge_tune_ids (spec 030) snapshots person_tune rows into person_tune_history
-- with an explicit column list, so a new column silently drops out of the merge
-- audit trail. Redefined here with `key` added to both snapshot INSERTs (the
-- clean-move UPDATE snapshot and the conflict-row DELETE snapshot). Body is
-- otherwise byte-identical to 030_tune_merge_gaps.sql.

CREATE OR REPLACE FUNCTION merge_tune_ids(
    old_tune_id INTEGER,
    new_tune_id INTEGER,
    changed_by_user_id INTEGER DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
AS $$
DECLARE
    v_old_name TEXT;
    v_new_name TEXT;
    v_names_differ BOOLEAN;
    v_affected_session_ids INTEGER[];

    tune_setting_updated INTEGER := 0;
    session_tune_updated INTEGER := 0;
    session_tune_deleted INTEGER := 0;
    session_tune_alias_updated INTEGER := 0;
    session_tune_alias_deleted INTEGER := 0;
    session_tune_alias_added INTEGER := 0;
    session_instance_tune_updated INTEGER := 0;
    person_tune_updated INTEGER := 0;
    person_tune_deleted INTEGER := 0;
    person_tune_instrument_moved INTEGER := 0;
    person_tune_instrument_dropped INTEGER := 0;
    recording_tune_segment_updated INTEGER := 0;
    person_tune_alias_filled INTEGER := 0;
    session_tune_alias_col_filled INTEGER := 0;
    session_instance_tune_name_filled INTEGER := 0;
    result JSON;
BEGIN
    -- Validate inputs
    IF old_tune_id IS NULL OR new_tune_id IS NULL THEN
        RAISE EXCEPTION 'Both old_tune_id and new_tune_id must be provided';
    END IF;

    IF old_tune_id = new_tune_id THEN
        RAISE EXCEPTION 'old_tune_id and new_tune_id cannot be the same';
    END IF;

    SELECT name INTO v_old_name FROM tune WHERE tune_id = old_tune_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'old_tune_id % does not exist in tune table', old_tune_id;
    END IF;

    SELECT name INTO v_new_name FROM tune WHERE tune_id = new_tune_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'new_tune_id % does not exist in tune table', new_tune_id;
    END IF;

    IF EXISTS (SELECT 1 FROM tune WHERE tune_id = old_tune_id AND redirect_to_tune_id IS NOT NULL) THEN
        RAISE EXCEPTION 'old_tune_id % is already a redirect', old_tune_id;
    END IF;

    IF EXISTS (SELECT 1 FROM tune WHERE tune_id = new_tune_id AND redirect_to_tune_id IS NOT NULL) THEN
        RAISE EXCEPTION 'new_tune_id % is a redirect - cannot redirect to a redirect', new_tune_id;
    END IF;

    v_names_differ := v_old_name IS DISTINCT FROM v_new_name;

    -- Sessions that knew the old tune, captured BEFORE any rows move: they get the
    -- old name as a searchable session_tune_alias on the new tune (spec 030 #2).
    SELECT COALESCE(array_agg(DISTINCT session_id), '{}') INTO v_affected_session_ids
    FROM (
        SELECT session_id FROM session_tune WHERE tune_id = old_tune_id
        UNION
        SELECT session_id FROM session_tune_alias WHERE tune_id = old_tune_id
    ) s;

    -- 1. tune_setting: setting_id is globally unique, plain move.
    INSERT INTO tune_setting_history
        (setting_id, operation, changed_by_user_id, tune_id, key, abc, image, incipit_abc, incipit_image,
         cache_updated_date, created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT setting_id, 'UPDATE', changed_by_user_id, tune_id, key, abc, image, incipit_abc, incipit_image,
           cache_updated_date, created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM tune_setting WHERE tune_id = old_tune_id;

    UPDATE tune_setting
    SET tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id;
    GET DIAGNOSTICS tune_setting_updated = ROW_COUNT;

    -- 2. session_instance_tune: move, preserving the displayed name. Rows with no
    -- per-row name were showing the OLD canonical name; freeze it into sit.name so
    -- the log keeps reading the way it was written.
    INSERT INTO session_instance_tune_history
        (session_instance_tune_id, operation, changed_by_user_id, session_instance_id, tune_id,
         name, order_position, record_type, played_timestamp, inserted_timestamp,
         key_override, setting_override, source, confidence, played_start, played_end,
         logged_timestamp, client_device_id, deleted,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT session_instance_tune_id, 'UPDATE', changed_by_user_id, session_instance_id, tune_id,
           name, order_position, record_type, played_timestamp, inserted_timestamp,
           key_override, setting_override, source, confidence, played_start, played_end,
           logged_timestamp, client_device_id, deleted,
           created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM session_instance_tune WHERE tune_id = old_tune_id;

    IF v_names_differ THEN
        SELECT COUNT(*) INTO session_instance_tune_name_filled
        FROM session_instance_tune WHERE tune_id = old_tune_id AND name IS NULL;
    END IF;

    UPDATE session_instance_tune
    SET tune_id = new_tune_id,
        name = CASE WHEN v_names_differ THEN COALESCE(name, v_old_name) ELSE name END,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id;
    GET DIAGNOSTICS session_instance_tune_updated = ROW_COUNT;

    -- 3. session_tune_alias: move where the (session_id, alias) slot is free...
    INSERT INTO session_tune_alias_history
        (session_tune_alias_id, operation, changed_by_user_id, session_id, tune_id, alias,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT session_tune_alias_id, 'UPDATE', changed_by_user_id, session_id, tune_id, alias,
           created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM session_tune_alias sta
    WHERE sta.tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM session_tune_alias sta2
        WHERE sta2.session_id = sta.session_id
          AND sta2.tune_id = new_tune_id
          AND sta2.alias = sta.alias
      );

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

    -- ...and drop true duplicates.
    INSERT INTO session_tune_alias_history
        (session_tune_alias_id, operation, changed_by_user_id, session_id, tune_id, alias,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT session_tune_alias_id, 'DELETE', changed_by_user_id, session_id, tune_id, alias,
           created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM session_tune_alias WHERE tune_id = old_tune_id;

    DELETE FROM session_tune_alias
    WHERE tune_id = old_tune_id;
    GET DIAGNOSTICS session_tune_alias_deleted = ROW_COUNT;

    -- 4. session_tune: move where the session doesn't already have the new tune,
    -- filling the session-level display alias with the old name (only where no
    -- alias was set — an existing alias was already the displayed name).
    INSERT INTO session_tune_history
        (session_id, tune_id, operation, changed_by_user_id, setting_id, key, alias,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT session_id, tune_id, 'UPDATE', changed_by_user_id, setting_id, key, alias,
           created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM session_tune st
    WHERE st.tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM session_tune st2
        WHERE st2.session_id = st.session_id AND st2.tune_id = new_tune_id
      );

    IF v_names_differ THEN
        SELECT COUNT(*) INTO session_tune_alias_col_filled
        FROM session_tune st
        WHERE st.tune_id = old_tune_id
          AND st.alias IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM session_tune st2
            WHERE st2.session_id = st.session_id AND st2.tune_id = new_tune_id
          );
    END IF;

    UPDATE session_tune
    SET tune_id = new_tune_id,
        alias = CASE WHEN v_names_differ THEN COALESCE(alias, v_old_name) ELSE alias END,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM session_tune st2
        WHERE st2.session_id = session_tune.session_id
          AND st2.tune_id = new_tune_id
      );
    GET DIAGNOSTICS session_tune_updated = ROW_COUNT;

    -- Conflict rows (session already has the new tune): survivor wins, drop old.
    INSERT INTO session_tune_history
        (session_id, tune_id, operation, changed_by_user_id, setting_id, key, alias,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT session_id, tune_id, 'DELETE', changed_by_user_id, setting_id, key, alias,
           created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM session_tune WHERE tune_id = old_tune_id;

    DELETE FROM session_tune
    WHERE tune_id = old_tune_id;
    GET DIAGNOSTICS session_tune_deleted = ROW_COUNT;

    -- 5. person_tune + person_tune_instrument. Instrument overrides follow their
    -- parent: clean moves carry them via the FK's ON UPDATE CASCADE; conflict
    -- deletes drop them via ON DELETE CASCADE (survivor wins, spec 030 #3).
    -- History for the children first (counts double as the audit).
    INSERT INTO person_tune_instrument_history
        (person_id, tune_id, instrument, operation, changed_by_user_id, status,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT pti.person_id, pti.tune_id, pti.instrument, 'UPDATE', changed_by_user_id, pti.status,
           pti.created_date, pti.last_modified_date, pti.created_by_user_id, pti.last_modified_user_id
    FROM person_tune_instrument pti
    JOIN person_tune pt ON pt.person_id = pti.person_id AND pt.tune_id = pti.tune_id
    WHERE pti.tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM person_tune pt2
        WHERE pt2.person_id = pt.person_id AND pt2.tune_id = new_tune_id
      );
    GET DIAGNOSTICS person_tune_instrument_moved = ROW_COUNT;

    INSERT INTO person_tune_instrument_history
        (person_id, tune_id, instrument, operation, changed_by_user_id, status,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT pti.person_id, pti.tune_id, pti.instrument, 'DELETE', changed_by_user_id, pti.status,
           pti.created_date, pti.last_modified_date, pti.created_by_user_id, pti.last_modified_user_id
    FROM person_tune_instrument pti
    WHERE pti.tune_id = old_tune_id
      AND EXISTS (
        SELECT 1 FROM person_tune pt2
        WHERE pt2.person_id = pti.person_id AND pt2.tune_id = new_tune_id
      );
    GET DIAGNOSTICS person_tune_instrument_dropped = ROW_COUNT;

    -- person_tune clean moves, filling the personal display alias with the old name.
    INSERT INTO person_tune_history
        (person_tune_id, operation, changed_by_user_id, person_id, tune_id, learn_status,
         heard_count, learned_date, notes, setting_id, name_alias, key,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT person_tune_id, 'UPDATE', changed_by_user_id, person_id, tune_id, learn_status,
           heard_count, learned_date, notes, setting_id, name_alias, key,
           created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM person_tune pt
    WHERE pt.tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM person_tune pt2
        WHERE pt2.person_id = pt.person_id AND pt2.tune_id = new_tune_id
      );

    IF v_names_differ THEN
        SELECT COUNT(*) INTO person_tune_alias_filled
        FROM person_tune pt
        WHERE pt.tune_id = old_tune_id
          AND pt.name_alias IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM person_tune pt2
            WHERE pt2.person_id = pt.person_id AND pt2.tune_id = new_tune_id
          );
    END IF;

    UPDATE person_tune
    SET tune_id = new_tune_id,
        name_alias = CASE WHEN v_names_differ THEN COALESCE(name_alias, v_old_name) ELSE name_alias END,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id
      AND NOT EXISTS (
        SELECT 1 FROM person_tune pt2
        WHERE pt2.person_id = person_tune.person_id
          AND pt2.tune_id = new_tune_id
      );
    GET DIAGNOSTICS person_tune_updated = ROW_COUNT;

    -- Conflict rows: survivor wins, old row (and its overrides, via cascade) go.
    INSERT INTO person_tune_history
        (person_tune_id, operation, changed_by_user_id, person_id, tune_id, learn_status,
         heard_count, learned_date, notes, setting_id, name_alias, key,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT person_tune_id, 'DELETE', changed_by_user_id, person_id, tune_id, learn_status,
           heard_count, learned_date, notes, setting_id, name_alias, key,
           created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM person_tune WHERE tune_id = old_tune_id;

    DELETE FROM person_tune
    WHERE tune_id = old_tune_id;
    GET DIAGNOSTICS person_tune_deleted = ROW_COUNT;

    -- 6. recording_tune_segment: plain move (no unique constraints, no history table).
    UPDATE recording_tune_segment
    SET tune_id = new_tune_id
    WHERE tune_id = old_tune_id;
    GET DIAGNOSTICS recording_tune_segment_updated = ROW_COUNT;

    -- 7. Old name stays searchable per session that knew the old tune: add it as a
    -- session_tune_alias on the new tune. UNIQUE (session_id, alias) skips dupes.
    IF v_names_differ AND array_length(v_affected_session_ids, 1) IS NOT NULL THEN
        WITH ins AS (
            INSERT INTO session_tune_alias (session_id, tune_id, alias, created_by_user_id, last_modified_user_id)
            SELECT sid, new_tune_id, v_old_name, changed_by_user_id, changed_by_user_id
            FROM unnest(v_affected_session_ids) AS sid
            ON CONFLICT (session_id, alias) DO NOTHING
            RETURNING session_tune_alias_id, session_id, tune_id, alias,
                      created_date, last_modified_date, created_by_user_id, last_modified_user_id
        ), hist AS (
            INSERT INTO session_tune_alias_history
                (session_tune_alias_id, operation, changed_by_user_id, session_id, tune_id, alias,
                 created_date, last_modified_date, created_by_user_id, last_modified_user_id)
            SELECT session_tune_alias_id, 'INSERT', changed_by_user_id, session_id, tune_id, alias,
                   created_date, last_modified_date, created_by_user_id, last_modified_user_id
            FROM ins
        )
        SELECT COUNT(*) INTO session_tune_alias_added FROM ins;
    END IF;

    -- 8. Tombstone the old tune.
    INSERT INTO tune_history
        (tune_id, operation, changed_by_user_id, name, tune_type, tunebook_count_cached,
         tunebook_count_cached_date, created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT tune_id, 'UPDATE', changed_by_user_id, name, tune_type, tunebook_count_cached,
           tunebook_count_cached_date, created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM tune WHERE tune_id = old_tune_id;

    UPDATE tune
    SET redirect_to_tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id;

    result := json_build_object(
        'success', true,
        'old_tune_id', old_tune_id,
        'new_tune_id', new_tune_id,
        'old_tune_name', v_old_name,
        'new_tune_name', v_new_name,
        'names_differ', v_names_differ,
        'tables_updated', json_build_object(
            'tune_setting', json_build_object(
                'updated', tune_setting_updated
            ),
            'session_instance_tune', json_build_object(
                'updated', session_instance_tune_updated,
                'name_filled', session_instance_tune_name_filled
            ),
            'session_tune_alias', json_build_object(
                'updated', session_tune_alias_updated,
                'deleted', session_tune_alias_deleted,
                'added', session_tune_alias_added
            ),
            'session_tune', json_build_object(
                'updated', session_tune_updated,
                'deleted', session_tune_deleted,
                'alias_filled', session_tune_alias_col_filled
            ),
            'person_tune', json_build_object(
                'updated', person_tune_updated,
                'deleted', person_tune_deleted,
                'alias_filled', person_tune_alias_filled
            ),
            'person_tune_instrument', json_build_object(
                'moved', person_tune_instrument_moved,
                'dropped', person_tune_instrument_dropped
            ),
            'recording_tune_segment', json_build_object(
                'updated', recording_tune_segment_updated
            )
        ),
        'total_records_affected',
            tune_setting_updated +
            session_instance_tune_updated +
            session_tune_alias_updated + session_tune_alias_deleted + session_tune_alias_added +
            session_tune_updated + session_tune_deleted +
            person_tune_updated + person_tune_deleted +
            person_tune_instrument_moved + person_tune_instrument_dropped +
            recording_tune_segment_updated
    );

    RETURN result;

EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Error merging tune_ids: %', SQLERRM;
END;
$$;
