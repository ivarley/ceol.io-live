-- session_instance_tune.name is an override slot: display resolves
-- COALESCE(sit.name, session_tune.alias, tune.name), so a stored copy of either
-- fallback is redundant — and it pins the row's display forever (a session alias
-- set later never shows on already-logged rows). The live logger and pill editor
-- used to write the display name on every linked row; writers now store a name
-- only when it genuinely differs from both fallbacks (database.normalize_override_name).
--
-- This backfills existing rows: NULL the redundant copies on linked rows. Genuine
-- overrides survive because they differ from the current fallbacks — per-night
-- renames, and the names frozen into sit.name by merge_tune_ids() (spec 030),
-- which by construction differ from the surviving tune's canonical name.
--
-- Comparison matches the app's name matching: case-, accent- and smart-quote-
-- insensitive (mirrors normalize_quotes_sql + LOWER(unaccent(...))).
--
-- NOTE: audit history is app-level (save_to_history); this bulk hygiene pass
-- intentionally writes no session_instance_tune_history rows.

CREATE FUNCTION pg_temp.norm_name(txt text) RETURNS text AS $$
  SELECT LOWER(unaccent(translate(txt,
    chr(8216)||chr(8217)||chr(700)||chr(8242)||chr(96)||chr(180)||
    chr(8220)||chr(8221)||chr(8222)||chr(8243)||chr(171)||chr(187),
    chr(39)||chr(39)||chr(39)||chr(39)||chr(39)||chr(39)||
    chr(34)||chr(34)||chr(34)||chr(34)||chr(34)||chr(34))))
$$ LANGUAGE sql STABLE;

UPDATE session_instance_tune sit
SET name = NULL
FROM session_instance si, tune t
WHERE si.session_instance_id = sit.session_instance_id
  AND t.tune_id = sit.tune_id
  AND sit.name IS NOT NULL
  AND (
    pg_temp.norm_name(sit.name) = pg_temp.norm_name(t.name)
    OR EXISTS (
      SELECT 1 FROM session_tune st
      WHERE st.session_id = si.session_id
        AND st.tune_id = sit.tune_id
        AND st.alias IS NOT NULL
        AND pg_temp.norm_name(st.alias) = pg_temp.norm_name(sit.name)
    )
  );

DROP FUNCTION pg_temp.norm_name(text);
