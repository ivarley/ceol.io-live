-- Migration 062: schema-qualify unaccent inside tune_search_key
--
-- pg_dump / pg_restore (and pg_upgrade, which runs pg_restore) run with an
-- empty search_path. tune_search_key's body named unaccent() and the
-- 'unaccent' dictionary without a schema, so rebuilding idx_tune_name_key
-- and idx_tune_name_trgm during a restore failed with
--   ERROR: function unaccent(unknown, text) does not exist
-- which is what sank the Render in-place upgrade from Postgres 16 to 18.
--
-- The function's output is identical; only the name resolution is now
-- explicit, so the existing indexes stay valid and need no rebuild.
-- lower(), translate() and chr() are pg_catalog and always resolve.

CREATE OR REPLACE FUNCTION tune_search_key(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $$
    SELECT lower(public.unaccent('public.unaccent'::regdictionary, translate($1,
        -- smart singles -> '   then smart doubles -> "
        chr(8216)||chr(8217)||chr(700)||chr(8242)||chr(96)||chr(180)
        ||chr(8220)||chr(8221)||chr(8222)||chr(8243)||chr(171)||chr(187),
        chr(39)||chr(39)||chr(39)||chr(39)||chr(39)||chr(39)
        ||chr(34)||chr(34)||chr(34)||chr(34)||chr(34)||chr(34))))
$$;
