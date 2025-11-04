-- Enable the unaccent extension for accent-insensitive text searches
-- This allows searching for "si" to match "sí" and similar cases

CREATE EXTENSION IF NOT EXISTS unaccent;
