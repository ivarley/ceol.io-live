-- =============================================================================
-- 063 A session admin can stop the "new person added" emails
-- =============================================================================
-- When someone is added to a session, its admins get an email. Until now there
-- was no way to turn that off. The setting lives on the person, not the account,
-- because admins without a login get the email too, and the one-click link in it
-- must be able to record their answer.
--
-- On by default, so nothing changes for anyone until they turn it off.

ALTER TABLE person
    ADD COLUMN IF NOT EXISTS notify_person_added BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE person_history
    ADD COLUMN IF NOT EXISTS notify_person_added BOOLEAN;

COMMENT ON COLUMN person.notify_person_added IS
    'Gets an email when someone is added to a session they admin; on by default, off on the profile or via the link in the email';
