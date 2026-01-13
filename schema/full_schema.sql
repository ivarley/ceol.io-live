-- =============================================================================
-- ceol.io Complete Database Schema
-- =============================================================================
-- This file creates the complete database schema from scratch.
-- Run this on an empty database to set up all tables, indexes, and triggers.
--
-- Usage:
--   psql -h localhost -U test_user -d ceol_test -f schema/full_schema.sql
--
-- Dependencies: PostgreSQL 12+
-- =============================================================================

-- =============================================================================
-- EXTENSIONS
-- =============================================================================

-- Enable unaccent extension for accent-insensitive text searches
CREATE EXTENSION IF NOT EXISTS unaccent;

-- =============================================================================
-- BASE TABLES (no foreign key dependencies)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Session table
-- -----------------------------------------------------------------------------
CREATE TABLE session (
    session_id SERIAL PRIMARY KEY,
    thesession_id INTEGER,
    name VARCHAR(255) NOT NULL,
    path VARCHAR(255) NOT NULL UNIQUE,
    location_name VARCHAR(255),
    location_website TEXT,
    location_phone VARCHAR(50),
    location_street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    comments TEXT,
    unlisted_address BOOLEAN DEFAULT FALSE,
    initiation_date DATE,
    termination_date DATE,
    recurrence TEXT,
    session_type VARCHAR(50) NOT NULL DEFAULT 'regular' CHECK (session_type IN ('regular', 'festival')),
    active_buffer_minutes_before INTEGER NOT NULL DEFAULT 60,
    active_buffer_minutes_after INTEGER NOT NULL DEFAULT 60,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_path ON session(path);
CREATE INDEX idx_session_created_by ON session(created_by_user_id);
CREATE INDEX idx_session_thesession_id ON session(thesession_id);
CREATE INDEX idx_session_timezone ON session(timezone);
CREATE INDEX idx_session_type ON session(session_type);

CREATE OR REPLACE FUNCTION update_session_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_session_last_modified_date
    BEFORE UPDATE ON session
    FOR EACH ROW
    EXECUTE FUNCTION update_session_last_modified_date();

COMMENT ON COLUMN session.timezone IS 'IANA timezone identifier (e.g., America/New_York) used to display session times';
COMMENT ON COLUMN session.active_buffer_minutes_before IS 'Minutes before session start time when it becomes active (default 60)';
COMMENT ON COLUMN session.active_buffer_minutes_after IS 'Minutes after session end time when it stops being active (default 60)';

-- -----------------------------------------------------------------------------
-- Person table
-- -----------------------------------------------------------------------------
CREATE TABLE person (
    person_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    sms_number VARCHAR(20),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    thesession_user_id INTEGER,
    active BOOLEAN DEFAULT TRUE NOT NULL,
    at_active_session_instance_id INTEGER, -- FK added after session_instance table
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE UNIQUE INDEX idx_person_email_unique ON person (email) WHERE email IS NOT NULL;
CREATE INDEX idx_person_thesession_user_id ON person (thesession_user_id);
CREATE INDEX idx_person_active ON person (active);
CREATE INDEX idx_person_created_by ON person(created_by_user_id);

COMMENT ON COLUMN person.active IS 'Whether the person is active. Inactive persons are hidden from lists.';
COMMENT ON COLUMN person.at_active_session_instance_id IS 'The session instance this person is currently attending (null when not at a session)';

-- -----------------------------------------------------------------------------
-- Tune table
-- -----------------------------------------------------------------------------
CREATE TABLE tune (
    tune_id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tune_type VARCHAR(50) CHECK (tune_type IN ('Jig', 'Reel', 'Slip Jig', 'Hop Jig', 'Hornpipe', 'Polka', 'Set Dance', 'Slide', 'Waltz', 'Barndance', 'Strathspey', 'Three-Two', 'Mazurka', 'March', 'Air')),
    tunebook_count_cached INTEGER DEFAULT 0,
    tunebook_count_cached_date DATE DEFAULT CURRENT_DATE,
    redirect_to_tune_id INTEGER REFERENCES tune(tune_id),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_tune_created_by ON tune(created_by_user_id);
CREATE INDEX idx_tune_redirect_to ON tune(redirect_to_tune_id) WHERE redirect_to_tune_id IS NOT NULL;

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

CREATE TRIGGER trigger_check_tune_redirect_chain
    BEFORE INSERT OR UPDATE ON tune
    FOR EACH ROW
    WHEN (NEW.redirect_to_tune_id IS NOT NULL)
    EXECUTE FUNCTION check_tune_redirect_chain();

CREATE OR REPLACE FUNCTION update_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_tune_last_modified_date
    BEFORE UPDATE ON tune
    FOR EACH ROW
    EXECUTE FUNCTION update_tune_last_modified_date();

-- =============================================================================
-- DEPENDENT TABLES (Level 1 - depend on base tables)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Session Instance table (depends on session)
-- -----------------------------------------------------------------------------
CREATE TABLE session_instance (
    session_instance_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES session(session_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    start_time TIME,
    end_time TIME,
    location_override VARCHAR(255),
    is_cancelled BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    comments TEXT,
    log_complete_date TIMESTAMPTZ DEFAULT NULL,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_instance_session_id ON session_instance(session_id);
CREATE INDEX idx_session_instance_date ON session_instance(date);
CREATE INDEX idx_session_instance_created_by ON session_instance(created_by_user_id);
CREATE INDEX idx_session_instance_log_complete_date ON session_instance(log_complete_date);
CREATE INDEX idx_session_instance_is_active ON session_instance(is_active) WHERE is_active = TRUE;

CREATE OR REPLACE FUNCTION update_session_instance_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_session_instance_last_modified_date
    BEFORE UPDATE ON session_instance
    FOR EACH ROW
    EXECUTE FUNCTION update_session_instance_last_modified_date();

COMMENT ON COLUMN session_instance.is_active IS 'Whether this session instance is currently active';
COMMENT ON COLUMN session_instance.log_complete_date IS 'UTC timestamp when session log was marked complete';

-- Now add the FK constraint on person.at_active_session_instance_id
ALTER TABLE person ADD CONSTRAINT fk_person_at_active_session_instance
    FOREIGN KEY (at_active_session_instance_id) REFERENCES session_instance(session_instance_id) ON DELETE SET NULL;
CREATE INDEX idx_person_at_active_session ON person(at_active_session_instance_id) WHERE at_active_session_instance_id IS NOT NULL;

-- -----------------------------------------------------------------------------
-- User Account table (depends on person)
-- -----------------------------------------------------------------------------
CREATE TABLE user_account (
    user_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL UNIQUE REFERENCES person(person_id) ON DELETE CASCADE,
    username VARCHAR(255) NOT NULL UNIQUE,
    user_email VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255),  -- NULL for passwordless (magic link) users
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT TRUE,
    is_system_admin BOOLEAN DEFAULT FALSE,
    email_verified BOOLEAN DEFAULT FALSE,
    auto_save_tunes BOOLEAN DEFAULT FALSE,
    auto_save_interval INTEGER DEFAULT 60 CHECK (auto_save_interval IN (10, 30, 60)),
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMPTZ,
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMPTZ,
    login_token VARCHAR(255),
    login_token_expires TIMESTAMPTZ,
    referred_by_person_id INTEGER REFERENCES person(person_id) ON DELETE SET NULL,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_user_person_id ON user_account (person_id);
CREATE INDEX idx_user_username ON user_account (username);
CREATE INDEX idx_user_verification_token ON user_account (verification_token) WHERE verification_token IS NOT NULL;
CREATE INDEX idx_user_reset_token ON user_account (password_reset_token) WHERE password_reset_token IS NOT NULL;
CREATE INDEX idx_user_login_token ON user_account (login_token) WHERE login_token IS NOT NULL;
CREATE UNIQUE INDEX idx_user_account_email_lower ON user_account (LOWER(user_email));
CREATE INDEX idx_user_referred_by ON user_account (referred_by_person_id) WHERE referred_by_person_id IS NOT NULL;

COMMENT ON COLUMN user_account.timezone IS 'IANA timezone identifier for displaying dates to user';
COMMENT ON COLUMN user_account.auto_save_tunes IS 'User preference for auto-saving tunes in session instance editor';
COMMENT ON COLUMN user_account.auto_save_interval IS 'User preference for auto-save interval in seconds (10, 30, or 60)';
COMMENT ON COLUMN user_account.hashed_password IS 'Bcrypt hashed password, NULL for passwordless users who use magic links';
COMMENT ON COLUMN user_account.login_token IS 'Token for magic link (passwordless) login, expires after 15 minutes';
COMMENT ON COLUMN user_account.login_token_expires IS 'UTC timestamp when magic link login token expires';
COMMENT ON COLUMN user_account.referred_by_person_id IS 'Person ID of the user who referred this account';

-- -----------------------------------------------------------------------------
-- Tune Setting table (depends on tune)
-- -----------------------------------------------------------------------------
CREATE TABLE tune_setting (
    setting_id INTEGER PRIMARY KEY,
    tune_id INTEGER NOT NULL REFERENCES tune(tune_id) ON DELETE CASCADE,
    key VARCHAR(20),
    abc TEXT,
    image TEXT,
    incipit_abc TEXT,
    incipit_image TEXT,
    cache_updated_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    UNIQUE(setting_id, tune_id)
);

CREATE INDEX idx_tune_setting_tune_id ON tune_setting (tune_id);
CREATE INDEX idx_tune_setting_cache_date ON tune_setting (cache_updated_date);

-- -----------------------------------------------------------------------------
-- Session Tune table (depends on session, tune)
-- -----------------------------------------------------------------------------
CREATE TABLE session_tune (
    session_id INTEGER REFERENCES session(session_id),
    tune_id INTEGER REFERENCES tune(tune_id),
    setting_id INTEGER,
    key VARCHAR(20),
    alias VARCHAR(255),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    PRIMARY KEY (session_id, tune_id)
);

CREATE OR REPLACE FUNCTION update_session_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_session_tune_last_modified_date
    BEFORE UPDATE ON session_tune
    FOR EACH ROW
    EXECUTE FUNCTION update_session_tune_last_modified_date();

-- -----------------------------------------------------------------------------
-- Session Tune Alias table (depends on session, tune)
-- -----------------------------------------------------------------------------
CREATE TABLE session_tune_alias (
    session_tune_alias_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES session(session_id),
    tune_id INTEGER REFERENCES tune(tune_id),
    alias VARCHAR(255) NOT NULL,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    CONSTRAINT unique_session_alias UNIQUE (session_id, alias)
);

CREATE INDEX idx_session_tune_alias_session_id ON session_tune_alias(session_id);
CREATE INDEX idx_session_tune_alias_tune_id ON session_tune_alias(tune_id);
CREATE INDEX idx_session_tune_alias_alias ON session_tune_alias(alias);

CREATE OR REPLACE FUNCTION update_session_tune_alias_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_session_tune_alias_last_modified_date
    BEFORE UPDATE ON session_tune_alias
    FOR EACH ROW
    EXECUTE FUNCTION update_session_tune_alias_last_modified_date();

-- -----------------------------------------------------------------------------
-- Person Instrument table (depends on person)
-- -----------------------------------------------------------------------------
CREATE TABLE person_instrument (
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    instrument VARCHAR(50) NOT NULL,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    PRIMARY KEY (person_id, instrument)
);

CREATE INDEX idx_person_instrument_instrument ON person_instrument (instrument);

-- -----------------------------------------------------------------------------
-- Person Tune table (depends on person, tune)
-- -----------------------------------------------------------------------------
CREATE TABLE person_tune (
    person_tune_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    tune_id INTEGER NOT NULL REFERENCES tune(tune_id) ON DELETE CASCADE,
    learn_status VARCHAR(20) NOT NULL DEFAULT 'want to learn'
        CHECK (learn_status IN ('want to learn', 'learning', 'learned')),
    heard_count INTEGER DEFAULT 0 CHECK (heard_count >= 0),
    learned_date TIMESTAMPTZ,
    notes TEXT,
    setting_id INTEGER,
    name_alias VARCHAR(255),
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    UNIQUE(person_id, tune_id)
);

CREATE INDEX idx_person_tune_person_id ON person_tune (person_id);
CREATE INDEX idx_person_tune_tune_id ON person_tune (tune_id);
CREATE INDEX idx_person_tune_learn_status ON person_tune (learn_status);
CREATE INDEX idx_person_tune_learned_date ON person_tune (learned_date) WHERE learned_date IS NOT NULL;

CREATE OR REPLACE FUNCTION update_person_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = (NOW() AT TIME ZONE 'UTC');

    -- Automatically set learned_date when status changes to 'learned'
    IF NEW.learn_status = 'learned' AND (OLD IS NULL OR OLD.learn_status != 'learned') THEN
        NEW.learned_date = (NOW() AT TIME ZONE 'UTC');
    END IF;

    -- Clear learned_date if status changes away from 'learned'
    IF NEW.learn_status != 'learned' AND OLD IS NOT NULL AND OLD.learn_status = 'learned' THEN
        NEW.learned_date = NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_person_tune_last_modified_date
    BEFORE UPDATE ON person_tune
    FOR EACH ROW
    EXECUTE FUNCTION update_person_tune_last_modified_date();

COMMENT ON COLUMN person_tune.setting_id IS 'The thesession.org setting ID for this person''s preferred version';
COMMENT ON COLUMN person_tune.name_alias IS 'Personal custom name/alias for this tune';

-- -----------------------------------------------------------------------------
-- Session Person table (depends on session, person)
-- -----------------------------------------------------------------------------
CREATE TABLE session_person (
    session_person_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES session(session_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    is_regular BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    gets_email_reminder BOOLEAN DEFAULT FALSE,
    gets_email_followup BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

ALTER TABLE session_person ADD CONSTRAINT uk_session_person UNIQUE (session_id, person_id);
CREATE INDEX idx_session_person_session_id ON session_person (session_id);
CREATE INDEX idx_session_person_person_id ON session_person (person_id);
CREATE INDEX idx_session_person_is_regular ON session_person (is_regular);
CREATE INDEX idx_session_person_is_admin ON session_person (is_admin);

-- =============================================================================
-- DEPENDENT TABLES (Level 2 - depend on level 1 tables)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Session Instance Tune table (depends on session_instance, tune, person)
-- -----------------------------------------------------------------------------
CREATE TABLE session_instance_tune (
    session_instance_tune_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER REFERENCES session_instance(session_instance_id),
    tune_id INTEGER REFERENCES tune(tune_id),
    name VARCHAR(255),
    order_number INTEGER NOT NULL,
    order_position VARCHAR(32),  -- Fractional index for CRDT-compatible ordering (base-36: 0-9a-z)
    continues_set BOOLEAN DEFAULT FALSE,
    played_timestamp TIMESTAMPTZ,
    inserted_timestamp TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    key_override VARCHAR(20),
    setting_override INTEGER,
    started_by_person_id INTEGER REFERENCES person(person_id),
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    CONSTRAINT session_instance_tune_name_or_id CHECK (tune_id IS NOT NULL OR name IS NOT NULL)
);

CREATE INDEX idx_session_instance_tune_started_by ON session_instance_tune (started_by_person_id) WHERE started_by_person_id IS NOT NULL;
CREATE INDEX idx_session_instance_tune_order_position ON session_instance_tune (session_instance_id, order_position);

CREATE OR REPLACE FUNCTION update_session_instance_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_session_instance_tune_last_modified_date
    BEFORE UPDATE ON session_instance_tune
    FOR EACH ROW
    EXECUTE FUNCTION update_session_instance_tune_last_modified_date();

-- -----------------------------------------------------------------------------
-- Session Instance Person table (depends on session_instance, person)
-- -----------------------------------------------------------------------------
CREATE TABLE session_instance_person (
    session_instance_person_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL REFERENCES session_instance(session_instance_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    attendance VARCHAR(5) CHECK (attendance IN ('yes', 'maybe', 'no')) DEFAULT NULL,
    comment TEXT,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

ALTER TABLE session_instance_person ADD CONSTRAINT uk_session_instance_person UNIQUE (session_instance_id, person_id);
CREATE INDEX idx_session_instance_person_session_instance_id ON session_instance_person (session_instance_id);
CREATE INDEX idx_session_instance_person_person_id ON session_instance_person (person_id);
CREATE INDEX idx_session_instance_person_attendance ON session_instance_person (attendance);

-- -----------------------------------------------------------------------------
-- User Session table (depends on user_account)
-- -----------------------------------------------------------------------------
CREATE TABLE user_session (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_account(user_id) ON DELETE CASCADE,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_accessed TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    expires_at TIMESTAMPTZ NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_user_session_user_id ON user_session (user_id);
CREATE INDEX idx_user_session_expires ON user_session (expires_at);
CREATE INDEX idx_user_session_last_accessed ON user_session (last_accessed);

-- -----------------------------------------------------------------------------
-- Login History table (depends on user_account)
-- -----------------------------------------------------------------------------
CREATE TABLE login_history (
    login_history_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL,
    username VARCHAR(255),
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('LOGIN_SUCCESS', 'LOGIN_FAILURE', 'LOGOUT', 'PASSWORD_RESET', 'ACCOUNT_LOCKED', 'MAGIC_LINK_SENT', 'REGISTRATION')),
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    failure_reason VARCHAR(255),
    timestamp TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    additional_data JSONB
);

CREATE INDEX idx_login_history_user_id ON login_history(user_id);
CREATE INDEX idx_login_history_username ON login_history(username);
CREATE INDEX idx_login_history_event_type ON login_history(event_type);
CREATE INDEX idx_login_history_timestamp ON login_history(timestamp);
CREATE INDEX idx_login_history_ip_address ON login_history(ip_address);
CREATE INDEX idx_login_history_session_id ON login_history(session_id);
CREATE INDEX idx_login_history_user_event_time ON login_history(user_id, event_type, timestamp);
CREATE INDEX idx_login_history_ip_event_time ON login_history(ip_address, event_type, timestamp);

-- =============================================================================
-- HISTORY/AUDIT TABLES
-- =============================================================================

-- Session history
CREATE TABLE session_history (
    history_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    thesession_id INTEGER,
    name VARCHAR(255),
    path VARCHAR(255),
    location_name VARCHAR(255),
    location_website TEXT,
    location_phone VARCHAR(50),
    location_street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    comments TEXT,
    unlisted_address BOOLEAN,
    initiation_date DATE,
    termination_date DATE,
    recurrence TEXT,
    session_type VARCHAR(50),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_history_session_id ON session_history(session_id);
CREATE INDEX idx_session_history_changed_at ON session_history(changed_at);
CREATE INDEX idx_session_history_operation ON session_history(operation);

-- Session instance history
CREATE TABLE session_instance_history (
    history_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    session_id INTEGER,
    date DATE,
    start_time TIME,
    end_time TIME,
    location_override VARCHAR(255),
    is_cancelled BOOLEAN,
    comments TEXT,
    log_complete_date TIMESTAMPTZ,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_instance_history_session_instance_id ON session_instance_history(session_instance_id);
CREATE INDEX idx_session_instance_history_changed_at ON session_instance_history(changed_at);
CREATE INDEX idx_session_instance_history_operation ON session_instance_history(operation);

-- Tune history
CREATE TABLE tune_history (
    history_id SERIAL PRIMARY KEY,
    tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    name VARCHAR(255),
    tune_type VARCHAR(50),
    tunebook_count_cached INTEGER,
    tunebook_count_cached_date DATE,
    redirect_to_tune_id INTEGER,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_tune_history_tune_id ON tune_history(tune_id);
CREATE INDEX idx_tune_history_changed_at ON tune_history(changed_at);
CREATE INDEX idx_tune_history_operation ON tune_history(operation);

-- Session tune history
CREATE TABLE session_tune_history (
    history_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    setting_id INTEGER,
    key VARCHAR(20),
    alias VARCHAR(255),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_tune_history_session_id ON session_tune_history(session_id);
CREATE INDEX idx_session_tune_history_tune_id ON session_tune_history(tune_id);
CREATE INDEX idx_session_tune_history_changed_at ON session_tune_history(changed_at);
CREATE INDEX idx_session_tune_history_operation ON session_tune_history(operation);

-- Session instance tune history
CREATE TABLE session_instance_tune_history (
    history_id SERIAL PRIMARY KEY,
    session_instance_tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    session_instance_id INTEGER,
    tune_id INTEGER,
    name VARCHAR(255),
    order_number INTEGER,
    order_position VARCHAR(32),
    continues_set BOOLEAN,
    played_timestamp TIMESTAMPTZ,
    inserted_timestamp TIMESTAMPTZ,
    key_override VARCHAR(20),
    setting_override INTEGER,
    started_by_person_id INTEGER,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_instance_tune_history_session_instance_tune_id ON session_instance_tune_history(session_instance_tune_id);
CREATE INDEX idx_session_instance_tune_history_changed_at ON session_instance_tune_history(changed_at);
CREATE INDEX idx_session_instance_tune_history_operation ON session_instance_tune_history(operation);

-- Session tune alias history
CREATE TABLE session_tune_alias_history (
    history_id SERIAL PRIMARY KEY,
    session_tune_alias_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    session_id INTEGER,
    tune_id INTEGER,
    alias VARCHAR(255),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_tune_alias_history_session_tune_alias_id ON session_tune_alias_history(session_tune_alias_id);
CREATE INDEX idx_session_tune_alias_history_changed_at ON session_tune_alias_history(changed_at);
CREATE INDEX idx_session_tune_alias_history_operation ON session_tune_alias_history(operation);

-- Session person history
CREATE TABLE session_person_history (
    history_id SERIAL PRIMARY KEY,
    session_person_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    session_id INTEGER,
    person_id INTEGER,
    is_regular BOOLEAN,
    is_admin BOOLEAN,
    gets_email_reminder BOOLEAN,
    gets_email_followup BOOLEAN,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_person_history_session_person_id ON session_person_history(session_person_id);
CREATE INDEX idx_session_person_history_changed_at ON session_person_history(changed_at);
CREATE INDEX idx_session_person_history_operation ON session_person_history(operation);

-- Session instance person history
CREATE TABLE session_instance_person_history (
    history_id SERIAL PRIMARY KEY,
    session_instance_person_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    session_instance_id INTEGER,
    person_id INTEGER,
    attendance VARCHAR(5) CHECK (attendance IN ('yes', 'maybe', 'no')),
    comment TEXT,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_session_instance_person_history_session_instance_person_id ON session_instance_person_history(session_instance_person_id);
CREATE INDEX idx_session_instance_person_history_changed_at ON session_instance_person_history(changed_at);
CREATE INDEX idx_session_instance_person_history_operation ON session_instance_person_history(operation);

-- Person history
CREATE TABLE person_history (
    history_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    sms_number VARCHAR(20),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    thesession_user_id INTEGER,
    active BOOLEAN,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_person_history_person_id ON person_history(person_id);
CREATE INDEX idx_person_history_changed_at ON person_history(changed_at);
CREATE INDEX idx_person_history_operation ON person_history(operation);

-- Person instrument history
CREATE TABLE person_instrument_history (
    history_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_person_instrument_history_person_id ON person_instrument_history (person_id);
CREATE INDEX idx_person_instrument_history_changed_at ON person_instrument_history (changed_at);
CREATE INDEX idx_person_instrument_history_operation ON person_instrument_history (operation);

-- Person tune history
CREATE TABLE person_tune_history (
    person_tune_history_id SERIAL PRIMARY KEY,
    person_tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    person_id INTEGER NOT NULL,
    tune_id INTEGER NOT NULL,
    learn_status VARCHAR(20) NOT NULL,
    heard_count INTEGER DEFAULT 0,
    learned_date TIMESTAMPTZ,
    notes TEXT,
    setting_id INTEGER,
    name_alias VARCHAR(255),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_person_tune_history_person_tune_id ON person_tune_history (person_tune_id);
CREATE INDEX idx_person_tune_history_person_id ON person_tune_history (person_id);
CREATE INDEX idx_person_tune_history_changed_at ON person_tune_history (changed_at);
CREATE INDEX idx_person_tune_history_operation ON person_tune_history (operation);

-- User account history
CREATE TABLE user_account_history (
    history_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    person_id INTEGER,
    username VARCHAR(255),
    user_email VARCHAR(255),
    hashed_password VARCHAR(255),
    timezone VARCHAR(50),
    is_active BOOLEAN,
    is_system_admin BOOLEAN,
    email_verified BOOLEAN,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMPTZ,
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMPTZ,
    login_token VARCHAR(255),
    login_token_expires TIMESTAMPTZ,
    referred_by_person_id INTEGER,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_user_account_history_user_id ON user_account_history(user_id);
CREATE INDEX idx_user_account_history_changed_at ON user_account_history(changed_at);
CREATE INDEX idx_user_account_history_operation ON user_account_history(operation);

-- Tune setting history
CREATE TABLE tune_setting_history (
    tune_setting_history_id SERIAL PRIMARY KEY,
    setting_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    tune_id INTEGER NOT NULL,
    key VARCHAR(20),
    abc TEXT,
    image TEXT,
    incipit_abc TEXT,
    incipit_image TEXT,
    cache_updated_date TIMESTAMPTZ,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_tune_setting_history_setting_id ON tune_setting_history (setting_id);
CREATE INDEX idx_tune_setting_history_changed_at ON tune_setting_history (changed_at);
CREATE INDEX idx_tune_setting_history_operation ON tune_setting_history (operation);

-- =============================================================================
-- STORED PROCEDURES AND FUNCTIONS
-- =============================================================================

-- Function to generate fractional positions from integers for CRDT-compatible ordering
-- Uses base-62 alphabet: 0-9, A-Z, a-z (sorted by ASCII byte value)
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

-- Stored procedure to merge one tune_id into another across all relevant tables
-- This updates main tables but leaves history tables unchanged to preserve audit trail
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
    UPDATE session_instance_tune
    SET tune_id = new_tune_id,
        last_modified_user_id = changed_by_user_id
    WHERE tune_id = old_tune_id;

    GET DIAGNOSTICS session_instance_tune_updated = ROW_COUNT;

    -- 3. session_tune_alias table - update where no conflict
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

    -- Delete remaining duplicates
    DELETE FROM session_tune
    WHERE tune_id = old_tune_id;

    GET DIAGNOSTICS session_tune_deleted = ROW_COUNT;

    -- 5. person_tune table - update where no conflict
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
            'tune_setting', json_build_object('updated', tune_setting_updated),
            'session_instance_tune', json_build_object('updated', session_instance_tune_updated),
            'session_tune_alias', json_build_object('updated', session_tune_alias_updated, 'deleted', session_tune_alias_deleted),
            'session_tune', json_build_object('updated', session_tune_updated, 'deleted', session_tune_deleted),
            'person_tune', json_build_object('updated', person_tune_updated, 'deleted', person_tune_deleted)
        ),
        'total_records_affected',
            tune_setting_updated + session_instance_tune_updated +
            session_tune_alias_updated + session_tune_alias_deleted +
            session_tune_updated + session_tune_deleted +
            person_tune_updated + person_tune_deleted
    );

    RETURN result;

EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Error merging tune_ids: %', SQLERRM;
END;
$$;

COMMENT ON FUNCTION merge_tune_ids(INTEGER, INTEGER, INTEGER) IS
'Merges all references from old_tune_id to new_tune_id across tables. Marks old tune with redirect_to_tune_id.';

-- =============================================================================
-- Schema creation complete
-- =============================================================================
