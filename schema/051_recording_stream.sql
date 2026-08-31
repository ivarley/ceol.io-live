-- =============================================================================
-- 051 Playback proxy for recordings
-- =============================================================================
-- A session recording is a big file -- 348MB for three hours at 256kbps stereo.
-- The segmenter has to pull it over cellular before anything can be heard, and
-- reported from a phone: "at first I thought it wasn't working."
--
-- So: keep the master, add a small mono proxy to PLAY. ~64kbps mono AAC is
-- around a fourteenth the size and loses nothing that matters for the job,
-- which is hearing where one tune stops and the next begins.
--
-- The split is deliberate and load-bearing:
--   * `storage_key` stays the MASTER. The training corpus is cut from it, and
--     nothing should ever cut audio from the proxy -- feeding a model artefacts
--     of a 64kbps encode would be a quiet, expensive mistake.
--   * `stream_key` is for the browser, and only for the browser.
-- Nullable throughout: recordings imported before this play the master, exactly
-- as they did.
-- =============================================================================

BEGIN;

ALTER TABLE recording
    ADD COLUMN IF NOT EXISTS stream_key VARCHAR(500),
    ADD COLUMN IF NOT EXISTS stream_mime_type VARCHAR(100),
    ADD COLUMN IF NOT EXISTS stream_size_bytes BIGINT;

COMMENT ON COLUMN recording.storage_key IS
    'S3 key of the master audio. The training corpus is cut from THIS, never from stream_key.';
COMMENT ON COLUMN recording.stream_key IS
    'S3 key of a small mono proxy used only for playback in the segmenter. NULL means play the master.';

ALTER TABLE recording_history
    ADD COLUMN IF NOT EXISTS stream_key VARCHAR(500),
    ADD COLUMN IF NOT EXISTS stream_mime_type VARCHAR(100),
    ADD COLUMN IF NOT EXISTS stream_size_bytes BIGINT;

COMMIT;
