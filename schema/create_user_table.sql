-- Create user table
CREATE TABLE user_account (
    user_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    username VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    time_zone VARCHAR(50) DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT TRUE,
    is_system_admin BOOLEAN DEFAULT FALSE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP,
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMP,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_user_person_id ON user_account (person_id);
CREATE INDEX idx_user_username ON user_account (username);
CREATE INDEX idx_user_verification_token ON user_account (verification_token) WHERE verification_token IS NOT NULL;
CREATE INDEX idx_user_reset_token ON user_account (password_reset_token) WHERE password_reset_token IS NOT NULL;