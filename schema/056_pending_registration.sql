-- =============================================================================
-- 056 Pending registrations: no account until the email link is clicked
-- =============================================================================
-- Login is email-first. Typing an address with no account used to create a
-- user_account row and a blank person row on the spot, then email a
-- verification link. A returning player who mistyped their address
-- (ian@gmial.com) got a phantom account, never learned the address was wrong,
-- and left junk rows behind.
--
-- Now typing an unknown address only records a pending registration here and
-- emails the link. Clicking the link (GET /verify-email/<token>, or
-- POST /api/auth/exchange from the app) creates the person and the account,
-- already verified, and deletes this row. A row nobody clicks is harmless and
-- is simply overwritten or ignored once it expires.
--
-- One row per address (case-insensitive): entering the same address again
-- refreshes the row instead of adding another.
--
-- Idempotent. An earlier, abandoned attempt created a table of the same name in
-- some local databases; nothing ever used it, so it is dropped and recreated.
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS pending_registration;

CREATE TABLE pending_registration (
    pending_registration_id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    verification_token VARCHAR(255) NOT NULL UNIQUE,
    verification_token_expires TIMESTAMPTZ NOT NULL,
    referred_by_person_id INTEGER REFERENCES person(person_id) ON DELETE SET NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_sent_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE UNIQUE INDEX idx_pending_registration_email_lower ON pending_registration (LOWER(email));

COMMENT ON TABLE pending_registration IS
    'An email address that asked to register but has not clicked its link yet. No person or user_account exists for it until the link is clicked (migration 056).';
COMMENT ON COLUMN pending_registration.verification_token IS
    'Token in the emailed /verify-email/<token> link, 24-hour expiry. Kept across re-entries while still valid, so an earlier email keeps working.';
COMMENT ON COLUMN pending_registration.referred_by_person_id IS
    'The ?referrer=<person_id> captured in the session when the address was entered; copied to user_account on completion.';
COMMENT ON COLUMN pending_registration.last_sent_date IS
    'When the verification email was last sent for this row.';

COMMIT;
