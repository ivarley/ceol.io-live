-- Person instrument history table
CREATE TABLE person_instrument_history (
    history_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    -- Copy of all person_instrument fields at time of change
    created_date TIMESTAMPTZ
);

-- Create indexes for history queries
CREATE INDEX idx_person_instrument_history_person_id ON person_instrument_history (person_id);
CREATE INDEX idx_person_instrument_history_changed_at ON person_instrument_history (changed_at);
CREATE INDEX idx_person_instrument_history_operation ON person_instrument_history (operation);