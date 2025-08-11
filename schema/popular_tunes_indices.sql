-- Database indices for optimal performance of the popular tunes query
-- These should be created to speed up the most popular tunes feature

-- Index for session_instance_tune lookups by session_instance_id
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_session_instance_id 
ON session_instance_tune (session_instance_id);

-- Index for session_instance lookups by session_id
CREATE INDEX IF NOT EXISTS idx_session_instance_session_id 
ON session_instance (session_id);

-- Index for session_tune lookups by session_id and tune_id
CREATE INDEX IF NOT EXISTS idx_session_tune_session_id_tune_id 
ON session_tune (session_id, tune_id);

-- Index for tune table to speed up tunebook_count_cached access
CREATE INDEX IF NOT EXISTS idx_tune_tunebook_count 
ON tune (tune_id, tunebook_count_cached);

-- Composite index for the main query join conditions
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_composite 
ON session_instance_tune (session_instance_id, tune_id);

-- Additional index to help with the COALESCE operations in the query
-- This helps when we need to group by the resolved tune name
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_name_tune_id 
ON session_instance_tune (name, tune_id) 
WHERE name IS NOT NULL;