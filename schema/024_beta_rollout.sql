-- =============================================================================
-- 024 Live Logging — beta rollout + one-way editor lock
-- =============================================================================
-- Per-user opt-in to the new live editor (admin-set), and a per-instance logging
-- mode so the classic editor can't clobber an instance the live editor owns.
-- Both additive + idempotent.
-- =============================================================================

-- Who gets the new live logger. Admin-set only (see web_routes admin people page).
ALTER TABLE user_account
    ADD COLUMN IF NOT EXISTS beta_live_logging BOOLEAN NOT NULL DEFAULT FALSE;

-- 'legacy' = classic pill editor; 'live' = new SSE editor (spec 024). Flipped to
-- 'live' on the first live op for an instance. The legacy mutation endpoints refuse
-- (read-only) on a 'live' instance — a one-way lock that prevents the classic bulk
-- save (which hard-deletes rows absent from its submitted set and emits no events)
-- from silently destroying live-editor data. An admin can reset it to 'legacy'.
ALTER TABLE session_instance
    ADD COLUMN IF NOT EXISTS logging_mode VARCHAR(10) NOT NULL DEFAULT 'legacy';
