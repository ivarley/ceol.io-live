-- Create session_tune_alias table
CREATE TABLE session_tune_alias (
    session_tune_alias_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES session(session_id),
    tune_id INTEGER REFERENCES tune(tune_id),
    alias VARCHAR(255) NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Ensure each alias within a session points to only one tune
    CONSTRAINT unique_session_alias UNIQUE (session_id, alias)
);

-- Create indexes for efficient querying
CREATE INDEX idx_session_tune_alias_session_id ON session_tune_alias(session_id);
CREATE INDEX idx_session_tune_alias_tune_id ON session_tune_alias(tune_id);
CREATE INDEX idx_session_tune_alias_alias ON session_tune_alias(alias);

-- Create trigger function to automatically update last_modified_date
CREATE OR REPLACE FUNCTION update_session_tune_alias_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to call the function before updates
CREATE TRIGGER trigger_session_tune_alias_last_modified_date
    BEFORE UPDATE ON session_tune_alias
    FOR EACH ROW
    EXECUTE FUNCTION update_session_tune_alias_last_modified_date();