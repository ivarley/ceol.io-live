-- =============================================================================
-- 060 Which model said how sure it was (spec 053, "Confidence that means what
-- it says")
-- =============================================================================
-- A tune the listener logs carries `confidence` (spec 024 §I): the chance, in
-- whole percent, that the name is right. That number comes from a calibration
-- model (lab/analysis/confidence.py, lab/configs/confidence.json) which will be
-- refitted as more nights are labelled, so a stored 70 only means "70 in 100
-- of these are right" under the model that made it. This records which one.
--
--   confidence_model  the model's version (e.g. "listen-1"); NULL when a person
--                     set the confidence (Confirm, a correction) or none was given.
--
-- Mirrored onto the history table like the other columns, so a correction keeps
-- what the machine said, how sure, and by which model, beside what a person
-- changed it to: the material the next model is fitted on.
-- =============================================================================

BEGIN;

ALTER TABLE session_instance_tune
    ADD COLUMN IF NOT EXISTS confidence_model VARCHAR(32);

ALTER TABLE session_instance_tune_history
    ADD COLUMN IF NOT EXISTS confidence_model VARCHAR(32);

COMMIT;
