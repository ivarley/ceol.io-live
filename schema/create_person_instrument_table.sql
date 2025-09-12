-- Create person_instrument table
-- Links people to the instruments they play
CREATE TABLE person_instrument (
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    instrument VARCHAR(50) NOT NULL,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (person_id, instrument)
);

-- Create index for instrument lookups
CREATE INDEX idx_person_instrument_instrument ON person_instrument (instrument);