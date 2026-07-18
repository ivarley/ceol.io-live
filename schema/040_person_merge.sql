-- 040: person merge (admin action)
--
-- Person merging is now an application-level operation
-- (services/person_merge_service.py + POST /api/admin/people/merge): it covers
-- all eleven person-referencing tables, field-merges colliding rows, handles
-- user accounts, and writes history rows. The old merge_person_ids() SQL
-- function covered only four tables (session_person, session_instance_person,
-- person_tune, person_instrument) and silently dropped conflicting data —
-- drop it so the stale version can never be run by accident.
--
-- NOTE: Render deploys do NOT run schema migrations. Apply manually:
--   psql $PROD_DATABASE_URL -f schema/040_person_merge.sql

DROP FUNCTION IF EXISTS merge_person_ids(INTEGER, INTEGER);
