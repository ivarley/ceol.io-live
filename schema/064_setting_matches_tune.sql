-- =============================================================================
-- 064 A row's setting must be a setting of that row's tune
-- =============================================================================
-- session_tune.setting_id, session_instance_tune.setting_override and
-- person_tune.setting_id name a setting of the row's tune. Setting ids are
-- numbered across all of thesession.org, not per tune, so "setting 1" is
-- Cooley's, whatever tune it is typed against. Before this, any number was
-- accepted, and the notation shown was whatever tune that setting belonged to.
-- Relinking a night's tune also kept the old tune's setting.
--
-- The endpoints check the setting and say what is wrong; this trigger is the
-- backstop for every other write. It blanks a setting we hold that belongs to
-- another tune, so the row falls back to its tune's first setting. A setting we
-- don't hold can't be checked here and is left alone (the endpoints import a
-- setting before pointing at it).
--
-- Merges (merge_tune_ids) move a tune's settings before its rows, so a merged
-- row's setting already belongs to the new tune when the row moves.
--
-- Run scripts/fix_mismatched_settings.py --apply after this, to clear the rows
-- written before it (with history).

CREATE OR REPLACE FUNCTION clear_setting_of_other_tune()
RETURNS TRIGGER AS $$
DECLARE
    v_setting INTEGER;
BEGIN
    IF TG_TABLE_NAME = 'session_instance_tune' THEN
        v_setting := NEW.setting_override;
    ELSE
        v_setting := NEW.setting_id;
    END IF;

    IF v_setting IS NOT NULL AND EXISTS (
        SELECT 1 FROM tune_setting
        WHERE setting_id = v_setting
          AND tune_id IS DISTINCT FROM NEW.tune_id
    ) THEN
        IF TG_TABLE_NAME = 'session_instance_tune' THEN
            NEW.setting_override := NULL;
        ELSE
            NEW.setting_id := NULL;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_session_tune_setting_matches_tune ON session_tune;
CREATE TRIGGER trigger_session_tune_setting_matches_tune
    BEFORE INSERT OR UPDATE OF setting_id, tune_id ON session_tune
    FOR EACH ROW
    WHEN (NEW.setting_id IS NOT NULL)
    EXECUTE FUNCTION clear_setting_of_other_tune();

DROP TRIGGER IF EXISTS trigger_session_instance_tune_setting_matches_tune ON session_instance_tune;
CREATE TRIGGER trigger_session_instance_tune_setting_matches_tune
    BEFORE INSERT OR UPDATE OF setting_override, tune_id ON session_instance_tune
    FOR EACH ROW
    WHEN (NEW.setting_override IS NOT NULL)
    EXECUTE FUNCTION clear_setting_of_other_tune();

DROP TRIGGER IF EXISTS trigger_person_tune_setting_matches_tune ON person_tune;
CREATE TRIGGER trigger_person_tune_setting_matches_tune
    BEFORE INSERT OR UPDATE OF setting_id, tune_id ON person_tune
    FOR EACH ROW
    WHEN (NEW.setting_id IS NOT NULL)
    EXECUTE FUNCTION clear_setting_of_other_tune();
