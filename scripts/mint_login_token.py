"""Mint a magic-link login token for a LOCAL account, as the login email would carry,
and print it. For the iOS sign-in UI tests (make ios-ui-test), which open
/auth/login/<token> in the app without sending any email.

    mint_login_token.py [email] [--create]

--create first makes the account (verified, no password, a complete profile) if it
doesn't exist: a throwaway for tests that delete their account.

Refuses to run against anything but a local database.
"""

import os
import sys
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

from auth import generate_login_token  # noqa: E402
from database import get_db_connection  # noqa: E402
from timezone_utils import now_utc  # noqa: E402


def main(email, create=False):
    if os.environ.get("PGHOST", "localhost") not in ("localhost", "127.0.0.1", "::1"):
        sys.exit("Refusing: PGHOST is not a local database.")
    token = generate_login_token()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if create:
            cur.execute("SELECT 1 FROM user_account WHERE LOWER(user_email) = LOWER(%s)", (email,))
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO person (first_name, last_name, city, created_date, last_modified_date) "
                    "VALUES ('Test', 'Throwaway', 'Galway', NOW(), NOW()) RETURNING person_id"
                )
                cur.execute(
                    "INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone, "
                    "email_verified, is_active, created_date, last_modified_date) "
                    "VALUES (%s, %s, %s, NULL, 'UTC', TRUE, TRUE, NOW(), NOW())",
                    (cur.fetchone()[0], email.split("@")[0], email),
                )
        cur.execute(
            "UPDATE user_account SET login_token = %s, login_token_expires = %s "
            "WHERE LOWER(user_email) = LOWER(%s) RETURNING user_id",
            (token, now_utc() + timedelta(minutes=15), email),
        )
        if cur.fetchone() is None:
            sys.exit(f"No account for {email}")
        conn.commit()
    finally:
        conn.close()
    print(token)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--create"]
    main(args[0] if args else "sarah.oconnor@example.com", create="--create" in sys.argv)
