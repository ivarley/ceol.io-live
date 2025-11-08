-- Create tune_setting table
-- This table caches setting information from thesession.org for specific tune variations
-- Settings are in a many-to-one relationship with tunes (one tune can have many settings)

CREATE TABLE IF NOT EXISTS tune_setting (
    setting_id INTEGER PRIMARY KEY,  -- from thesession.org, globally unique
    tune_id INTEGER NOT NULL REFERENCES tune(tune_id) ON DELETE CASCADE,
    key VARCHAR(10),
    abc TEXT,
    image TEXT,  -- future: URL to generated sheet music
    incipit_abc TEXT,  -- future: first few bars
    incipit_image TEXT,  -- future: image of first bars
    cache_updated_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    UNIQUE(setting_id, tune_id)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_tune_setting_tune_id ON tune_setting (tune_id);
CREATE INDEX IF NOT EXISTS idx_tune_setting_cache_date ON tune_setting (cache_updated_date);

-- Create tune_setting_history table for audit trail
CREATE TABLE IF NOT EXISTS tune_setting_history (
    tune_setting_history_id SERIAL PRIMARY KEY,
    setting_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(100) NOT NULL DEFAULT 'system',
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),

    -- Historical data fields (snapshot at time of change)
    tune_id INTEGER NOT NULL,
    key VARCHAR(10),
    abc TEXT,
    image TEXT,
    incipit_abc TEXT,
    incipit_image TEXT,
    cache_updated_date TIMESTAMPTZ,
    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ
);

-- Create indexes for history table
CREATE INDEX IF NOT EXISTS idx_tune_setting_history_setting_id ON tune_setting_history (setting_id);
CREATE INDEX IF NOT EXISTS idx_tune_setting_history_changed_at ON tune_setting_history (changed_at);
CREATE INDEX IF NOT EXISTS idx_tune_setting_history_operation ON tune_setting_history (operation);
