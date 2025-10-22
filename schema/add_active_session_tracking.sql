-- Add active session tracking columns for Feature 005
-- This enables tracking of currently active session instances and which people are at them

-- Add columns to session table
ALTER TABLE session ADD COLUMN active_buffer_minutes_before INTEGER NOT NULL DEFAULT 60;
ALTER TABLE session ADD COLUMN active_buffer_minutes_after INTEGER NOT NULL DEFAULT 60;

-- Add column to session_instance table
ALTER TABLE session_instance ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT FALSE;

-- Add index for querying active instances
CREATE INDEX idx_session_instance_is_active ON session_instance(is_active) WHERE is_active = TRUE;

-- Add column to person table
ALTER TABLE person ADD COLUMN at_active_session_instance_id INTEGER REFERENCES session_instance(session_instance_id) ON DELETE SET NULL;

-- Add index for querying people at active sessions
CREATE INDEX idx_person_at_active_session ON person(at_active_session_instance_id) WHERE at_active_session_instance_id IS NOT NULL;

-- Comments for documentation
COMMENT ON COLUMN session.active_buffer_minutes_before IS 'Minutes before session start time when it becomes active (default 60)';
COMMENT ON COLUMN session.active_buffer_minutes_after IS 'Minutes after session end time when it stops being active (default 60)';
COMMENT ON COLUMN session_instance.is_active IS 'Whether this session instance is currently active (multiple instances per session can be active simultaneously)';
COMMENT ON COLUMN person.at_active_session_instance_id IS 'The session instance this person is currently attending (null when not at a session)';
