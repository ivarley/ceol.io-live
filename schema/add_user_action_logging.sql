-- Migration: Add user action logging columns
-- Adds created_by_user_id and last_modified_user_id to all tables
-- Replaces changed_by VARCHAR with changed_by_user_id INTEGER in history tables

-- ============================================
-- CORE TABLES (14)
-- ============================================

-- session
ALTER TABLE session ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- session_instance
ALTER TABLE session_instance ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_instance ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- tune
ALTER TABLE tune ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE tune ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- person
ALTER TABLE person ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE person ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- user_account
ALTER TABLE user_account ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE user_account ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- person_tune
ALTER TABLE person_tune ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE person_tune ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- person_instrument
ALTER TABLE person_instrument ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE person_instrument ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- session_person
ALTER TABLE session_person ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_person ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- session_instance_person
ALTER TABLE session_instance_person ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_instance_person ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- session_tune
ALTER TABLE session_tune ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_tune ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- session_tune_alias
ALTER TABLE session_tune_alias ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_tune_alias ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- session_instance_tune
ALTER TABLE session_instance_tune ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_instance_tune ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- tune_setting
ALTER TABLE tune_setting ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE tune_setting ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- user_session
ALTER TABLE user_session ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE user_session ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;

-- ============================================
-- HISTORY TABLES (13)
-- Add changed_by_user_id, created_by_user_id, last_modified_user_id
-- Drop changed_by VARCHAR column
-- ============================================

-- session_history
ALTER TABLE session_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE session_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE session_history DROP COLUMN IF EXISTS changed_by;

-- session_instance_history
ALTER TABLE session_instance_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_instance_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE session_instance_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE session_instance_history DROP COLUMN IF EXISTS changed_by;

-- tune_history
ALTER TABLE tune_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE tune_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE tune_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE tune_history DROP COLUMN IF EXISTS changed_by;

-- person_history
ALTER TABLE person_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE person_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE person_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE person_history DROP COLUMN IF EXISTS changed_by;

-- user_account_history
ALTER TABLE user_account_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE user_account_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE user_account_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE user_account_history DROP COLUMN IF EXISTS changed_by;

-- person_tune_history
ALTER TABLE person_tune_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE person_tune_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE person_tune_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE person_tune_history DROP COLUMN IF EXISTS changed_by;

-- person_instrument_history
ALTER TABLE person_instrument_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE person_instrument_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE person_instrument_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE person_instrument_history DROP COLUMN IF EXISTS changed_by;

-- session_person_history
ALTER TABLE session_person_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_person_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE session_person_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE session_person_history DROP COLUMN IF EXISTS changed_by;

-- session_instance_person_history
ALTER TABLE session_instance_person_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_instance_person_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE session_instance_person_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE session_instance_person_history DROP COLUMN IF EXISTS changed_by;

-- session_tune_history
ALTER TABLE session_tune_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_tune_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE session_tune_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE session_tune_history DROP COLUMN IF EXISTS changed_by;

-- session_tune_alias_history
ALTER TABLE session_tune_alias_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_tune_alias_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE session_tune_alias_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE session_tune_alias_history DROP COLUMN IF EXISTS changed_by;

-- session_instance_tune_history
ALTER TABLE session_instance_tune_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE session_instance_tune_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE session_instance_tune_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE session_instance_tune_history DROP COLUMN IF EXISTS changed_by;

-- tune_setting_history
ALTER TABLE tune_setting_history ADD COLUMN IF NOT EXISTS changed_by_user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL;
ALTER TABLE tune_setting_history ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER;
ALTER TABLE tune_setting_history ADD COLUMN IF NOT EXISTS last_modified_user_id INTEGER;
ALTER TABLE tune_setting_history DROP COLUMN IF EXISTS changed_by;

-- ============================================
-- INDEXES for common queries
-- ============================================

-- Indexes on core tables for finding records by creator/modifier
CREATE INDEX IF NOT EXISTS idx_session_created_by ON session(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_session_instance_created_by ON session_instance(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_tune_created_by ON tune(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_person_created_by ON person(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_created_by ON session_instance_tune(created_by_user_id);

-- Indexes on history tables for audit queries
CREATE INDEX IF NOT EXISTS idx_session_history_changed_by_user ON session_history(changed_by_user_id);
CREATE INDEX IF NOT EXISTS idx_session_instance_history_changed_by_user ON session_instance_history(changed_by_user_id);
CREATE INDEX IF NOT EXISTS idx_tune_history_changed_by_user ON tune_history(changed_by_user_id);
CREATE INDEX IF NOT EXISTS idx_person_history_changed_by_user ON person_history(changed_by_user_id);
CREATE INDEX IF NOT EXISTS idx_user_account_history_changed_by_user ON user_account_history(changed_by_user_id);
