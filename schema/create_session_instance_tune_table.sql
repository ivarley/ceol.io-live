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
    CONSTRAINT session_instance_tune_name_or_id CHECK (tune_id IS NOT NULL OR name IS NOT NULL)
);