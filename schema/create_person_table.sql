-- Create person table
CREATE TABLE person (
    person_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    sms_number VARCHAR(20),
    country VARCHAR(100),
    city VARCHAR(100),
    thesession_user_id INTEGER,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create unique index on email (when not null)
CREATE UNIQUE INDEX idx_person_email_unique ON person (email) WHERE email IS NOT NULL;

-- Create index on thesession_user_id
CREATE INDEX idx_person_thesession_user_id ON person (thesession_user_id);