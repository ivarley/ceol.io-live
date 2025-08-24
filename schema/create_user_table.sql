-- Create user table
CREATE TABLE user_account (
    user_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    username VARCHAR(255) NOT NULL UNIQUE,
    user_email VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT TRUE,
    is_system_admin BOOLEAN DEFAULT FALSE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMPTZ,
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMPTZ,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Create indexes
CREATE INDEX idx_user_person_id ON user_account (person_id);
CREATE INDEX idx_user_username ON user_account (username);
CREATE INDEX idx_user_verification_token ON user_account (verification_token) WHERE verification_token IS NOT NULL;
CREATE INDEX idx_user_reset_token ON user_account (password_reset_token) WHERE password_reset_token IS NOT NULL;

-- Comments for documentation
COMMENT ON COLUMN user_account.timezone IS 'IANA timezone identifier (e.g., America/New_York) for displaying dates to user';
COMMENT ON COLUMN user_account.created_date IS 'UTC timestamp when user account was created';
COMMENT ON COLUMN user_account.last_modified_date IS 'UTC timestamp when user account was last modified';
COMMENT ON COLUMN user_account.verification_token_expires IS 'UTC timestamp when email verification token expires';
COMMENT ON COLUMN user_account.password_reset_expires IS 'UTC timestamp when password reset token expires';