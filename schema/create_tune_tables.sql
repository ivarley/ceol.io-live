-- Create tune table
CREATE TABLE tune (
    tune_id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tune_type VARCHAR(50) CHECK (tune_type IN ('Jig', 'Reel', 'Slip Jig', 'Hop Jig', 'Hornpipe', 'Polka', 'Set Dance', 'Slide', 'Waltz', 'Barndance', 'Strathspey', 'Three-Two', 'Mazurka', 'March', 'Air')),
    tunebook_count_cached INTEGER DEFAULT 0
);

-- Create session_tune table
CREATE TABLE session_tune (
    session_id INTEGER REFERENCES session(session_id),
    tune_id INTEGER REFERENCES tune(tune_id),
    setting_id INTEGER,
    key VARCHAR(10),
    alias VARCHAR(255),
    PRIMARY KEY (session_id, tune_id)
);