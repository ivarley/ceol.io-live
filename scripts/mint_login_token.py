"""Mint a magic-link login token for a LOCAL account, as the login email would carry,
and print it. For the iOS sign-in UI tests (make ios-ui-test), which open
/auth/login/<token> in the app without sending any email.

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


def main(email):
    if os.environ.get("PGHOST", "localhost") not in ("localhost", "127.0.0.1", "::1"):
        sys.exit("Refusing: PGHOST is not a local database.")
    token = generate_login_token()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
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
    main(sys.argv[1] if len(sys.argv) > 1 else "sarah.oconnor@example.com")
