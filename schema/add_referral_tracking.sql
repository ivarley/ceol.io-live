-- Add referral tracking column to user_account table
-- This allows tracking which person referred a new user to the site

ALTER TABLE user_account
ADD COLUMN referred_by_person_id INTEGER REFERENCES person(person_id) ON DELETE SET NULL;

-- Create index for referral queries
CREATE INDEX idx_user_referred_by ON user_account (referred_by_person_id) WHERE referred_by_person_id IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN user_account.referred_by_person_id IS 'Person ID of the user who referred this account via shared QR code link';

-- Add same column to history table for audit trail
ALTER TABLE user_account_history
ADD COLUMN referred_by_person_id INTEGER;
