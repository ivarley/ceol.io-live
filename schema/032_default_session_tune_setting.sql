-- Spec 032: session_tune.setting_id is always populated — the tune's default
-- (lowest setting_id) when no specific setting was ever chosen — so the setting in
-- use is visible and linkable everywhere (preview pager, thesession deep links).
-- New enrollments fill it automatically (_enroll_session_tune / add_session_tune /
-- insert_session_instance_tune); this backfills existing rows.
--
-- Semantics note: a session-level setting equal to the tune's default is treated as
-- "no real preference yet" — an explicitly chosen setting replaces it (see
-- live_logging_routes._apply_chosen_setting). Only a non-default session setting
-- causes chosen settings to fall back to per-row overrides.

UPDATE session_tune st
SET setting_id = d.setting_id
FROM (
    SELECT tune_id, MIN(setting_id) AS setting_id
    FROM tune_setting
    GROUP BY tune_id
) d
WHERE st.setting_id IS NULL
  AND d.tune_id = st.tune_id;

-- Rows whose tune has no tune_setting at all stay NULL (nothing to point to);
-- they pick up a setting the first time one exists and is chosen/enrolled.
