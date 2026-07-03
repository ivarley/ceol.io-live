-- Fix: person_tune.learned_date was never cleared on learned -> not-learned.
--
-- The trigger guarded the clear branch with `OLD IS NOT NULL`. For a composite ROW that
-- is TRUE only when every column is non-null, so any person_tune row with a null column
-- (notes, setting_id, name_alias, ...) skipped the clear branch and kept a stale
-- learned_date. That leaves learn_status='learning'/'want to learn' with learned_date set,
-- which the PersonTune model validator rejects -> GET /api/my-tunes/<id> (the detail modal)
-- returns 404 for those tunes.
--
-- Idempotent: re-running just re-applies the function and re-heals (0 rows the second time).

CREATE OR REPLACE FUNCTION update_person_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = (NOW() AT TIME ZONE 'UTC');
    IF NEW.learn_status = 'learned' AND OLD.learn_status <> 'learned' THEN
        NEW.learned_date = (NOW() AT TIME ZONE 'UTC');
    ELSIF NEW.learn_status <> 'learned' AND OLD.learn_status = 'learned' THEN
        NEW.learned_date = NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Heal rows already left inconsistent by the old trigger.
UPDATE person_tune SET learned_date = NULL
WHERE learn_status <> 'learned' AND learned_date IS NOT NULL;
