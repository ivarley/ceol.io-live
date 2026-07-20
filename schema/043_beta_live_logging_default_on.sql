-- =============================================================================
-- 043 Live Logging — new logger default-on for all users
-- =============================================================================
-- The new live logger has graduated from opt-in beta. Flip the column default to
-- TRUE for future accounts, and backfill every existing account that hadn't
-- opted in yet. Additive + idempotent.
-- =============================================================================

ALTER TABLE user_account
    ALTER COLUMN beta_live_logging SET DEFAULT TRUE;

UPDATE user_account
    SET beta_live_logging = TRUE
    WHERE beta_live_logging = FALSE;
