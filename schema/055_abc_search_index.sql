-- 055: Index-backed ABC (notation) search.
--
-- Searching by notes -- "fdd cAA | B" finds "My Darling Asleep" -- used to live only in
-- the deep search, which did this on every tune_setting row:
--     REGEXP_REPLACE(abc, '\s', '', 'g') ILIKE '%fddcaab%'
-- A leading-wildcard LIKE cannot use a B-tree, so that is a sequential scan that
-- recomputes a regex per row. Tolerable when only a deliberate deep search reached it;
-- not tolerable now that notation search backs every tune-search box in the app,
-- including the public, every-page, debounced "Find a tune" overlay. And the
-- "is this query ABC?" test is looser than it looks -- `cabbage`, `bee`, `face` and
-- `ace` are all note letters -- so ordinary NAME typing triggers notation scans too.
--
-- Same shape as migration 026 did for names: ONE immutable normalization function used
-- by BOTH the index expression AND the query, so the planner sees identical expressions
-- and actually uses the index. See database.abc_query_key() for the query side, and
-- frontend/src/shared/abcquery.js normAbc() for the browser side -- all three must agree.
--
-- Idempotent; safe to re-run.

-- pg_trgm provides the trigram GIN operator class for substring LIKE. (Already created by
-- migration 026; repeated here so this file stands alone.)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- The normalized form we search notation on. Two jobs:
--
--   1. Drop what a player would never type but the notation carries anyway: grace notes
--      {...} and chord symbols / annotations "...". Without this, `{g}A{d}A{e}A {g}ABc`
--      can never match a typed `AAABc` -- roughly 9% of settings have such ornaments.
--      Bare `!` goes too: thesession's ABC uses it as a line break (converted to \n on
--      ingest since spec 024, but legacy rows still carry it), and it is also the
--      delimiter of !trill!-style decorations. Stripping the delimiter rather than
--      `!...!` spans is the safe choice -- treating it as a span would silently eat a
--      whole phrase between two line breaks.
--   2. Drop whitespace, which is meaningless in ABC, and lowercase -- ABC's octave case
--      distinction is deliberately ignored so `GED` and `ged` find the same tune.
--
-- IMMUTABLE (and STRICT, so NULL abc yields NULL) so it can be indexed.
CREATE OR REPLACE FUNCTION abc_search_key(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $$
    SELECT lower(
        regexp_replace(
            regexp_replace($1, '\{[^}]*\}|"[^"]*"', '', 'g'),  -- grace notes, chords
            '[[:space:]!]', '', 'g'                            -- whitespace + line breaks
        )
    )
$$;

-- Substring notation search: GIN trigram index on the normalized ABC. (pg_trgm needs at
-- least 3 characters in the pattern to use the index -- which is why the query layer
-- enforces a 3-character minimum on blended notation searches.)
CREATE INDEX IF NOT EXISTS idx_tune_setting_abc_trgm
    ON tune_setting USING gin (abc_search_key(abc) gin_trgm_ops);
