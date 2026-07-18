-- 041_retire_person_email_unify_active.sql
--
-- MANUAL migration (Render does NOT run schema/*.sql — psql this against prod
-- yourself, section by section). Two independent cleanups, each preceded by a
-- REVIEW query you should eyeball before running its mutations:
--
--   A) Retire person.email for connected people. person.email exists only to
--      match a person to a later-created account (registration matches on it).
--      Once connected, user_account.user_email is the authoritative address, so
--      person.email becomes redundant. The app now nulls it at connection time;
--      this backfills existing rows.
--
--   B) Unify active status for connected people. A person and their login
--      account now share one active flag (deactivating a person disables their
--      login). This reconciles rows that are currently out of sync using the
--      "deactivated if either" rule: if either flag is false, both become false.
--
-- History note: these are bulk admin updates; they intentionally do NOT write
-- *_history rows (there are no DB history triggers — history is app-level only).
-- Run the ship of the CODE changes BEFORE running section A, so nothing is still
-- reading person.email for connected people.

-- ===========================================================================
-- SECTION A — retire person.email for connected people
-- ===========================================================================

-- --- REVIEW A1: genuine email conflicts (both present and different). Eyeball
--     these before running the mutations — after A they collapse to user_email.
SELECT p.person_id, p.first_name, p.last_name,
       p.email AS person_email, ua.user_email AS account_email,
       ua.is_active, ua.receive_update_emails
FROM person p
JOIN user_account ua ON ua.person_id = p.person_id
WHERE p.email IS NOT NULL AND ua.user_email IS NOT NULL
  AND LOWER(btrim(p.email)) <> LOWER(btrim(ua.user_email))
ORDER BY p.last_name, p.first_name;

-- --- REVIEW A2: connected accounts with a blank/empty user_email but a person
--     email (A-step-1 copies person.email into user_email for these). Expected
--     to be ~0 rows: user_email is NOT NULL + unique-lower in prod.
SELECT p.person_id, p.first_name, p.last_name, p.email AS person_email
FROM person p
JOIN user_account ua ON ua.person_id = p.person_id
WHERE (ua.user_email IS NULL OR btrim(ua.user_email) = '')
  AND p.email IS NOT NULL AND btrim(p.email) <> ''
ORDER BY p.last_name, p.first_name;

-- --- MUTATION A-step-1: where the account has no usable email, adopt the
--     person's email so no address is lost before we null person.email.
UPDATE user_account ua
SET user_email = btrim(p.email),
    last_modified_date = (now() AT TIME ZONE 'UTC')
FROM person p
WHERE ua.person_id = p.person_id
  AND (ua.user_email IS NULL OR btrim(ua.user_email) = '')
  AND p.email IS NOT NULL AND btrim(p.email) <> '';

-- --- MUTATION A-step-2: retire person.email for every connected person.
UPDATE person p
SET email = NULL,
    last_modified_date = (now() AT TIME ZONE 'UTC')
FROM user_account ua
WHERE ua.person_id = p.person_id
  AND p.email IS NOT NULL;

-- --- VERIFY A: should return 0.
SELECT COUNT(*) AS connected_people_still_with_person_email
FROM person p
JOIN user_account ua ON ua.person_id = p.person_id
WHERE p.email IS NOT NULL;

-- ===========================================================================
-- SECTION B — unify active status for connected people (deactivated-if-either)
-- ===========================================================================

-- --- REVIEW B1: connected people whose two active flags disagree (this is the
--     "57 vs 61" delta). Eyeball before reconciling — each of these will be
--     fully deactivated (both flags -> false) under the deactivated-if-either rule.
SELECT p.person_id, p.first_name, p.last_name,
       p.active AS person_active, ua.is_active AS account_active,
       ua.receive_update_emails, ua.user_email
FROM person p
JOIN user_account ua ON ua.person_id = p.person_id
WHERE p.active IS DISTINCT FROM ua.is_active
ORDER BY p.last_name, p.first_name;

-- --- MUTATION B-step-1: a person active but whose account is inactive -> deactivate the person.
UPDATE person p
SET active = FALSE,
    last_modified_date = (now() AT TIME ZONE 'UTC')
FROM user_account ua
WHERE ua.person_id = p.person_id
  AND p.active = TRUE AND ua.is_active = FALSE;

-- --- MUTATION B-step-2: an account active but whose person is inactive -> deactivate the account.
UPDATE user_account ua
SET is_active = FALSE,
    last_modified_date = (now() AT TIME ZONE 'UTC')
FROM person p
WHERE p.person_id = ua.person_id
  AND ua.is_active = TRUE AND p.active = FALSE;

-- --- VERIFY B: should return 0.
SELECT COUNT(*) AS connected_people_still_desynced
FROM person p
JOIN user_account ua ON ua.person_id = p.person_id
WHERE p.active IS DISTINCT FROM ua.is_active;
