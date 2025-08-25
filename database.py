import os
import psycopg2


def normalize_apostrophes(text):
    """Normalize smart apostrophes and quotes to standard ASCII characters."""
    if not text:
        return text
    # Replace various smart apostrophes and quotes with standard apostrophe
    return text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')


def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST"),
        database=os.environ.get("PGDATABASE"),
        user=os.environ.get("PGUSER"),
        password=os.environ.get("PGPASSWORD"),
        port=int(os.environ.get("PGPORT", 5432)),
    )
    return conn


def save_to_history(cur, table_name, operation, record_id, changed_by="system"):
    """Save a record to its history table before modification/deletion"""
    # history_table = f"{table_name}_history"

    if table_name == "session":
        cur.execute(
            """
            INSERT INTO session_history
            (session_id, operation, changed_by, thesession_id, name, path, location_name,
             location_website, location_phone, location_street, city, state, country, comments,
             unlisted_address, initiation_date, termination_date, recurrence, created_date, last_modified_date)
            SELECT session_id, %s, %s, thesession_id, name, path, location_name,
                   location_website, location_phone, location_street, city, state, country, comments,
                   unlisted_address, initiation_date, termination_date, recurrence, created_date, last_modified_date
            FROM session WHERE session_id = %s
        """,
            (operation, changed_by, record_id),
        )

    elif table_name == "session_instance":
        cur.execute(
            """
            INSERT INTO session_instance_history
            (session_instance_id, operation, changed_by, session_id, date, start_time,
             end_time, location_override, is_cancelled, comments, created_date, last_modified_date)
            SELECT session_instance_id, %s, %s, session_id, date, start_time,
                   end_time, location_override, is_cancelled, comments, created_date, last_modified_date
            FROM session_instance WHERE session_instance_id = %s
        """,
            (operation, changed_by, record_id),
        )

    elif table_name == "tune":
        cur.execute(
            """
            INSERT INTO tune_history
            (tune_id, operation, changed_by, name, tune_type, tunebook_count_cached, tunebook_count_cached_date, created_date, last_modified_date)
            SELECT tune_id, %s, %s, name, tune_type, tunebook_count_cached, tunebook_count_cached_date, created_date, last_modified_date
            FROM tune WHERE tune_id = %s
        """,
            (operation, changed_by, record_id),
        )

    elif table_name == "session_tune":
        # For session_tune, record_id should be a tuple (session_id, tune_id)
        session_id, tune_id = record_id
        cur.execute(
            """
            INSERT INTO session_tune_history
            (session_id, tune_id, operation, changed_by, setting_id, key, alias, created_date, last_modified_date)
            SELECT session_id, tune_id, %s, %s, setting_id, key, alias, created_date, last_modified_date
            FROM session_tune WHERE session_id = %s AND tune_id = %s
        """,
            (operation, changed_by, session_id, tune_id),
        )

    elif table_name == "session_instance_tune":
        cur.execute(
            """
            INSERT INTO session_instance_tune_history
            (session_instance_tune_id, operation, changed_by, session_instance_id, tune_id,
             name, order_number, continues_set, played_timestamp, inserted_timestamp,
             key_override, setting_override, created_date, last_modified_date)
            SELECT session_instance_tune_id, %s, %s, session_instance_id, tune_id,
                   name, order_number, continues_set, played_timestamp, inserted_timestamp,
                   key_override, setting_override, created_date, last_modified_date
            FROM session_instance_tune WHERE session_instance_tune_id = %s
        """,
            (operation, changed_by, record_id),
        )

    elif table_name == "person":
        cur.execute(
            """
            INSERT INTO person_history
            (person_id, operation, changed_by, first_name, last_name, email, sms_number,
             city, state, country, thesession_user_id, created_date, last_modified_date)
            SELECT person_id, %s, %s, first_name, last_name, email, sms_number,
                   city, state, country, thesession_user_id, created_date, last_modified_date
            FROM person WHERE person_id = %s
        """,
            (operation, changed_by, record_id),
        )

    elif table_name == "user_account":
        cur.execute(
            """
            INSERT INTO user_account_history
            (user_id, operation, changed_by, person_id, username, user_email, hashed_password,
             timezone, is_active, is_system_admin, email_verified, verification_token,
             verification_token_expires, password_reset_token, password_reset_expires,
             created_date, last_modified_date)
            SELECT user_id, %s, %s, person_id, username, user_email, hashed_password,
                   timezone, is_active, is_system_admin, email_verified, verification_token,
                   verification_token_expires, password_reset_token, password_reset_expires,
                   created_date, last_modified_date
            FROM user_account WHERE user_id = %s
        """,
            (operation, changed_by, record_id),
        )


def find_matching_tune(
    cur, session_id, tune_name, allow_multiple_session_aliases=False
):
    """
    Find a matching tune by searching session aliases and tune names.

    Returns:
        tuple: (tune_id, final_name, error_message) where:
        - tune_id: The matched tune ID or None if no match
        - final_name: The actual tune name from database or original name
        - error_message: Error message if multiple matches found, None otherwise
    """
    # Normalize the search string the same way we normalize input
    normalized_tune_name = normalize_apostrophes(tune_name.strip())
    # First, search session_tune table for alias match (case insensitive)
    cur.execute(
        """
        SELECT tune_id
        FROM session_tune
        WHERE session_id = %s AND LOWER(alias) = LOWER(%s)
    """,
        (session_id, normalized_tune_name),
    )

    session_tune_matches = cur.fetchall()

    if len(session_tune_matches) > 1 and not allow_multiple_session_aliases:
        return (
            None,
            tune_name,
            f'Multiple tunes found with alias "{tune_name}" in this session. Please be more specific.',
        )
    elif len(session_tune_matches) == 1:
        return session_tune_matches[0][0], tune_name, None
    elif len(session_tune_matches) == 0:
        # No session_tune alias match, search session_tune_alias table
        cur.execute(
            """
            SELECT tune_id
            FROM session_tune_alias
            WHERE session_id = %s AND LOWER(alias) = LOWER(%s)
        """,
            (session_id, normalized_tune_name),
        )

        alias_matches = cur.fetchall()

        if len(alias_matches) > 1:
            return (
                None,
                tune_name,
                f'Multiple tunes found with alias "{tune_name}" in this session. Please be more specific.',
            )
        elif len(alias_matches) == 1:
            return alias_matches[0][0], tune_name, None
        elif len(alias_matches) == 0:
            # No alias match in either table, search tune table by name with flexible "The " matching
            cur.execute(
                """
                SELECT tune_id, name
                FROM tune
                WHERE (LOWER(name) = LOWER(%s)
                OR LOWER(name) = LOWER('The ' || %s)
                OR LOWER('The ' || name) = LOWER(%s))
            """,
                (normalized_tune_name, normalized_tune_name, normalized_tune_name),
            )

            tune_matches = cur.fetchall()

            if len(tune_matches) > 1:
                return (
                    None,
                    tune_name,
                    f'Multiple tunes found with name "{tune_name}". Please be more specific or use an alias.',
                )
            elif len(tune_matches) == 1:
                return tune_matches[0][0], tune_matches[0][1], None

    # No matches found
    return None, tune_name, None
