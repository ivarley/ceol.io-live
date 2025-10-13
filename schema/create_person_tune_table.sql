-- Create person_tune table for personal tune management
CREATE TABLE person_tune (
    person_tune_id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    tune_id INTEGER NOT NULL REFERENCES tune(tune_id) ON DELETE CASCADE,
    learn_status VARCHAR(20) NOT NULL DEFAULT 'want to learn' 
        CHECK (learn_status IN ('want to learn', 'learning', 'learned')),
    heard_before_learning_count INTEGER DEFAULT 0 CHECK (heard_before_learning_count >= 0),
    learned_date TIMESTAMPTZ, -- Set when status changes to 'learned'
    notes TEXT,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    UNIQUE(person_id, tune_id)
);

-- Create indexes for optimal query performance
CREATE INDEX idx_person_tune_person_id ON person_tune (person_id);
CREATE INDEX idx_person_tune_tune_id ON person_tune (tune_id);
CREATE INDEX idx_person_tune_learn_status ON person_tune (learn_status);
CREATE INDEX idx_person_tune_learned_date ON person_tune (learned_date) WHERE learned_date IS NOT NULL;

-- Create trigger function to automatically update last_modified_date
CREATE OR REPLACE FUNCTION update_person_tune_last_modified_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified_date = (NOW() AT TIME ZONE 'UTC');
    
    -- Automatically set learned_date when status changes to 'learned'
    IF NEW.learn_status = 'learned' AND OLD.learn_status != 'learned' THEN
        NEW.learned_date = (NOW() AT TIME ZONE 'UTC');
    END IF;
    
    -- Clear learned_date if status changes away from 'learned'
    IF NEW.learn_status != 'learned' AND OLD.learn_status = 'learned' THEN
        NEW.learned_date = NULL;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to call the function before updates
CREATE TRIGGER trigger_person_tune_last_modified_date
    BEFORE UPDATE ON person_tune
    FOR EACH ROW
    EXECUTE FUNCTION update_person_tune_last_modified_date();