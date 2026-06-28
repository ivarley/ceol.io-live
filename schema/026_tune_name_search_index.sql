-- 026: Index-backed tune-name search (fast type-ahead + exact match).
--
-- The live logger and the legacy pill editor both resolve a typed string through
-- api_routes.match_tune_core, which does TWO full scans of `tune` on every keystroke:
--   1. find_matching_tune's exact tune-name lookup (database.py) -- an equality scan.
--   2. the wildcard candidate list -- a substring `LIKE '%q%'` scan.
-- On the production catalog (tens of thousands of tunes) that is the 2-3s lag.
--
-- A substring LIKE with a leading wildcard cannot use a B-tree (no sorted prefix to seek);
-- only a pg_trgm GIN index accelerates it. And `unaccent()` is STABLE, so it can't appear
-- in an index expression directly. We solve both with ONE immutable normalization function,
-- `tune_search_key(text)`, used by BOTH the index expressions AND the queries -- so the
-- planner sees identical expressions and the index is actually used.
--
-- Idempotent; safe to re-run.

-- pg_trgm provides the trigram GIN operator class for substring LIKE/ILIKE.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Single source of truth for "the normalized form we search on": fold smart quotes to
-- straight ASCII (mirrors database.normalize_quotes_sql -- code points, never literal
-- smart-quote characters, which editors silently auto-correct), strip accents, lowercase.
-- Marked IMMUTABLE (using the two-arg unaccent with an explicit dictionary, the standard
-- immutable-unaccent pattern) so it is indexable.
CREATE OR REPLACE FUNCTION tune_search_key(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $$
    SELECT lower(unaccent('unaccent', translate($1,
        -- smart singles -> '   then smart doubles -> "
        chr(8216)||chr(8217)||chr(700)||chr(8242)||chr(96)||chr(180)
        ||chr(8220)||chr(8221)||chr(8222)||chr(8243)||chr(171)||chr(187),
        chr(39)||chr(39)||chr(39)||chr(39)||chr(39)||chr(39)
        ||chr(34)||chr(34)||chr(34)||chr(34)||chr(34)||chr(34))))
$$;

-- Substring search (wildcard candidate list): GIN trigram index on the normalized name.
CREATE INDEX IF NOT EXISTS idx_tune_name_trgm
    ON tune USING gin (tune_search_key(name) gin_trgm_ops)
    WHERE redirect_to_tune_id IS NULL;

-- Exact / "The "-flexible match (find_matching_tune): B-tree on the same normalized name,
-- so the equality lookup is an index probe instead of a full scan.
CREATE INDEX IF NOT EXISTS idx_tune_name_key
    ON tune (tune_search_key(name))
    WHERE redirect_to_tune_id IS NULL;
