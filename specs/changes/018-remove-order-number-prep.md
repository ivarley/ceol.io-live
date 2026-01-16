# 018: Remove order_number Preparation

**Date:** 2025-01-15
**Status:** Ready for deployment
**Related:** [015-fractional-indexing.md](015-fractional-indexing.md)

## Overview

This change prepares the codebase for removing the sequential `order_number` column from `session_instance_tune` in favor of the fractional `order_position` column. All code has been migrated, and this PR addresses remaining cleanup items identified during code review.

## Changes Made

### 1. Schema Fixes

#### Comment Correction (base-36 → base-62)
The schema comments incorrectly stated "base-36" but the implementation uses base-62 (0-9, A-Z, a-z).

**Files updated:**
- `schema/create_session_instance_tune_table.sql:8`
- `schema/full_schema.sql:449`

#### Added COLLATE "C" to Schema Files
The migration script adds `COLLATE "C"` but the base schema files were missing it. This ensures new database deployments have correct collation.

**Files updated:**
- `schema/create_session_instance_tune_table.sql` - main table
- `schema/full_schema.sql:449` - main table
- `schema/full_schema.sql:660` - history table
- `schema/create_history_tables.sql:101` - history table

### 2. Seed Data Update

Added an UPDATE statement at the end of `schema/seed_data.sql` that populates `order_position` from `order_number` after loading seed data. This ensures local development databases have consistent data.

**Location:** `schema/seed_data.sql:2190-2210`

### 3. NOT NULL Constraint Migration

Created new migration script to add NOT NULL constraint to `order_position` column after production verification.

**New file:** `schema/add_order_position_not_null.sql`

### 4. Deprecated SQL Stored Procedures

The SQL stored procedures `insert_session_instance_tune` don't generate `order_position` and have been replaced by the Python function at `api_routes.py:62`. Added deprecation notices and RAISE EXCEPTION to prevent accidental use.

**Files updated:**
- `schema/insert_session_instance_tune.sql`
- `schema/update_insert_session_instance_tune_with_history.sql`

### 5. New Tests

#### Unit Tests for Rebalance Scenarios
Added `TestRebalanceScenarios` class to `tests/unit/test_fractional_indexing.py` with tests for:
- Position length growth under repeated inserts (demonstrates need for rebalancing)
- Bulk insert optimization efficiency
- Rebalance reset behavior
- Normal append usage limits
- Interleaved insert/append operations

#### Integration Tests for Python Insert Function
Added `TestInsertSessionInstanceTuneFunction` class to `tests/integration/test_database.py` with tests for:
- Single insert generates correct order_position
- Multiple inserts generate sequential positions
- order_position and order_number orderings match

## Deployment Instructions

### Step 1: Deploy Code Changes
Merge this PR and deploy to production. The code changes are backward compatible.

### Step 2: Run Verification (Already Done)
Verification was already run using `schema/verify_fractional_indexing.sql`. Results showed:
- No NULL order_position values
- No ordering mismatches
- No duplicate positions

### Step 3: Add NOT NULL Constraint (Tomorrow)
After deployment, run the NOT NULL migration on production:

```sql
-- Connect to production database
\i schema/add_order_position_not_null.sql
```

Or run directly:
```sql
BEGIN;

-- Verify no NULLs exist
SELECT COUNT(*) FROM session_instance_tune WHERE order_position IS NULL;
-- Should return 0

-- Add constraint
ALTER TABLE session_instance_tune
ALTER COLUMN order_position SET NOT NULL;

COMMIT;
```

### Step 4: Future - Remove order_number
Once confident that order_position is working correctly in production:
1. Remove all `order_number` references from Python code
2. Remove `order_number` column from database
3. Update API endpoints to not accept/return order_number

## Files Changed

### Modified
1. `schema/create_session_instance_tune_table.sql` - Comment fix + COLLATE "C"
2. `schema/full_schema.sql` - Comment fix + COLLATE "C" (2 locations)
3. `schema/create_history_tables.sql` - COLLATE "C"
4. `schema/seed_data.sql` - order_position population
5. `schema/insert_session_instance_tune.sql` - Deprecated
6. `schema/update_insert_session_instance_tune_with_history.sql` - Deprecated
7. `tests/unit/test_fractional_indexing.py` - Rebalance tests
8. `tests/integration/test_database.py` - Insert function tests

### Created
1. `schema/add_order_position_not_null.sql` - NOT NULL migration
2. `specs/changes/018-remove-order-number-prep.md` - This file

## Testing

Run the new tests to verify everything works:

```bash
# Unit tests for fractional indexing (includes new rebalance tests)
make test-unit

# Or specifically:
pytest tests/unit/test_fractional_indexing.py -v

# Integration tests (includes new insert function tests)
make test-integration

# Or specifically:
pytest tests/integration/test_database.py::TestInsertSessionInstanceTuneFunction -v
pytest tests/integration/test_database.py::TestFractionalIndexingCollation -v
```

## Rollback

These changes are backward compatible. To rollback:
1. Revert the PR
2. The NOT NULL constraint can be removed with:
   ```sql
   ALTER TABLE session_instance_tune ALTER COLUMN order_position DROP NOT NULL;
   ```
