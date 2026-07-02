-- Per-instrument tune status (see specs/current/data/people-model.md).
--
-- Adds a second, orthogonal axis to person_tune: how far along a tune is on each
-- instrument a person plays. `person_tune.learn_status` stays the person's "auto"
-- (linked) instruments' shared status; per-instrument state is stored sparsely as
-- OVERRIDE rows here. Resolution for (person, tune, instrument):
--   1. an override row exists  -> use it
--   2. else instrument is_auto -> person_tune.learn_status
--   3. else                    -> not tracked on that instrument
--
-- Idempotent-ish: guarded so re-running is safe on a partially-migrated DB.

-- 1. Each instrument on a person's profile is either "auto" (follows the main status
--    control) or manual (a curated, independent list that starts empty).
ALTER TABLE person_instrument
    ADD COLUMN IF NOT EXISTS is_auto BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Sparse per-instrument override rows.
CREATE TABLE IF NOT EXISTS person_tune_instrument (
    person_id INTEGER NOT NULL,
    tune_id INTEGER NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'learning'
        CHECK (status IN ('want to learn', 'learning', 'learned')),
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    PRIMARY KEY (person_id, tune_id, instrument),
    -- Overrides only exist for tunes already on the person's list; cascade-delete
    -- with the parent person_tune row (its UNIQUE(person_id, tune_id) backs this FK).
    FOREIGN KEY (person_id, tune_id)
        REFERENCES person_tune (person_id, tune_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_person_tune_instrument_person_id
    ON person_tune_instrument (person_id);

CREATE OR REPLACE FUNCTION update_person_tune_instrument_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = (NOW() AT TIME ZONE 'UTC');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_person_tune_instrument_last_modified_date ON person_tune_instrument;
CREATE TRIGGER trigger_person_tune_instrument_last_modified_date
    BEFORE UPDATE ON person_tune_instrument
    FOR EACH ROW
    EXECUTE FUNCTION update_person_tune_instrument_last_modified_date();

-- 3. Audit table (schema parity with the other person_* history tables).
CREATE TABLE IF NOT EXISTS person_tune_instrument_history (
    history_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL,
    tune_id INTEGER NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    status VARCHAR(20),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_person_tune_instrument_history_person_id
    ON person_tune_instrument_history (person_id);
CREATE INDEX IF NOT EXISTS idx_person_tune_instrument_history_changed_at
    ON person_tune_instrument_history (changed_at);
CREATE INDEX IF NOT EXISTS idx_person_tune_instrument_history_operation
    ON person_tune_instrument_history (operation);
