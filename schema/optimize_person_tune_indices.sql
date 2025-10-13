-- Performance optimization indexes for person_tune queries
-- These indexes optimize common query patterns for personal tune management

-- Composite index for filtered queries (person_id + learn_status)
-- Optimizes queries that filter by person and status
CREATE INDEX IF NOT EXISTS idx_person_tune_person_status 
ON person_tune (person_id, learn_status);

-- Composite index for person_id + created_date (for pagination with ORDER BY)
-- Optimizes the default sort order in the API
CREATE INDEX IF NOT EXISTS idx_person_tune_person_created 
ON person_tune (person_id, created_date DESC);

-- Composite index for person_id + tune_id (for quick lookups)
-- Already has UNIQUE constraint, but explicit index helps query planner
-- This is already covered by the UNIQUE constraint, so we skip it

-- Index for heard_before_learning_count queries
-- Optimizes queries that filter or sort by heard count
CREATE INDEX IF NOT EXISTS idx_person_tune_heard_count 
ON person_tune (person_id, heard_before_learning_count) 
WHERE learn_status = 'want to learn';

-- Analyze the table to update statistics for query planner
ANALYZE person_tune;
