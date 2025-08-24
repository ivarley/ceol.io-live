-- Create session_person table
-- Association between a person and a session, created when person has attended at least once or added by admin
CREATE TABLE session_person (
    session_person_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES session(session_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    is_regular BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    gets_email_reminder BOOLEAN DEFAULT FALSE,
    gets_email_followup BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Create unique constraint to prevent duplicate session-person associations
ALTER TABLE session_person ADD CONSTRAINT uk_session_person UNIQUE (session_id, person_id);

-- Create indexes
CREATE INDEX idx_session_person_session_id ON session_person (session_id);
CREATE INDEX idx_session_person_person_id ON session_person (person_id);
CREATE INDEX idx_session_person_is_regular ON session_person (is_regular);
CREATE INDEX idx_session_person_is_admin ON session_person (is_admin);