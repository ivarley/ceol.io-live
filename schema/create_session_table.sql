-- Create sessions table based on schema.md specification
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
    comments TEXT,
    unlisted_address BOOLEAN DEFAULT FALSE,
    initiation_date DATE,
    termination_date DATE,
    recurrence TEXT, -- JSON or structured text for recurrence pattern
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on path for URL lookups
CREATE INDEX idx_session_path ON session(path);

-- Create index on thesession_id for external references
CREATE INDEX idx_session_thesession_id ON session(thesession_id);

-- Create trigger function to automatically update last_modified_date
CREATE OR REPLACE FUNCTION update_session_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to call the function before updates
CREATE TRIGGER trigger_session_last_modified_date
    BEFORE UPDATE ON session
    FOR EACH ROW
    EXECUTE FUNCTION update_session_last_modified_date();