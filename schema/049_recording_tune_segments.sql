-- =============================================================================
-- 049 Recordings and tune segments
-- =============================================================================
-- Replaces the abandoned spec-022 recording tables (chunked S3 live capture,
-- never finished, zero rows in every environment) with a clean-slate model for
-- the segmenter: a recording is ONE audio file, and a segment maps ONE logged
-- tune to a time range inside it.
--
-- The point of all this is the training corpus: `recording_tune_segment_resolved`
-- yields (audio file, start, end, tune_id) tuples ready to slice for an ML
-- tune-recognition model.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Out with the old. All seven tables were defined by schema/021_recording_tables.sql
-- and never populated -- verified 0 rows in production and local before dropping.
--
-- DESTRUCTIVE ON RE-RUN: this drops the tables it then recreates, so running it
-- a second time against an environment that has been segmenting discards the
-- segments and their audit history. It is a one-shot clean slate, not a
-- reconcile-to-desired-state migration.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS recording_tune_segment_resolved CASCADE;
DROP TABLE IF EXISTS recording_tune_segment_history CASCADE;
DROP TABLE IF EXISTS recording_tune_segment CASCADE;
DROP TABLE IF EXISTS recording_chunk_history CASCADE;
DROP TABLE IF EXISTS recording_chunk CASCADE;
DROP TABLE IF EXISTS recording_event_history CASCADE;
DROP TABLE IF EXISTS recording_event CASCADE;
DROP TABLE IF EXISTS recording_history CASCADE;
DROP TABLE IF EXISTS recording CASCADE;
DROP FUNCTION IF EXISTS update_recording_last_modified_date() CASCADE;

-- -----------------------------------------------------------------------------
-- recording -- one audio file covering some or all of one session instance.
--
-- Many recordings per instance (several phones on the table, or one phone that
-- stopped and restarted), so they are placed on a SHARED instance timeline:
--   * exactly one recording per instance carries is_clock_anchor -- its t=0 IS
--     the instance's zero point, enforced by a partial unique index;
--   * every other recording states clock_offset_ms, how far after that zero
--     point its own t=0 falls (negative if it started first -- then you would
--     normally move the anchor instead).
-- Instance-relative time for any recording is therefore
--   clock_offset_ms + <ms into that file>,
-- and absolute wall-clock time is started_at + <ms into that file> whenever
-- started_at is known.
--
-- Only the single-recording case matters today; the offset column is what keeps
-- the multi-recording case from needing a migration later.
-- -----------------------------------------------------------------------------
CREATE TABLE recording (
    recording_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL REFERENCES session_instance(session_instance_id) ON DELETE CASCADE,
    -- Who made the recording. Nullable: an uploaded file often has no known
    -- recordist, and the segmenter never needs one. Kept because with several
    -- phones on the table "whose recording is this" is how you tell them apart --
    -- and because person merging already repoints it (services/person_merge_service).
    person_id INTEGER REFERENCES person(person_id) ON DELETE SET NULL,
    label VARCHAR(200),
    storage_key VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'audio/mp4',
    duration_ms BIGINT NOT NULL CHECK (duration_ms > 0),
    file_size_bytes BIGINT,
    sample_rate INTEGER,
    channels SMALLINT,
    is_clock_anchor BOOLEAN NOT NULL DEFAULT FALSE,
    clock_offset_ms BIGINT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    -- Precomputed waveform: base64 of a Uint8Array, one 0-255 amplitude per
    -- bucket at peaks_hz buckets/second. Precomputed because the alternative --
    -- decoding a 3-hour file in the browser -- is a non-starter on a phone.
    peaks TEXT,
    peaks_hz NUMERIC(6, 2),
    notes TEXT,
    created_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_recording_session_instance_id ON recording(session_instance_id);
CREATE INDEX idx_recording_person_id ON recording(person_id) WHERE person_id IS NOT NULL;

-- At most one clock anchor per instance.
CREATE UNIQUE INDEX uk_recording_clock_anchor
    ON recording(session_instance_id)
    WHERE is_clock_anchor;

-- -----------------------------------------------------------------------------
-- recording_tune_segment -- "this logged tune occupies this time range in this
-- audio file". The junction between session_instance_tune and recording.
--
-- end_ms is NULLABLE on purpose and that nullability is the whole ergonomic
-- point of the segmenter: marking the next tune's start implies the previous
-- tune's end, so an operator only types an explicit end at the END OF A SET,
-- where the following start is minutes of chatter away. NULL therefore means
-- "runs until the next segment starts", resolved by the view below -- never
-- "unknown".
-- -----------------------------------------------------------------------------
CREATE TABLE recording_tune_segment (
    recording_tune_segment_id SERIAL PRIMARY KEY,
    recording_id INTEGER NOT NULL REFERENCES recording(recording_id) ON DELETE CASCADE,
    session_instance_tune_id INTEGER NOT NULL REFERENCES session_instance_tune(session_instance_tune_id) ON DELETE CASCADE,
    start_ms BIGINT NOT NULL CHECK (start_ms >= 0),
    end_ms BIGINT CHECK (end_ms IS NULL OR end_ms > start_ms),
    created_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

-- One tune is placed at most once per recording. (The same tune played twice in
-- a night is two session_instance_tune rows, so this does not get in the way.)
ALTER TABLE recording_tune_segment
    ADD CONSTRAINT uk_recording_tune_segment UNIQUE (recording_id, session_instance_tune_id);

CREATE INDEX idx_recording_tune_segment_recording ON recording_tune_segment(recording_id, start_ms);
CREATE INDEX idx_recording_tune_segment_sit ON recording_tune_segment(session_instance_tune_id);

-- -----------------------------------------------------------------------------
-- The training-corpus view: every segment with its end resolved and its tune
-- identified. An implicit end (end_ms IS NULL) becomes the next segment's start;
-- the last segment in a recording, if left implicit, falls back to the end of
-- the file.
-- -----------------------------------------------------------------------------
CREATE VIEW recording_tune_segment_resolved AS
SELECT
    rts.recording_tune_segment_id,
    rts.recording_id,
    r.session_instance_id,
    r.storage_key,
    rts.session_instance_tune_id,
    sit.tune_id,
    COALESCE(sit.name, st.alias, t.name) AS display_name,
    t.tune_type,
    rts.start_ms,
    COALESCE(
        rts.end_ms,
        LEAD(rts.start_ms) OVER (PARTITION BY rts.recording_id ORDER BY rts.start_ms),
        r.duration_ms
    ) AS resolved_end_ms,
    rts.end_ms IS NOT NULL AS end_is_explicit,
    r.clock_offset_ms + rts.start_ms AS instance_start_ms,
    r.started_at + (rts.start_ms || ' milliseconds')::INTERVAL AS absolute_start
FROM recording_tune_segment rts
JOIN recording r ON r.recording_id = rts.recording_id
JOIN session_instance_tune sit ON sit.session_instance_tune_id = rts.session_instance_tune_id
JOIN session_instance si ON si.session_instance_id = r.session_instance_id
LEFT JOIN tune t ON t.tune_id = sit.tune_id
LEFT JOIN session_tune st ON st.tune_id = sit.tune_id AND st.session_id = si.session_id;

-- =============================================================================
-- HISTORY TABLES (existing audit-trail pattern; see database.save_to_history)
-- =============================================================================

CREATE TABLE recording_history (
    history_id SERIAL PRIMARY KEY,
    recording_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    session_instance_id INTEGER,
    person_id INTEGER,
    label VARCHAR(200),
    storage_key VARCHAR(500),
    mime_type VARCHAR(100),
    duration_ms BIGINT,
    file_size_bytes BIGINT,
    sample_rate INTEGER,
    channels SMALLINT,
    is_clock_anchor BOOLEAN,
    clock_offset_ms BIGINT,
    started_at TIMESTAMPTZ,
    peaks_hz NUMERIC(6, 2),
    notes TEXT,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);
-- NB: `peaks` is deliberately NOT copied into history -- it is a large derived
-- blob recomputable from the audio, and versioning it would bloat the table.

CREATE INDEX idx_recording_history_recording_id ON recording_history(recording_id);
CREATE INDEX idx_recording_history_changed_at ON recording_history(changed_at);

CREATE TABLE recording_tune_segment_history (
    history_id SERIAL PRIMARY KEY,
    recording_tune_segment_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    recording_id INTEGER,
    session_instance_tune_id INTEGER,
    start_ms BIGINT,
    end_ms BIGINT,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_rts_history_segment_id ON recording_tune_segment_history(recording_tune_segment_id);
CREATE INDEX idx_rts_history_changed_at ON recording_tune_segment_history(changed_at);

-- -----------------------------------------------------------------------------
-- last_modified_date triggers
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION touch_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_recording_touch
    BEFORE UPDATE ON recording
    FOR EACH ROW EXECUTE FUNCTION touch_last_modified_date();

CREATE TRIGGER trigger_recording_tune_segment_touch
    BEFORE UPDATE ON recording_tune_segment
    FOR EACH ROW EXECUTE FUNCTION touch_last_modified_date();

-- =============================================================================
-- merge_tune_ids: keep tune merging working across the reshape
-- =============================================================================
-- Spec 030's merge_tune_ids moved recording_tune_segment rows by UPDATEing their
-- tune_id. That column is gone -- segments now reach their tune through
-- session_instance_tune -- so the old body would fail outright on every merge.
-- Re-declared here with that step replaced by a count, since the remap of
-- session_instance_tune.tune_id already carries the segments. The returned JSON
-- keeps its `recording_tune_segment.updated` key so callers don't have to change.
-- Everything else is spec 030's function verbatim.

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

    -- recording_tune_segment (reshaped by schema/049) hangs off
    -- session_instance_tune, not tune, so step 2 below carries the segments across
    -- on its own and there is nothing to move. Counted HERE, before that remap,
    -- because afterwards these rows are indistinguishable from segments that were
    -- already on the surviving tune -- reported only so the merge summary still
    -- says how much placed audio changed hands.
    SELECT count(*) INTO recording_tune_segment_updated
    FROM recording_tune_segment rts
    JOIN session_instance_tune sit
      ON sit.session_instance_tune_id = rts.session_instance_tune_id
    WHERE sit.tune_id = old_tune_id;

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
         heard_count, learned_date, notes, setting_id, name_alias,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT person_tune_id, 'UPDATE', changed_by_user_id, person_id, tune_id, learn_status,
           heard_count, learned_date, notes, setting_id, name_alias,
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
         heard_count, learned_date, notes, setting_id, name_alias,
         created_date, last_modified_date, created_by_user_id, last_modified_user_id)
    SELECT person_tune_id, 'DELETE', changed_by_user_id, person_id, tune_id, learn_status,
           heard_count, learned_date, notes, setting_id, name_alias,
           created_date, last_modified_date, created_by_user_id, last_modified_user_id
    FROM person_tune WHERE tune_id = old_tune_id;

    DELETE FROM person_tune
    WHERE tune_id = old_tune_id;
    GET DIAGNOSTICS person_tune_deleted = ROW_COUNT;

    -- 6. recording_tune_segment: nothing to do -- see the count before step 2.

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

COMMENT ON FUNCTION merge_tune_ids(INTEGER, INTEGER, INTEGER) IS
'Merges all references from old_tune_id to new_tune_id (tune_setting, session_tune, session_tune_alias, session_instance_tune, person_tune + person_tune_instrument via FK cascade; recording_tune_segment follows session_instance_tune), preserving the old display name as per-context aliases where no override existed, writing app-convention history rows, then marks the old tune as a redirect. Returns JSON summary. Spec 030, reshaped by 049.';

COMMIT;
