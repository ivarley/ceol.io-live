-- Unified activity view from core tables
-- Shows creates and modifications using created_date/last_modified_date
-- Used by admin activity page

DROP VIEW IF EXISTS recent_activity;

CREATE OR REPLACE VIEW recent_activity AS

-- session: created
SELECT
    created_date AS activity_date,
    'session' AS entity_type,
    session_id::TEXT AS entity_id,
    'created' AS activity_type,
    created_by_user_id AS user_id,
    name AS entity_name,
    '/admin/sessions/' || path AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM session
WHERE created_date IS NOT NULL

UNION ALL

-- session: modified
SELECT
    last_modified_date AS activity_date,
    'session' AS entity_type,
    session_id::TEXT AS entity_id,
    'modified' AS activity_type,
    last_modified_user_id AS user_id,
    name AS entity_name,
    '/admin/sessions/' || path AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM session
WHERE last_modified_date IS NOT NULL
  AND last_modified_date != created_date

UNION ALL

-- session_instance: created
SELECT
    si.created_date AS activity_date,
    'session_instance' AS entity_type,
    si.session_instance_id::TEXT AS entity_id,
    'created' AS activity_type,
    si.created_by_user_id AS user_id,
    s.name || ' (' || si.date::TEXT || ')' AS entity_name,
    '/' || s.path || '/' || si.date::TEXT AS entity_path,
    si.session_id AS session_id_ref
FROM session_instance si
JOIN session s ON si.session_id = s.session_id
WHERE si.created_date IS NOT NULL

UNION ALL

-- session_instance: modified
SELECT
    si.last_modified_date AS activity_date,
    'session_instance' AS entity_type,
    si.session_instance_id::TEXT AS entity_id,
    'modified' AS activity_type,
    si.last_modified_user_id AS user_id,
    s.name || ' (' || si.date::TEXT || ')' AS entity_name,
    '/' || s.path || '/' || si.date::TEXT AS entity_path,
    si.session_id AS session_id_ref
FROM session_instance si
JOIN session s ON si.session_id = s.session_id
WHERE si.last_modified_date IS NOT NULL
  AND si.last_modified_date != si.created_date

UNION ALL

-- tune: created
SELECT
    created_date AS activity_date,
    'tune' AS entity_type,
    tune_id::TEXT AS entity_id,
    'created' AS activity_type,
    created_by_user_id AS user_id,
    name AS entity_name,
    '/tune/' || tune_id::TEXT AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM tune
WHERE created_date IS NOT NULL

UNION ALL

-- tune: modified
SELECT
    last_modified_date AS activity_date,
    'tune' AS entity_type,
    tune_id::TEXT AS entity_id,
    'modified' AS activity_type,
    last_modified_user_id AS user_id,
    name AS entity_name,
    '/tune/' || tune_id::TEXT AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM tune
WHERE last_modified_date IS NOT NULL
  AND last_modified_date != created_date

UNION ALL

-- tune_setting: created
SELECT
    ts.created_date AS activity_date,
    'tune_setting' AS entity_type,
    ts.setting_id::TEXT AS entity_id,
    'created' AS activity_type,
    ts.created_by_user_id AS user_id,
    t.name || ' (setting ' || ts.setting_id::TEXT || ')' AS entity_name,
    '/tune/' || ts.tune_id::TEXT AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM tune_setting ts
JOIN tune t ON ts.tune_id = t.tune_id
WHERE ts.created_date IS NOT NULL

UNION ALL

-- tune_setting: modified
SELECT
    ts.last_modified_date AS activity_date,
    'tune_setting' AS entity_type,
    ts.setting_id::TEXT AS entity_id,
    'modified' AS activity_type,
    ts.last_modified_user_id AS user_id,
    t.name || ' (setting ' || ts.setting_id::TEXT || ')' AS entity_name,
    '/tune/' || ts.tune_id::TEXT AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM tune_setting ts
JOIN tune t ON ts.tune_id = t.tune_id
WHERE ts.last_modified_date IS NOT NULL
  AND ts.last_modified_date != ts.created_date

UNION ALL

-- session_tune: created
SELECT
    st.created_date AS activity_date,
    'session_tune' AS entity_type,
    st.session_id::TEXT || '/' || st.tune_id::TEXT AS entity_id,
    'created' AS activity_type,
    st.created_by_user_id AS user_id,
    COALESCE(st.alias, t.name) || ' @ ' || s.name AS entity_name,
    '/admin/sessions/' || s.path AS entity_path,
    st.session_id AS session_id_ref
FROM session_tune st
JOIN session s ON st.session_id = s.session_id
JOIN tune t ON st.tune_id = t.tune_id
WHERE st.created_date IS NOT NULL

UNION ALL

-- session_tune: modified
SELECT
    st.last_modified_date AS activity_date,
    'session_tune' AS entity_type,
    st.session_id::TEXT || '/' || st.tune_id::TEXT AS entity_id,
    'modified' AS activity_type,
    st.last_modified_user_id AS user_id,
    COALESCE(st.alias, t.name) || ' @ ' || s.name AS entity_name,
    '/admin/sessions/' || s.path AS entity_path,
    st.session_id AS session_id_ref
FROM session_tune st
JOIN session s ON st.session_id = s.session_id
JOIN tune t ON st.tune_id = t.tune_id
WHERE st.last_modified_date IS NOT NULL
  AND st.last_modified_date != st.created_date

UNION ALL

-- session_tune_alias: created
SELECT
    sta.created_date AS activity_date,
    'session_tune_alias' AS entity_type,
    sta.session_tune_alias_id::TEXT AS entity_id,
    'created' AS activity_type,
    sta.created_by_user_id AS user_id,
    sta.alias || ' @ ' || s.name AS entity_name,
    '/admin/sessions/' || s.path AS entity_path,
    sta.session_id AS session_id_ref
FROM session_tune_alias sta
JOIN session s ON sta.session_id = s.session_id
WHERE sta.created_date IS NOT NULL

UNION ALL

-- session_tune_alias: modified
SELECT
    sta.last_modified_date AS activity_date,
    'session_tune_alias' AS entity_type,
    sta.session_tune_alias_id::TEXT AS entity_id,
    'modified' AS activity_type,
    sta.last_modified_user_id AS user_id,
    sta.alias || ' @ ' || s.name AS entity_name,
    '/admin/sessions/' || s.path AS entity_path,
    sta.session_id AS session_id_ref
FROM session_tune_alias sta
JOIN session s ON sta.session_id = s.session_id
WHERE sta.last_modified_date IS NOT NULL
  AND sta.last_modified_date != sta.created_date

UNION ALL

-- session_instance_tune: created
SELECT
    sit.created_date AS activity_date,
    'session_instance_tune' AS entity_type,
    sit.session_instance_tune_id::TEXT AS entity_id,
    'created' AS activity_type,
    sit.created_by_user_id AS user_id,
    sit.name || ' @ ' || s.name || ' (' || si.date::TEXT || ')' AS entity_name,
    '/' || s.path || '/' || si.date::TEXT AS entity_path,
    si.session_id AS session_id_ref
FROM session_instance_tune sit
JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
JOIN session s ON si.session_id = s.session_id
WHERE sit.created_date IS NOT NULL

UNION ALL

-- session_instance_tune: modified
SELECT
    sit.last_modified_date AS activity_date,
    'session_instance_tune' AS entity_type,
    sit.session_instance_tune_id::TEXT AS entity_id,
    'modified' AS activity_type,
    sit.last_modified_user_id AS user_id,
    sit.name || ' @ ' || s.name || ' (' || si.date::TEXT || ')' AS entity_name,
    '/' || s.path || '/' || si.date::TEXT AS entity_path,
    si.session_id AS session_id_ref
FROM session_instance_tune sit
JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
JOIN session s ON si.session_id = s.session_id
WHERE sit.last_modified_date IS NOT NULL
  AND sit.last_modified_date != sit.created_date

UNION ALL

-- person: created
SELECT
    created_date AS activity_date,
    'person' AS entity_type,
    person_id::TEXT AS entity_id,
    'created' AS activity_type,
    created_by_user_id AS user_id,
    first_name || ' ' || last_name AS entity_name,
    '/admin/people' AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM person
WHERE created_date IS NOT NULL

UNION ALL

-- person: modified
SELECT
    last_modified_date AS activity_date,
    'person' AS entity_type,
    person_id::TEXT AS entity_id,
    'modified' AS activity_type,
    last_modified_user_id AS user_id,
    first_name || ' ' || last_name AS entity_name,
    '/admin/people' AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM person
WHERE last_modified_date IS NOT NULL
  AND last_modified_date != created_date

UNION ALL

-- user_account: created
SELECT
    created_date AS activity_date,
    'user_account' AS entity_type,
    user_id::TEXT AS entity_id,
    'created' AS activity_type,
    created_by_user_id AS user_id,
    username AS entity_name,
    '/admin/people' AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM user_account
WHERE created_date IS NOT NULL

UNION ALL

-- user_account: modified
SELECT
    last_modified_date AS activity_date,
    'user_account' AS entity_type,
    user_id::TEXT AS entity_id,
    'modified' AS activity_type,
    last_modified_user_id AS user_id,
    username AS entity_name,
    '/admin/people' AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM user_account
WHERE last_modified_date IS NOT NULL
  AND last_modified_date != created_date

UNION ALL

-- person_instrument: created
SELECT
    pi.created_date AS activity_date,
    'person_instrument' AS entity_type,
    pi.person_id::TEXT || '/' || pi.instrument AS entity_id,
    'created' AS activity_type,
    pi.created_by_user_id AS user_id,
    p.first_name || ' ' || p.last_name || ' - ' || pi.instrument AS entity_name,
    '/admin/people' AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM person_instrument pi
JOIN person p ON pi.person_id = p.person_id
WHERE pi.created_date IS NOT NULL

UNION ALL

-- person_tune: created
SELECT
    pt.created_date AS activity_date,
    'person_tune' AS entity_type,
    pt.person_id::TEXT || '/' || pt.tune_id::TEXT AS entity_id,
    'created' AS activity_type,
    pt.created_by_user_id AS user_id,
    p.first_name || ' ' || p.last_name || ' - ' || t.name AS entity_name,
    '/my-tunes' AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM person_tune pt
JOIN person p ON pt.person_id = p.person_id
JOIN tune t ON pt.tune_id = t.tune_id
WHERE pt.created_date IS NOT NULL

UNION ALL

-- person_tune: modified
SELECT
    pt.last_modified_date AS activity_date,
    'person_tune' AS entity_type,
    pt.person_id::TEXT || '/' || pt.tune_id::TEXT AS entity_id,
    'modified' AS activity_type,
    pt.last_modified_user_id AS user_id,
    p.first_name || ' ' || p.last_name || ' - ' || t.name AS entity_name,
    '/my-tunes' AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM person_tune pt
JOIN person p ON pt.person_id = p.person_id
JOIN tune t ON pt.tune_id = t.tune_id
WHERE pt.last_modified_date IS NOT NULL
  AND pt.last_modified_date != pt.created_date

UNION ALL

-- session_person: created
SELECT
    sp.created_date AS activity_date,
    'session_person' AS entity_type,
    sp.session_id::TEXT || '/' || sp.person_id::TEXT AS entity_id,
    'created' AS activity_type,
    sp.created_by_user_id AS user_id,
    p.first_name || ' ' || p.last_name || ' @ ' || s.name AS entity_name,
    '/admin/sessions/' || s.path AS entity_path,
    sp.session_id AS session_id_ref
FROM session_person sp
JOIN session s ON sp.session_id = s.session_id
JOIN person p ON sp.person_id = p.person_id
WHERE sp.created_date IS NOT NULL

UNION ALL

-- session_person: modified
SELECT
    sp.last_modified_date AS activity_date,
    'session_person' AS entity_type,
    sp.session_id::TEXT || '/' || sp.person_id::TEXT AS entity_id,
    'modified' AS activity_type,
    sp.last_modified_user_id AS user_id,
    p.first_name || ' ' || p.last_name || ' @ ' || s.name AS entity_name,
    '/admin/sessions/' || s.path AS entity_path,
    sp.session_id AS session_id_ref
FROM session_person sp
JOIN session s ON sp.session_id = s.session_id
JOIN person p ON sp.person_id = p.person_id
WHERE sp.last_modified_date IS NOT NULL
  AND sp.last_modified_date != sp.created_date

UNION ALL

-- session_instance_person: created
SELECT
    sip.created_date AS activity_date,
    'session_instance_person' AS entity_type,
    sip.session_instance_id::TEXT || '/' || sip.person_id::TEXT AS entity_id,
    'created' AS activity_type,
    sip.created_by_user_id AS user_id,
    p.first_name || ' ' || p.last_name || ' @ ' || s.name || ' (' || si.date::TEXT || ')' AS entity_name,
    '/' || s.path || '/' || si.date::TEXT AS entity_path,
    si.session_id AS session_id_ref
FROM session_instance_person sip
JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
JOIN session s ON si.session_id = s.session_id
JOIN person p ON sip.person_id = p.person_id
WHERE sip.created_date IS NOT NULL

UNION ALL

-- session_instance_person: modified
SELECT
    sip.last_modified_date AS activity_date,
    'session_instance_person' AS entity_type,
    sip.session_instance_id::TEXT || '/' || sip.person_id::TEXT AS entity_id,
    'modified' AS activity_type,
    sip.last_modified_user_id AS user_id,
    p.first_name || ' ' || p.last_name || ' @ ' || s.name || ' (' || si.date::TEXT || ')' AS entity_name,
    '/' || s.path || '/' || si.date::TEXT AS entity_path,
    si.session_id AS session_id_ref
FROM session_instance_person sip
JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
JOIN session s ON si.session_id = s.session_id
JOIN person p ON sip.person_id = p.person_id
WHERE sip.last_modified_date IS NOT NULL
  AND sip.last_modified_date != sip.created_date

UNION ALL

-- login_history: login events
SELECT
    timestamp AS activity_date,
    'login' AS entity_type,
    login_history_id::TEXT AS entity_id,
    event_type AS activity_type,
    user_id AS user_id,
    username AS entity_name,
    '/admin/login-history' AS entity_path,
    NULL::INTEGER AS session_id_ref
FROM login_history;

-- Index recommendation: ensure indexes exist on created_date, last_modified_date columns
-- These should already exist from previous migrations
