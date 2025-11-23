# Tune Model

Tune metadata, session-specific aliases, ABC notation cache.

## Three-Layer Structure

1. **tune** - Canonical tune from thesession.org
2. **session_tune** - Session-specific aliases and settings
3. **session_instance_tune** - Actual plays in session logs

## Tables

### tune
Canonical tune database.
- tune_id, thesession_tune_id (unique)
- name, type (jig, reel, etc.)
- tunebook_count (popularity from thesession.org)

### session_tune
Session-specific tune information.
- session_tune_id, session_id, tune_id (nullable)
- tune_name, thesession_tune_id
- key (VARCHAR(20) - expanded to support "Amixolydian")
- alias (single alternative name)

### session_tune_alias
Multiple alternative names per tune at session.
- (session_id, session_tune_id, alias) composite PK

### tune_setting
ABC notation cache from thesession.org.
- setting_id, tune_id, key
- abc (text notation), image (PNG bytea)
- incipit_abc (first 2 bars), incipit_image (PNG bytea)
- cache_updated timestamp

### session_instance_tune
Logged tune plays (the actual session log).
- session_instance_tune_id, session_instance_id, tune_id (nullable), name
- order_number (typically increments of 1000)
- continues_set (boolean - true if continues previous tune in a set)
- played_timestamp, inserted_timestamp
- key_override (VARCHAR(20)), setting_override

**Constraint**: tune_id IS NOT NULL OR name IS NOT NULL

## Set Management

**Set** = consecutive tunes played without pause
- continues_set = TRUE means tune continues previous tune
- Sets are implicit (no set_id, derived from continues_set sequence)

## ABC Integration

- Full ABC in tune_setting.abc
- Incipit (first 2 bars) in tune_setting.incipit_abc
- Rendered by ABC renderer service → stored as PNG bytea
- See [ABC Renderer](../services/abc-renderer.md)

## Key Operations

**Search**: GET /api/tunes/search?q=<query> - searches local + thesession.org
**Link**: POST /api/sessions/<path>/<date_or_id>/match_tune - link to thesession.org
**Save Log**: POST /api/sessions/<path>/<date_or_id>/save_tunes - bulk save

**Scripts**:
- scripts/cache_missing_settings.py - Cache ABC notation
- scripts/refresh_tunebook_counts.py - Update popularity

## Related

- [Session Model](session-model.md) - session_instance_tune details
- [External APIs](../logic/external-apis.md) - thesession.org integration
- [ABC Renderer](../services/abc-renderer.md) - ABC to PNG conversion
