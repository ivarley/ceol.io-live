-- Add session_type field to session table
-- This supports different types of sessions: regular (recurring) and festival (multi-day events)

-- Add the session_type column with default value of 'regular' to session table
ALTER TABLE session
ADD COLUMN session_type VARCHAR(50) NOT NULL DEFAULT 'regular';

-- Add a check constraint to ensure only valid session types
ALTER TABLE session
ADD CONSTRAINT session_type_check CHECK (session_type IN ('regular', 'festival'));

-- Add an index for session_type queries
CREATE INDEX idx_session_type ON session(session_type);

-- Add comment for documentation
COMMENT ON COLUMN session.session_type IS 'Type of session: regular (recurring) or festival (multi-day event)';

-- Add the session_type column to session_history table for audit tracking
ALTER TABLE session_history
ADD COLUMN session_type VARCHAR(50);

-- Add comment for history table
COMMENT ON COLUMN session_history.session_type IS 'Type of session: regular (recurring) or festival (multi-day event)';
