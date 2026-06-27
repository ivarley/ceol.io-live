-- 025: Per-session local-cache (fast-match vocabulary) size limits (spec 024).
--
-- The live-logging screen ships each session a "local vocabulary" the client indexes
-- for offline / zero-network exact-match logging. It has two tiers:
--   N (live_cache_session_limit) — this session's own most-played tunes
--   M (live_cache_global_limit)  — globally-popular tunes (by tunebook count) not in N
-- A session leader can tune N/M from the session admin "Local Cache" tab. Defaults
-- mirror the LOCAL_VOCAB_* fallbacks in live_logging_routes.py.
--
-- Idempotent; safe to re-run. (Config columns — not mirrored into session_history,
-- matching the auto_create_* precedent.)

ALTER TABLE session
    ADD COLUMN IF NOT EXISTS live_cache_session_limit INTEGER NOT NULL DEFAULT 200,
    ADD COLUMN IF NOT EXISTS live_cache_global_limit  INTEGER NOT NULL DEFAULT 25;
