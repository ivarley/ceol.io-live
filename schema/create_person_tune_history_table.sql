-- Create person_tune_history table for audit trail
CREATE TABLE person_tune_history (
    person_tune_history_id SERIAL PRIMARY KEY,
    person_tune_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(100) NOT NULL DEFAULT 'system',
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    
    -- Historical data fields (snapshot of person_tune at time of change)
    person_id INTEGER NOT NULL,
    tune_id INTEGER NOT NULL,
    learn_status VARCHAR(20) NOT NULL,
    heard_count INTEGER DEFAULT 0,
    learned_date TIMESTAMPTZ,
    notes TEXT,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Create indexes for efficient querying of history
CREATE INDEX idx_person_tune_history_person_tune_id ON person_tune_history (person_tune_id);
CREATE INDEX idx_person_tune_history_person_id ON person_tune_history (person_id);
CREATE INDEX idx_person_tune_history_changed_at ON person_tune_history (changed_at);
CREATE INDEX idx_person_tune_history_operation ON person_tune_history (operation);