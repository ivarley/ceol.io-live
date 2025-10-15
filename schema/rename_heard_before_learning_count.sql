-- Migration: Rename heard_before_learning_count to heard_count
-- This field tracks how many times a tune has been heard, regardless of learning status
-- The original name was too restrictive - it's useful to continue tracking after learning

-- Rename column in person_tune table
ALTER TABLE person_tune
RENAME COLUMN heard_before_learning_count TO heard_count;

-- Rename column in person_tune_history table
ALTER TABLE person_tune_history
RENAME COLUMN heard_before_learning_count TO heard_count;
