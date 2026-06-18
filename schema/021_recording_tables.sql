-- =============================================================================
-- 021 Session Audio Recording Tables
-- =============================================================================
-- Creates tables for audio recording: recording, recording_chunk,
-- recording_event, recording_tune_segment, plus history tables.
-- =============================================================================

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
-- HISTORY TABLES
-- =============================================================================

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
