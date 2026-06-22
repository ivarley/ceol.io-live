-- =============================================================================
-- 024 Live Logging — Phase 1 schema delta  (spec 024 §I)
-- =============================================================================
-- Adds the columns/tables the full op vocabulary needs, on top of the Phase 0
-- session_event feed (schema/024_session_event.sql). All additive, idempotent.
--
--   session_instance_tune:  source / confidence / played_start / played_end
--                           / logged_timestamp / client_device_id / deleted
--   session_event:          op_id (idempotency key, §C)
--   NEW corroboration:      per-user assertions about a record (§H30 / §I)
--   session_instance_person: arrival_seq (color ordinal, §F)
--
-- Audio-only columns (source/confidence/played_*) are added now but human ops
-- never write played_*; they exist so the future audio task plugs in with no
-- further migration. See specs/changes/024-live-logging-architecture.md.
-- =============================================================================

-- 1. session_instance_tune delta -------------------------------------------
ALTER TABLE session_instance_tune
    ADD COLUMN IF NOT EXISTS source            VARCHAR(16) NOT NULL DEFAULT 'human',
    ADD COLUMN IF NOT EXISTS confidence        SMALLINT,            -- 0..100; NULL = definite human
    ADD COLUMN IF NOT EXISTS played_start      TIMESTAMPTZ,         -- audio-only
    ADD COLUMN IF NOT EXISTS played_end        TIMESTAMPTZ,         -- audio-only
    ADD COLUMN IF NOT EXISTS logged_timestamp  TIMESTAMPTZ,         -- client-asserted log time
    ADD COLUMN IF NOT EXISTS client_device_id  VARCHAR(64),
    ADD COLUMN IF NOT EXISTS deleted           BOOLEAN NOT NULL DEFAULT FALSE;  -- soft tombstone (§C)

-- Mirror onto the history table (nullable, like the other copied columns).
ALTER TABLE session_instance_tune_history
    ADD COLUMN IF NOT EXISTS source            VARCHAR(16),
    ADD COLUMN IF NOT EXISTS confidence        SMALLINT,
    ADD COLUMN IF NOT EXISTS played_start      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS played_end        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS logged_timestamp  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS client_device_id  VARCHAR(64),
    ADD COLUMN IF NOT EXISTS deleted           BOOLEAN;

-- Live reads skip tombstoned rows; index the common (instance, not-deleted) path.
CREATE INDEX IF NOT EXISTS idx_session_instance_tune_live
    ON session_instance_tune (session_instance_id, order_position)
    WHERE deleted = FALSE;

-- 2. session_event op_id (idempotency key, §C) -----------------------------
-- Client-generated UUID; a retried POST whose ack was lost dedupes to the same
-- event. Server-generated events (corroborate/conflict) leave it NULL. Postgres
-- allows many NULLs under a UNIQUE constraint, so a partial unique index is not
-- strictly required, but we use one to document intent and stay index-lean.
ALTER TABLE session_event
    ADD COLUMN IF NOT EXISTS op_id UUID;
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_event_op_id
    ON session_event (op_id) WHERE op_id IS NOT NULL;

-- 3. corroboration child table (§H30 / §I) ---------------------------------
-- Per-user assertions about a tune record (who else logged/heard the same tune
-- in the same slot, with what source/confidence). Keyed by user; person derived.
CREATE TABLE IF NOT EXISTS corroboration (
    corroboration_id    SERIAL PRIMARY KEY,
    record_id           INTEGER NOT NULL REFERENCES session_instance_tune(session_instance_tune_id) ON DELETE CASCADE,
    user_id             INTEGER,
    source              VARCHAR(16) NOT NULL DEFAULT 'human',
    confidence          SMALLINT,
    client_asserted_ts  TIMESTAMPTZ,
    created_date        TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    CONSTRAINT uq_corroboration_record_user UNIQUE (record_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_corroboration_record ON corroboration (record_id);

-- 4. session_instance_person.arrival_seq (color ordinal, §F) ---------------
-- Monotonic per-instance by first arrival; the UI infers color from the ordinal
-- (palette[seq mod N]). Claimed on first SSE connect via ON CONFLICT DO NOTHING.
ALTER TABLE session_instance_person
    ADD COLUMN IF NOT EXISTS arrival_seq INTEGER;
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_instance_person_arrival
    ON session_instance_person (session_instance_id, arrival_seq)
    WHERE arrival_seq IS NOT NULL;
