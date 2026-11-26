-- 068: a night's setting_override is set only where it is an actual override.
--
-- session_instance_tune.setting_override says a night played a different setting
-- from the one the session plays (session_tune.setting_id). The old linking flows
-- copied the session's setting onto every logged row, so in production ten
-- thousand rows "overrode" the session's setting with that same setting. Those
-- copies say nothing, and with the per-night setting editor gone (spec 037,
-- Nov 2026) nothing writes them any more: the live logger marks a night only
-- when its chosen setting differs from the session's. Clear them, each with a
-- history row, and leave every override that differs (a night that really did
-- play another setting) and every one on a tune the session has no row for.
--
--     psql "$PROD_URL" -f schema/068_clear_redundant_setting_overrides.sql

BEGIN;

CREATE TEMP TABLE redundant_override ON COMMIT DROP AS
SELECT sit.session_instance_tune_id
FROM session_instance_tune sit
JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
JOIN session_tune st ON st.session_id = si.session_id AND st.tune_id = sit.tune_id
WHERE sit.setting_override IS NOT NULL
  AND sit.setting_override = st.setting_id;

INSERT INTO session_instance_tune_history
    (session_instance_tune_id, operation, changed_by_user_id, session_instance_id, tune_id,
     name, order_position, record_type, played_timestamp, inserted_timestamp,
     key_override, setting_override, source, confidence, confidence_model, played_start, played_end,
     logged_timestamp, client_device_id, deleted,
     created_date, last_modified_date, created_by_user_id, last_modified_user_id)
SELECT sit.session_instance_tune_id, 'UPDATE', NULL, sit.session_instance_id, sit.tune_id,
       sit.name, sit.order_position, sit.record_type, sit.played_timestamp, sit.inserted_timestamp,
       sit.key_override, sit.setting_override, sit.source, sit.confidence, sit.confidence_model, sit.played_start, sit.played_end,
       sit.logged_timestamp, sit.client_device_id, sit.deleted,
       sit.created_date, sit.last_modified_date, sit.created_by_user_id, sit.last_modified_user_id
FROM session_instance_tune sit
JOIN redundant_override r ON r.session_instance_tune_id = sit.session_instance_tune_id;

UPDATE session_instance_tune sit
SET setting_override = NULL
FROM redundant_override r
WHERE r.session_instance_tune_id = sit.session_instance_tune_id;

COMMIT;
