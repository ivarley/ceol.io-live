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

-- Enable pg_trgm for index-backed substring tune-name search (see migration 026 and
-- the idx_tune_name_trgm index below).
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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
    -- Auto-create upcoming instances from the recurrence (see add_auto_create_instances.sql).
    auto_create_instances BOOLEAN NOT NULL DEFAULT FALSE,
    auto_create_hours_ahead INTEGER NOT NULL DEFAULT 24
        CHECK (auto_create_hours_ahead >= 1 AND auto_create_hours_ahead <= 168),
    -- Per-session live-logging local-cache sizes (spec 024): N most-played tunes of this
    -- session + M globally-popular tunes not already in N (see migration 025).
    live_cache_session_limit INTEGER NOT NULL DEFAULT 200,
    live_cache_global_limit INTEGER NOT NULL DEFAULT 25,
    -- Per-session people-tracking flags (spec 039, migration 038). All default TRUE:
    -- opt-out, not opt-in. Set-starters require attendance (the CHECK below).
    show_people_list BOOLEAN NOT NULL DEFAULT TRUE,
    track_attendance BOOLEAN NOT NULL DEFAULT TRUE,
    track_set_starters BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_session_starters_need_attendance
        CHECK (track_attendance OR NOT track_set_starters),
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

-- Index-backed tune-name search (see migration 026). One IMMUTABLE normalization
-- function (fold smart quotes -> ASCII, strip accents, lowercase) shared by both the
-- index expressions and the matching queries (api_routes.match_tune_core,
-- database.find_matching_tune), so the planner uses the indexes.
CREATE OR REPLACE FUNCTION tune_search_key(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $$
    SELECT lower(unaccent('unaccent', translate($1,
        chr(8216)||chr(8217)||chr(700)||chr(8242)||chr(96)||chr(180)
        ||chr(8220)||chr(8221)||chr(8222)||chr(8243)||chr(171)||chr(187),
        chr(39)||chr(39)||chr(39)||chr(39)||chr(39)||chr(39)
        ||chr(34)||chr(34)||chr(34)||chr(34)||chr(34)||chr(34))))
$$;

-- Substring (wildcard candidate list) and exact ("The "-flexible) name search.
CREATE INDEX idx_tune_name_trgm ON tune USING gin (tune_search_key(name) gin_trgm_ops)
    WHERE redirect_to_tune_id IS NULL;
CREATE INDEX idx_tune_name_key ON tune (tune_search_key(name))
    WHERE redirect_to_tune_id IS NULL;

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
    -- 'legacy' (classic pill editor) | 'live' (new SSE editor, spec 024). Set 'live' on the
    -- first live op; the legacy editor is read-only for a 'live' instance (one-way lock).
    logging_mode VARCHAR(10) NOT NULL DEFAULT 'legacy',
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
    beta_live_logging BOOLEAN NOT NULL DEFAULT FALSE,  -- opt-in to the new live logger (admin-set, spec 024)
    receive_update_emails BOOLEAN NOT NULL DEFAULT TRUE,  -- app update emails, on by default; opt-out on profile (spec 027)
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
COMMENT ON COLUMN user_account.receive_update_emails IS 'Receives occasional app update emails; on by default, opt-out on profile or via unsubscribe link (spec 027)';

-- -----------------------------------------------------------------------------
-- Email message tables (spec 027) — admin-sent app update emails
-- -----------------------------------------------------------------------------
-- One row per admin send (test sends to yourself are not recorded)
CREATE TABLE email_message (
    email_message_id   SERIAL PRIMARY KEY,
    subject            TEXT NOT NULL,
    body_markdown      TEXT NOT NULL,
    sent_by_user_id    INTEGER NOT NULL REFERENCES user_account(user_id),
    sent_date          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recipient_count    INTEGER NOT NULL DEFAULT 0,
    success_count      INTEGER NOT NULL DEFAULT 0,
    failure_count      INTEGER NOT NULL DEFAULT 0
);

-- One row per recipient per message
CREATE TABLE email_message_recipient (
    email_message_id   INTEGER NOT NULL REFERENCES email_message(email_message_id),
    user_id            INTEGER NOT NULL REFERENCES user_account(user_id),
    email              TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('sent', 'failed')),
    error_message      TEXT,
    PRIMARY KEY (email_message_id, user_id)
);

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
    -- "auto" (linked) instruments follow person_tune.learn_status; manual ones are a
    -- curated per-instrument list that starts empty (per-instrument tune status).
    is_auto BOOLEAN NOT NULL DEFAULT TRUE,
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
    key VARCHAR(20),
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

    -- BEFORE UPDATE only, so OLD is always the prior row. Do NOT guard with
    -- `OLD IS [NOT] NULL`: for a composite row that is NULL only when *every* column is
    -- null, so any row with a null column (notes, setting_id, ...) made the clear branch
    -- never run, leaving learned_date set after learned -> not-learned (breaks the model
    -- validator / the detail modal).
    IF NEW.learn_status = 'learned' AND OLD.learn_status <> 'learned' THEN
        NEW.learned_date = (NOW() AT TIME ZONE 'UTC');
    ELSIF NEW.learn_status <> 'learned' AND OLD.learn_status = 'learned' THEN
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
-- Person Tune Instrument table (depends on person_tune)
-- Sparse per-instrument status OVERRIDES. Resolution for (person, tune, instrument):
--   override row -> else instrument is_auto -> person_tune.learn_status -> else absent.
-- -----------------------------------------------------------------------------
CREATE TABLE person_tune_instrument (
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
    FOREIGN KEY (person_id, tune_id)
        REFERENCES person_tune (person_id, tune_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX idx_person_tune_instrument_person_id ON person_tune_instrument (person_id);

CREATE OR REPLACE FUNCTION update_person_tune_instrument_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = (NOW() AT TIME ZONE 'UTC');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_person_tune_instrument_last_modified_date
    BEFORE UPDATE ON person_tune_instrument
    FOR EACH ROW
    EXECUTE FUNCTION update_person_tune_instrument_last_modified_date();

-- -----------------------------------------------------------------------------
-- Session Person table (depends on session, person)
-- -----------------------------------------------------------------------------
-- Spec 034: four orthogonal fields, each answering exactly one question.
--   relationship -- whose session is this? Set by the person OR a session admin. Grants no
--                   access; drives the "my sessions" lenses and community tune stats.
--   confirmed    -- does the session vouch for them? The SOLE gate on people-visibility
--                   (is_admin OR confirmed). Admin-set. Check-in never sets it.
--   archived     -- an admin's display preference: hidden from default lists, still findable
--                   by typing. Never inferred; check-in does not un-archive.
-- There is no is_regular: "regular-ness" is computed from attendance and is advisory only.
CREATE TABLE session_person (
    session_person_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES session(session_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    relationship VARCHAR(10) NOT NULL DEFAULT 'member'
        CHECK (relationship IN ('member', 'visitor')),
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
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
CREATE INDEX idx_session_person_relationship ON session_person (session_id, relationship)
    WHERE archived = FALSE;
CREATE INDEX idx_session_person_is_admin ON session_person (is_admin);

-- Live-logging color (spec 024 §F): a person's stable palette color at a session,
-- assigned on first appearance and persistent across instances/weeks/restarts.
-- Deliberately its OWN table (not session_person): a color is not membership and
-- not attendance, so assigning one must never imply either.
CREATE TABLE session_logger_color (
    session_id  INTEGER NOT NULL REFERENCES session(session_id) ON DELETE CASCADE,
    person_id   INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    color       SMALLINT NOT NULL,   -- palette index (0..N-1); UI maps index -> color
    created_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (session_id, person_id)
);

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
    order_position VARCHAR(32) COLLATE "C",  -- Fractional index for CRDT-compatible ordering (base-62: 0-9, A-Z, a-z)
    record_type VARCHAR(16) NOT NULL DEFAULT 'tune',  -- 'tune' | 'break' (a 'break' row is an explicit set boundary, see spec 023)
    played_timestamp TIMESTAMPTZ,
    inserted_timestamp TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    key_override VARCHAR(20),
    setting_override INTEGER,
    started_by_person_id INTEGER REFERENCES person(person_id),
    -- live logging (spec 024 §I): provenance + soft-delete tombstone. Audio-only
    -- columns (source/confidence/played_*) exist now so the audio task plugs in
    -- with no later migration; human ops never write played_*.
    source VARCHAR(16) NOT NULL DEFAULT 'human',
    confidence SMALLINT,            -- 0..100; NULL = definite human entry
    played_start TIMESTAMPTZ,       -- audio-only
    played_end TIMESTAMPTZ,         -- audio-only
    logged_timestamp TIMESTAMPTZ,   -- client-asserted log time
    client_device_id VARCHAR(64),
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    -- break rows carry neither tune_id nor name; tune rows still require one of them
    CONSTRAINT session_instance_tune_name_or_id CHECK (record_type = 'break' OR tune_id IS NOT NULL OR name IS NOT NULL)
);

CREATE INDEX idx_session_instance_tune_started_by ON session_instance_tune (started_by_person_id) WHERE started_by_person_id IS NOT NULL;
CREATE INDEX idx_session_instance_tune_order_position ON session_instance_tune (session_instance_id, order_position);
-- Live reads skip tombstoned rows (spec 024).
CREATE INDEX idx_session_instance_tune_live ON session_instance_tune (session_instance_id, order_position) WHERE deleted = FALSE;

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
    -- live logging (spec 024 §F): monotonic per-instance arrival ordinal; the UI
    -- infers a presence color from it (palette[seq mod N]). Claimed on first SSE connect.
    arrival_seq INTEGER,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

ALTER TABLE session_instance_person ADD CONSTRAINT uk_session_instance_person UNIQUE (session_instance_id, person_id);
CREATE INDEX idx_session_instance_person_session_instance_id ON session_instance_person (session_instance_id);
CREATE INDEX idx_session_instance_person_person_id ON session_instance_person (person_id);
CREATE INDEX idx_session_instance_person_attendance ON session_instance_person (attendance);
CREATE UNIQUE INDEX uq_session_instance_person_arrival ON session_instance_person (session_instance_id, arrival_seq) WHERE arrival_seq IS NOT NULL;

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
-- Session Event table (depends on session_instance) -- live logging feed, spec 024
-- -----------------------------------------------------------------------------
-- Append-only change feed driving real-time SSE fan-out. session_instance_tune
-- remains canonical state; this is the ordered delivery/replay log. event_id is
-- globally monotonic and doubles as the SSE Last-Event-ID cursor. See spec 024 §B.
CREATE TABLE session_event (
    event_id            BIGSERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL REFERENCES session_instance(session_instance_id) ON DELETE CASCADE,
    op_type             VARCHAR(32) NOT NULL,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    op_id               UUID,                 -- client idempotency key (spec 024 §C); NULL for server-generated events
    created_by_user_id  INTEGER,
    server_ts           TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX idx_session_event_instance ON session_event (session_instance_id, event_id);
CREATE UNIQUE INDEX uq_session_event_op_id ON session_event (op_id) WHERE op_id IS NOT NULL;

-- -----------------------------------------------------------------------------
-- Corroboration table (depends on session_instance_tune) -- spec 024 §H30/§I
-- -----------------------------------------------------------------------------
-- Per-user assertions about a tune record (who else logged/heard the same tune
-- in the same slot, with what source/confidence). Keyed by user; person derived.
CREATE TABLE corroboration (
    corroboration_id    SERIAL PRIMARY KEY,
    record_id           INTEGER NOT NULL REFERENCES session_instance_tune(session_instance_tune_id) ON DELETE CASCADE,
    user_id             INTEGER,
    source              VARCHAR(16) NOT NULL DEFAULT 'human',
    confidence          SMALLINT,
    client_asserted_ts  TIMESTAMPTZ,
    created_date        TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    CONSTRAINT uq_corroboration_record_user UNIQUE (record_id, user_id)
);
CREATE INDEX idx_corroboration_record ON corroboration (record_id);

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

-- -----------------------------------------------------------------------------
-- Recording table - one continuous recording from one device at one session
-- -----------------------------------------------------------------------------
CREATE TABLE recording (
    recording_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL REFERENCES session_instance(session_instance_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    source VARCHAR(10) NOT NULL DEFAULT 'live' CHECK (source IN ('live', 'upload')),
    status VARCHAR(20) NOT NULL DEFAULT 'started' CHECK (status IN ('started', 'recording', 'paused', 'stopped', 'failed')),
    device_info JSONB,
    format VARCHAR(50),
    sample_rate INTEGER,
    channels INTEGER,
    bitrate INTEGER,
    s3_prefix VARCHAR(500),
    total_chunks INTEGER DEFAULT 0,
    total_duration_ms BIGINT DEFAULT 0,
    total_size_bytes BIGINT DEFAULT 0,
    client_started_at TIMESTAMPTZ,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_recording_session_instance_id ON recording(session_instance_id);
CREATE INDEX idx_recording_person_id ON recording(person_id);
CREATE INDEX idx_recording_status ON recording(status);

CREATE OR REPLACE FUNCTION update_recording_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_recording_last_modified_date
    BEFORE UPDATE ON recording
    FOR EACH ROW
    EXECUTE FUNCTION update_recording_last_modified_date();

-- -----------------------------------------------------------------------------
-- Recording chunk table - individual 30-second audio chunks
-- -----------------------------------------------------------------------------
CREATE TABLE recording_chunk (
    recording_chunk_id SERIAL PRIMARY KEY,
    recording_id INTEGER NOT NULL REFERENCES recording(recording_id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    start_timestamp_ms BIGINT NOT NULL,
    end_timestamp_ms BIGINT NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    file_size_bytes INTEGER,
    upload_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (upload_status IN ('pending', 'uploading', 'uploaded', 'failed')),
    checksum VARCHAR(64),
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

ALTER TABLE recording_chunk ADD CONSTRAINT uk_recording_chunk_seq UNIQUE (recording_id, sequence_number);
CREATE INDEX idx_recording_chunk_recording_id ON recording_chunk(recording_id);
CREATE INDEX idx_recording_chunk_upload_status ON recording_chunk(upload_status);

-- -----------------------------------------------------------------------------
-- Recording event table - lifecycle events for debugging
-- -----------------------------------------------------------------------------
CREATE TABLE recording_event (
    recording_event_id SERIAL PRIMARY KEY,
    recording_id INTEGER NOT NULL REFERENCES recording(recording_id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN ('start', 'pause', 'resume', 'stop', 'error', 'chunk_gap')),
    event_data JSONB,
    client_timestamp TIMESTAMPTZ,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX idx_recording_event_recording_id ON recording_event(recording_id);
CREATE INDEX idx_recording_event_event_type ON recording_event(event_type);

-- -----------------------------------------------------------------------------
-- Recording tune segment table (future - define schema only)
-- -----------------------------------------------------------------------------
CREATE TABLE recording_tune_segment (
    recording_tune_segment_id SERIAL PRIMARY KEY,
    recording_id INTEGER NOT NULL REFERENCES recording(recording_id) ON DELETE CASCADE,
    tune_id INTEGER REFERENCES tune(tune_id),
    start_timestamp_ms BIGINT NOT NULL,
    end_timestamp_ms BIGINT NOT NULL,
    confidence DECIMAL(5,4),
    detection_method VARCHAR(50),
    detection_metadata JSONB,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX idx_recording_tune_segment_recording_id ON recording_tune_segment(recording_id);
CREATE INDEX idx_recording_tune_segment_tune_id ON recording_tune_segment(tune_id);

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
    auto_create_instances BOOLEAN,
    auto_create_hours_ahead INTEGER,
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
    order_number INTEGER,  -- historical only, no longer written
    order_position VARCHAR(32) COLLATE "C",
    record_type VARCHAR(16),
    played_timestamp TIMESTAMPTZ,
    inserted_timestamp TIMESTAMPTZ,
    key_override VARCHAR(20),
    setting_override INTEGER,
    started_by_person_id INTEGER,
    source VARCHAR(16),
    confidence SMALLINT,
    played_start TIMESTAMPTZ,
    played_end TIMESTAMPTZ,
    logged_timestamp TIMESTAMPTZ,
    client_device_id VARCHAR(64),
    deleted BOOLEAN,
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
    relationship VARCHAR(10),
    confirmed BOOLEAN,
    archived BOOLEAN,
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
    key VARCHAR(20),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_person_tune_history_person_tune_id ON person_tune_history (person_tune_id);
CREATE INDEX idx_person_tune_history_person_id ON person_tune_history (person_id);
CREATE INDEX idx_person_tune_history_changed_at ON person_tune_history (changed_at);
CREATE INDEX idx_person_tune_history_operation ON person_tune_history (operation);

-- Person tune instrument history
CREATE TABLE person_tune_instrument_history (
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

CREATE INDEX idx_person_tune_instrument_history_person_id ON person_tune_instrument_history (person_id);
CREATE INDEX idx_person_tune_instrument_history_changed_at ON person_tune_instrument_history (changed_at);
CREATE INDEX idx_person_tune_instrument_history_operation ON person_tune_instrument_history (operation);

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
    receive_update_emails BOOLEAN,
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

-- Recording history
CREATE TABLE recording_history (
    history_id SERIAL PRIMARY KEY,
    recording_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    session_instance_id INTEGER,
    person_id INTEGER,
    source VARCHAR(10),
    status VARCHAR(20),
    device_info JSONB,
    format VARCHAR(50),
    sample_rate INTEGER,
    channels INTEGER,
    bitrate INTEGER,
    s3_prefix VARCHAR(500),
    total_chunks INTEGER,
    total_duration_ms BIGINT,
    total_size_bytes BIGINT,
    client_started_at TIMESTAMPTZ,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ,
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER
);

CREATE INDEX idx_recording_history_recording_id ON recording_history(recording_id);
CREATE INDEX idx_recording_history_changed_at ON recording_history(changed_at);
CREATE INDEX idx_recording_history_operation ON recording_history(operation);

-- Recording chunk history
CREATE TABLE recording_chunk_history (
    history_id SERIAL PRIMARY KEY,
    recording_chunk_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    recording_id INTEGER,
    sequence_number INTEGER,
    start_timestamp_ms BIGINT,
    end_timestamp_ms BIGINT,
    s3_key VARCHAR(500),
    file_size_bytes INTEGER,
    upload_status VARCHAR(20),
    checksum VARCHAR(64),
    created_date TIMESTAMPTZ
);

CREATE INDEX idx_recording_chunk_history_recording_chunk_id ON recording_chunk_history(recording_chunk_id);
CREATE INDEX idx_recording_chunk_history_changed_at ON recording_chunk_history(changed_at);
CREATE INDEX idx_recording_chunk_history_operation ON recording_chunk_history(operation);

-- Recording event history
CREATE TABLE recording_event_history (
    history_id SERIAL PRIMARY KEY,
    recording_event_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by_user_id INTEGER,
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    recording_id INTEGER,
    event_type VARCHAR(30),
    event_data JSONB,
    client_timestamp TIMESTAMPTZ,
    created_date TIMESTAMPTZ
);

CREATE INDEX idx_recording_event_history_recording_event_id ON recording_event_history(recording_event_id);
CREATE INDEX idx_recording_event_history_changed_at ON recording_event_history(changed_at);
CREATE INDEX idx_recording_event_history_operation ON recording_event_history(operation);

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
-- (spec 030 version: covers person_tune_instrument + recording_tune_segment, preserves
-- the old display name as per-context aliases, and writes app-convention history rows)
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

COMMENT ON FUNCTION merge_tune_ids(INTEGER, INTEGER, INTEGER) IS
'Merges all references from old_tune_id to new_tune_id (tune_setting, session_tune, session_tune_alias, session_instance_tune, person_tune + person_tune_instrument via FK cascade, recording_tune_segment), preserving the old display name as per-context aliases where no override existed, writing app-convention history rows, then marks the old tune as a redirect. Returns JSON summary. Spec 030.';

-- -----------------------------------------------------------------------------
-- thesession.org merge sync (spec 031; see schema/031_merge_scan.sql)
-- -----------------------------------------------------------------------------
-- A weekly job diffs local tune ids against thesession's weekly data dump,
-- resolves where merged-away ids went, live-verifies the redirect, and
-- auto-applies the merge via merge_tune_ids(). One tune_merge_scan row per
-- run (heartbeat detects a dead thread); result rows are kept ACROSS runs as
-- the record the admin page shows (applied merges are one-shot and can't be
-- re-detected later).
CREATE TABLE tune_merge_scan (
    scan_id             SERIAL PRIMARY KEY,
    status              VARCHAR(16) NOT NULL CHECK (status IN ('running', 'completed', 'cancelled')),
    total_count         INTEGER NOT NULL,   -- local active tunes at run start
    checked_count       INTEGER NOT NULL DEFAULT 0,
    merged_count        INTEGER NOT NULL DEFAULT 0,   -- merges detected this run
    applied_count       INTEGER NOT NULL DEFAULT 0,   -- merges actually applied this run
    deleted_count       INTEGER NOT NULL DEFAULT 0,
    error_count         INTEGER NOT NULL DEFAULT 0,
    started_by_user_id  INTEGER REFERENCES user_account(user_id),  -- NULL = cron
    started_at          TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    heartbeat_at        TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    finished_at         TIMESTAMPTZ
);

-- Outcomes worth recording: 'merged' (applied_at set when auto-applied),
-- 'deleted' upstream (informational, recorded once), 'error' (latest attempt
-- only; retried next run). No FK on tune_id: the row must survive its tune
-- being merged.
CREATE TABLE tune_merge_scan_result (
    scan_id         INTEGER NOT NULL REFERENCES tune_merge_scan(scan_id) ON DELETE CASCADE,
    tune_id         INTEGER NOT NULL,
    result_type     VARCHAR(16) NOT NULL CHECK (result_type IN ('merged', 'deleted', 'error')),
    target_tune_id  INTEGER,                -- final id after resolution (merged only)
    target_name     TEXT,                   -- thesession's canonical name for the target
    target_aliases  JSONB,                  -- thesession's alternate titles for the target
    detail          TEXT,                   -- how it was detected / error message
    applied_at      TIMESTAMPTZ,            -- when the merge was auto-applied (merged only)
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (scan_id, tune_id)
);

CREATE INDEX idx_tune_merge_scan_result_tune ON tune_merge_scan_result (tune_id);

-- =============================================================================
-- Schema creation complete
-- =============================================================================
