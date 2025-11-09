-- Expand key field length from VARCHAR(10) to VARCHAR(20)
-- This fixes the error "value too long for type character varying(10)"
-- that occurs when trying to save keys like "Amixolydian" (11 chars)

-- Expand key field in session_tune table
ALTER TABLE session_tune
ALTER COLUMN key TYPE VARCHAR(20);

-- Expand key_override field in session_instance_tune table
ALTER TABLE session_instance_tune
ALTER COLUMN key_override TYPE VARCHAR(20);

-- Expand key field in tune_setting table
ALTER TABLE tune_setting
ALTER COLUMN key TYPE VARCHAR(20);

-- Expand key field in tune_setting_history table
ALTER TABLE tune_setting_history
ALTER COLUMN key TYPE VARCHAR(20);
