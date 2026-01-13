-- Add auto-create instance settings to session table
-- This allows sessions to automatically create upcoming instances based on their recurrence pattern

-- Add auto_create_instances column - when TRUE, instances will be auto-created ahead of time
ALTER TABLE session
ADD COLUMN auto_create_instances BOOLEAN NOT NULL DEFAULT FALSE;

-- Add auto_create_hours_ahead column - how many hours ahead to create instances (default 24 hours)
ALTER TABLE session
ADD COLUMN auto_create_hours_ahead INTEGER NOT NULL DEFAULT 24;

-- Add constraint to ensure hours_ahead is reasonable (at least 1 hour, at most 168 hours = 1 week)
ALTER TABLE session
ADD CONSTRAINT auto_create_hours_ahead_check CHECK (auto_create_hours_ahead >= 1 AND auto_create_hours_ahead <= 168);

-- Add comments for documentation
COMMENT ON COLUMN session.auto_create_instances IS 'When TRUE, session instances will be automatically created based on the recurrence pattern by the cron job';
COMMENT ON COLUMN session.auto_create_hours_ahead IS 'Number of hours ahead to auto-create session instances (default 24)';

-- Add the columns to session_history table for audit tracking
ALTER TABLE session_history
ADD COLUMN auto_create_instances BOOLEAN;

ALTER TABLE session_history
ADD COLUMN auto_create_hours_ahead INTEGER;

-- Add comments for history table
COMMENT ON COLUMN session_history.auto_create_instances IS 'When TRUE, session instances will be automatically created based on the recurrence pattern';
COMMENT ON COLUMN session_history.auto_create_hours_ahead IS 'Number of hours ahead to auto-create session instances';
