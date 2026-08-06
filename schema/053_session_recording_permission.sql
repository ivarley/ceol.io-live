-- =============================================================================
-- 053 Let a session admin manage that session's recordings
-- =============================================================================
-- The segmenter (spec 050) has been system-admin only since it was built, on the
-- grounds that it is corpus-building rather than a member feature. That holds for
-- the cross-session views -- /admin/recordings lists every night in the system --
-- but not for the work itself: the person who recorded a session and knows what
-- was played is usually the one running it, not whoever administers the site.
--
-- So the grant is per session and opt-in, rather than a role anybody gets by
-- default:
--
--   * it lives on session_person, so it is scoped to ONE session;
--   * it is only meaningful alongside `is_admin`. The check is
--     `is_admin AND can_manage_recordings` everywhere -- a non-admin member with
--     the bit set has nothing, which keeps "who can do this" answerable by
--     looking at the session's admins rather than at every row;
--   * it defaults FALSE, so this migration grants nobody anything. Every
--     existing session admin keeps exactly the access they had this morning,
--     and a system admin turns it on one person at a time.
--
-- What it unlocks is scoped the same way: uploading, deleting and timestamping
-- recordings that belong to THIS session. It grants nothing on any other
-- session's audio, and nothing on the site-wide recordings index.
-- =============================================================================

BEGIN;

ALTER TABLE session_person
    ADD COLUMN IF NOT EXISTS can_manage_recordings BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE session_person_history
    ADD COLUMN IF NOT EXISTS can_manage_recordings BOOLEAN;

COMMENT ON COLUMN session_person.can_manage_recordings IS
    'May upload, delete and timestamp this session''s recordings. Only takes effect together with is_admin.';

-- The grant is rare, so the useful index is over the few rows that have it --
-- "who can manage recordings here" and the per-request permission check both
-- land on the (session_id, person_id) unique key anyway.
CREATE INDEX IF NOT EXISTS idx_session_person_manages_recordings
    ON session_person(session_id, person_id)
    WHERE can_manage_recordings;

COMMIT;
