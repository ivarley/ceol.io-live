-- Create session_person table
-- Any relationship between a person and a session (spec 034). Created explicitly (join,
-- admin roster-add) or implicitly (check-in, which creates an unconfirmed visitor).
--
--   relationship -- whose session is this? 'member' | 'visitor'. Person OR admin sets it.
--   confirmed    -- does the session vouch for them? SOLE gate on people-visibility. Admins.
--   archived     -- admin's roster display preference. Hidden by default, still searchable.
CREATE TABLE session_person (
    session_person_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES session(session_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    relationship VARCHAR(10) NOT NULL DEFAULT 'member'
        CHECK (relationship IN ('member', 'visitor')),
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
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
CREATE INDEX idx_session_person_relationship ON session_person (session_id, relationship)
    WHERE archived = FALSE;
CREATE INDEX idx_session_person_is_admin ON session_person (is_admin);