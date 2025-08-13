-- Create session_instance_tune table
CREATE TABLE session_instance_tune (
    session_instance_tune_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER REFERENCES session_instance(session_instance_id),
    tune_id INTEGER REFERENCES tune(tune_id),
    name VARCHAR(255),
    order_number INTEGER NOT NULL,
    continues_set BOOLEAN DEFAULT FALSE,
    played_timestamp TIMESTAMP,
    inserted_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    key_override VARCHAR(10),
    setting_override INTEGER,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT session_instance_tune_name_or_id CHECK (tune_id IS NOT NULL OR name IS NOT NULL)
);

-- Create trigger function to automatically update last_modified_date
CREATE OR REPLACE FUNCTION update_session_instance_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to call the function before updates
CREATE TRIGGER trigger_session_instance_tune_last_modified_date
    BEFORE UPDATE ON session_instance_tune
    FOR EACH ROW
    EXECUTE FUNCTION update_session_instance_tune_last_modified_date();