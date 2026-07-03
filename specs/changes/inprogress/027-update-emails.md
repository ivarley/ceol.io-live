# 027: App Update Emails (Opt-in + Admin Send Screen)

## Purpose

Let users opt in to occasional news about the app, and give the admin a way to send it:

1. **Profile checkbox** — "Get regular updates about this app via email" on the user's own
   profile page (`/me`). On by default (existing users backfilled to on at launch);
   users opt out via the checkbox or the unsubscribe link.
2. **Admin send screen** — a system-admin-only page to compose an update email (Markdown),
   test-send it to yourself, then send it to every opted-in user, from **ceol@ceol.io**
   (already a verified SendGrid sender) via the existing SendGrid integration.

Each send is recorded as an **email message** (terminology: "message", not "blast") with
per-recipient success/failure, and every outgoing email carries a personalized **one-click
unsubscribe** link that flips the opt-in off without requiring login (CAN-SPAM / RFC 8058).

## Current state (verified)

- **SendGrid** lives entirely in `email_utils.py`. Core sender
  `send_email_via_sendgrid(to_email, subject, body_text, body_html=None)` (`email_utils.py:11`)
  takes both plain-text and HTML parts; the from-address is hardcoded to
  `MAIL_DEFAULT_SENDER` (default `noreply@ceol.io`, `email_utils.py:19`) with **no per-call
  override**. It already sets `List-Unsubscribe` headers, but only as
  `mailto:unsubscribe@ceol.io` (`email_utils.py:36-37`). Env vars: `SENDGRID_API_KEY`,
  `MAIL_DEFAULT_SENDER`, `MAIL_UNSUBSCRIBE`.
- Existing emails (password reset / verification / login link, `email_utils.py:67,99,135`) are
  composed as inline f-string HTML — there are no email template files and no Markdown
  dependency in `requirements.txt`.
- **Profile page**: `/me` → `person_details` (`web_routes.py:2805`, route registered at
  `app.py:253`), rendering `templates/person_details.html`. The self-edit form is gated by
  `{% if is_user_profile %}` (~line 260); precedent controls include the timezone `<select>`
  (~282-285) and Bootstrap `.form-check` checkboxes (~293-295). Saves go through
  `PUT /api/person/<int:person_id>/update` → `update_person_details` (`api_routes.py:5497`),
  which takes `{person: {...}, user: {...}}` and writes `user_account` prefs with
  `save_to_history`.
- **Preference storage precedent**: booleans like `auto_save_tunes` and `beta_live_logging`
  live on `user_account` (`schema/full_schema.sql:259-283`), not `person`.
- **Admin pattern**: no decorator — each page handler does an inline
  `if not current_user.is_system_admin: flash(...); redirect(home)` check (e.g.
  `web_routes.py:2333` `admin()`); admin API endpoints return 403 JSON instead
  (e.g. `admin_set_beta_logging`, `api_routes.py:146`). Admin pages are registered in
  `app.py:270-281` and share tab nav via `templates/admin_tabs.html`.
- **Schema convention**: hand-written idempotent SQL in `schema/NNN_description.sql`
  (e.g. `schema/024_beta_rollout.sql`); `user_account` has a history table
  (`full_schema.sql:1077`) that must get the same new column (paired-ALTER pattern per
  `schema/add_referral_tracking.sql`); `full_schema.sql` and
  `specs/current/data/people-model.md` are kept in sync.

---

## A. Schema (`schema/027_update_emails.sql`)

Additive + idempotent, per convention:

```sql
-- Subscription flag (paired with history table); default TRUE + one-time
-- backfill of existing users (decided during build — originally opt-in/FALSE)
ALTER TABLE user_account
    ADD COLUMN IF NOT EXISTS receive_update_emails BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE user_account_history
    ADD COLUMN IF NOT EXISTS receive_update_emails BOOLEAN;
UPDATE user_account SET receive_update_emails = TRUE WHERE receive_update_emails = FALSE;

-- One row per admin send
CREATE TABLE IF NOT EXISTS email_message (
    email_message_id   SERIAL PRIMARY KEY,
    subject            TEXT NOT NULL,
    body_markdown      TEXT NOT NULL,
    sent_by_user_id    INTEGER NOT NULL REFERENCES user_account(user_id),
    sent_date          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recipient_count    INTEGER NOT NULL DEFAULT 0,
    success_count      INTEGER NOT NULL DEFAULT 0,
    failure_count      INTEGER NOT NULL DEFAULT 0
);

-- One row per recipient per message
CREATE TABLE IF NOT EXISTS email_message_recipient (
    email_message_id   INTEGER NOT NULL REFERENCES email_message(email_message_id),
    user_id            INTEGER NOT NULL REFERENCES user_account(user_id),
    email              TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('sent', 'failed')),
    error_message      TEXT,
    PRIMARY KEY (email_message_id, user_id)
);
```

Also update `schema/full_schema.sql` and `specs/current/data/people-model.md`.

**No unsubscribe-token column.** Unsubscribe links use stateless signed tokens:
`itsdangerous.URLSafeSerializer(SECRET_KEY, salt="email-unsub")` over the `user_id`.
`itsdangerous` ships with Flask (no new dependency), tokens never expire, and unsubscribing is
idempotent, so nothing needs to be stored or cleaned up. (The stored-token pattern used by
`verification_token` etc. exists for *expiring* tokens; not needed here.)

Test messages ("send to me") are **not** recorded in `email_message` — only real sends.

## B. Profile checkbox

- `templates/person_details.html`: inside the `{% if is_user_profile %}` edit form (~line 260),
  add a `.form-check` checkbox (same markup as the `is_active` checkbox at ~293-295):
  label **"Get regular updates about this app via email"**, bound to
  `user.receive_update_emails`. Display-mode (non-edit) view shows the current state alongside
  the other account fields.
- `web_routes.py:2805 person_details`: add `receive_update_emails` to the `user_account`
  SELECT + template context.
- `api_routes.py:5497 update_person_details`: accept `receive_update_emails` (coerced to bool)
  in the `user` block of the PUT payload; include it in the `user_account` UPDATE +
  `save_to_history` call. (Build note: the endpoint actually shipped with **no** auth —
  fixed as part of this change: `@api_login_required` + owner-or-admin check, and the
  `user.user_id` in the payload must be the account attached to the person being updated.)

## C. Email plumbing (`email_utils.py` + `requirements.txt`)

1. **Per-call from-address**: add optional params to `send_email_via_sendgrid`:

   ```python
   def send_email_via_sendgrid(to_email, subject, body_text, body_html=None,
                               from_email=None, unsubscribe_url=None):
   ```

   - `from_email=None` → current behavior (`MAIL_DEFAULT_SENDER`); all existing callers
     unchanged.
   - `unsubscribe_url=None` → current mailto `List-Unsubscribe` headers (lines 36-37).
     When provided, instead set `List-Unsubscribe: <{unsubscribe_url}>` and keep
     `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058 — Gmail/Yahoo render the
     native "Unsubscribe" button and POST to the URL).

2. **New sender** `send_update_email(user_id, to_email, subject, body_markdown)`:
   - From address: `MAIL_UPDATES_SENDER` env var, default `"ceol@ceol.io"` (already verified
     in SendGrid).
   - Renders `body_markdown` → HTML via the **`markdown`** package (**new entry in
     `requirements.txt`**), wrapped in a minimal HTML shell consistent with the existing
     inline-styled emails.
   - Plain-text part = the raw Markdown source (readable as-is).
   - Footer (both parts): "You're receiving this because you opted in to updates on
     ceol.io. [Unsubscribe]" — link is `url_for("unsubscribe_updates", token=..., _external=True)`
     with the signed token for this `user_id`. Same URL passed as `unsubscribe_url` for the
     header.
   - Sends are **individual per recipient** (personalized token), never BCC.
   - Token helpers `generate_unsubscribe_token(user_id)` / `verify_unsubscribe_token(token)`
     live in `email_utils.py`.

## D. Unsubscribe route (no login)

New handler `unsubscribe_updates(token)` in `web_routes.py`, registered in `app.py` as
`/unsubscribe/<token>` with `methods=["GET", "POST"]`. **No** `@login_required`.

- Verify the signed token → `user_id`; invalid token → 404-style "link not valid" page.
- Valid token (GET or POST): `UPDATE user_account SET receive_update_emails = FALSE` (with
  `save_to_history`), idempotent.
- **GET** renders a small confirmation template (`templates/unsubscribe.html`, extends
  `base.html`): "You've been unsubscribed from app updates" + note that they can re-enable it
  any time on their profile (`/me`).
- **POST** is the RFC 8058 one-click target (mail clients POST with
  `List-Unsubscribe=One-Click` body): return plain 200, no body needed.

## E. Admin screen (`/admin/email-updates`)

- New handler `admin_email_updates()` in `web_routes.py` with the standard inline
  `is_system_admin` guard (pattern at `web_routes.py:2333`); route registered in `app.py`
  next to the other `/admin/...` rules (~270-281); new tab added to
  `templates/admin_tabs.html` (`active_tab` list + nav block).
- New template `templates/admin_email_updates.html`:
  - **Recipient count**: "N users are opted in" (server-rendered).
  - **Compose form**: subject input + Markdown textarea (with a hint that Markdown is
    supported).
  - **"Send test to me"** button — sends the composed message to the logged-in admin's own
    email only; does not record an `email_message` row.
  - **"Send to N recipients"** button — JS `confirm()` before POSTing.
  - **History table**: past messages (date, subject, sender username, sent/failed counts),
    newest first; failed recipients' errors visible via an expandable detail or title text.
- Standard AJAX pattern (`specs/current/ui/ajax.md`) for both buttons, with disabled state
  while sending.

## F. Admin API (`api_routes.py`)

Both endpoints use the admin API guard (403 JSON, per `admin_set_beta_logging`,
`api_routes.py:146`), registered in `app.py`:

- `POST /api/admin/email-updates/test` — `{subject, body_markdown}` → `send_update_email` to
  `current_user`'s email only. Returns `{success, message}`.
- `POST /api/admin/email-updates/send` — `{subject, body_markdown}`:
  1. Validate subject/body non-empty.
  2. Recipient query:
     ```sql
     SELECT user_id, user_email FROM user_account
     WHERE receive_update_emails = TRUE AND is_active = TRUE AND user_email IS NOT NULL
     ```
  3. INSERT the `email_message` row, then loop recipients **synchronously**, calling
     `send_update_email` per user and inserting an `email_message_recipient` row with
     `sent`/`failed` per result; update the counts on `email_message` at the end; commit.
  4. Returns `{success, recipient_count, success_count, failure_count}`.

Synchronous sending is acceptable at current scale (SendGrid calls ~100-300ms each; ~1 minute
per ~200 recipients against Gunicorn's default 30s timeout — see Risks). A failed individual
send is recorded and skipped, never aborts the message.

## Risks

- **Synchronous send timeout**: past a few hundred recipients the send request may exceed the
  worker timeout. Mitigation deferred (background job / batching) — well below that scale
  today. The per-recipient rows make a partial send visible and diagnosable.
- **No retry/resend UI**: a failed recipient is recorded but there is no "resend to failures"
  button in v1; re-sending would email everyone again.
- **Signed tokens never expire**: an old unsubscribe link always works. That's the desired
  behavior for unsubscribe (idempotent, flag-off only); the token grants no other capability.
- **Stale spec**: `specs/current/logic/external-apis.md` lists `ceol@ceol.io` as the default
  sender (the code default is actually `noreply@ceol.io`, `email_utils.py:19`) and names
  functions that no longer exist — update it as part of this change.

## Rollout

1. No sender setup needed — **ceol@ceol.io** is already verified in SendGrid; optionally set
   `MAIL_UPDATES_SENDER=ceol@ceol.io` explicitly in Render env (it's also the code default).
2. Add `markdown` to `requirements.txt`; `make install`.
3. Run `schema/027_update_emails.sql` on local test DB, then production.
4. Deploy code. Flag defaults TRUE and existing users are backfilled to TRUE by the
   schema script — everyone is subscribed until they opt out.
5. Compose a message, "Send test to me", verify rendering + unsubscribe link, then do
   a real send.

## Test plan

- **Profile round-trip**: check the box on `/me`, save, reload → still checked;
  `user_account.receive_update_emails` is TRUE and a history row was written. Uncheck → FALSE.
- **Recipient query**: seeded users — opted-in+active included; opted-out, inactive, or
  NULL-email excluded.
- **Test send**: goes only to the admin, from ceol@ceol.io, Markdown rendered in the HTML part,
  raw Markdown in the text part, footer link present; no `email_message` row created.
- **Real send**: `email_message` + one `email_message_recipient` row per recipient with
  correct status; counts match; a SendGrid failure for one recipient records `failed` and
  doesn't stop the rest.
- **Unsubscribe**: GET the footer link logged-out → confirmation page, flag now FALSE; repeat
  GET → still fine (idempotent); POST → 200 and flag FALSE; tampered token → error page, no
  change.
- **Permissions**: non-admin hitting `/admin/email-updates` is redirected with a flash;
  non-admin POST to the API endpoints gets 403 JSON.

## Files

- `schema/027_update_emails.sql` — new (opt-in column ×2, `email_message`,
  `email_message_recipient`)
- `schema/full_schema.sql` — sync new columns/tables
- `email_utils.py` — `from_email`/`unsubscribe_url` params; `send_update_email`; token helpers
- `requirements.txt` — add `markdown`
- `templates/person_details.html` — opt-in checkbox
- `web_routes.py` — `person_details` context; `unsubscribe_updates`; `admin_email_updates`
- `api_routes.py` — `update_person_details` user block; test + send endpoints
- `app.py` — routes: `/unsubscribe/<token>`, `/admin/email-updates`, 2 API rules
- `templates/admin_email_updates.html`, `templates/unsubscribe.html` — new
- `templates/admin_tabs.html` — new tab
- `specs/current/data/people-model.md`, `specs/current/logic/external-apis.md` — doc updates
