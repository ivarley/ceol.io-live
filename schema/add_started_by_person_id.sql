-- Add started_by_person_id column to session_instance_tune table
-- This tracks which person started each set (stored on each tune in the set)

ALTER TABLE session_instance_tune
ADD COLUMN IF NOT EXISTS started_by_person_id INTEGER REFERENCES person(person_id);

-- Add index for efficient lookups by person_id
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_started_by
ON session_instance_tune (started_by_person_id)
WHERE started_by_person_id IS NOT NULL;

-- Add the column to the history table as well
ALTER TABLE session_instance_tune_history
ADD COLUMN IF NOT EXISTS started_by_person_id INTEGER;
