# Tune Search and Linking Logic

Finding tunes by name and linking to thesession.org canonical database.

## Tune Matching Algorithm

**Function**: `find_matching_tune(cur, session_id, tune_name, allow_multiple_session_aliases)` | `database.py:355-435`

**Returns**: `(tune_id, final_name, error_message)`

**Search Order** (cascading, case/accent insensitive):
1. `session_tune.alias` - Session-specific primary alias
2. `session_tune_alias.alias` - Additional session aliases
3. `tune.name` - Canonical names with "The" flexibility

**"The" Flexibility**: Matches "Silver Spear" with/without "The" prefix
```sql
WHERE LOWER(unaccent(name)) = LOWER(unaccent(%s))
   OR LOWER(unaccent(name)) = LOWER(unaccent('The ' || %s))
   OR LOWER(unaccent('The ' || name)) = LOWER(unaccent(%s))
```

**String Normalization**: `normalize_apostrophes()` | `database.py:5-10` - Smart quotes → ASCII

**Accent Insensitivity**: `unaccent` extension | `schema/add_unaccent_extension.sql`

**Error on Duplicates**: Multiple matches raise error unless `allow_multiple_session_aliases=True`

## Tune Linking

**API**: `POST /api/sessions/<path>/<date_or_id>/match_tune` | `api_routes.py:5666`

**Payload**: `{"session_instance_tune_id": 123, "thesession_tune_id": 456, "setting_id": 789}`

**Process**:
1. Validate session_instance_tune exists
2. Fetch from thesession.org (if not cached)
3. Create/update `tune` record (canonical metadata)
4. Create/update `tune_setting` record(s) (ABC + images)
5. Create/update `session_tune` record (session preferences)
6. Update `session_instance_tune.tune_id` (link log entry)

**Storage**:
- `tune` - Name, type, tunebook_count_cached
- `tune_setting` - ABC notation, images (PNG), key
- `session_tune` - Session-specific alias, key, setting_id

## ABC Caching

**Incipit**: `extract_abc_incipit(abc, tune_type)` | `database.py:131-202` - First 2 bars (3 if pickup)

**Images**: Via ABC renderer service (see [ABC Renderer](../services/abc-renderer.md))

**Script**: `scripts/cache_missing_settings.py`

**Storage**: `tune_setting` - abc, incipit_abc, image, incipit_image

## Tune Search

**API**: `GET /api/tunes/search?q=<query>` | `api_person_tune_routes.py:902`

**Strategy**:
1. Search local `tune` table
2. If insufficient results, query thesession.org API
3. Merge, deduplicate, sort by relevance + popularity
4. Cache new results locally

**Session-Specific Search** (prioritizes session aliases):
1. `session_tune` & `session_tune_alias` - Highest priority
2. Global `tune` table - Medium priority
3. thesession.org API - Lowest priority

**Ranking**: Session exact > Session partial > Canonical exact > Canonical partial > External

## Popularity Tracking

**Field**: `tune.tunebook_count_cached` - Bookmark count from thesession.org

**Refresh**: `scripts/refresh_tunebook_counts.py` - Weekly/monthly cron

**Usage**: Sort search results, identify common tunes

## Alias Management

**Primary Alias**: `session_tune.alias` - Single per (session, tune)

**Additional Aliases**: `session_tune_alias` table - Unlimited

**Create API**: `POST /api/session/<id>/tune/<tune_id>/alias` with `{"alias": "..."}`

**Search**: Both types searched with equal priority

## Error Handling

**Multiple Matches**: Error unless disambiguated with alias
**No Matches**: Options - create unlinked, refine search, search thesession.org
**API Failures**: Fall back to local cache, show warning

## Performance

**Indexes**:
- `idx_tune_name` - Name searches
- `idx_tune_tunebook_count` DESC - Popularity sorting
- Session alias indexes - Session-specific lookups

**Scripts**: `schema/optimize_session_tune_performance.sql`, `schema/popular_tunes_indices.sql`

**Caching**: Most searches satisfied by local cache without external API call
