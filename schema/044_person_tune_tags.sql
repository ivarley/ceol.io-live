-- Spec 042 (groundwork): person_tune.tags — freeform per-person tags on a tune.
--
-- Mirrors IrishTune.info's per tune × member tag list and our own per-person
-- `notes` column: instrument-agnostic, one set of tags per (person, tune). Kept
-- as a Postgres TEXT[] so the future IrishTune sync can do a three-way SET MERGE
-- (union each side's adds/removes) and so `WHERE %s = ANY(tags)` filtering stays
-- cheap (GIN-indexable later if we filter My Tunes by tag).
--
-- Normalization is enforced in the app (services/person_tune_service.normalize_tags
-- and the matching client normalizeTag): one word each, lowercased, internal
-- whitespace -> single hyphen, de-duplicated, order preserved. No DB CHECK — the
-- vocabulary is freeform, same as `notes`.
--
-- NOT NULL DEFAULT '{}' is safe for every existing write path: INSERTs that omit
-- the column get '{}', and UPDATEs with an explicit column list (models/person_tune.py,
-- the merge function) never mention `tags`, so they leave it untouched.

ALTER TABLE person_tune
ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN person_tune.tags IS 'Freeform per-person tags on this tune (spec 042); normalized app-side, sync = set merge';

-- Keep the audit table structurally parallel with the table it shadows. Nullable
-- (no default) — a history snapshot mirrors whatever the live row held.
ALTER TABLE person_tune_history
ADD COLUMN IF NOT EXISTS tags TEXT[];

-- NOTE on merge_tune_ids (spec 030/037/040): its person_tune_history snapshots use
-- an explicit column list that does NOT include `tags` (same as it already omits
-- `key` in full_schema.sql — the merge audit snapshot is not exhaustively
-- maintained). This is intentionally left as-is here: live data is unaffected
-- (clean moves carry tags along via `UPDATE person_tune SET tune_id=...`; conflict
-- rows are deleted, discarding their tags by design), and only the rarely-written
-- tune-merge AUDIT row omits tags. Redefining the whole 380-line function to add
-- one audit column is not worth the regression risk.
