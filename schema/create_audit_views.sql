-- Create views for easy audit reporting and daily diffs

-- Daily changes summary view
CREATE OR REPLACE VIEW daily_changes_summary AS
SELECT 
    DATE(changed_at) AS change_date,
    'session' AS table_name,
    operation,
    COUNT(*) AS change_count
FROM session_history
GROUP BY DATE(changed_at), operation
UNION ALL
SELECT 
    DATE(changed_at) AS change_date,
    'session_instance' AS table_name,
    operation,
    COUNT(*) AS change_count
FROM session_instance_history
GROUP BY DATE(changed_at), operation
UNION ALL
SELECT 
    DATE(changed_at) AS change_date,
    'tune' AS table_name,
    operation,
    COUNT(*) AS change_count
FROM tune_history
GROUP BY DATE(changed_at), operation
UNION ALL
SELECT 
    DATE(changed_at) AS change_date,
    'session_tune' AS table_name,
    operation,
    COUNT(*) AS change_count
FROM session_tune_history
GROUP BY DATE(changed_at), operation
UNION ALL
SELECT 
    DATE(changed_at) AS change_date,
    'session_instance_tune' AS table_name,
    operation,
    COUNT(*) AS change_count
FROM session_instance_tune_history
GROUP BY DATE(changed_at), operation
ORDER BY change_date DESC, table_name, operation;

-- Recent changes detail view (last 30 days)
CREATE OR REPLACE VIEW recent_changes_detail AS
SELECT 
    changed_at,
    'session' AS table_name,
    session_id::TEXT AS record_id,
    operation,
    changed_by,
    name AS record_name
FROM session_history
WHERE changed_at >= CURRENT_DATE - INTERVAL '30 days'
UNION ALL
SELECT 
    changed_at,
    'session_instance' AS table_name,
    session_instance_id::TEXT AS record_id,
    operation,
    changed_by,
    CAST(date AS TEXT) AS record_name
FROM session_instance_history
WHERE changed_at >= CURRENT_DATE - INTERVAL '30 days'
UNION ALL
SELECT 
    changed_at,
    'tune' AS table_name,
    tune_id::TEXT AS record_id,
    operation,
    changed_by,
    name AS record_name
FROM tune_history
WHERE changed_at >= CURRENT_DATE - INTERVAL '30 days'
UNION ALL
SELECT 
    changed_at,
    'session_tune' AS table_name,
    (session_id::TEXT || '/' || tune_id::TEXT) AS record_id,
    operation,
    changed_by,
    alias AS record_name
FROM session_tune_history
WHERE changed_at >= CURRENT_DATE - INTERVAL '30 days'
UNION ALL
SELECT 
    changed_at,
    'session_instance_tune' AS table_name,
    session_instance_tune_id::TEXT AS record_id,
    operation,
    changed_by,
    name AS record_name
FROM session_instance_tune_history
WHERE changed_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY changed_at DESC;

-- Function to get changes for a specific date
CREATE OR REPLACE FUNCTION get_daily_changes(target_date DATE)
RETURNS TABLE (
    table_name TEXT,
    operation TEXT,
    record_id INTEGER,
    changed_at TIMESTAMP,
    changed_by TEXT,
    details JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'session'::TEXT,
        sh.operation,
        sh.session_id,
        sh.changed_at,
        sh.changed_by,
        jsonb_build_object(
            'name', sh.name,
            'path', sh.path,
            'city', sh.city,
            'state', sh.state
        ) AS details
    FROM session_history sh
    WHERE DATE(sh.changed_at) = target_date
    
    UNION ALL
    
    SELECT 
        'session_instance'::TEXT,
        sih.operation,
        sih.session_instance_id,
        sih.changed_at,
        sih.changed_by,
        jsonb_build_object(
            'session_id', sih.session_id,
            'date', sih.date,
            'comments', sih.comments
        ) AS details
    FROM session_instance_history sih
    WHERE DATE(sih.changed_at) = target_date
    
    UNION ALL
    
    SELECT 
        'tune'::TEXT,
        th.operation,
        th.tune_id,
        th.changed_at,
        th.changed_by,
        jsonb_build_object(
            'name', th.name,
            'tune_type', th.tune_type
        ) AS details
    FROM tune_history th
    WHERE DATE(th.changed_at) = target_date
    
    UNION ALL
    
    SELECT 
        'session_tune'::TEXT,
        sth.operation,
        sth.session_id,
        sth.changed_at,
        sth.changed_by,
        jsonb_build_object(
            'tune_id', sth.tune_id,
            'alias', sth.alias,
            'key', sth.key
        ) AS details
    FROM session_tune_history sth
    WHERE DATE(sth.changed_at) = target_date
    
    UNION ALL
    
    SELECT 
        'session_instance_tune'::TEXT,
        sith.operation,
        sith.session_instance_tune_id,
        sith.changed_at,
        sith.changed_by,
        jsonb_build_object(
            'session_instance_id', sith.session_instance_id,
            'tune_id', sith.tune_id,
            'name', sith.name,
            'order_number', sith.order_number
        ) AS details
    FROM session_instance_tune_history sith
    WHERE DATE(sith.changed_at) = target_date
    
    ORDER BY changed_at DESC;
END;
$$ LANGUAGE plpgsql;