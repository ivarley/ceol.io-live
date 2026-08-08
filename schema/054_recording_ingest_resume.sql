-- =============================================================================
-- 054 Let a stranded ingest pick itself back up
-- =============================================================================
-- Ingest already runs on a background thread, so closing the tab does not stop
-- it. What stops it is the dyno: Render's free tier idles a web service out
-- after ~15 minutes without inbound traffic, and the upload page's own poll was
-- the only thing keeping it awake. Walk away from a long file and the thread can
-- die mid-transcode, leaving the row 'processing' forever.
--
-- Two columns make that recoverable without a human noticing:
--
--   * `ingest_heartbeat_at` -- proof of life, written every 30s by whoever is
--     running the ingest. Liveness used to be inferred from last_modified_date,
--     which only moves at stage boundaries; Waveform and Proxy each run for
--     minutes on a long recording with no write in between, so the "presumed
--     dead" threshold had to be two hours to avoid reaping a live run. A real
--     heartbeat brings that to 90 seconds. Same mechanism, same interval, and
--     the same reasoning as tune_merge_scan.heartbeat_at (spec 031).
--
--   * `ingest_attempts` -- a retry budget. A sweeper that re-runs anything stale
--     would otherwise retry a genuinely unreadable file every ten minutes
--     forever. After a few goes the row is marked failed and stays that way. An
--     explicit human Retry resets the count, because a person choosing to try
--     again is a different event from a machine looping.
--
-- The status vocabulary also gains 'queued': the create endpoint can then hand a
-- recording off without depending on its thread ever starting, and the sweeper
-- picks it up either way.
-- =============================================================================

BEGIN;

ALTER TABLE recording
    ADD COLUMN IF NOT EXISTS ingest_heartbeat_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ingest_attempts SMALLINT NOT NULL DEFAULT 0;

ALTER TABLE recording
    DROP CONSTRAINT IF EXISTS ck_recording_status;
ALTER TABLE recording
    ADD CONSTRAINT ck_recording_status
    CHECK (status IN ('queued', 'processing', 'ready', 'failed'));

COMMENT ON COLUMN recording.ingest_heartbeat_at IS
    'Proof of life from whoever is running ingest, refreshed every 30s. Older than 90s means the run died and the row can be claimed again.';
COMMENT ON COLUMN recording.ingest_attempts IS
    'Automatic ingest attempts so far. Caps the sweeper so an unreadable file fails visibly instead of retrying forever; an explicit Retry resets it to 0.';

-- The sweeper's only query: the handful of rows that are not finished. Partial,
-- because in steady state every row is 'ready' and this index stays tiny.
DROP INDEX IF EXISTS idx_recording_status;
CREATE INDEX IF NOT EXISTS idx_recording_pending_ingest
    ON recording(status, ingest_heartbeat_at)
    WHERE status IN ('queued', 'processing');

COMMIT;
