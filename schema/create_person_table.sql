-- Create person table
CREATE TABLE person (
    person_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    sms_number VARCHAR(20),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    thesession_user_id INTEGER,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Create unique index on email (when not null)
CREATE UNIQUE INDEX idx_person_email_unique ON person (email) WHERE email IS NOT NULL;

-- Create index on thesession_user_id
CREATE INDEX idx_person_thesession_user_id ON person (thesession_user_id);