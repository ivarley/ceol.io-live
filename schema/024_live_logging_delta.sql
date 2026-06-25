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
-- SUPERSEDED by section 5 (live_logger_order on session_instance). Left in place
-- (harmless, unused) so the migration stays additive; the live service no longer
-- writes it. See section 5 for why presence-driven arrival order moved off
-- session_instance_person.
ALTER TABLE session_instance_person
    ADD COLUMN IF NOT EXISTS arrival_seq INTEGER;
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_instance_person_arrival
    ON session_instance_person (session_instance_id, arrival_seq)
    WHERE arrival_seq IS NOT NULL;

-- 5. session_logger_color (persisted per-session color, §F) ----------------
-- A person's palette color at a session, keyed by (session_id, person_id) and
-- PERMANENT: assigned on first appearance (the least-used palette index among
-- everyone who's logged at that session, so colors are distinct), then reused for
-- every future instance. This gives week-to-week visual identity ("Sarah is always
-- blue here") and survives streaming restarts / deploys for free.
--
-- Its OWN table, deliberately. A color is neither membership nor attendance:
--   * session_person rows imply membership (drive "My Sessions", suggested tunes,
--     people lists) — minting one to hold a color would make casual loggers look
--     like members.
--   * session_instance_person rows imply attendance — same inflation problem.
-- A standalone table assigns color without touching either, keyed the same way, so
-- it needs no schema change to session_person and triggers no attendance audit.
-- (Manual color override, when built, writes the same row.)
CREATE TABLE IF NOT EXISTS session_logger_color (
    session_id  INTEGER NOT NULL REFERENCES session(session_id) ON DELETE CASCADE,
    person_id   INTEGER NOT NULL REFERENCES person(person_id) ON DELETE CASCADE,
    color       SMALLINT NOT NULL,   -- palette index (0..N-1); UI maps index -> color
    created_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    PRIMARY KEY (session_id, person_id)
);
