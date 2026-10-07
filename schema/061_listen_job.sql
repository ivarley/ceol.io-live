-- =============================================================================
-- 061 Background work for the listening service (spec 053,
-- "053 files/find-tunes-on-the-server.md")
-- =============================================================================
-- An admin asks the segmenter to find a night's tunes from its recording; the
-- listening service does it in the background, after live listening, and
-- reports where it has got to. One row per request.
--
--   status     queued -> running <-> paused -> done | failed | cancelled.
--              paused: live listening has the service; the job waits between
--              steps.
--   phase      listening | following | finishing, while running or paused.
--   heard_ms / total_ms   how far through the audio the listening has got.
--   progress   0..1 within the phase (following: sets done of sets).
--   worker / heartbeat_at the service instance that holds it, and when it last
--              said so; a running or paused job silent for two minutes went
--              down with its worker and is queued again (attempts, at most 3).
--   running_s / paused_s  time spent working and time spent waiting for live
--              listening, as the worker counts them; with queued_at,
--              started_at and finished_at, what the page and the admin list
--              show as "waited", "ran" and "paused".
--   result     {"tunes", "sets", "need_check", "confidence_model"} once done.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS listen_job (
    listen_job_id         SERIAL PRIMARY KEY,
    kind                  VARCHAR(16) NOT NULL DEFAULT 'find_tunes',
    recording_id          INTEGER NOT NULL REFERENCES recording(recording_id) ON DELETE CASCADE,
    requested_by_user_id  INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL,
    status                VARCHAR(16) NOT NULL DEFAULT 'queued',
    phase                 VARCHAR(16),
    progress              REAL,
    heard_ms              INTEGER,
    total_ms              INTEGER,
    worker                VARCHAR(64),
    heartbeat_at          TIMESTAMPTZ,
    attempts              SMALLINT NOT NULL DEFAULT 0,
    queued_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at            TIMESTAMPTZ,
    finished_at           TIMESTAMPTZ,
    running_s             REAL NOT NULL DEFAULT 0,
    paused_s              REAL NOT NULL DEFAULT 0,
    result                JSONB,
    error                 TEXT,
    CONSTRAINT listen_job_status CHECK (status IN ('queued', 'running', 'paused', 'done', 'failed', 'cancelled')),
    CONSTRAINT listen_job_kind CHECK (kind IN ('find_tunes'))
);

-- the queue, oldest first
CREATE INDEX IF NOT EXISTS idx_listen_job_queue ON listen_job (status, queued_at);
-- one job at a time for a recording
CREATE UNIQUE INDEX IF NOT EXISTS uq_listen_job_active_recording
    ON listen_job (recording_id) WHERE status IN ('queued', 'running', 'paused');

COMMIT;
