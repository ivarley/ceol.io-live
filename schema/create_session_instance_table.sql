-- Create session_instance table based on schema.md specification
CREATE TABLE session_instance (
    session_instance_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES session(session_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    start_time TIME,
    end_time TIME,
    location_override VARCHAR(255),
    is_cancelled BOOLEAN DEFAULT FALSE,
    comments TEXT
);

-- Create index on session_id for efficient queries
CREATE INDEX idx_session_instance_session_id ON session_instance(session_id);

-- Create index on date for temporal queries
CREATE INDEX idx_session_instance_date ON session_instance(date);

-- Create unique constraint to prevent overlapping instances for the same session
CREATE UNIQUE INDEX idx_session_instance_no_overlap ON session_instance(session_id, date, start_time);