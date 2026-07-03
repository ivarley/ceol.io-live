-- =============================================================================
-- 027 App Update Emails — opt-in flag + admin send tracking
-- =============================================================================
-- Users receive occasional app-update emails (on by default, opt-out on their
-- profile); a system admin composes and sends them (Markdown) from the
-- /admin/email-updates screen. Each
-- real send is recorded in email_message with per-recipient success/failure.
-- Unsubscribe links use stateless signed tokens (itsdangerous), so no token
-- column is needed. All additive + idempotent.
-- =============================================================================

-- Subscription flag (paired with history table, per convention). Default TRUE:
-- new accounts are subscribed unless they opt out on their profile.
ALTER TABLE user_account
    ADD COLUMN IF NOT EXISTS receive_update_emails BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE user_account
    ALTER COLUMN receive_update_emails SET DEFAULT TRUE;  -- fix-up for DBs created with an earlier FALSE default
ALTER TABLE user_account_history
    ADD COLUMN IF NOT EXISTS receive_update_emails BOOLEAN;

-- One-time launch backfill: subscribe all existing users (nobody has had a
-- chance to opt out yet). CAUTION: this statement is NOT idempotent after
-- launch — re-running it once users have unsubscribed would re-subscribe them.
UPDATE user_account SET receive_update_emails = TRUE WHERE receive_update_emails = FALSE;

-- One row per admin send (test sends to yourself are not recorded)
CREATE TABLE IF NOT EXISTS email_message (
    email_message_id   SERIAL PRIMARY KEY,
    subject            TEXT NOT NULL,
    body_markdown      TEXT NOT NULL,
    sent_by_user_id    INTEGER NOT NULL REFERENCES user_account(user_id),
    sent_date          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recipient_count    INTEGER NOT NULL DEFAULT 0,
    success_count      INTEGER NOT NULL DEFAULT 0,
    failure_count      INTEGER NOT NULL DEFAULT 0
);

-- One row per recipient per message
CREATE TABLE IF NOT EXISTS email_message_recipient (
    email_message_id   INTEGER NOT NULL REFERENCES email_message(email_message_id),
    user_id            INTEGER NOT NULL REFERENCES user_account(user_id),
    email              TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('sent', 'failed')),
    error_message      TEXT,
    PRIMARY KEY (email_message_id, user_id)
);
