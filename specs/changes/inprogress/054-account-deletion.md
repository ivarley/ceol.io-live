# 054: Account deletion

**Date:** 2026-09-26
**Status:** BUILT 2026-09-26 — `POST /api/me/delete-account`, the Delete Account row on `/me`.

## Why

App Store review requires in-app account deletion from any app that lets people sign up
(Guideline 5.1.1(v)). Ceol had none, on the web or anywhere else. It is a prerequisite for
the native app (spec 052), built on the web first like the rest of that work, so the
endpoint the app calls is one the web already uses.

## The decision: what goes, what stays

Made by the product owner, 2026-09-26. **Immediate** (no grace period), and:

| Goes | Stays |
|---|---|
| The login: `user_account`, every `user_session` (all tokens, all devices), `login_history`, `email_message_recipient` rows | The person's **name**, on the rosters (`session_person`) and attendance lists (`session_instance_person`) session admins keep — as a no-login person, like the ones admins add by hand |
| Private data: `person_tune`, `person_tune_instrument`, `person_instrument` | The shared session record: logged tunes (`session_instance_tune`), corroborations, recordings, logger colours |
| Contact details on the person: `email`, `sms_number`, `city`, `state`, `country`, `thesession_user_id` | Audit columns elsewhere (`created_by_user_id` etc.): bare numbers with no foreign key, which simply stop resolving |
| The history-table copies of all of the above (`user_account_history`, `person_tune*_history`, `person_instrument_history`; contact columns in `person_history` are nulled) | |

The history copies are the easy thing to miss: without them the audit trail would keep
exactly what the user asked to delete. The deletion is therefore NOT written through
`save_to_history`, which would copy the private rows straight back.

Consequences worth knowing:
- The "tunes this person logged" views (`/api/person/<id>/logged-tunes`, admin people
  list) join through `user_account`, so they show nothing for the person afterwards. The
  logs themselves are untouched.
- A session whose only admin deleted their account keeps a no-login admin on its roster;
  a system admin reassigns.
- The email address is free again: signing up with it starts a new account and a new person.

## Refusals

- **System admins** (403 `admin_account`). Removing an admin is another admin's decision,
  and their account owns audit rows. The web hides the row for them.
- **A former admin who sent update emails** (403 `sent_update_emails`):
  `email_message.sent_by_user_id` is NOT NULL.

## Contract

`POST /api/me/delete-account {confirm_email}` — `operationId: deleteAccount` in
`specs/api/native-surface.yaml`. The body repeats the account email (case-insensitive,
trimmed); a mismatch is 400 `confirmation_mismatch` and changes nothing. On success every
token of the account is dead, the calling browser is signed out, and the web's next page
shows "Your account has been deleted."

## Where

- `services/account_deletion.py` — `delete_account(cur, user_id)`, one transaction.
- `api_app_routes.delete_account_api` — confirmation, refusals, sign-out.
- `frontend/src/personpage/AccountSection.svelte` — Delete Account, last and on its own;
  the Dialog's confirm stays disabled (new `confirmDisabled` kit prop) until the email is typed.
- Tests: `tests/integration/test_account_deletion_054.py`, `frontend/tests/accountdelete.test.js`.

## Not done

- No confirmation email afterwards (the address is gone by the time one could be sent).
- No admin-side "delete this person's account" button; a system admin can still remove
  their own admin flag and use this flow, or do it in SQL.
