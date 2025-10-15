-- Add setting_id and name_alias fields to person_tune table
-- This allows users to customize their personal tune collection with:
-- - setting_id: A specific thesession.org setting ID for their preferred version
-- - name_alias: Their personal alias/name for a tune

ALTER TABLE person_tune
ADD COLUMN IF NOT EXISTS setting_id INTEGER,
ADD COLUMN IF NOT EXISTS name_alias VARCHAR(255);

-- Add comment explaining the fields
COMMENT ON COLUMN person_tune.setting_id IS 'The thesession.org setting ID for this person''s preferred version of the tune';
COMMENT ON COLUMN person_tune.name_alias IS 'The person''s custom name/alias for this tune, if different from the standard name';

-- Update history table to include new fields
ALTER TABLE person_tune_history
ADD COLUMN IF NOT EXISTS setting_id INTEGER,
ADD COLUMN IF NOT EXISTS name_alias VARCHAR(255);
