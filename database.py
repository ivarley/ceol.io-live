import os
import psycopg2


def get_current_user_id():
    """Get current user_id for audit logging, or None for system actions.

    This function safely retrieves the current user's ID from Flask-Login's
    current_user proxy. Returns None if:
    - No user is logged in
    - Running outside a request context (e.g., cron jobs, scripts)
    - current_user is not authenticated

    Returns:
        int or None: The current user's user_id, or None for system actions
    """
    try:
        from flask_login import current_user
        if current_user and hasattr(current_user, 'user_id') and current_user.is_authenticated:
            return current_user.user_id
    except RuntimeError:
        # Outside of request context (e.g., in cron jobs or scripts)
        pass
    return None


def normalize_apostrophes(text):
    """Normalize smart apostrophes and quotes to standard ASCII characters."""
    if not text:
        return text
    # Replace various smart apostrophes and quotes with standard apostrophe
    return text.replace("'", "'").replace("'", "'").replace(""", '"').replace(""", '"')


# Mapping of tune types to expected eighth notes per bar
# Used for detecting pickup notes (anacrusis) in ABC notation
TUNE_TYPE_BEATS = {
    'Jig': 6,           # 6/8 time
    'Reel': 8,          # 4/4 time
    'Slip Jig': 9,      # 9/8 time
    'Hop Jig': 9,       # 9/8 time
    'Hornpipe': 8,      # 4/4 time
    'Polka': 4,         # 2/4 time
    'Set Dance': 8,     # 4/4 time
    'Slide': 12,        # 12/8 time
    'Waltz': 6,         # 3/4 time
    'Barndance': 8,     # 4/4 time
    'Strathspey': 8,    # 4/4 time
    'Three-Two': 12,    # 3/2 time
    'Mazurka': 6,       # 3/4 time
    'March': 8,         # 4/4 time (most common)
    'Air': 8,           # Variable, defaulting to 4/4
}


def count_eighth_notes_in_bar(bar_content):
    """
    Count the number of eighth notes worth of duration in an ABC notation bar.

    This is used to detect pickup bars (anacrusis) which have fewer notes than
    a complete bar.

    Args:
        bar_content: String of ABC notation representing one bar

    Returns:
        Number of eighth notes worth of duration (e.g., "A" = 1, "A2" = 2, "A/" = 0.5)
    """
    if not bar_content:
        return 0

    total_eighths = 0
    i = 0

    while i < len(bar_content):
        char = bar_content[i]

        # Skip decorations and grace notes
        if char == '!':
            # Skip until next !
            i += 1
            while i < len(bar_content) and bar_content[i] != '!':
                i += 1
            i += 1
            continue

        if char == '{':
            # Skip grace notes until }
            while i < len(bar_content) and bar_content[i] != '}':
                i += 1
            i += 1
            continue

        # Handle chords [...]
        if char == '[':
            # Chords count as one note, get the duration after the ]
            while i < len(bar_content) and bar_content[i] != ']':
                i += 1
            i += 1
            # Now get the duration modifier if any
            duration = 1  # Default eighth note
            if i < len(bar_content):
                if bar_content[i:i+2] == '/2':
                    duration = 0.5
                    i += 2
                elif bar_content[i] == '/':
                    duration = 0.5
                    i += 1
                elif bar_content[i].isdigit():
                    num = ''
                    while i < len(bar_content) and bar_content[i].isdigit():
                        num += bar_content[i]
                        i += 1
                    duration = int(num)
            total_eighths += duration
            continue

        # Note letters (A-G, a-g) and rest (z, x)
        if char in 'ABCDEFGabcdefgzxZ':
            duration = 1  # Default is one eighth note
            i += 1

            # Check for accidentals (^, =, _) - already skipped if before note
            # Check for octave modifiers (', ,)
            while i < len(bar_content) and bar_content[i] in "',":
                i += 1

            # Check for duration modifiers
            if i < len(bar_content):
                if bar_content[i:i+2] == '/2':
                    duration = 0.5
                    i += 2
                elif bar_content[i:i+2] == '/4':
                    duration = 0.25
                    i += 2
                elif bar_content[i] == '/':
                    duration = 0.5
                    i += 1
                elif bar_content[i].isdigit():
                    num = ''
                    while i < len(bar_content) and bar_content[i].isdigit():
                        num += bar_content[i]
                        i += 1
                    duration = int(num)

            total_eighths += duration
        else:
            i += 1

    return total_eighths


def extract_abc_incipit(abc_notation, tune_type=None):
    """
    Extract the first two bars of ABC notation plus any pickup notes.
    Bars are delineated by vertical bar characters (|).

    If tune_type is provided, this function will detect pickup bars (anacrusis)
    and include an extra bar to ensure two full bars are included.

    Args:
        abc_notation: The full ABC notation string (music only, no headers)
        tune_type: Optional tune type (e.g., 'Jig', 'Reel') for pickup detection

    Returns:
        The incipit (first two bars plus pickup notes), or empty string if invalid
    """
    if not abc_notation:
        return ""

    # Find all bar line positions
    # Bar lines are | characters (including variants like |:, :|, ||, etc.)
    bar_positions = []
    i = 0
    while i < len(abc_notation):
        if abc_notation[i] == '|':
            bar_positions.append(i)
            # Skip any immediately following bar-related characters (:, |, etc.)
            while i + 1 < len(abc_notation) and abc_notation[i + 1] in ':|]':
                i += 1
        i += 1

    # We need at least 2 bar lines to extract 2 bars
    if len(bar_positions) < 2:
        # If there are fewer than 2 bars, return the whole thing
        return abc_notation

    # Default: assume no pickup, so get 2 bars (bar index 2)
    target_bar_index = min(2, len(bar_positions) - 1)

    # If tune_type is provided, detect pickup notes
    if tune_type and tune_type in TUNE_TYPE_BEATS:
        expected_beats = TUNE_TYPE_BEATS[tune_type]

        # Check if there's a pickup bar between first and second bar lines
        # Common pattern: |: pickup | bar1 | bar2 |
        if len(bar_positions) >= 2:
            # Extract content between first and second bar line
            first_bar_start = bar_positions[0]
            # Skip past the bar line and any modifiers (:, |, etc.)
            while first_bar_start < len(abc_notation) and abc_notation[first_bar_start] in ':|[]':
                first_bar_start += 1

            first_bar_content = abc_notation[first_bar_start:bar_positions[1]]

            # Count beats in first bar
            first_bar_beats = count_eighth_notes_in_bar(first_bar_content)

            # If first bar has less than half the expected beats, it's likely a pickup
            if first_bar_beats > 0 and first_bar_beats < (expected_beats * 0.5):
                # This is a pickup bar - we need 3 bars total to get 2 full bars + pickup
                # (|: pickup | full bar 1 | full bar 2 |)
                target_bar_index = min(3, len(bar_positions) - 1)

    incipit_end = bar_positions[target_bar_index]

    # Include the bar line character itself
    incipit_end += 1

    # Also include any bar modifiers immediately after (like : or |)
    while incipit_end < len(abc_notation) and abc_notation[incipit_end] in ':|]':
        incipit_end += 1

    return abc_notation[:incipit_end]


def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST"),
        database=os.environ.get("PGDATABASE"),
        user=os.environ.get("PGUSER"),
        password=os.environ.get("PGPASSWORD"),
        port=int(os.environ.get("PGPORT", 5432)),
    )
    return conn


def save_to_history(cur, table_name, operation, record_id, user_id=None):
    """Save a record to its history table before modification/deletion.

    Args:
        cur: Database cursor
        table_name: Name of the table being modified
        operation: 'INSERT', 'UPDATE', or 'DELETE'
        record_id: Primary key of the record (or tuple for composite keys)
        user_id: The user_id performing the action, or None for system actions
    """

    if table_name == "session":
        cur.execute(
            """
            INSERT INTO session_history
            (session_id, operation, changed_by_user_id, thesession_id, name, path, location_name,
             location_website, location_phone, location_street, city, state, country, comments,
             unlisted_address, initiation_date, termination_date, recurrence, created_date, last_modified_date,
             created_by_user_id, last_modified_user_id)
            SELECT session_id, %s, %s, thesession_id, name, path, location_name,
                   location_website, location_phone, location_street, city, state, country, comments,
                   unlisted_address, initiation_date, termination_date, recurrence, created_date, last_modified_date,
                   created_by_user_id, last_modified_user_id
            FROM session WHERE session_id = %s
        """,
            (operation, user_id, record_id),
        )

    elif table_name == "session_instance":
        cur.execute(
            """
            INSERT INTO session_instance_history
            (session_instance_id, operation, changed_by_user_id, session_id, date, start_time,
             end_time, location_override, is_cancelled, comments, created_date, last_modified_date,
             created_by_user_id, last_modified_user_id)
            SELECT session_instance_id, %s, %s, session_id, date, start_time,
                   end_time, location_override, is_cancelled, comments, created_date, last_modified_date,
                   created_by_user_id, last_modified_user_id
            FROM session_instance WHERE session_instance_id = %s
        """,
            (operation, user_id, record_id),
        )

    elif table_name == "tune":
        cur.execute(
            """
            INSERT INTO tune_history
            (tune_id, operation, changed_by_user_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date,
             created_date, last_modified_date, created_by_user_id, last_modified_user_id)
            SELECT tune_id, %s, %s, name, tune_type, tunebook_count_cached, tunebook_count_cached_date,
                   created_date, last_modified_date, created_by_user_id, last_modified_user_id
            FROM tune WHERE tune_id = %s
        """,
            (operation, user_id, record_id),
        )

    elif table_name == "tune_setting":
        cur.execute(
            """
            INSERT INTO tune_setting_history
            (setting_id, operation, changed_by_user_id, tune_id, key, abc, image, incipit_abc, incipit_image,
             cache_updated_date, created_date, last_modified_date, created_by_user_id, last_modified_user_id)
            SELECT setting_id, %s, %s, tune_id, key, abc, image, incipit_abc, incipit_image,
                   cache_updated_date, created_date, last_modified_date, created_by_user_id, last_modified_user_id
            FROM tune_setting WHERE setting_id = %s
        """,
            (operation, user_id, record_id),
        )

    elif table_name == "session_tune":
        # For session_tune, record_id should be a tuple (session_id, tune_id)
        session_id, tune_id = record_id
        cur.execute(
            """
            INSERT INTO session_tune_history
            (session_id, tune_id, operation, changed_by_user_id, setting_id, key, alias,
             created_date, last_modified_date, created_by_user_id, last_modified_user_id)
            SELECT session_id, tune_id, %s, %s, setting_id, key, alias,
                   created_date, last_modified_date, created_by_user_id, last_modified_user_id
            FROM session_tune WHERE session_id = %s AND tune_id = %s
        """,
            (operation, user_id, session_id, tune_id),
        )

    elif table_name == "session_instance_tune":
        cur.execute(
            """
            INSERT INTO session_instance_tune_history
            (session_instance_tune_id, operation, changed_by_user_id, session_instance_id, tune_id,
             name, order_number, order_position, continues_set, played_timestamp, inserted_timestamp,
             key_override, setting_override, created_date, last_modified_date, created_by_user_id, last_modified_user_id)
            SELECT session_instance_tune_id, %s, %s, session_instance_id, tune_id,
                   name, order_number, order_position, continues_set, played_timestamp, inserted_timestamp,
                   key_override, setting_override, created_date, last_modified_date, created_by_user_id, last_modified_user_id
            FROM session_instance_tune WHERE session_instance_tune_id = %s
        """,
            (operation, user_id, record_id),
        )

    elif table_name == "person":
        cur.execute(
            """
            INSERT INTO person_history
            (person_id, operation, changed_by_user_id, first_name, last_name, email, sms_number,
             city, state, country, thesession_user_id, created_date, last_modified_date,
             created_by_user_id, last_modified_user_id)
            SELECT person_id, %s, %s, first_name, last_name, email, sms_number,
                   city, state, country, thesession_user_id, created_date, last_modified_date,
                   created_by_user_id, last_modified_user_id
            FROM person WHERE person_id = %s
        """,
            (operation, user_id, record_id),
        )

    elif table_name == "user_account":
        cur.execute(
            """
            INSERT INTO user_account_history
            (user_id, operation, changed_by_user_id, person_id, username, user_email, hashed_password,
             timezone, is_active, is_system_admin, email_verified, verification_token,
             verification_token_expires, password_reset_token, password_reset_expires,
             created_date, last_modified_date, referred_by_person_id, created_by_user_id, last_modified_user_id)
            SELECT user_id, %s, %s, person_id, username, user_email, hashed_password,
                   timezone, is_active, is_system_admin, email_verified, verification_token,
                   verification_token_expires, password_reset_token, password_reset_expires,
                   created_date, last_modified_date, referred_by_person_id, created_by_user_id, last_modified_user_id
            FROM user_account WHERE user_id = %s
        """,
            (operation, user_id, record_id),
        )
        
    elif table_name == "person_instrument":
        # For person_instrument, record_id should be a tuple (person_id, instrument)
        person_id, instrument = record_id
        cur.execute(
            """
            INSERT INTO person_instrument_history
            (person_id, instrument, operation, changed_by_user_id, changed_at, created_date,
             created_by_user_id, last_modified_user_id)
            SELECT person_id, instrument, %s, %s, (NOW() AT TIME ZONE 'UTC'), created_date,
                   created_by_user_id, last_modified_user_id
            FROM person_instrument WHERE person_id = %s AND instrument = %s
        """,
            (operation, user_id, person_id, instrument),
        )
        
    elif table_name == "session_instance_person":
        # For session_instance_person, record_id should be a tuple (session_instance_id, person_id)
        session_instance_id, person_id = record_id
        cur.execute(
            """
            INSERT INTO session_instance_person_history
            (session_instance_person_id, session_instance_id, person_id, attendance, comment, operation,
             changed_by_user_id, changed_at, created_date, created_by_user_id, last_modified_user_id)
            SELECT session_instance_person_id, session_instance_id, person_id, attendance, comment, %s,
                   %s, (NOW() AT TIME ZONE 'UTC'), created_date, created_by_user_id, last_modified_user_id
            FROM session_instance_person WHERE session_instance_id = %s AND person_id = %s
        """,
            (operation, user_id, session_instance_id, person_id),
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
    # First, search session_tune table for alias match (case and accent insensitive)
    cur.execute(
        """
        SELECT tune_id
        FROM session_tune
        WHERE session_id = %s AND LOWER(unaccent(alias)) = LOWER(unaccent(%s))
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
        # No session_tune alias match, search session_tune_alias table (accent insensitive)
        cur.execute(
            """
            SELECT tune_id
            FROM session_tune_alias
            WHERE session_id = %s AND LOWER(unaccent(alias)) = LOWER(unaccent(%s))
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
            # No alias match in either table, search tune table by name with flexible "The " matching (accent insensitive)
            # Exclude redirected tunes - they should not match
            cur.execute(
                """
                SELECT tune_id, name
                FROM tune
                WHERE (LOWER(unaccent(name)) = LOWER(unaccent(%s))
                OR LOWER(unaccent(name)) = LOWER(unaccent('The ' || %s))
                OR LOWER(unaccent('The ' || name)) = LOWER(unaccent(%s)))
                AND redirect_to_tune_id IS NULL
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


def check_in_person(session_instance_id, person_id, attendance, comment='', user_id=None):
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
                user_id=user_id,
            )
            
            # Update existing record
            cur.execute("""
                UPDATE session_instance_person
                SET attendance = %s, comment = %s, last_modified_date = (NOW() AT TIME ZONE 'UTC'),
                    last_modified_user_id = %s
                WHERE session_instance_id = %s AND person_id = %s
            """, (attendance, comment, user_id, session_instance_id, person_id))
            
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
                    INSERT INTO session_person (session_id, person_id, is_regular, is_admin, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (session_id, person_id, False, False, user_id))
            
            # Insert new attendance record
            cur.execute("""
                INSERT INTO session_instance_person (session_instance_id, person_id, attendance, comment, created_date, created_by_user_id)
                VALUES (%s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
                RETURNING session_instance_person_id
            """, (session_instance_id, person_id, attendance, comment, user_id))
            
            new_record_id = cur.fetchone()[0]
            
            # Log INSERT to history (manually since record was just created)
            cur.execute("""
                INSERT INTO session_instance_person_history
                (session_instance_person_id, session_instance_id, person_id, attendance, comment, operation, changed_by_user_id, changed_at, created_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
            """, (new_record_id, session_instance_id, person_id, attendance, comment, 'INSERT', user_id))
            
            action = "added"
        
        # Commit transaction
        cur.execute("COMMIT")

        # Update the session instance's active status based on current time
        # This ensures the instance is correctly marked active/inactive before
        # we update the person's location
        try:
            from active_session_manager import update_session_instance_active_status
            update_session_instance_active_status(session_instance_id, conn)
        except Exception as e:
            # Log error but don't fail the check-in
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to update session instance {session_instance_id} active status: {e}")

        # Update person's active session based on their attendance status
        # Import locally to avoid circular dependency
        try:
            if attendance == 'yes':
                # If they checked in as "yes", update their active session instance
                from active_session_manager import update_person_active_instance
                update_person_active_instance(person_id, session_instance_id, conn)
            else:
                # If they checked in as "maybe" or "no", recalculate their active session
                # (they should not be at this session, but may be at another overlapping one)
                from active_session_manager import recalculate_person_active_instance
                recalculate_person_active_instance(person_id, conn)
            conn.commit()
        except Exception as e:
            # Log error but don't fail the check-in
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to update person {person_id} active instance: {e}")

        return True, f"Successfully {action} attendance", action

    except Exception as e:
        cur.execute("ROLLBACK")
        return False, str(e), None
    finally:
        cur.close()
        conn.close()


def create_person_with_instruments(first_name, last_name, email=None, instruments=None, user_id=None):
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
            INSERT INTO person (first_name, last_name, email, created_date, created_by_user_id)
            VALUES (%s, %s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
            RETURNING person_id
        """, (first_name, last_name, email, user_id))
        
        person_id = cur.fetchone()[0]
        
        # Log person creation to history (manually since record was just created)
        cur.execute("""
            INSERT INTO person_history
            (person_id, first_name, last_name, email, operation, changed_by_user_id, changed_at, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
        """, (person_id, first_name, last_name, email, 'INSERT', user_id))
        
        # Insert instruments
        for instrument in instruments:
            cur.execute("""
                INSERT INTO person_instrument (person_id, instrument, created_date, created_by_user_id)
                VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
            """, (person_id, instrument, user_id))

            # Log instrument creation to history (manually since record was just created)
            cur.execute("""
                INSERT INTO person_instrument_history
                (person_id, instrument, operation, changed_by_user_id, changed_at, created_date)
                VALUES (%s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
            """, (person_id, instrument, 'INSERT', user_id))
        
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


def update_person_instruments(person_id, instruments, user_id=None):
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
                user_id=user_id,
            )
            
            cur.execute("DELETE FROM person_instrument WHERE person_id = %s AND instrument = %s", 
                       (person_id, instrument))
        
        # Add new instruments
        for instrument in instruments_to_add:
            cur.execute("""
                INSERT INTO person_instrument (person_id, instrument, created_date, created_by_user_id)
                VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
            """, (person_id, instrument, user_id))

            # Log addition to history (manually since record was just created)
            cur.execute("""
                INSERT INTO person_instrument_history
                (person_id, instrument, operation, changed_by_user_id, changed_at, created_date)
                VALUES (%s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC'))
            """, (person_id, instrument, 'INSERT', user_id))
        
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


def remove_person_attendance(session_instance_id, person_id, user_id=None):
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
            user_id=user_id,
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
        
        # Commit transaction
        cur.execute("COMMIT")

        # Recalculate person's active session after removal
        # They should no longer be at this session, but may be at another overlapping one
        try:
            from active_session_manager import recalculate_person_active_instance
            recalculate_person_active_instance(person_id, conn)
            conn.commit()
        except Exception as e:
            # Log error but don't fail the removal
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to recalculate person {person_id} active instance after removal: {e}")

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
                  AND p.active = TRUE
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
