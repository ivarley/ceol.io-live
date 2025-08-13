-- Create tune table
CREATE TABLE tune (
    tune_id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tune_type VARCHAR(50) CHECK (tune_type IN ('Jig', 'Reel', 'Slip Jig', 'Hop Jig', 'Hornpipe', 'Polka', 'Set Dance', 'Slide', 'Waltz', 'Barndance', 'Strathspey', 'Three-Two', 'Mazurka', 'March', 'Air')),
    tunebook_count_cached INTEGER DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create session_tune table
CREATE TABLE session_tune (
    session_id INTEGER REFERENCES session(session_id),
    tune_id INTEGER REFERENCES tune(tune_id),
    setting_id INTEGER,
    key VARCHAR(10),
    alias VARCHAR(255),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, tune_id)
);

-- Create trigger functions to automatically update last_modified_date
CREATE OR REPLACE FUNCTION update_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_session_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to call the functions before updates
CREATE TRIGGER trigger_tune_last_modified_date
    BEFORE UPDATE ON tune
    FOR EACH ROW
    EXECUTE FUNCTION update_tune_last_modified_date();

CREATE TRIGGER trigger_session_tune_last_modified_date
    BEFORE UPDATE ON session_tune
    FOR EACH ROW
    EXECUTE FUNCTION update_session_tune_last_modified_date();