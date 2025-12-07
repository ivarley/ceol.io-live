-- Migration: 013 Simplified Login
-- Enables email-only login with optional passwords and magic link authentication

-- Make password optional for passwordless users
ALTER TABLE user_account ALTER COLUMN hashed_password DROP NOT NULL;

-- Add magic link login tokens
ALTER TABLE user_account ADD COLUMN IF NOT EXISTS login_token VARCHAR(255);
ALTER TABLE user_account ADD COLUMN IF NOT EXISTS login_token_expires TIMESTAMPTZ;

-- Index for login token lookup
CREATE INDEX IF NOT EXISTS idx_user_login_token ON user_account (login_token) WHERE login_token IS NOT NULL;

-- Ensure email is unique (case-insensitive) for login by email
-- First check if index already exists to make migration idempotent
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_user_account_email_lower'
    ) THEN
        CREATE UNIQUE INDEX idx_user_account_email_lower ON user_account (LOWER(user_email));
    END IF;
END $$;

-- Add comments for documentation
COMMENT ON COLUMN user_account.login_token IS 'Token for magic link (passwordless) login, expires after 15 minutes';
COMMENT ON COLUMN user_account.login_token_expires IS 'UTC timestamp when magic link login token expires';
COMMENT ON COLUMN user_account.hashed_password IS 'Bcrypt hashed password, NULL for passwordless users who use magic links';
