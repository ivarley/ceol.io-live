# External APIs

Integration with third-party services.

## thesession.org API

### Purpose

- Canonical tune metadata database for Irish traditional music
- 40,000+ tunes with names, types, keys, ABC notation
- Community recordings, discussions, tunebook tracking

### Endpoints Used

**Base URL**: `https://thesession.org/tunes/`

**Search**: `/search?q=<query>&format=json`
- Returns array of tune matches
- Used in tune linking search

**Tune Detail**: `/<tune_id>?format=json`
- Returns full tune metadata
- Includes settings (versions), aliases, recordings

**Popularity**: `/popular?format=json`
- Tunebook counts (how many users have bookmarked)
- Used for ranking tune popularity

### Integration Points

**Files**: Multiple references across templates and API routes (15+ files)

**Key Functions**:
- `api_routes.py:search_tunes()` - Search wrapper
- `api_routes.py:get_tune_details()` - Metadata fetch
- `scripts/refresh_tunebook_counts.py` - Popularity sync

### Data Flow

1. User searches tune name
2. Search local `tune` table + thesession.org API
3. User selects match
4. Fetch full metadata from thesession.org
5. Store in local `tune` table
6. Link `session_instance_tune.session_tune_id` → `session_tune.thesession_tune_id`

### Rate Limiting

- No explicit rate limit documented
- Respectful usage: cache results, don't spam
- Failed requests: graceful degradation (use local data only)

### Response Format

```json
{
  "id": 1234,
  "name": "The Butterfly",
  "type": "slip jig",
  "settings": [
    {
      "id": 1,
      "key": "Em",
      "abc": "X:1\nT:The Butterfly\nM:9/8\nL:1/8\n...",
      "date": "2005-01-01"
    }
  ],
  "tunebooks": 856,
  "aliases": []
}
```

## SendGrid Email Service

### Purpose

- Transactional email delivery
- Password resets
- Account email verification
- System notifications

### Configuration

**Environment Variable**: `SENDGRID_API_KEY`

**Default Sender**: `ceol@ceol.io`

**Library**: `sendgrid` Python package

### Integration

**File**: `email_utils.py`

**Functions**:
- `send_reset_email(user_email, reset_token)` - Password reset
- `send_verification_email(user_email, verification_token)` - Account verification

### Email Templates

**Password Reset**:
```
Subject: Password Reset Request - ceol.io
Body: Custom HTML template with reset link
Link: https://ceol.io/auth/reset_password?token=<token>
```

**Verification**:
```
Subject: Verify Your Email - ceol.io
Body: Custom HTML with verification link
Link: https://ceol.io/auth/verify_email?token=<token>
```

### Error Handling

- Failed sends: Log error, show user generic message
- No retry logic (user can request new email)
- Invalid API key: Fails gracefully, logs error

### Testing

**Unit Tests**: Mock SendGrid client
**Manual**: Use test mode in development (env var)

## Related Specs

- [Tune Model](../data/tune-model.md) - Local tune storage
- [Tune Services](tune-logic.md) - Search and sync logic
- [Authentication](auth.md) - Email verification flow
- [ABC Renderer](../services/abc-renderer.md) - Internal microservice (not external API)
