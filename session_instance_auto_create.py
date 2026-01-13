"""
Auto-create session instances based on recurrence patterns.

This module provides functionality to automatically create upcoming session instances
for sessions that have recurrence patterns defined.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from database import get_db_connection
from recurrence_utils import SessionRecurrence

logger = logging.getLogger(__name__)


def auto_create_next_week_instances(session_id: int) -> Tuple[int, List[str]]:
    """
    Auto-create session instances for the next 7 days based on recurrence pattern.

    Args:
        session_id: The session ID to create instances for

    Returns:
        Tuple of (count of instances created, list of created dates as strings)

    Raises:
        ValueError: If session not found or has no recurrence pattern
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get session details including recurrence pattern
        cur.execute("""
            SELECT session_id, name, recurrence, timezone
            FROM session
            WHERE session_id = %s
        """, (session_id,))

        session_row = cur.fetchone()
        if not session_row:
            raise ValueError(f"Session {session_id} not found")

        session_id, session_name, recurrence_json, session_timezone = session_row

        if not recurrence_json:
            logger.info(f"Session {session_id} ({session_name}) has no recurrence pattern, skipping auto-create")
            return 0, []

        # Parse recurrence pattern
        try:
            session_recurrence = SessionRecurrence(recurrence_json, session_timezone or 'UTC')
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid recurrence pattern for session {session_id}: {e}")
            raise ValueError(f"Invalid recurrence pattern: {e}")

        # Calculate date range: next 7 days starting tomorrow
        today = datetime.now().date()
        start_date = today + timedelta(days=1)
        end_date = today + timedelta(days=7)

        # Get all occurrences in the next 7 days
        occurrences = session_recurrence.get_occurrences(start_date, end_date)

        if not occurrences:
            logger.info(f"No occurrences found for session {session_id} in next 7 days")
            return 0, []

        # Check which instances already exist
        dates_to_check = [occ['date'] for occ in occurrences]
        placeholders = ','.join(['%s'] * len(dates_to_check))

        cur.execute(f"""
            SELECT date
            FROM session_instance
            WHERE session_id = %s AND date IN ({placeholders})
        """, [session_id] + dates_to_check)

        existing_dates = set(row[0] for row in cur.fetchall())

        # Create missing instances
        created_dates = []
        for occurrence in occurrences:
            if occurrence['date'] not in existing_dates:
                # Insert new session instance (system auto-creation, no user)
                cur.execute("""
                    INSERT INTO session_instance (session_id, date, start_time, end_time, created_by_user_id)
                    VALUES (%s, %s, %s, %s, NULL)
                    RETURNING session_instance_id
                """, (
                    session_id,
                    occurrence['date'],
                    occurrence['start_time'],
                    occurrence['end_time']
                ))

                new_instance_id = cur.fetchone()[0]
                created_dates.append(occurrence['date'].isoformat())

                logger.info(
                    f"Created session_instance {new_instance_id} for session {session_id} "
                    f"on {occurrence['date']} from {occurrence['start_time']} to {occurrence['end_time']}"
                )

        conn.commit()

        logger.info(
            f"Auto-created {len(created_dates)} instances for session {session_id} ({session_name}): "
            f"{', '.join(created_dates)}"
        )

        return len(created_dates), created_dates

    except Exception as e:
        conn.rollback()
        logger.error(f"Error auto-creating instances for session {session_id}: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def auto_create_instances_hours_ahead(
    session_id: int,
    hours_ahead: int,
    session_timezone: str,
    recurrence_json: str,
    conn=None
) -> Tuple[int, List[str]]:
    """
    Auto-create session instances for a specified number of hours ahead.

    This is called by the cron job for sessions that have auto_create_instances=TRUE.
    It creates instances that fall within the hours_ahead window from now.

    Args:
        session_id: The session ID to create instances for
        hours_ahead: Number of hours ahead to look for occurrences
        session_timezone: IANA timezone string for the session
        recurrence_json: The recurrence pattern JSON
        conn: Optional database connection (creates new one if not provided)

    Returns:
        Tuple of (count of instances created, list of created dates as strings)
    """
    should_close = conn is None
    if conn is None:
        conn = get_db_connection()

    cur = conn.cursor()

    try:
        # Parse timezone
        try:
            tz = ZoneInfo(session_timezone)
        except Exception as e:
            logger.error(f"Invalid timezone '{session_timezone}' for session {session_id}: {e}")
            return 0, []

        # Parse recurrence pattern
        try:
            session_recurrence = SessionRecurrence(recurrence_json)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid recurrence pattern for session {session_id}: {e}")
            return 0, []

        # Calculate the time window in the session's timezone
        now_utc = datetime.now(ZoneInfo('UTC'))
        now_local = now_utc.astimezone(tz)
        future_local = now_local + timedelta(hours=hours_ahead)

        # Get date range to check (we need whole days for the recurrence lookup)
        start_date = now_local.date()
        end_date = future_local.date()

        # Get all occurrences in the date range
        # Returns list of (start_datetime, end_datetime) tuples
        occurrences = session_recurrence.get_occurrences_in_range(start_date, end_date, tz)

        if not occurrences:
            logger.debug(f"No occurrences found for session {session_id} in next {hours_ahead} hours")
            return 0, []

        # Filter occurrences to only those starting within the hours_ahead window
        valid_occurrences = []
        for start_dt, end_dt in occurrences:
            # Only include if the session starts within the window
            if now_local <= start_dt <= future_local:
                valid_occurrences.append((start_dt, end_dt))

        if not valid_occurrences:
            logger.debug(f"No occurrences starting in next {hours_ahead} hours for session {session_id}")
            return 0, []

        # Check which instances already exist
        dates_to_check = [start_dt.date() for start_dt, _ in valid_occurrences]
        placeholders = ','.join(['%s'] * len(dates_to_check))

        cur.execute(f"""
            SELECT date
            FROM session_instance
            WHERE session_id = %s AND date IN ({placeholders})
        """, [session_id] + dates_to_check)

        existing_dates = set(row[0] for row in cur.fetchall())

        # Create missing instances
        created_dates = []
        for start_dt, end_dt in valid_occurrences:
            occ_date = start_dt.date()
            if occ_date not in existing_dates:
                # Insert new session instance (system auto-creation, no user)
                cur.execute("""
                    INSERT INTO session_instance (session_id, date, start_time, end_time, created_by_user_id)
                    VALUES (%s, %s, %s, %s, NULL)
                    RETURNING session_instance_id
                """, (
                    session_id,
                    occ_date,
                    start_dt.time(),
                    end_dt.time()
                ))

                new_instance_id = cur.fetchone()[0]
                created_dates.append(occ_date.isoformat())

                logger.info(
                    f"Auto-created session_instance {new_instance_id} for session {session_id} "
                    f"on {occ_date} from {start_dt.time()} to {end_dt.time()} "
                    f"({hours_ahead}h ahead)"
                )

        if should_close:
            conn.commit()

        return len(created_dates), created_dates

    except Exception as e:
        if should_close:
            conn.rollback()
        logger.error(f"Error auto-creating instances for session {session_id}: {e}")
        raise
    finally:
        cur.close()
        if should_close:
            conn.close()


def auto_create_instances_for_all_sessions() -> dict:
    """
    Auto-create instances for all active sessions with recurrence patterns.

    This function can be run periodically (e.g., daily via cron) to ensure
    upcoming session instances are always created.

    Returns:
        Dictionary with statistics: {
            'sessions_processed': int,
            'total_instances_created': int,
            'sessions_with_instances': list of session_ids that had instances created
        }
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get all active sessions with recurrence patterns
        cur.execute("""
            SELECT session_id, name
            FROM session
            WHERE recurrence IS NOT NULL
              AND recurrence != ''
              AND (termination_date IS NULL OR termination_date >= CURRENT_DATE)
            ORDER BY session_id
        """)

        sessions = cur.fetchall()

        stats = {
            'sessions_processed': 0,
            'total_instances_created': 0,
            'sessions_with_instances': []
        }

        for session_id, session_name in sessions:
            try:
                count, dates = auto_create_next_week_instances(session_id)
                stats['sessions_processed'] += 1
                stats['total_instances_created'] += count

                if count > 0:
                    stats['sessions_with_instances'].append({
                        'session_id': session_id,
                        'session_name': session_name,
                        'instances_created': count,
                        'dates': dates
                    })

            except Exception as e:
                logger.error(f"Failed to auto-create instances for session {session_id} ({session_name}): {e}")
                # Continue with other sessions
                continue

        logger.info(
            f"Auto-create completed: processed {stats['sessions_processed']} sessions, "
            f"created {stats['total_instances_created']} instances"
        )

        return stats

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    # For testing: run auto-create for all sessions
    logging.basicConfig(level=logging.INFO)
    stats = auto_create_instances_for_all_sessions()
    print(f"\nAuto-create summary:")
    print(f"  Sessions processed: {stats['sessions_processed']}")
    print(f"  Total instances created: {stats['total_instances_created']}")

    if stats['sessions_with_instances']:
        print(f"\n  Sessions with new instances:")
        for session_info in stats['sessions_with_instances']:
            print(f"    - {session_info['session_name']}: {session_info['instances_created']} instances")
            for date in session_info['dates']:
                print(f"      • {date}")
