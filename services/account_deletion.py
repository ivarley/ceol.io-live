"""Delete a user's account and their private data (spec 054).

What goes, and what stays, is a product decision recorded in the spec:

- **Gone:** the login itself (user_account, its sessions/tokens, login history,
  update-email delivery rows) and everything private to the person: their tune list
  and per-instrument statuses, their instruments, and the contact details and
  thesession.org link on the person row. The history-table copies of all of that
  go too — otherwise the audit trail would keep what the user asked us to delete.
- **Stays:** the person's NAME, as a no-login person on the rosters and attendance
  lists that session admins keep — exactly like the people admins add by hand. The
  shared session record (which tunes were played, recordings) stays, as it is the
  community's, not the user's. Its created_by/last_modified user ids are bare numbers
  with no foreign key and simply stop resolving to anyone.

Immediate: one transaction, no grace period. Deliberately NOT written through
save_to_history, which would copy the private rows straight back into *_history.
"""

import logging

logger = logging.getLogger(__name__)


class AccountDeletionRefused(Exception):
    """The account exists but this flow must not delete it. `code` is machine-readable."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# Contact details and outside identities on the person row (and its history copies).
# The name is not here: it is what keeps the roster entry meaningful.
PRIVATE_PERSON_COLUMNS = ("email", "sms_number", "city", "state", "country", "thesession_user_id")


def delete_account(cur, user_id):
    """Delete the account `user_id` and its private data on `cur`. The caller commits.

    Returns {"person_id": ...}. Raises LookupError if there is no such account and
    AccountDeletionRefused for a system admin (whose account also owns audit rows —
    sent update emails, merge scans — and whose removal is a decision for another
    admin, not a button)."""
    cur.execute(
        "SELECT person_id, is_system_admin FROM user_account WHERE user_id = %s FOR UPDATE",
        (user_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise LookupError("No such account")
    person_id, is_system_admin = row
    if is_system_admin:
        raise AccountDeletionRefused(
            "admin_account",
            "A system admin account can't be deleted from here. Ask another admin to "
            "remove your admin rights first.",
        )
    # A former admin may still be the sender of record on update emails; that column is
    # NOT NULL, so the account cannot go without deciding who sent them. Refuse cleanly.
    cur.execute("SELECT 1 FROM email_message WHERE sent_by_user_id = %s LIMIT 1", (user_id,))
    if cur.fetchone():
        raise AccountDeletionRefused(
            "sent_update_emails",
            "This account sent update emails, so it can't be deleted from here. Ask an admin.",
        )

    # --- private to the person: tune list, per-instrument status, instruments ---
    # (person_tune_instrument also cascades from person_tune; deleted explicitly so
    # the order does not depend on that constraint.)
    for table in ("person_tune_instrument", "person_tune", "person_instrument"):
        cur.execute(f"DELETE FROM {table} WHERE person_id = %s", (person_id,))
        cur.execute(f"DELETE FROM {table}_history WHERE person_id = %s", (person_id,))

    # --- the person row keeps its name; everything else personal is cleared ---
    cleared = ", ".join(f"{c} = NULL" for c in PRIVATE_PERSON_COLUMNS)
    cur.execute(
        f"UPDATE person SET {cleared}, at_active_session_instance_id = NULL, "
        "last_modified_date = NOW() WHERE person_id = %s",
        (person_id,),
    )
    cur.execute(f"UPDATE person_history SET {cleared} WHERE person_id = %s", (person_id,))

    # --- the login ---
    # Rows that reference the account by FK without a cascade, then the account and
    # its own history (usernames, emails, password hashes). user_session cascades.
    cur.execute("DELETE FROM email_message_recipient WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM login_history WHERE user_id = %s", (user_id,))
    cur.execute("UPDATE tune_merge_scan SET started_by_user_id = NULL WHERE started_by_user_id = %s", (user_id,))
    cur.execute("DELETE FROM user_account_history WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM user_account WHERE user_id = %s", (user_id,))

    # No names, no email: the ids are enough to answer "what happened to account 42".
    logger.info("account deleted: user_id=%s person_id=%s", user_id, person_id)
    return {"person_id": person_id}
