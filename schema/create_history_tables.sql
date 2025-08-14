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
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Copy of all session fields at time of change
    thesession_id INTEGER,
    name VARCHAR(255),
    path VARCHAR(255),
    location_name VARCHAR(255),
    location_website TEXT,
    location_phone VARCHAR(50),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    comments TEXT,
    unlisted_address BOOLEAN,
    initiation_date DATE,
    termination_date DATE,
    recurrence TEXT,
    created_date TIMESTAMP,
    last_modified_date TIMESTAMP
);

-- Session instance history table
CREATE TABLE session_instance_history (
    history_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Copy of all session_instance fields at time of change
    session_id INTEGER,
    date DATE,
    start_time TIME,
    end_time TIME,
    location_override VARCHAR(255),
    is_cancelled BOOLEAN,
    comments TEXT,
    created_date TIMESTAMP,
    last_modified_date TIMESTAMP
);

-- Tune history table
CREATE TABLE tune_history (
    history_id SERIAL PRIMARY KEY,
    tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Copy of all tune fields at time of change
    name VARCHAR(255),
    tune_type VARCHAR(50),
    tunebook_count_cached INTEGER,
    tunebook_count_cached_date DATE,
    created_date TIMESTAMP,
    last_modified_date TIMESTAMP
);

-- Session tune history table
CREATE TABLE session_tune_history (
    history_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Copy of all session_tune fields at time of change
    setting_id INTEGER,
    key VARCHAR(10),
    alias VARCHAR(255),
    created_date TIMESTAMP,
    last_modified_date TIMESTAMP
);

-- Session instance tune history table
CREATE TABLE session_instance_tune_history (
    history_id SERIAL PRIMARY KEY,
    session_instance_tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Copy of all session_instance_tune fields at time of change
    session_instance_id INTEGER,
    tune_id INTEGER,
    name VARCHAR(255),
    order_number INTEGER,
    continues_set BOOLEAN,
    played_timestamp TIMESTAMP,
    inserted_timestamp TIMESTAMP,
    key_override VARCHAR(10),
    setting_override INTEGER,
    created_date TIMESTAMP,
    last_modified_date TIMESTAMP
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