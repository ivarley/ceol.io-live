-- =============================================================================
-- 055 "There is nothing else in this recording to place"
-- =============================================================================
-- /admin/recordings measures how far a recording has been timestamped by
-- counting its placements against the night's logged tunes: `38 / 52`. That
-- comparison assumes the audio covers the whole night, and often it does not --
-- a phone started an hour in, a battery that died before the last set, a file
-- that is deliberately just the good bit. For those the count can never reach
-- its denominator, so the row sits in the work queue forever advertising work
-- that does not exist.
--
-- The missing fact is not derivable from anything the database holds: only the
-- person who listened to the file knows whether the tunes that are NOT placed
-- are missing from the corpus or simply missing from the recording. So it is
-- recorded rather than inferred.
--
-- Deliberately NOT a status value. `status` is the ingest pipeline's state
-- (queued -> processing -> ready | failed) and is written by machines;
-- this is a human's judgement about the audio's contents, and a recording can
-- be re-ingested without that judgement becoming untrue. Two different facts,
-- two columns.
--
-- `segmenting_complete_at` is kept alongside the flag because "when did we
-- decide this was finished" is the question asked of a corpus that later turns
-- out to have a gap in it, and recording_history alone answers that only by
-- diffing adjacent rows.
-- =============================================================================

BEGIN;

ALTER TABLE recording
    ADD COLUMN IF NOT EXISTS segmenting_complete BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS segmenting_complete_at TIMESTAMPTZ;

COMMENT ON COLUMN recording.segmenting_complete IS
    'Set by hand: every tune actually present in this audio has been placed, so the work queue should stop counting the unplaced ones against it. For partial recordings, where placements can never reach the night''s tune count.';
COMMENT ON COLUMN recording.segmenting_complete_at IS
    'When segmenting_complete was last turned on. NULL whenever the flag is off.';

ALTER TABLE recording_history
    ADD COLUMN IF NOT EXISTS segmenting_complete BOOLEAN,
    ADD COLUMN IF NOT EXISTS segmenting_complete_at TIMESTAMPTZ;

COMMIT;
