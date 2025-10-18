"""
Auto-create session instances based on recurrence patterns.

This module provides functionality to automatically create upcoming session instances
for sessions that have recurrence patterns defined.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Tuple
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
                # Insert new session instance
                cur.execute("""
                    INSERT INTO session_instance (session_id, date, start_time, end_time)
                    VALUES (%s, %s, %s, %s)
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
