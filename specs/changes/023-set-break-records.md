# 023: Set Breaks as Records

**Date:** 2026-06-20
**Status:** Implemented — prerequisite refactor for [021-simplified-session-screen.md](021-simplified-session-screen.md)
**Related:** [015-fractional-indexing.md](015-fractional-indexing.md), [009-person-set-tracking.md](009-person-set-tracking.md)

## Overview

Today a set boundary is **implicit**: `session_instance_tune.continues_set = false` on the
*first tune of each set*. Sets are reconstructed everywhere by walking tunes in
`order_position` order and starting a new set whenever `continues_set` is false.

This change makes a set boundary an **explicit record** in the same
`session_instance_tune` table — a row with `record_type = 'break'` that carries no
tune — positioned in the normal `order_position` stream like any tune. A set becomes
"the run of tune records between two breaks (or instance start/end)."

This is a **behavior-preserving refactor**. No UX changes, no change to the bulk-save
model. It only changes the *representation* of a boundary. It is being done **first, on
its own**, so that the data model is already correct before the new live-logging UI
(Feature 021) is built on top of it.

## Motivation

The current `continues_set` boolean can't express things Feature 021 requires, and the
fixes are awkward to bolt on later:

1. **End a set before the next tune exists (or ever exists).** During live logging you
   must be able to *definitively* close the open set when a set ends — before anyone
   knows what the next tune will be, or whether the session is simply over. A boolean
   that lives on "the first tune of the *next* set" has no row to attach to until that
   next tune arrives. An explicit **trailing break** (a break after the last tune, with
   no tune following) is the durable "this set is closed" with nothing to anticipate.

2. **Boundaries carry metadata.** A break can be asserted by a human *or* by the audio
   recognizer hearing a pause (Feature 021 §G25), so it needs the same provenance a tune
   record has — author, eventually `source` (human|audio) and `confidence`, and a
   `played_timestamp` (audio knows the wall-clock moment of the pause). A boolean holds
   none of this.

3. **Breaks are records in the future op stream.** Feature 021 logs every action as an
   incremental, attributable op against a shared session. "End set" / "Split" / "Join"
   are far cleaner as *insert/remove a positioned break record* — uniform with adding a
   tune — than as "mutate a neighbor tune's boolean."

4. **It mirrors the audio model.** The recorder captures the *gap between sets* as a
   segment too (classified "not a tune," not shared/used otherwise). A break being a
   sibling record of a tune — same table, different `record_type` — matches that reality.

### Why a `record_type` column on the existing table (not a separate table)

A separate `set_break` table was considered and rejected. Keeping breaks **in
`session_instance_tune`** means:

- **Ordering stays unified.** Every read remains a single `ORDER BY order_position`
  scan — the way the code already walks rows — instead of merge-sorting two tables.
- **Audit is free.** The existing `session_instance_tune` history trigger audits break
  rows automatically; no second history table or trigger wiring.
- **It matches the eventual op stream** (a break is just another positioned record).

The cost is a constraint change and a careful sweep of tune-count/aggregation queries
(see Risks). That trade is worth it.

## Design

### The discriminator must be explicit

A break can **not** be identified by "`tune_id IS NULL`" — that is already taken: an
*unlinked tune* (typed by name, not yet matched to thesession.org) has `tune_id` null
and `name` not null. So a new explicit column is required:

- `record_type VARCHAR(16) NOT NULL DEFAULT 'tune'` — `'tune'` | `'break'`.

A break row: `record_type = 'break'`, `tune_id` null, `name` null, with an
`order_position` between its neighbors. A tune row is unchanged.

### A set, redefined

A set is the maximal run of `record_type = 'tune'` rows between two breaks (or between
instance start/end and a break). The segmentation loop changes from:

```
# old
if not row.continues_set and current_set:
    start new set
```
to:
```
# new
if row.record_type == 'break':
    close current set            # the break itself is not part of any set
else:
    append tune to current set
```

A **trailing break** (last record in the instance) means the final set is explicitly
**closed**. Its *absence* on a live instance means the final set is still **open**
(accepting tunes).

**Decision (supersedes the original draft): we always synthesize trailing breaks.** Every
set is terminated by a break, including the final set of every instance — in the backfill
and on every bulk save. This matches what leaving edit mode produces anyway and makes the
model uniform: **exactly one break per set, positioned immediately after the set**, so
`num_breaks == num_sets`. (Open/no-trailing-break sets only arise transiently during
incremental live logging — Feature 021 — e.g. while `add_tune` appends to the current
set; `segment_records_into_sets` handles the open case too.)

### What does NOT change here

- `started_by_person_id` stays **per-tune** (it is not moved onto a set entity — there
  is no set entity in this model; that was the explicit reason for choosing records over
  a first-class `session_instance_set` table). Feature 021 can revisit if needed.
- The bulk-save endpoint keeps its "send the whole array, diff it" behavior; it simply
  derives break rows from set boundaries instead of setting a boolean.
- No UX changes anywhere.

## Schema Changes

**New migration** `schema/0xx_set_break_records.sql` (and mirror into `full_schema.sql`,
`create_session_instance_tune_table.sql`, and the history table definitions):

1. Add column:
   ```sql
   ALTER TABLE session_instance_tune
     ADD COLUMN record_type VARCHAR(16) NOT NULL DEFAULT 'tune';
   ```
   Mirror onto the history table.

2. Replace the name-or-id CHECK constraint:
   ```sql
   -- old: CHECK (tune_id IS NOT NULL OR name IS NOT NULL)
   -- new:
   CHECK (record_type = 'break' OR tune_id IS NOT NULL OR name IS NOT NULL)
   ```

3. Columns reused as-is: `order_position`, `played_timestamp` (handy later — audio can
   time a break with zero new columns). `source` / `confidence` are **not** added here;
   they arrive with Feature 021 and will apply uniformly to both record types.

### Backfill (same migration, inside a transaction)

For every instance, insert a `record_type='break'` row at each **interior** set
boundary — i.e. immediately before each tune that currently has `continues_set = false`,
**except** the first tune of the instance — with an `order_position` strung between the
prior tune and that tune (reuse the fractional-index midpoint helper), **plus a trailing
break** after the last tune of every instance (net: one break per set). This is lossless:
sets render identically afterward.

The backfill is implemented as a Python script (`scripts/migrate_023_set_breaks.py`) so it
can reuse the audited `fractional_indexing` helpers (`generate_position_between`,
`generate_append_position`) instead of re-implementing the base-62 midpoint in PL/pgSQL. It
verifies that break-segmentation reproduces the old `continues_set` grouping for every
instance before dropping `continues_set`.

## Code Changes

### `api_routes.py` (~34 `continues_set` references, the bulk of the work)

Three clusters:

- **Set-grouping reads** (~lines 2953, 3353, 3989–4019, 7388–7424, 10694–10710) —
  replace the `continues_set` segmentation with the `record_type='break'` walk. **Factor
  into one shared helper** (`segment_records_into_sets(rows)`) so the logic lives in one
  place instead of the ~6 hand-rolled copies it is today.
- **Bulk save** (`save_session_instance_tunes_ajax`, ~7291–7359) — when diffing the
  incoming `tune_sets` array, INSERT/DELETE break rows at set boundaries instead of
  setting `continues_set`.
- **Reorder/move logic** (~4167–4324) — the "swap `continues_set` values when moving a
  tune across a boundary" code largely **disappears**; moving a tune no longer mutates a
  neighbor's flag.

### Stored SQL functions

`schema/insert_session_instance_tune.sql` and
`schema/update_insert_session_instance_tune_with_history.sql` reference `continues_set`
(both are already partly deprecated per Feature 018). Update or add a break-insert path
as needed; verify they aren't the live insert path before investing.

### `web_routes.py` + templates

The desktop logger (`templates/session_instance_detail.html`) and the view-a-session
page group sets client-side. Their data feed gains break records (or a pre-segmented
structure from the shared helper); update the grouping accordingly. Small but real.

### Tests + seed

`tests/integration/test_api_endpoints.py`, `tests/integration/test_database.py`,
`tests/fixtures/sample_data.py`, and `schema/seed_data.sql` encode `continues_set`;
update to the records model. Add coverage for: segmentation with break rows, backfill
correctness (breaks ↔ old `continues_set` agree), and that breaks are excluded from tune
aggregations.

## Risks

The one new failure mode: code that **counts or aggregates** `session_instance_tune`
rows without joining tune metadata would count breaks as tunes. Mitigations:

- Anything that INNER JOINs on `tune_id` already excludes breaks automatically.
- Audit every `FROM session_instance_tune` that does a bare `COUNT(*)` or iterates rows
  assuming `tune_id`/`name` is present; add `WHERE record_type = 'tune'`. This is
  grep-able and is the main thing to sweep carefully (popularity, "played here" stats,
  per-instance tune counts).

## Rollout (single full migration, one prod DB)

**Decision (supersedes the original two-release plan): full expand → contract in one go.**
No `continues_set` mirroring/safety-net column is kept; reversal, if ever needed, is simply
deleting `record_type='break'` rows. Manual prod steps, in order:

1. `psql ... -f schema/023_set_break_records.sql` — adds `record_type` + swaps the CHECK
   constraint + mirrors the column onto the history table (additive, idempotent).
2. `python3 scripts/migrate_023_set_breaks.py` — backfills breaks, verifies equivalence
   with `continues_set`, then **drops `continues_set`** from the table and history table,
   all in one transaction.

## Resolved Decision

- `source` / `confidence` on break (and tune) records: **deferred** to Feature 021 — they're
  meaningless until the audio/multi-user pipeline exists, and adding them is a cheap one-line
  migration then. (`played_timestamp` already exists, so audio-timed breaks need no new column.)

## Files

**Created:** `schema/023_set_break_records.sql` (expand DDL),
`scripts/migrate_023_set_breaks.py` (backfill + drop, transactional),
`tests/unit/test_set_segmentation.py`, this spec.
**Modified:** `schema/full_schema.sql`, `schema/create_session_instance_tune_table.sql`,
`schema/create_history_tables.sql`, `schema/seed_data.sql`,
`schema/insert_session_instance_tune.sql`,
`schema/update_insert_session_instance_tune_with_history.sql`, `api_routes.py`
(shared `segment_records_into_sets` + `reconcile_break_records` helpers; all reads/writes
cut over), `web_routes.py`, `database.py` (history copy), and the tests/fixtures above.
The desktop logger template needed **no** change — it still receives pre-segmented
`tune_sets` nested arrays.
