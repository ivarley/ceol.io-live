-- Spec 057: the language a person reads Ceol in. English or Irish, chosen on the
-- profile; signed-out visitors choose with a cookie instead. Idempotent.

BEGIN;

ALTER TABLE user_account ADD COLUMN IF NOT EXISTS language VARCHAR(8) NOT NULL DEFAULT 'en';
DO $$ BEGIN
    ALTER TABLE user_account ADD CONSTRAINT ck_user_account_language CHECK (language IN ('en', 'ga'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE user_account_history ADD COLUMN IF NOT EXISTS language VARCHAR(8);

COMMIT;
