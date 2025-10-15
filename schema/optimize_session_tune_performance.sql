-- Performance optimization indexes for session_instance_tune queries
-- These indexes dramatically improve the performance of tune detail queries
-- that need to count how many times a person has seen a tune at their sessions

-- Index on tune_id for fast lookups when querying "where did this tune get played"
-- This is critical for the tune detail modal query
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_tune_id
ON session_instance_tune (tune_id);

-- Index on session_instance_id for fast joins with session_instance
-- This helps with the JOIN in the tune detail query
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_session_instance_id
ON session_instance_tune (session_instance_id);

-- Composite index for the most common query pattern (tune_id + session_instance_id)
-- This is the optimal index for the tune detail "session play count" query
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_tune_session
ON session_instance_tune (tune_id, session_instance_id);

-- Analyze the table to update statistics for query planner
ANALYZE session_instance_tune;
