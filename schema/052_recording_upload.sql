-- =============================================================================
-- 052 Upload status for recordings
-- =============================================================================
-- In-app upload (spec 050, "Uploading from the browser") splits what the CLI
-- importer did in one breath into two moments that are minutes apart:
--
--   1. the browser PUTs the audio straight to S3 and the row is created, and
--   2. the server downloads it back, probes it, computes the waveform envelope
--      and transcodes the playback proxy.
--
-- Step 2 takes minutes on a three-hour file -- longer on a small dyno -- so the
-- row exists for a while in a state where `peaks` is NULL and `duration_ms` is
-- whatever the browser guessed from the file's own metadata. Without a status
-- column that row is indistinguishable from a finished one that happens to have
-- no waveform, and the segmenter would open it and show a flat line.
--
-- So the state is written down rather than inferred:
--   'processing' -- uploaded, being probed/encoded. duration_ms is PROVISIONAL.
--   'ready'      -- peaks and proxy are in place; safe to segment.
--   'failed'     -- ingest raised; status_detail says what, and the operator can
--                   retry from /admin/recordings.
--
-- Existing rows all came from scripts/import_recording.py, which only ever
-- committed after the whole pipeline succeeded, so 'ready' is the correct
-- default for every one of them.
--
-- status/status_detail are deliberately NOT added to recording_history: they are
-- operational state rather than content, and a single ingest run would otherwise
-- write three history rows saying nothing about the recording itself. Same
-- reasoning that keeps `peaks` out of history (schema/049).
-- =============================================================================

BEGIN;

ALTER TABLE recording
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ready',
    ADD COLUMN IF NOT EXISTS status_detail TEXT;

ALTER TABLE recording
    DROP CONSTRAINT IF EXISTS ck_recording_status;
ALTER TABLE recording
    ADD CONSTRAINT ck_recording_status
    CHECK (status IN ('processing', 'ready', 'failed'));

COMMENT ON COLUMN recording.status IS
    'processing | ready | failed. While processing, duration_ms is the browser''s provisional guess and peaks is NULL.';
COMMENT ON COLUMN recording.status_detail IS
    'Why ingest failed, or which step is running. Shown verbatim on /admin/recordings.';

-- "What still needs ingesting" is the only query this column is asked, and it
-- wants the handful of rows that are not ready.
CREATE INDEX IF NOT EXISTS idx_recording_status
    ON recording(status)
    WHERE status <> 'ready';

COMMIT;
