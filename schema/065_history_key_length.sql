-- =============================================================================
-- 065 History tables hold keys as long as the tables they copy
-- =============================================================================
-- expand_key_field_length.sql widened session_tune.key and
-- session_instance_tune.key_override to VARCHAR(20) but not their history
-- tables, which stayed VARCHAR(10) in production. Saving history for a row
-- keyed "Dmixolydian" (11 characters) then failed with "value too long for
-- type character varying(10)", and with it the edit. full_schema.sql already
-- has 20 for both; this brings production in line.

ALTER TABLE session_tune_history
    ALTER COLUMN key TYPE VARCHAR(20);

ALTER TABLE session_instance_tune_history
    ALTER COLUMN key_override TYPE VARCHAR(20);
