-- Spec 039 — per-session people-tracking flags.
--
-- Three independent switches for a session's people features, each default TRUE so
-- existing behaviour is preserved and this is purely an opt-OUT:
--
--   show_people_list    the session-page members roster (the "People" tab). Off => no
--                       members list anywhere for non-admins. Admins always manage
--                       membership from the session admin page, regardless of this flag.
--   track_attendance    check-ins. Off => no check-in UI, the attendance ops are
--                       refused, and attendance rows for this session are excluded from
--                       every display app-wide (the person Attended tab, the /admin/people
--                       "Checked In" count, the "while I was there" lens) — historic
--                       included. The rows are never deleted, just unqueried.
--   track_set_starters  the "started by" pill. Off => pills hidden (past and present),
--                       the picker/bulk-assign gone, the attribute-starter op refused.
--
-- Dependency: recording who STARTED a set is meaningless without recording who was
-- THERE, so set-starters require attendance. The CHECK makes the nonsensical state
-- unrepresentable; the UI also disables the starters box when attendance is off.
--
-- NOT touched by any of these: presence, "currently logging / away", typing, and the
-- per-row "logged by" name/color — that's attribution of who's actively logging, which
-- a collaborative logger can't hide. Nor is `session_person.is_admin` or membership
-- itself: a people-hidden session must stay administrable.

ALTER TABLE session
    ADD COLUMN IF NOT EXISTS show_people_list   BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS track_attendance   BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS track_set_starters BOOLEAN NOT NULL DEFAULT TRUE;

-- Starters imply attendance. Named so it can be found and dropped if the coupling ever
-- changes.
ALTER TABLE session
    DROP CONSTRAINT IF EXISTS ck_session_starters_need_attendance;
ALTER TABLE session
    ADD CONSTRAINT ck_session_starters_need_attendance
    CHECK (track_attendance OR NOT track_set_starters);

COMMENT ON COLUMN session.show_people_list IS 'Spec 039: show the members roster to session members (admins manage membership regardless).';
COMMENT ON COLUMN session.track_attendance IS 'Spec 039: record + display attendance; off excludes this session''s attendance everywhere, historic included.';
COMMENT ON COLUMN session.track_set_starters IS 'Spec 039: record + display who started each set; requires track_attendance.';
