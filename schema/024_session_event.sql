-- =============================================================================
-- 024 Session Event Feed  (live logging — Phase 0 walking skeleton)
-- =============================================================================
-- Append-only change feed for the real-time live-logging screen (spec 024 §B).
-- `session_instance_tune` stays the canonical current state; this table is the
-- ordered delivery/replay log that drives SSE fan-out.
--
--   * event_id            globally monotonic BIGSERIAL — doubles as the SSE
--                         Last-Event-ID cursor (gap recovery / offline catch-up).
--   * session_instance_id which instance's feed this event belongs to (indexed).
--   * op_type             the operation ('add_tune' in Phase 0).
--   * payload             JSONB describing the committed result.
--   * created_by_user_id  the actor (audit; person is derived, §D).
--   * server_ts           receipt time.
--
-- Write path: the event row is appended in the SAME transaction as the
-- session_instance_tune mutation, then `pg_notify('session_instance_<id>', event_id)`
-- fires so the streaming service can re-read the row and push it to subscribers.
--
-- Distinct from the *_history audit tables: this is a transient delivery log,
-- kept for the instance's lifetime, not a permanent column-level audit.
--
-- Idempotent.  See specs/changes/024-live-logging-architecture.md.
-- =============================================================================

CREATE TABLE IF NOT EXISTS session_event (
    event_id            BIGSERIAL PRIMARY KEY,
    session_instance_id INTEGER NOT NULL REFERENCES session_instance(session_instance_id) ON DELETE CASCADE,
    op_type             VARCHAR(32) NOT NULL,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_user_id  INTEGER,
    server_ts           TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Replay/catch-up reads filter by instance and walk event_id ascending.
CREATE INDEX IF NOT EXISTS idx_session_event_instance
    ON session_event (session_instance_id, event_id);
