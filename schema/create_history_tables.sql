-- Create history/audit tables for tracking all changes
-- These tables store previous versions of records before they are modified or deleted

-- Common audit columns structure
-- operation: 'INSERT', 'UPDATE', 'DELETE'
-- changed_by: user/system performing the operation
-- changed_at: timestamp of the change
-- old_values: JSON representation of the previous state

-- Session history table
CREATE TABLE session_history (
    history_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all session fields at time of change
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
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Session instance history table
CREATE TABLE session_instance_history (
    history_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all session_instance fields at time of change
    session_id INTEGER,
    date DATE,
    start_time TIME,
    end_time TIME,
    location_override VARCHAR(255),
    is_cancelled BOOLEAN,
    comments TEXT,
    log_complete_date TIMESTAMPTZ,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Tune history table
CREATE TABLE tune_history (
    history_id SERIAL PRIMARY KEY,
    tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all tune fields at time of change
    name VARCHAR(255),
    tune_type VARCHAR(50),
    tunebook_count_cached INTEGER,
    tunebook_count_cached_date DATE,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Session tune history table
CREATE TABLE session_tune_history (
    history_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all session_tune fields at time of change
    setting_id INTEGER,
    key VARCHAR(10),
    alias VARCHAR(255),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Session instance tune history table
CREATE TABLE session_instance_tune_history (
    history_id SERIAL PRIMARY KEY,
    session_instance_tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all session_instance_tune fields at time of change
    session_instance_id INTEGER,
    tune_id INTEGER,
    name VARCHAR(255),
    order_number INTEGER,
    continues_set BOOLEAN,
    played_timestamp TIMESTAMPTZ,
    inserted_timestamp TIMESTAMPTZ,
    key_override VARCHAR(10),
    setting_override INTEGER,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Create indexes for efficient querying
CREATE INDEX idx_session_history_session_id ON session_history(session_id);
CREATE INDEX idx_session_history_changed_at ON session_history(changed_at);
CREATE INDEX idx_session_history_operation ON session_history(operation);

CREATE INDEX idx_session_instance_history_session_instance_id ON session_instance_history(session_instance_id);
CREATE INDEX idx_session_instance_history_changed_at ON session_instance_history(changed_at);
CREATE INDEX idx_session_instance_history_operation ON session_instance_history(operation);

CREATE INDEX idx_tune_history_tune_id ON tune_history(tune_id);
CREATE INDEX idx_tune_history_changed_at ON tune_history(changed_at);
CREATE INDEX idx_tune_history_operation ON tune_history(operation);

CREATE INDEX idx_session_tune_history_session_id ON session_tune_history(session_id);
CREATE INDEX idx_session_tune_history_tune_id ON session_tune_history(tune_id);
CREATE INDEX idx_session_tune_history_changed_at ON session_tune_history(changed_at);
CREATE INDEX idx_session_tune_history_operation ON session_tune_history(operation);

CREATE INDEX idx_session_instance_tune_history_session_instance_tune_id ON session_instance_tune_history(session_instance_tune_id);
CREATE INDEX idx_session_instance_tune_history_changed_at ON session_instance_tune_history(changed_at);
CREATE INDEX idx_session_instance_tune_history_operation ON session_instance_tune_history(operation);

-- Session tune alias history table
CREATE TABLE session_tune_alias_history (
    history_id SERIAL PRIMARY KEY,
    session_tune_alias_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all session_tune_alias fields at time of change
    session_id INTEGER,
    tune_id INTEGER,
    alias VARCHAR(255),
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

CREATE INDEX idx_session_tune_alias_history_session_tune_alias_id ON session_tune_alias_history(session_tune_alias_id);
CREATE INDEX idx_session_tune_alias_history_changed_at ON session_tune_alias_history(changed_at);
CREATE INDEX idx_session_tune_alias_history_operation ON session_tune_alias_history(operation);

-- Session person history table
CREATE TABLE session_person_history (
    history_id SERIAL PRIMARY KEY,
    session_person_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all session_person fields at time of change
    session_id INTEGER,
    person_id INTEGER,
    is_regular BOOLEAN,
    is_admin BOOLEAN,
    gets_email_reminder BOOLEAN,
    gets_email_followup BOOLEAN,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Session instance person history table
CREATE TABLE session_instance_person_history (
    history_id SERIAL PRIMARY KEY,
    session_instance_person_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all session_instance_person fields at time of change
    session_instance_id INTEGER,
    person_id INTEGER,
    attended BOOLEAN,
    plans_to_attend VARCHAR(10),
    comment TEXT,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Create indexes for the new history tables
CREATE INDEX idx_session_person_history_session_person_id ON session_person_history(session_person_id);
CREATE INDEX idx_session_person_history_changed_at ON session_person_history(changed_at);
CREATE INDEX idx_session_person_history_operation ON session_person_history(operation);

CREATE INDEX idx_session_instance_person_history_session_instance_person_id ON session_instance_person_history(session_instance_person_id);
CREATE INDEX idx_session_instance_person_history_changed_at ON session_instance_person_history(changed_at);
CREATE INDEX idx_session_instance_person_history_operation ON session_instance_person_history(operation);

-- Person history table
CREATE TABLE person_history (
    history_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all person fields at time of change
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    sms_number VARCHAR(20),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    thesession_user_id INTEGER,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- User account history table
CREATE TABLE user_account_history (
    history_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all user_account fields at time of change
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
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

CREATE INDEX idx_person_history_person_id ON person_history(person_id);
CREATE INDEX idx_person_history_changed_at ON person_history(changed_at);
CREATE INDEX idx_person_history_operation ON person_history(operation);

CREATE INDEX idx_user_account_history_user_id ON user_account_history(user_id);
CREATE INDEX idx_user_account_history_changed_at ON user_account_history(changed_at);
CREATE INDEX idx_user_account_history_operation ON user_account_history(operation);