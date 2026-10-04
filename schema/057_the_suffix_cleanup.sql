-- Names stored as "Kesh, The" instead of "The Kesh". The catalog (tune.name) keeps
-- the article in front; these rows were munged so they would sort under the noun.
-- Sorting without the article belongs at display time, not in the data.
--
-- 1. person_tune.name_alias: a person's own names ending ", The". The article goes
--    back in front; where that is just the tune's catalog name, the alias goes.
--
-- 2. session_instance_tune.name on B.D. Riley's, 2026-10-01 (instance 673): the
--    native app's live listener logged each tune with its candidate's name, and the
--    listener names tunes from the thesession.org data dump, which stores setting
--    names ("Holly Bush, The", "Maids Of Mount Kisco, The", "Toss The Feathers").
--    None of the 53 was a rename chosen that night, so every one goes and the rows
--    show the session alias or the catalog name like any other.
--
-- Comparison matches the app's name matching: case-, accent- and smart-quote-
-- insensitive (as in 039_sit_name_override_only.sql).
--
-- NOTE: audit history is app-level (save_to_history); this bulk hygiene pass
-- intentionally writes no history rows.

BEGIN;

CREATE FUNCTION pg_temp.norm_name(txt text) RETURNS text AS $$
  SELECT LOWER(unaccent(translate(txt,
    chr(8216)||chr(8217)||chr(700)||chr(8242)||chr(96)||chr(180)||
    chr(8220)||chr(8221)||chr(8222)||chr(8243)||chr(171)||chr(187),
    chr(39)||chr(39)||chr(39)||chr(39)||chr(39)||chr(39)||
    chr(34)||chr(34)||chr(34)||chr(34)||chr(34)||chr(34))))
$$ LANGUAGE sql STABLE;

-- 1. person_tune: "X, The" -> "The X", or NULL when that is the catalog name.
UPDATE person_tune pt
SET name_alias = CASE
      WHEN pg_temp.norm_name('The ' || regexp_replace(pt.name_alias, ',\s*the\s*$', '', 'i'))
         = pg_temp.norm_name(t.name)
      THEN NULL
      ELSE 'The ' || regexp_replace(pt.name_alias, ',\s*the\s*$', '', 'i')
    END,
    last_modified_date = NOW()
FROM tune t
WHERE t.tune_id = pt.tune_id
  AND pt.name_alias ~* ',\s*the\s*$';

-- 2. Instance 673: the listener's names. By id, so nothing else on the night is touched.
UPDATE session_instance_tune
SET name = NULL,
    last_modified_date = NOW()
WHERE session_instance_id = 673
  AND tune_id IS NOT NULL
  AND session_instance_tune_id IN (
    37855, 37858, 37859, 37867, 37868, 37870, 37876, 37884, 37888, 37890,
    37893, 37901, 37905, 37911, 37916, 37922, 37926, 37933, 37936, 37938,
    37939, 37940, 37942, 37949, 37951, 37954, 37955, 37957, 37959, 37960,
    37962, 37964, 37966, 37970, 37971, 37976, 37979, 37981, 37982, 37984,
    37985, 37987, 37988, 37989, 37991, 37993, 37994, 38001, 38002, 38004,
    38007, 38008, 38009
  );

COMMIT;
