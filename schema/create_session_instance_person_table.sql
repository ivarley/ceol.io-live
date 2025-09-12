-- Create session_instance_person table
-- Junction between session instances and people, representing who attended or plans to attend
CREATE TABLE session_instance_person (
    session_instance_person_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL REFERENCES session_instance(session_instance_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    attendance VARCHAR(5) CHECK (attendance IN ('yes', 'maybe', 'no')) DEFAULT NULL,  -- NULL means unknown (unusual case)
    comment TEXT,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Create unique constraint to prevent duplicate session_instance-person associations
ALTER TABLE session_instance_person ADD CONSTRAINT uk_session_instance_person UNIQUE (session_instance_id, person_id);

-- Create indexes
CREATE INDEX idx_session_instance_person_session_instance_id ON session_instance_person (session_instance_id);
CREATE INDEX idx_session_instance_person_person_id ON session_instance_person (person_id);
CREATE INDEX idx_session_instance_person_attendance ON session_instance_person (attendance);