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
        
    elif table_name == "person_instrument":
        # For person_instrument, record_id should be a tuple (person_id, instrument)
        person_id, instrument = record_id
        cur.execute(
            """
            INSERT INTO person_instrument_history
            (person_id, instrument, operation, changed_by, changed_at, created_date)
            SELECT person_id, instrument, %s, %s, (NOW() AT TIME ZONE 'UTC'), created_date
            FROM person_instrument WHERE person_id = %s AND instrument = %s
        """,
            (operation, changed_by, person_id, instrument),
        )
        
    elif table_name == "session_instance_person":
        # For session_instance_person, record_id should be a tuple (session_instance_id, person_id)
        session_instance_id, person_id = record_id
        cur.execute(
            """
            INSERT INTO session_instance_person_history
            (session_instance_person_id, session_instance_id, person_id, attendance, comment, operation, changed_by, changed_at, created_date)
            SELECT session_instance_person_id, session_instance_id, person_id, attendance, comment, %s, %s, (NOW() AT TIME ZONE 'UTC'), created_date
            FROM session_instance_person WHERE session_instance_id = %s AND person_id = %s
        """,
            (operation, changed_by, session_instance_id, person_id),
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



# Session Attendee Tracking Database Functions

def get_session_attendees(session_instance_id):
    """
    Get all attendees for a session instance with their details and instruments.
    
    Returns tuple of (regulars, attendees) where each is a list of person dictionaries.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get session_id from session_instance_id
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        session_result = cur.fetchone()
        if not session_result:
            return [], []
        
        session_id = session_result[0]
        
        # Get all people associated with this session instance
        cur.execute("""
            WITH session_people AS (
                -- Get regular session members
                SELECT p.person_id, p.first_name, p.last_name, p.email,
                       sp.is_regular, sp.is_session_admin,
                       COALESCE(sip.attendance, 'no') as attendance,
                       COALESCE(sip.comment, '') as comment,
                       TRUE as is_regular_member
                FROM person p
                JOIN session_person sp ON p.person_id = sp.person_id
                LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id 
                    AND sip.session_instance_id = %s
                WHERE sp.session_id = %s AND sp.is_regular = TRUE
                
                UNION
                
                -- Get session admins who aren't regulars
                SELECT p.person_id, p.first_name, p.last_name, p.email,
                       sp.is_regular, sp.is_session_admin,
                       COALESCE(sip.attendance, 'no') as attendance,
                       COALESCE(sip.comment, '') as comment,
                       sp.is_regular as is_regular_member
                FROM person p
                JOIN session_person sp ON p.person_id = sp.person_id
                LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id 
                    AND sip.session_instance_id = %s
                WHERE sp.session_id = %s AND sp.is_session_admin = TRUE
                    AND sp.is_regular = FALSE
                
                UNION
                
                -- Get attendees who aren't regular members or admins
                SELECT p.person_id, p.first_name, p.last_name, p.email,
                       FALSE as is_regular, FALSE as is_session_admin,
                       sip.attendance, COALESCE(sip.comment, '') as comment,
                       FALSE as is_regular_member
                FROM person p
                JOIN session_instance_person sip ON p.person_id = sip.person_id
                LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
                WHERE sip.session_instance_id = %s 
                    AND (sp.person_id IS NULL OR (sp.is_regular = FALSE AND sp.is_session_admin = FALSE))
            ),
            person_instruments AS (
                SELECT sp.person_id,
                       COALESCE(
                           array_agg(pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                           '{}'::text[]
                       ) as instruments
                FROM session_people sp
                LEFT JOIN person_instrument pi ON sp.person_id = pi.person_id
                GROUP BY sp.person_id
            )
            SELECT sp.person_id, sp.first_name, sp.last_name, sp.email,
                   sp.is_regular, sp.is_session_admin, sp.attendance, sp.comment,
                   sp.is_regular_member, pi.instruments,
                   CONCAT(sp.first_name, ' ', sp.last_name) as display_name
            FROM session_people sp
            JOIN person_instruments pi ON sp.person_id = pi.person_id
            ORDER BY 
                sp.is_regular_member DESC,  -- Regulars first
                sp.display_name            -- Then alphabetical
        """, (session_instance_id, session_id, session_instance_id, session_id, session_id, session_instance_id))
        
        results = cur.fetchall()
        
        regulars = []
        attendees = []
        
        for row in results:
            person_id, first_name, last_name, email, is_regular, is_session_admin, attendance, comment, is_regular_member, instruments, display_name = row
            
            person_data = {
                'person_id': person_id,
                'first_name': first_name,
                'last_name': last_name,  
                'email': email,
                'display_name': display_name,
                'is_regular': is_regular,
                'is_admin': is_session_admin,
                'attendance': attendance,
                'comment': comment,
                'instruments': list(instruments) if instruments else []
            }
            
            if is_regular_member or is_session_admin:
                regulars.append(person_data)
            else:
                attendees.append(person_data)
        
        return regulars, attendees
        
    finally:
        cur.close()
        conn.close()


def check_in_person(session_instance_id, person_id, attendance, comment='', changed_by='system'):
    """
    Check a person into a session instance or update their attendance status.
    
    Returns tuple of (success, message, action) where action is 'added' or 'updated'.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Begin transaction
        cur.execute("BEGIN")
        
        # Check if attendance record already exists
        cur.execute("""
            SELECT attendance, comment, created_date 
            FROM session_instance_person 
            WHERE session_instance_id = %s AND person_id = %s
        """, (session_instance_id, person_id))
        
        existing_record = cur.fetchone()
        
        if existing_record:
            # Get the session_instance_person_id for history logging
            cur.execute("""
                SELECT session_instance_person_id 
                FROM session_instance_person 
                WHERE session_instance_id = %s AND person_id = %s
            """, (session_instance_id, person_id))
            
            existing_id = cur.fetchone()[0]
            
            # Log to history before update
            save_to_history(
                cur,
                'session_instance_person',
                'UPDATE',
                (session_instance_id, person_id),
                changed_by
            )
            
            # Update existing record
            cur.execute("""
                UPDATE session_instance_person 
                SET attendance = %s, comment = %s, last_modified_date = (NOW() AT TIME ZONE 'UTC')
                WHERE session_instance_id = %s AND person_id = %s
            """, (attendance, comment, session_instance_id, person_id))
            
            action = "updated"
        else:
            # Get the session_id for this session_instance_id
            cur.execute("""
                SELECT session_id FROM session_instance 
                WHERE session_instance_id = %s
            """, (session_instance_id,))
            
            session_id_result = cur.fetchone()
            if not session_id_result:
                raise Exception(f"Session instance {session_instance_id} not found")
            
            session_id = session_id_result[0]
            
            # Ensure session_person record exists (create if it doesn't)
            cur.execute("""
                SELECT COUNT(*) FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            session_person_exists = cur.fetchone()[0] > 0
            
            if not session_person_exists:
                # Create session_person record with is_regular=false by default
                cur.execute("""
                    INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
                    VALUES (%s, %s, %s, %s)
                """, (session_id, person_id, False, False))
            
            # Insert new attendance record
            cur.execute("""
                INSERT INTO session_instance_person (session_instance_id, person_id, attendance, comment, created_date)
                VALUES (%s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
                RETURNING session_instance_person_id
            """, (session_instance_id, person_id, attendance, comment))
            
            new_record_id = cur.fetchone()[0]
            
            # Log INSERT to history (manually since record was just created)
            cur.execute("""
                INSERT INTO session_instance_person_history
                (session_instance_person_id, session_instance_id, person_id, attendance, comment, operation, changed_by, changed_at, created_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
            """, (new_record_id, session_instance_id, person_id, attendance, comment, 'INSERT', changed_by))
            
            action = "added"
        
        # Commit transaction
        cur.execute("COMMIT")
        
        return True, f"Successfully {action} attendance", action
        
    except Exception as e:
        cur.execute("ROLLBACK")
        return False, str(e), None
    finally:
        cur.close()
        conn.close()


def create_person_with_instruments(first_name, last_name, email=None, instruments=None, changed_by='system'):
    """
    Create a new person with associated instruments.
    
    Returns tuple of (success, message, person_id, display_name).
    """
    if instruments is None:
        instruments = []
        
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Begin transaction
        cur.execute("BEGIN")
        
        # Check if person with same name already exists (for display name disambiguation)
        cur.execute("""
            SELECT person_id, first_name, last_name, email 
            FROM person 
            WHERE LOWER(first_name) = LOWER(%s) AND LOWER(last_name) = LOWER(%s)
        """, (first_name, last_name))
        
        existing_people = cur.fetchall()
        
        # Insert person
        cur.execute("""
            INSERT INTO person (first_name, last_name, email, created_date)
            VALUES (%s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
            RETURNING person_id
        """, (first_name, last_name, email))
        
        person_id = cur.fetchone()[0]
        
        # Log person creation to history (manually since record was just created)
        cur.execute("""
            INSERT INTO person_history
            (person_id, first_name, last_name, email, operation, changed_by, changed_at, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
        """, (person_id, first_name, last_name, email, 'INSERT', changed_by))
        
        # Insert instruments
        for instrument in instruments:
            cur.execute("""
                INSERT INTO person_instrument (person_id, instrument, created_date)
                VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'))
            """, (person_id, instrument))
            
            # Log instrument creation to history (manually since record was just created)
            cur.execute("""
                INSERT INTO person_instrument_history
                (person_id, instrument, operation, changed_by, changed_at, created_date)
                VALUES (%s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
            """, (person_id, instrument, 'INSERT', changed_by))
        
        # Commit transaction
        cur.execute("COMMIT")
        
        # Generate display name (with disambiguation if needed)
        base_name = f"{first_name} {last_name}"
        display_name = base_name
        
        # If there are existing people with same name, add email or ID for disambiguation
        if existing_people:
            if email:
                display_name = f"{base_name} ({email})"
            else:
                display_name = f"{base_name} (#{person_id})"
        
        return True, f"Successfully created person: {display_name}", person_id, display_name
        
    except Exception as e:
        cur.execute("ROLLBACK")
        return False, str(e), None, None
    finally:
        cur.close()
        conn.close()


def get_person_instruments(person_id):
    """
    Get all instruments for a specific person.
    
    Returns list of instrument names.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT instrument 
            FROM person_instrument 
            WHERE person_id = %s 
            ORDER BY instrument
        """, (person_id,))
        
        results = cur.fetchall()
        return [row[0] for row in results]
        
    finally:
        cur.close()
        conn.close()


def update_person_instruments(person_id, instruments, changed_by='system'):
    """
    Update all instruments for a specific person.
    
    Returns tuple of (success, message, changes_dict).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Begin transaction
        cur.execute("BEGIN")
        
        # Get existing instruments
        cur.execute("SELECT instrument FROM person_instrument WHERE person_id = %s", (person_id,))
        existing_results = cur.fetchall()
        existing_instruments = set(row[0] for row in existing_results)
        new_instruments = set(instruments)
        
        # Calculate changes
        instruments_to_remove = existing_instruments - new_instruments
        instruments_to_add = new_instruments - existing_instruments
        
        # Remove instruments no longer in the list
        for instrument in instruments_to_remove:
            # Log removal to history before delete
            save_to_history(
                cur,
                'person_instrument',
                'DELETE',
                (person_id, instrument),
                changed_by
            )
            
            cur.execute("DELETE FROM person_instrument WHERE person_id = %s AND instrument = %s", 
                       (person_id, instrument))
        
        # Add new instruments
        for instrument in instruments_to_add:
            cur.execute("""
                INSERT INTO person_instrument (person_id, instrument, created_date)
                VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'))
            """, (person_id, instrument))
            
            # Log addition to history (manually since record was just created)
            cur.execute("""
                INSERT INTO person_instrument_history
                (person_id, instrument, operation, changed_by, changed_at, created_date)
                VALUES (%s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
            """, (person_id, instrument, 'INSERT', changed_by))
        
        # Commit transaction
        cur.execute("COMMIT")
        
        changes = {
            'added': sorted(list(instruments_to_add)),
            'removed': sorted(list(instruments_to_remove)),
            'total_changes': len(instruments_to_add) + len(instruments_to_remove)
        }
        
        return True, "Successfully updated instruments", changes
        
    except Exception as e:
        cur.execute("ROLLBACK")
        return False, str(e), None
    finally:
        cur.close()
        conn.close()


def remove_person_attendance(session_instance_id, person_id, changed_by='system'):
    """
    Remove a person from a session instance attendance list.
    
    Returns tuple of (success, message, previous_attendance_data).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Begin transaction
        cur.execute("BEGIN")
        
        # Get existing record before deletion
        cur.execute("""
            SELECT attendance, comment, created_date 
            FROM session_instance_person 
            WHERE session_instance_id = %s AND person_id = %s
        """, (session_instance_id, person_id))
        
        existing_record = cur.fetchone()
        if not existing_record:
            return False, "Person is not currently attending this session instance", None
        
        # Log removal to history before delete
        save_to_history(
            cur,
            'session_instance_person',
            'DELETE',
            (session_instance_id, person_id),
            changed_by
        )
        
        # Get the session_id for this session_instance_id
        cur.execute("""
            SELECT session_id FROM session_instance 
            WHERE session_instance_id = %s
        """, (session_instance_id,))
        
        session_id_result = cur.fetchone()
        if not session_id_result:
            raise Exception(f"Session instance {session_instance_id} not found")
        
        session_id = session_id_result[0]
        
        # Delete attendance record
        cur.execute("""
            DELETE FROM session_instance_person 
            WHERE session_instance_id = %s AND person_id = %s
        """, (session_instance_id, person_id))
        
        # Check if this was the last attendance record for this person in this session
        cur.execute("""
            SELECT COUNT(*) FROM session_instance_person sip
            JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND sip.person_id = %s
        """, (session_id, person_id))
        
        remaining_attendances = cur.fetchone()[0]
        
        # If no more attendance records exist for this session, delete session_person record
        if remaining_attendances == 0:
            cur.execute("""
                DELETE FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
        
        # Commit transaction
        cur.execute("COMMIT")
        
        previous_data = {
            'attendance': existing_record[0],
            'comment': existing_record[1],
            'created_date': existing_record[2]
        }
        
        return True, "Successfully removed person from attendance", previous_data
        
    except Exception as e:
        cur.execute("ROLLBACK")
        return False, str(e), None
    finally:
        cur.close()
        conn.close()


def search_session_people(session_id, search_query, limit=20):
    """
    Search for people associated with a session.
    
    Returns list of people matching the search query.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        search_pattern = f"%{search_query.lower()}%"
        
        cur.execute("""
            WITH session_people AS (
                -- Get all people who have been associated with this session
                SELECT DISTINCT p.person_id, p.first_name, p.last_name, p.email,
                       COALESCE(sp.is_regular, FALSE) as is_regular,
                       sp.is_session_admin
                FROM person p
                LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
                LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id
                LEFT JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                WHERE (sp.session_id = %s OR si.session_id = %s)
                  AND (LOWER(p.first_name) LIKE %s 
                       OR LOWER(p.last_name) LIKE %s
                       OR LOWER(CONCAT(p.first_name, ' ', p.last_name)) LIKE %s)
            ),
            person_instruments AS (
                -- Get instruments for these people
                SELECT sp.person_id,
                       COALESCE(
                           array_agg(pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                           '{}'::text[]
                       ) as instruments
                FROM session_people sp
                LEFT JOIN person_instrument pi ON sp.person_id = pi.person_id
                GROUP BY sp.person_id
            )
            SELECT sp.person_id, sp.first_name, sp.last_name, sp.email,
                   sp.is_regular, sp.is_session_admin,
                   pi.instruments,
                   CONCAT(sp.first_name, ' ', sp.last_name) as display_name
            FROM session_people sp
            JOIN person_instruments pi ON sp.person_id = pi.person_id
            ORDER BY 
                sp.is_regular DESC,  -- Regulars first
                sp.display_name      -- Then alphabetical
            LIMIT %s
        """, (session_id, session_id, session_id, search_pattern, search_pattern, search_pattern, limit))
        
        results = cur.fetchall()
        
        people = []
        for row in results:
            person_id, first_name, last_name, email, is_regular, is_session_admin, instruments, display_name = row
            
            people.append({
                'person_id': person_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'display_name': display_name,
                'is_regular': is_regular,
                'is_session_admin': is_session_admin or False,
                'instruments': list(instruments) if instruments else []
            })
        
        return people
        
    finally:
        cur.close()
        conn.close()
