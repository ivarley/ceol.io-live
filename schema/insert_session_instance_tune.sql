-- Stored procedure to insert a tune into session_instance_tune table
CREATE OR REPLACE FUNCTION insert_session_instance_tune(
    p_session_id INTEGER,
    p_date DATE,
    p_tune_id INTEGER,
    p_setting INTEGER,
    p_name VARCHAR(255),
    p_starts_set BOOLEAN
)
RETURNS INTEGER AS $$
DECLARE
    v_session_instance_id INTEGER;
    v_order_number INTEGER;
    v_continues_set BOOLEAN;
    v_new_id INTEGER;
    v_session_tune_exists BOOLEAN;
BEGIN
    -- Look up the session_instance_id for the given session_id and date
    -- If multiple exist, take the highest id
    SELECT session_instance_id 
    INTO v_session_instance_id
    FROM session_instance 
    WHERE session_id = p_session_id AND date = p_date
    ORDER BY session_instance_id DESC
    LIMIT 1;
    
    -- If no session instance found, raise an error
    IF v_session_instance_id IS NULL THEN
        RAISE EXCEPTION 'No session instance found for session_id % on date %', p_session_id, p_date;
    END IF;
    
    -- If tune_id is provided, ensure it exists in session_tune for this session
    IF p_tune_id IS NOT NULL THEN
        -- Check if the tune is already in session_tune for this session
        SELECT EXISTS(
            SELECT 1 FROM session_tune 
            WHERE session_id = p_session_id AND tune_id = p_tune_id
        ) INTO v_session_tune_exists;
        
        -- If not exists, insert it into session_tune
        IF NOT v_session_tune_exists THEN
            INSERT INTO session_tune (session_id, tune_id, setting_id, key, alias)
            VALUES (p_session_id, p_tune_id, p_setting, NULL, NULL)
            ON CONFLICT (session_id, tune_id) DO NOTHING;
        END IF;
    END IF;
    
    -- Look up the current max order number for this session_instance_id and increment by 1
    SELECT COALESCE(MAX(order_number), 0) + 1
    INTO v_order_number
    FROM session_instance_tune
    WHERE session_instance_id = v_session_instance_id;
    
    -- Set continues_set as the negation of starts_set
    v_continues_set := NOT p_starts_set;
    
    -- Insert the new record
    INSERT INTO session_instance_tune (
        session_instance_id,
        tune_id,
        name,
        order_number,
        continues_set,
        played_timestamp,
        inserted_timestamp,
        key_override,
        setting_override
    ) VALUES (
        v_session_instance_id,
        p_tune_id,
        p_name,
        v_order_number,
        v_continues_set,
        NULL, -- played_timestamp not set in this procedure
        CURRENT_TIMESTAMP,
        NULL, -- key_override not provided in parameters
        p_setting
    ) RETURNING session_instance_tune_id INTO v_new_id;
    
    RETURN v_new_id;
END;
$$ LANGUAGE plpgsql;