# 015 Fractional Indexing

Replace integer-based `order_number` in `session_instance_tune` with string-based `order_position` to enable CRDT-compatible ordering for future collaborative editing.

## Problem

The current system uses integer `order_number` for tune ordering:

```sql
order_number INTEGER NOT NULL  -- values: 1, 2, 3, 4, ...
```

**Issues:**
1. **Insertion requires renumbering** - To insert between positions 2 and 3, you must update all tunes from position 3 onward
2. **Reordering is expensive** - Moving a tune or set requires swapping/updating multiple rows
3. **CRDT-incompatible** - Two offline clients assigning `order_number = 5` creates a conflict
4. **Stored procedure complexity** - `insert_session_instance_tune.sql` calculates `MAX(order_number) + 1`

## Solution: Fractional Indexing

Use lexicographically-ordered strings that allow insertion anywhere without renumbering:

```sql
order_position VARCHAR(32) NOT NULL  -- values: "A", "B", "C", "AI", "N", ...
```

**Benefits:**
1. **Insert without renumbering** - To insert between "A" and "B", generate "AI" (midpoint)
2. **O(1) insertions** - Only the new row gets written
3. **CRDT-ready** - Each client can independently generate unique positions
4. **Simpler move operations** - Moving a tune only updates that one row

## Technical Design

### Alphabet

Base-62: `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`

- Full alphanumeric range for maximum position density
- Requires `COLLATE "C"` on the database column to ensure byte-order sorting
- With COLLATE "C", ordering is: 0-9 < A-Z < a-z (ASCII byte order)
- 62 chars per level means shorter strings and more room for insertions
- Printable, URL-safe, easy to debug

### Position Generation

**Appending (most common - ~95% of inserts):**
```python
def generate_append_position(last_position: str | None) -> str:
    if last_position is None:
        return "V"  # Start in middle, leaves room for insertions before
    # Increment last character, extend with midpoint if needed
    # "V" -> "W", "z" -> "zV", "zz" -> "zzV", etc.
```

**Inserting between two positions:**
```python
def generate_position_between(before: str | None, after: str | None) -> str:
    # Find exact midpoint in the position space
    # ("V", "X") -> "W"
    # ("V", "W") -> "VV"  (no room, so extend with midpoint char)
```

**Sequential bulk insert optimization:**
When inserting multiple consecutive new tunes in one save, positions are generated sequentially rather than bisecting each time:
- First new tune: bisects (V, z) → k
- Second new tune: appends → l
- Third: m, n, o, ...

This prevents position explosion when pasting many tunes.

### Overflow Handling

If a generated position exceeds 32 characters (extremely rare edge case - requires ~30+ individual insert-in-same-spot operations), all positions for that session instance are rebalanced from scratch. A toast notification warns that other editors may lose pending changes.

### Database Migration

1. Add new column alongside existing (with COLLATE "C" for consistent byte-order sorting):
   ```sql
   ALTER TABLE session_instance_tune
   ADD COLUMN order_position VARCHAR(32) COLLATE "C";

   ALTER TABLE session_instance_tune_history
   ADD COLUMN order_position VARCHAR(32) COLLATE "C";
   ```

2. Populate from existing data:
   ```sql
   UPDATE session_instance_tune
   SET order_position = generate_fractional_position(order_number);
   ```

3. Create index:
   ```sql
   CREATE INDEX idx_sit_order_position
   ON session_instance_tune(session_instance_id, order_position);
   ```

4. After verification, make NOT NULL:
   ```sql
   ALTER TABLE session_instance_tune
   ALTER COLUMN order_position SET NOT NULL;
   ```

### API Changes

All queries change from:
```sql
ORDER BY order_number
```
to:
```sql
ORDER BY order_position
```

All inserts/updates use Python-generated positions instead of stored procedure.

## Files to Modify

### New Files
- `fractional_indexing.py` - Position generation functions
- `schema/migrate_to_fractional_indexing.sql` - Migration script

### Modified Files
- `api_routes.py` - ~17 functions (insert, move, reorder, delete operations)
- `web_routes.py` - Read queries for session detail
- `database.py` - History tracking includes new field
- `static/js/session-*.js` - Frontend position handling

### Removed/Deprecated
- `schema/insert_session_instance_tune.sql` - Stored procedure replaced by Python

## Key Functions to Update

### Read Operations
- `get_session_instance_tunes()` - ORDER BY order_position
- `get_tunes_api()` - Include order_position in response

### Write Operations
- `add_tune_ajax()` - Generate append position
- `link_tune_ajax()` - Generate append position
- `delete_tune_by_order_ajax()` - Find by position, no renumbering needed
- `move_tune_ajax()` - Generate new position, update single row
- `move_set_ajax()` - Generate new positions for set, update only moving tunes
- `save_session_instance_tunes_ajax()` - Preserve existing positions where possible
- `save_session_beta_ajax()` - Full rewrite with position handling

## Migration Strategy

1. **Add column** - Deploy migration, column nullable
2. **Dual-write** - Write both order_number and order_position
3. **Verify** - Runtime checks compare orderings match
4. **Switch reads** - ORDER BY order_position
5. **Remove old** - Stop writing order_number (keep column for rollback)
6. **Cleanup** - Eventually drop order_number column

## Testing Checklist

- [ ] Append tune to empty session
- [ ] Append tune to session with tunes
- [ ] Insert tune between existing tunes
- [ ] Move single tune up/down
- [ ] Move set up/down
- [ ] Delete tune (no position gaps created)
- [ ] Bulk import maintains order
- [ ] History records include order_position
- [ ] Frontend displays in correct order
