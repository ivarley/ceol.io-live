"""Create (or reset) the account App Review signs in with.

    python scripts/create_review_account.py [--email appreview@ceol.app] [--session PATH ...]

Run it where the database is: the Render shell of the `ceol` service for production,
or locally. It asks for the password at the prompt, so it never appears in a command,
a log or the shell history; put the same one in App Store Connect's sign-in details.

The account is ordinary, not an admin: verified, a complete profile (so the app skips
profile setup), no update emails, and a tunebook of the 30 tunes most logged on Ceol
(learned, learning and to learn), so Tunes isn't empty. Each --session (a session
path, e.g. austin/mueller) makes it a confirmed member there, so Home and Sessions
show something real; it then shows on that session's people list, so pick sessions
whose admins don't mind. Run again to reset the password; nothing else changes.

Removing it afterwards: Me -> Delete Account in the app, signed in as it.
"""

import argparse
import getpass
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

import bcrypt  # noqa: E402

from database import get_db_connection, save_to_history  # noqa: E402
from timezone_utils import now_utc  # noqa: E402

TUNEBOOK = [("learned", 15), ("learning", 10), ("want to learn", 5)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--email", default="appreview@ceol.app")
    parser.add_argument(
        "--session", action="append", default=[], help="a session path to join"
    )
    args = parser.parse_args()

    password = getpass.getpass(f"Password for {args.email}: ")
    if len(password) < 8 or password != getpass.getpass("Again: "):
        sys.exit("Passwords must match and be at least 8 characters.")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = now_utc()

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, person_id FROM user_account WHERE LOWER(user_email) = LOWER(%s)",
            (args.email,),
        )
        row = cur.fetchone()
        if row:
            user_id, person_id = row
            save_to_history(cur, "user_account", "UPDATE", user_id)
            cur.execute(
                "UPDATE user_account SET hashed_password = %s, last_modified_date = %s WHERE user_id = %s",
                (hashed, now, user_id),
            )
            conn.commit()
            print(f"Password reset for {args.email} (user {user_id}).")
            return

        cur.execute(
            """
            INSERT INTO person (first_name, last_name, email, city, country, created_date, last_modified_date)
            VALUES ('App', 'Review', %s, 'Galway', 'Ireland', %s, %s) RETURNING person_id
            """,
            (args.email, now, now),
        )
        person_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone,
                                      email_verified, is_active, receive_update_emails,
                                      created_date, last_modified_date)
            VALUES (%s, %s, %s, %s, 'Europe/Dublin', TRUE, TRUE, FALSE, %s, %s) RETURNING user_id
            """,
            (person_id, args.email.split("@")[0], args.email, hashed, now, now),
        )
        user_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO person_instrument (person_id, instrument) VALUES (%s, 'Fiddle')",
            (person_id,),
        )

        cur.execute(
            """
            SELECT sit.tune_id FROM session_instance_tune sit
            WHERE sit.tune_id IS NOT NULL
            GROUP BY sit.tune_id ORDER BY COUNT(*) DESC LIMIT %s
            """,
            (sum(n for _, n in TUNEBOOK),),
        )
        tunes = [r[0] for r in cur.fetchall()]
        i = 0
        for status, n in TUNEBOOK:
            for tune_id in tunes[i : i + n]:
                cur.execute(
                    """
                    INSERT INTO person_tune (person_id, tune_id, learn_status, created_date, last_modified_date)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (person_id, tune_id, status, now, now),
                )
            i += n

        for path in args.session:
            cur.execute("SELECT session_id FROM session WHERE path = %s", (path,))
            found = cur.fetchone()
            if not found:
                conn.rollback()
                sys.exit(f"No session at {path}; nothing was created.")
            cur.execute(
                """
                INSERT INTO session_person (session_id, person_id, relationship, confirmed)
                VALUES (%s, %s, 'member', TRUE)
                """,
                (found[0], person_id),
            )
        conn.commit()
    finally:
        conn.close()
    print(
        f"Created {args.email} (user {user_id}, person {person_id}): {len(tunes)} tunes, "
        f"{len(args.session)} session(s)."
    )


if __name__ == "__main__":
    main()
