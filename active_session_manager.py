"""
Active Session Manager

Manages the lifecycle of active session instances based on recurrence patterns,
time zones, and buffer windows. Handles activation/deactivation of sessions and
updates which people are currently at active sessions.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict
from zoneinfo import ZoneInfo

from database import get_db_connection
from recurrence_utils import SessionRecurrence

logger = logging.getLogger(__name__)


def update_active_sessions() -> Dict[str, any]:
    """
    Check all sessions and update their active status based on current time.

    This function looks 1 minute into the future when activating sessions,
    ensuring sessions scheduled for round times (e.g., 7:00pm) become active
    right at that time when run at 6:59pm.

    Returns:
        Dictionary with statistics about activations and deactivations
    """
    conn = get_db_connection()
    cur = conn.cursor()

    stats = {
        'activated': [],
        'deactivated': [],
        'errors': []
    }

    try:
        # Get all active sessions (non-terminated, with recurrence patterns)
        cur.execute("""
            SELECT session_id, name, recurrence, timezone,
                   active_buffer_minutes_before, active_buffer_minutes_after,
                   initiation_date
            FROM session
            WHERE (termination_date IS NULL OR termination_date >= CURRENT_DATE)
              AND recurrence IS NOT NULL
              AND recurrence != ''
            ORDER BY session_id
        """)

        sessions = cur.fetchall()

        for session_row in sessions:
            try:
                (session_id, name, recurrence_json, timezone_str,
                 buffer_before, buffer_after, initiation_date) = session_row

                # Parse timezone
                try:
                    tz = ZoneInfo(timezone_str)
                except Exception as e:
                    logger.error(f"Invalid timezone '{timezone_str}' for session {session_id}: {e}")
                    stats['errors'].append({'session_id': session_id, 'error': f'Invalid timezone: {timezone_str}'})
                    continue

                # Get current time in session's timezone (look ahead 1 minute)
                now_utc = datetime.now(ZoneInfo('UTC'))
                now_local = now_utc.astimezone(tz)
                lookahead_local = now_local + timedelta(minutes=1)

                # Parse recurrence pattern
                try:
                    recurrence = SessionRecurrence(recurrence_json)
                except Exception as e:
                    logger.error(f"Invalid recurrence for session {session_id}: {e}")
                    stats['errors'].append({'session_id': session_id, 'error': f'Invalid recurrence: {e}'})
                    continue

                # Get all session instances for this session (within reasonable time range)
                # We check past instances (in case they should still be active) and future ones
                search_start = (now_local - timedelta(days=1)).date()
                search_end = (now_local + timedelta(days=2)).date()

                cur.execute("""
                    SELECT session_instance_id, date, start_time, end_time, is_active, is_cancelled
                    FROM session_instance
                    WHERE session_id = %s
                      AND date BETWEEN %s AND %s
                      AND is_cancelled = FALSE
                    ORDER BY date, start_time
                """, (session_id, search_start, search_end))

                instances = cur.fetchall()

                # Determine which instances should be active
                instances_that_should_be_active = set()
                currently_active_instances = set()

                for instance in instances:
                    inst_id, inst_date, start_time, end_time, is_active, is_cancelled = instance

                    # Track what's currently active
                    if is_active:
                        currently_active_instances.add(inst_id)

                    # Skip instances without defined times (can't determine active window)
                    if start_time is None or end_time is None:
                        continue

                    # Combine date and time to get full datetimes in session timezone
                    start_dt = datetime.combine(inst_date, start_time).replace(tzinfo=tz)
                    end_dt = datetime.combine(inst_date, end_time).replace(tzinfo=tz)

                    # Calculate active window (with buffer)
                    active_start = start_dt - timedelta(minutes=buffer_before)
                    active_end = end_dt + timedelta(minutes=buffer_after)

                    # Check if lookahead time is within active window
                    if active_start <= lookahead_local <= active_end:
                        instances_that_should_be_active.add(inst_id)

                # Activate instances that should be active but aren't
                for inst_id in instances_that_should_be_active - currently_active_instances:
                    activate_session_instance(session_id, inst_id, conn)
                    stats['activated'].append({
                        'session_id': session_id,
                        'session_name': name,
                        'instance_id': inst_id
                    })

                # Deactivate instances that are active but shouldn't be
                for inst_id in currently_active_instances - instances_that_should_be_active:
                    deactivate_session_instance(session_id, inst_id, conn)
                    stats['deactivated'].append({
                        'session_id': session_id,
                        'session_name': name,
                        'instance_id': inst_id
                    })

            except Exception as e:
                logger.error(f"Error processing session {session_id}: {e}", exc_info=True)
                stats['errors'].append({'session_id': session_id, 'error': str(e)})
                conn.rollback()
                continue

        conn.commit()

        logger.info(
            f"Active session update completed: "
            f"{len(stats['activated'])} activated, "
            f"{len(stats['deactivated'])} deactivated, "
            f"{len(stats['errors'])} errors"
        )

        return stats

    finally:
        cur.close()
        conn.close()


def activate_session_instance(session_id: int, instance_id: int, conn=None) -> None:
    """
    Activate a session instance and update all related entities.

    This marks the instance as active and updates people who have checked in as "yes"
    to be at this active session (unless they're already at another active session).

    Args:
        session_id: The session ID
        instance_id: The session instance ID to activate
        conn: Database connection (creates new one if not provided)
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cur = conn.cursor()

    try:
        # Mark instance as active
        cur.execute("""
            UPDATE session_instance
            SET is_active = TRUE
            WHERE session_instance_id = %s
        """, (instance_id,))

        # Get all people who checked in as "yes" for this instance
        cur.execute("""
            SELECT person_id
            FROM session_instance_person
            WHERE session_instance_id = %s
              AND attendance = 'yes'
        """, (instance_id,))

        checked_in_people = [row[0] for row in cur.fetchall()]

        # Update each person's active session (respecting overlap rules)
        for person_id in checked_in_people:
            update_person_active_instance(person_id, instance_id, conn)

        if should_close:
            conn.commit()

        logger.info(f"Activated session instance {instance_id} for session {session_id}, "
                   f"updated {len(checked_in_people)} people")

    except Exception as e:
        if should_close:
            conn.rollback()
        logger.error(f"Error activating session instance {instance_id}: {e}")
        raise
    finally:
        cur.close()
        if should_close:
            conn.close()


def deactivate_session_instance(session_id: int, instance_id: int, conn=None) -> None:
    """
    Deactivate a session instance and update all related entities.

    This marks the instance as inactive and removes this session from people's
    at_active_session_instance_id (unless they have another overlapping active
    session to switch to).

    Args:
        session_id: The session ID
        instance_id: The session instance ID to deactivate
        conn: Database connection (creates new one if not provided)
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cur = conn.cursor()

    try:
        # Get all people currently at this session
        cur.execute("""
            SELECT person_id
            FROM person
            WHERE at_active_session_instance_id = %s
        """, (instance_id,))

        affected_people = [row[0] for row in cur.fetchall()]

        # Mark instance as inactive
        cur.execute("""
            UPDATE session_instance
            SET is_active = FALSE
            WHERE session_instance_id = %s
        """, (instance_id,))

        # For each affected person, recalculate their active session
        for person_id in affected_people:
            recalculate_person_active_instance(person_id, conn)

        if should_close:
            conn.commit()

        logger.info(f"Deactivated session instance {instance_id} for session {session_id}, "
                   f"updated {len(affected_people)} people")

    except Exception as e:
        if should_close:
            conn.rollback()
        logger.error(f"Error deactivating session instance {instance_id}: {e}")
        raise
    finally:
        cur.close()
        if should_close:
            conn.close()


def update_person_active_instance(person_id: int, new_instance_id: int, conn=None) -> None:
    """
    Update a person's active session instance when they check in.

    Handles overlapping sessions according to the rules:
    - If person has multiple overlapping active sessions, choose the one that starts first
    - On ties, choose the one they most recently checked in to

    Args:
        person_id: The person ID
        new_instance_id: The session instance they're checking in to
        conn: Database connection (creates new one if not provided)
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cur = conn.cursor()

    try:
        # Check if the new instance is actually active
        cur.execute("""
            SELECT is_active
            FROM session_instance
            WHERE session_instance_id = %s
        """, (new_instance_id,))

        result = cur.fetchone()
        if not result or not result[0]:
            # Instance is not active, don't update person's location
            logger.debug(f"Instance {new_instance_id} is not active, not updating person {person_id}")
            if should_close:
                conn.close()
            return

        # Get all active sessions this person has checked in to as "yes"
        cur.execute("""
            SELECT
                sip.session_instance_id,
                si.date,
                si.start_time,
                sip.created_date as checkin_time
            FROM session_instance_person sip
            JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
            WHERE sip.person_id = %s
              AND sip.attendance = 'yes'
              AND si.is_active = TRUE
            ORDER BY si.date, si.start_time, sip.created_date DESC
        """, (person_id,))

        active_sessions = cur.fetchall()

        if not active_sessions:
            # No active sessions, clear their location
            cur.execute("""
                UPDATE person
                SET at_active_session_instance_id = NULL
                WHERE person_id = %s
            """, (person_id,))
        else:
            # Use the first one (earliest start time, most recent check-in on ties)
            chosen_instance_id = active_sessions[0][0]

            cur.execute("""
                UPDATE person
                SET at_active_session_instance_id = %s
                WHERE person_id = %s
            """, (chosen_instance_id, person_id))

            logger.debug(f"Updated person {person_id} to be at instance {chosen_instance_id}")

        if should_close:
            conn.commit()

    except Exception as e:
        if should_close:
            conn.rollback()
        logger.error(f"Error updating person {person_id} active instance: {e}")
        raise
    finally:
        cur.close()
        if should_close:
            conn.close()


def recalculate_person_active_instance(person_id: int, conn=None) -> None:
    """
    Recalculate which session instance (if any) a person should be at.

    This is called when a session deactivates to see if the person should
    be switched to another overlapping active session they've checked in to.

    Args:
        person_id: The person ID
        conn: Database connection (creates new one if not provided)
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cur = conn.cursor()

    try:
        # Get all active sessions this person has checked in to as "yes"
        cur.execute("""
            SELECT
                sip.session_instance_id,
                si.date,
                si.start_time,
                sip.created_date as checkin_time
            FROM session_instance_person sip
            JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
            WHERE sip.person_id = %s
              AND sip.attendance = 'yes'
              AND si.is_active = TRUE
            ORDER BY si.date, si.start_time, sip.created_date DESC
        """, (person_id,))

        active_sessions = cur.fetchall()

        if not active_sessions:
            # No active sessions, clear their location
            cur.execute("""
                UPDATE person
                SET at_active_session_instance_id = NULL
                WHERE person_id = %s
            """, (person_id,))
        else:
            # Use the first one (earliest start time, most recent check-in on ties)
            chosen_instance_id = active_sessions[0][0]

            cur.execute("""
                UPDATE person
                SET at_active_session_instance_id = %s
                WHERE person_id = %s
            """, (chosen_instance_id, person_id))

        if should_close:
            conn.commit()

    except Exception as e:
        if should_close:
            conn.rollback()
        logger.error(f"Error recalculating person {person_id} active instance: {e}")
        raise
    finally:
        cur.close()
        if should_close:
            conn.close()


def get_session_active_instances(session_id: int) -> List[int]:
    """
    Get all currently active instances for a session.

    Args:
        session_id: The session ID

    Returns:
        List of session instance IDs that are currently active (empty list if none)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT session_instance_id
            FROM session_instance
            WHERE session_id = %s
              AND is_active = TRUE
            ORDER BY date, start_time
        """, (session_id,))

        results = cur.fetchall()
        return [row[0] for row in results]

    finally:
        cur.close()
        conn.close()


def get_person_active_session(person_id: int) -> Optional[Dict[str, any]]:
    """
    Get the session instance a person is currently at.

    Args:
        person_id: The person ID

    Returns:
        Dictionary with session and instance details, or None if not at a session
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                p.at_active_session_instance_id,
                si.session_id,
                si.date,
                si.start_time,
                si.end_time,
                si.location_override,
                s.name,
                s.path
            FROM person p
            LEFT JOIN session_instance si ON p.at_active_session_instance_id = si.session_instance_id
            LEFT JOIN session s ON si.session_id = s.session_id
            WHERE p.person_id = %s
              AND p.at_active_session_instance_id IS NOT NULL
        """, (person_id,))

        result = cur.fetchone()

        if not result:
            return None

        return {
            'session_instance_id': result[0],
            'session_id': result[1],
            'date': result[2],
            'start_time': result[3],
            'end_time': result[4],
            'location_override': result[5],
            'session_name': result[6],
            'session_path': result[7]
        }

    finally:
        cur.close()
        conn.close()


def update_session_instance_active_status(session_instance_id: int, conn=None) -> bool:
    """
    Update the active status of a single session instance based on current time.

    This runs the same logic as the cron job but for a single instance,
    checking if it should be active or inactive right now based on its
    time window, timezone, and buffer settings.

    Called during check-in to ensure the instance's active status is current
    before updating person locations.

    Args:
        session_instance_id: The session instance ID to check
        conn: Database connection (creates new one if not provided)

    Returns:
        True if successful, False if error occurred
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cur = conn.cursor()

    try:
        # Get session instance and parent session details
        cur.execute("""
            SELECT
                si.session_instance_id,
                si.session_id,
                si.date,
                si.start_time,
                si.end_time,
                si.is_active,
                si.is_cancelled,
                s.name,
                s.recurrence,
                s.timezone,
                s.active_buffer_minutes_before,
                s.active_buffer_minutes_after
            FROM session_instance si
            JOIN session s ON si.session_id = s.session_id
            WHERE si.session_instance_id = %s
        """, (session_instance_id,))

        result = cur.fetchone()

        if not result:
            logger.warning(f"Session instance {session_instance_id} not found")
            return False

        (inst_id, session_id, inst_date, start_time, end_time, is_active,
         is_cancelled, name, recurrence_json, timezone_str, buffer_before, buffer_after) = result

        # Skip cancelled instances
        if is_cancelled:
            logger.debug(f"Instance {inst_id} is cancelled, skipping active status check")
            return True

        # Skip instances without defined times (can't determine active window)
        if start_time is None or end_time is None:
            logger.debug(f"Instance {inst_id} has no start/end times, skipping active status check")
            return True

        # Parse timezone
        try:
            tz = ZoneInfo(timezone_str)
        except Exception as e:
            logger.error(f"Invalid timezone '{timezone_str}' for session {session_id}: {e}")
            return False

        # Get current time in session's timezone (with 1-minute lookahead)
        now_utc = datetime.now(ZoneInfo('UTC'))
        now_local = now_utc.astimezone(tz)
        lookahead_local = now_local + timedelta(minutes=1)

        # Combine date and time to get full datetimes in session timezone
        start_dt = datetime.combine(inst_date, start_time).replace(tzinfo=tz)
        end_dt = datetime.combine(inst_date, end_time).replace(tzinfo=tz)

        # Calculate active window (with buffer)
        active_start = start_dt - timedelta(minutes=buffer_before)
        active_end = end_dt + timedelta(minutes=buffer_after)

        # Determine if instance should be active
        should_be_active = active_start <= lookahead_local <= active_end

        # Update status if needed
        if should_be_active and not is_active:
            activate_session_instance(session_id, inst_id, conn)
            logger.info(f"Activated instance {inst_id} for session '{name}' during check-in")
        elif not should_be_active and is_active:
            deactivate_session_instance(session_id, inst_id, conn)
            logger.info(f"Deactivated instance {inst_id} for session '{name}' during check-in")
        else:
            logger.debug(f"Instance {inst_id} active status unchanged (is_active={is_active})")

        if should_close:
            conn.commit()

        return True

    except Exception as e:
        if should_close:
            conn.rollback()
        logger.error(f"Error updating session instance {session_instance_id} active status: {e}", exc_info=True)
        return False
    finally:
        cur.close()
        if should_close:
            conn.close()
