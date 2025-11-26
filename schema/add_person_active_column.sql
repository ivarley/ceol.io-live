-- Add active column to person table
-- Default to TRUE so all existing persons are active

ALTER TABLE person ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE NOT NULL;

-- Add active column to person_history table for audit trail
ALTER TABLE person_history ADD COLUMN IF NOT EXISTS active BOOLEAN;

-- Create index for filtering by active status
CREATE INDEX IF NOT EXISTS idx_person_active ON person (active);
