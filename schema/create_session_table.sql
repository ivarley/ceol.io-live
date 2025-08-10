-- Create sessions table based on schema.md specification
CREATE TABLE session (
    session_id SERIAL PRIMARY KEY,
    thesession_id INTEGER,
    name VARCHAR(255) NOT NULL,
    path VARCHAR(255) NOT NULL UNIQUE,
    location_name VARCHAR(255),
    location_website TEXT,
    location_phone VARCHAR(50),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    comments TEXT,
    unlisted_address BOOLEAN DEFAULT FALSE,
    initiation_date DATE,
    termination_date DATE,
    recurrence TEXT -- JSON or structured text for recurrence pattern
);

-- Create index on path for URL lookups
CREATE INDEX idx_session_path ON session(path);

-- Create index on thesession_id for external references
CREATE INDEX idx_session_thesession_id ON session(thesession_id);