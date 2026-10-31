-- 067 Spec 061 stage 1: the right to listen on the server. The listening service
-- (listen/) admitted system admins only; a system admin can now give the right to
-- a named person from their admin page. System admins have it without the flag.
-- Idempotent.

BEGIN;

ALTER TABLE user_account ADD COLUMN IF NOT EXISTS can_listen_on_server BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user_account_history ADD COLUMN IF NOT EXISTS can_listen_on_server BOOLEAN;

COMMIT;
