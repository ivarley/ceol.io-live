-- Spec 055: places and session paths.
--
-- A session's path is exactly `{place}/{second}`, and the first segment is a row
-- here: a town or metro (kind 'place') or a festival prefix (kind 'festival', spec
-- 056). session.place_id is the session's TOWN, whichever slug its path uses.
--
-- session.place_id is NULLABLE until the step-two cleanup that drops city/state/
-- country (spec 055, Implementation notes): the API write paths require it and
-- scripts/migrate_055_places.py backfills every production row; SET NOT NULL lands
-- with the column drop.
--
-- path_redirect is a runtime table, not a list in code: the migration writes the
-- legacy strays, and path renames from the admin UI write the rest.
--
-- Run before scripts/migrate_055_places.py. Idempotent.

BEGIN;

CREATE TABLE IF NOT EXISTS place (
    place_id SERIAL PRIMARY KEY,
    slug VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    kind VARCHAR(16) NOT NULL DEFAULT 'place' CHECK (kind IN ('place', 'festival')),
    parent_place_id INTEGER REFERENCES place(place_id),
    area VARCHAR(255),
    country VARCHAR(255),
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_modified_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_by_user_id INTEGER,
    last_modified_user_id INTEGER,
    CONSTRAINT ck_place_not_own_parent CHECK (parent_place_id IS NULL OR parent_place_id <> place_id)
);

CREATE INDEX IF NOT EXISTS idx_place_parent ON place(parent_place_id);

CREATE TABLE IF NOT EXISTS path_redirect (
    from_path VARCHAR(255) PRIMARY KEY,
    to_path VARCHAR(255) NOT NULL,
    created_date TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX IF NOT EXISTS idx_path_redirect_to_path ON path_redirect(to_path);

ALTER TABLE session ADD COLUMN IF NOT EXISTS place_id INTEGER REFERENCES place(place_id);
CREATE INDEX IF NOT EXISTS idx_session_place ON session(place_id);

ALTER TABLE session_history ADD COLUMN IF NOT EXISTS place_id INTEGER;

COMMIT;
