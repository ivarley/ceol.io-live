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

- Transactional email delivery: password resets, email verification, magic
  login links
- App update emails (spec 027): admin-composed Markdown newsletters to
  opted-in users

### Configuration

**Environment Variables**:
- `SENDGRID_API_KEY` - API key (required; sends fail gracefully without it)
- `MAIL_DEFAULT_SENDER` - transactional from-address, default `noreply@ceol.io`
- `MAIL_UPDATES_SENDER` - update-email from-address, default `ceol@ceol.io`
  (verified sender in SendGrid)
- `MAIL_UNSUBSCRIBE` - mailto used in the default `List-Unsubscribe` header,
  default `unsubscribe@ceol.io`

**Library**: `sendgrid` Python package (plus `markdown` for update-email bodies)

### Integration

**File**: `email_utils.py`

**Functions**:
- `send_email_via_sendgrid(to_email, subject, body_text, body_html=None, from_email=None, unsubscribe_url=None)` -
  core sender. `from_email` overrides the default sender per message;
  `unsubscribe_url` replaces the mailto `List-Unsubscribe` header with a
  one-click URL (RFC 8058, `List-Unsubscribe-Post: List-Unsubscribe=One-Click`).
- `send_password_reset_email(user, token)` - password reset (1h expiry)
- `send_verification_email(user, token)` - account verification (24h expiry)
- `send_login_link_email(user, token)` - magic link login (15m expiry)
- `send_update_email(user_id, to_email, subject, body_markdown)` - one app
  update email: HTML part is rendered Markdown, plain-text part is the raw
  Markdown, footer carries a personalized unsubscribe link. Sent individually
  per recipient (never BCC) from `MAIL_UPDATES_SENDER`.
- `generate_unsubscribe_token(user_id)` / `verify_unsubscribe_token(token)` -
  stateless signed unsubscribe tokens (`itsdangerous.URLSafeSerializer`, salt
  `email-unsub`, never expire; the token only grants flag-off).

### Update Email Flow (spec 027)

1. Users are subscribed by default (`user_account.receive_update_emails`,
   default TRUE) and can opt out on `/me` or via any email's unsubscribe link.
2. Admin composes subject + Markdown at `/admin/email-updates`; "Send test to
   me" (`POST /api/admin/email-updates/test`) emails only the admin and records
   nothing.
3. `POST /api/admin/email-updates/send` loops opted-in active users
   synchronously, recording an `email_message` row plus one
   `email_message_recipient` row per user ('sent'/'failed'); one failure never
   aborts the rest.
4. Every update email's unsubscribe link (`/unsubscribe/<token>`, no login)
   flips the flag off; GET shows a confirmation page, POST is the RFC 8058
   one-click target.

### Error Handling

- Failed sends: Log error, show user generic message
- No retry logic (transactional: user can request a new email; updates: the
  per-recipient 'failed' row records who was missed)
- Invalid API key: Fails gracefully, logs error

### Testing

**Unit Tests**: Mock SendGrid client (`tests/unit/test_email_utils.py`);
update-email flow covered in `tests/integration/test_update_emails.py`

## Related Specs

- [Tune Model](../data/tune-model.md) - Local tune storage
- [Tune Services](tune-logic.md) - Search and sync logic
- [Authentication](auth.md) - Email verification flow
- [ABC Renderer](../services/abc-renderer.md) - Internal microservice (not external API)
