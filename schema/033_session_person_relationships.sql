-- 033: session_person relationships (spec 034)
--
-- Replaces the is_regular/is_admin boolean pair with four orthogonal fields, each
-- answering exactly one question:
--
--   relationship  'member' | 'visitor'  -- whose session is this?      (person OR admin sets)
--   confirmed     BOOLEAN               -- does the session vouch for them?  (admins only)
--   archived      BOOLEAN               -- are they still around?            (admins only)
--   is_admin      BOOLEAN               -- session admin  (unchanged)
--
-- is_regular is DROPPED with no replacement. "Regular-ness" is now computed from actual
-- attendance and is advisory only (sort order, quick-pick lists) -- it gates nothing.
--
-- Backfill makes every existing row 'member / confirmed / not archived', i.e. exactly its
-- current behavior. Grandfathering confirmed=TRUE matters: `confirmed` is the new gate on
-- people-visibility, and silently revoking it from everyone who has it today would be its
-- own bug.

BEGIN;

ALTER TABLE session_person
    ADD COLUMN relationship VARCHAR(10) NOT NULL DEFAULT 'member'
        CHECK (relationship IN ('member', 'visitor')),
    ADD COLUMN confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN archived  BOOLEAN NOT NULL DEFAULT FALSE;

-- Grandfather: everyone who can see the roster today keeps seeing it.
UPDATE session_person SET confirmed = TRUE;

DROP INDEX IF EXISTS idx_session_person_is_regular;
ALTER TABLE session_person DROP COLUMN is_regular;

-- The roster query: "this session's current members" / "...visitors".
CREATE INDEX idx_session_person_relationship
    ON session_person (session_id, relationship)
    WHERE archived = FALSE;

-- History table mirrors the live table.
ALTER TABLE session_person_history
    ADD COLUMN relationship VARCHAR(10),
    ADD COLUMN confirmed BOOLEAN,
    ADD COLUMN archived  BOOLEAN,
    DROP COLUMN is_regular;

COMMIT;
