-- Create session_instance_person table
-- Junction between session instances and people, representing who attended or plans to attend
CREATE TABLE session_instance_person (
    session_instance_person_id SERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL REFERENCES session_instance(session_instance_id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    attended BOOLEAN DEFAULT NULL,  -- NULL means unknown, TRUE means attended, FALSE means did not attend
    plans_to_attend VARCHAR(10) CHECK (plans_to_attend IN ('yes', 'probably', 'maybe', 'no')) DEFAULT NULL,
    comment TEXT,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Create unique constraint to prevent duplicate session_instance-person associations
ALTER TABLE session_instance_person ADD CONSTRAINT uk_session_instance_person UNIQUE (session_instance_id, person_id);

-- Create indexes
CREATE INDEX idx_session_instance_person_session_instance_id ON session_instance_person (session_instance_id);
CREATE INDEX idx_session_instance_person_person_id ON session_instance_person (person_id);
CREATE INDEX idx_session_instance_person_attended ON session_instance_person (attended);
CREATE INDEX idx_session_instance_person_plans_to_attend ON session_instance_person (plans_to_attend);