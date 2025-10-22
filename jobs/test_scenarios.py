#!/usr/bin/env python3
"""
Test Scenarios - Sample Data Generator

Creates realistic test data for testing the active session cron job.
Generates sessions with various recurrence patterns, time zones, and
session instances to test different activation scenarios.
"""

import sys
import os
from datetime import datetime, date, time, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection


def create_test_scenarios():
    """
    Create comprehensive test data covering various scenarios.

    Creates:
    - Sessions in different time zones
    - Various recurrence patterns (weekly, bi-weekly, monthly)
    - Session instances with different start times
    - Overlapping sessions
    - Sessions that should be active now vs later
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        print("Creating test scenarios...")

        # Get current date and time
        now = datetime.now()
        today = now.date()

        # Clean up existing test sessions (ones with 'TEST:' prefix)
        cur.execute("""
            DELETE FROM session_instance_tune WHERE session_instance_id IN (
                SELECT session_instance_id FROM session_instance WHERE session_id IN (
                    SELECT session_id FROM session WHERE name LIKE 'TEST:%'
                )
            )
        """)
        cur.execute("""
            DELETE FROM session_instance WHERE session_id IN (
                SELECT session_id FROM session WHERE name LIKE 'TEST:%'
            )
        """)
        cur.execute("DELETE FROM session WHERE name LIKE 'TEST:%'")

        print("✓ Cleaned up old test data")

        # Scenario 1: Evening session that should be active now (7pm sessions)
        create_evening_session(cur, today, now)

        # Scenario 2: Morning session that should have deactivated
        create_morning_session(cur, today)

        # Scenario 3: Overlapping sessions (multiple active at once)
        create_overlapping_sessions(cur, today)

        # Scenario 4: Session in different timezone
        create_timezone_session(cur, today)

        # Scenario 5: Future session that shouldn't be active yet
        create_future_session(cur, today)

        # Scenario 6: Session with custom buffer times
        create_custom_buffer_session(cur, today)

        conn.commit()
        print("✓ All test scenarios created successfully")

    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating test scenarios: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def create_evening_session(cur, today, now):
    """Create a session that starts at 7pm (should activate at 6pm with 60min buffer)."""
    print("  Creating evening session scenario...")

    # Weekly Thursday session at 7pm-10:30pm
    recurrence = '''{
        "schedules": [{
            "type": "weekly",
            "weekday": "thursday",
            "start_time": "19:00",
            "end_time": "22:30",
            "every_n_weeks": 1
        }]
    }'''

    cur.execute("""
        INSERT INTO session (name, path, location_name, city, state, country,
                            recurrence, timezone, initiation_date,
                            active_buffer_minutes_before, active_buffer_minutes_after)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """, (
        'TEST: Evening Session (7pm)',
        'test/evening-7pm',
        'Test Venue',
        'Austin',
        'TX',
        'USA',
        recurrence,
        'America/Chicago',
        today,
        60,  # Buffer before
        60   # Buffer after
    ))

    session_id = cur.fetchone()[0]

    # Create instance for today (or next Thursday)
    days_until_thursday = (3 - today.weekday()) % 7  # Thursday is 3
    if days_until_thursday == 0 and now.hour >= 23:
        days_until_thursday = 7  # If it's late Thursday, use next Thursday

    instance_date = today + timedelta(days=days_until_thursday)

    cur.execute("""
        INSERT INTO session_instance (session_id, date, start_time, end_time, is_cancelled)
        VALUES (%s, %s, %s, %s, %s)
    """, (session_id, instance_date, time(19, 0), time(22, 30), False))

    print(f"    ✓ Created evening session for {instance_date}")


def create_morning_session(cur, today):
    """Create a morning session that should have ended."""
    print("  Creating morning session scenario...")

    recurrence = '''{
        "schedules": [{
            "type": "weekly",
            "weekday": "wednesday",
            "start_time": "09:00",
            "end_time": "11:00",
            "every_n_weeks": 1
        }]
    }'''

    cur.execute("""
        INSERT INTO session (name, path, location_name, city, state, country,
                            recurrence, timezone, initiation_date,
                            active_buffer_minutes_before, active_buffer_minutes_after)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """, (
        'TEST: Morning Session (9am)',
        'test/morning-9am',
        'Test Cafe',
        'Austin',
        'TX',
        'USA',
        recurrence,
        'America/Chicago',
        today - timedelta(days=30),
        60,
        60
    ))

    session_id = cur.fetchone()[0]

    # Create instance for this week's Wednesday
    days_until_wednesday = (2 - today.weekday()) % 7
    if days_until_wednesday == 0:
        instance_date = today
    else:
        instance_date = today + timedelta(days=days_until_wednesday)

    cur.execute("""
        INSERT INTO session_instance (session_id, date, start_time, end_time, is_cancelled)
        VALUES (%s, %s, %s, %s, %s)
    """, (session_id, instance_date, time(9, 0), time(11, 0), False))

    print(f"    ✓ Created morning session for {instance_date}")


def create_overlapping_sessions(cur, today):
    """Create two sessions that overlap in time."""
    print("  Creating overlapping sessions scenario...")

    # Session 1: 8pm-11pm
    recurrence1 = '''{
        "schedules": [{
            "type": "weekly",
            "weekday": "friday",
            "start_time": "20:00",
            "end_time": "23:00",
            "every_n_weeks": 1
        }]
    }'''

    cur.execute("""
        INSERT INTO session (name, path, location_name, city, state, country,
                            recurrence, timezone, initiation_date,
                            active_buffer_minutes_before, active_buffer_minutes_after)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """, (
        'TEST: Overlap Session A (8pm)',
        'test/overlap-a-8pm',
        'Test Pub A',
        'Austin',
        'TX',
        'USA',
        recurrence1,
        'America/Chicago',
        today,
        60,
        60
    ))

    session1_id = cur.fetchone()[0]

    # Session 2: 9pm-midnight
    recurrence2 = '''{
        "schedules": [{
            "type": "weekly",
            "weekday": "friday",
            "start_time": "21:00",
            "end_time": "00:00",
            "every_n_weeks": 1
        }]
    }'''

    cur.execute("""
        INSERT INTO session (name, path, location_name, city, state, country,
                            recurrence, timezone, initiation_date,
                            active_buffer_minutes_before, active_buffer_minutes_after)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """, (
        'TEST: Overlap Session B (9pm)',
        'test/overlap-b-9pm',
        'Test Pub B',
        'Austin',
        'TX',
        'USA',
        recurrence2,
        'America/Chicago',
        today,
        60,
        60
    ))

    session2_id = cur.fetchone()[0]

    # Create instances for next Friday
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    instance_date = today + timedelta(days=days_until_friday)

    cur.execute("""
        INSERT INTO session_instance (session_id, date, start_time, end_time, is_cancelled)
        VALUES (%s, %s, %s, %s, %s)
    """, (session1_id, instance_date, time(20, 0), time(23, 0), False))

    cur.execute("""
        INSERT INTO session_instance (session_id, date, start_time, end_time, is_cancelled)
        VALUES (%s, %s, %s, %s, %s)
    """, (session2_id, instance_date, time(21, 0), time(0, 0), False))

    print(f"    ✓ Created overlapping sessions for {instance_date}")


def create_timezone_session(cur, today):
    """Create a session in a different timezone (NYC)."""
    print("  Creating timezone session scenario...")

    recurrence = '''{
        "schedules": [{
            "type": "weekly",
            "weekday": "tuesday",
            "start_time": "20:00",
            "end_time": "23:00",
            "every_n_weeks": 1
        }]
    }'''

    cur.execute("""
        INSERT INTO session (name, path, location_name, city, state, country,
                            recurrence, timezone, initiation_date,
                            active_buffer_minutes_before, active_buffer_minutes_after)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """, (
        'TEST: NYC Session (8pm ET)',
        'test/nyc-8pm',
        'Test NYC Venue',
        'New York',
        'NY',
        'USA',
        recurrence,
        'America/New_York',
        today,
        60,
        60
    ))

    session_id = cur.fetchone()[0]

    # Create instance for next Tuesday
    days_until_tuesday = (1 - today.weekday()) % 7
    if days_until_tuesday == 0:
        days_until_tuesday = 7
    instance_date = today + timedelta(days=days_until_tuesday)

    cur.execute("""
        INSERT INTO session_instance (session_id, date, start_time, end_time, is_cancelled)
        VALUES (%s, %s, %s, %s, %s)
    """, (session_id, instance_date, time(20, 0), time(23, 0), False))

    print(f"    ✓ Created NYC timezone session for {instance_date}")


def create_future_session(cur, today):
    """Create a session that's in the future and shouldn't be active yet."""
    print("  Creating future session scenario...")

    recurrence = '''{
        "schedules": [{
            "type": "weekly",
            "weekday": "saturday",
            "start_time": "14:00",
            "end_time": "17:00",
            "every_n_weeks": 1
        }]
    }'''

    cur.execute("""
        INSERT INTO session (name, path, location_name, city, state, country,
                            recurrence, timezone, initiation_date,
                            active_buffer_minutes_before, active_buffer_minutes_after)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """, (
        'TEST: Future Session (2pm)',
        'test/future-2pm',
        'Test Library',
        'Austin',
        'TX',
        'USA',
        recurrence,
        'America/Chicago',
        today,
        60,
        60
    ))

    session_id = cur.fetchone()[0]

    # Create instance for next Saturday
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    instance_date = today + timedelta(days=days_until_saturday)

    cur.execute("""
        INSERT INTO session_instance (session_id, date, start_time, end_time, is_cancelled)
        VALUES (%s, %s, %s, %s, %s)
    """, (session_id, instance_date, time(14, 0), time(17, 0), False))

    print(f"    ✓ Created future session for {instance_date}")


def create_custom_buffer_session(cur, today):
    """Create a session with custom buffer times (30 min before, 90 min after)."""
    print("  Creating custom buffer session scenario...")

    recurrence = '''{
        "schedules": [{
            "type": "weekly",
            "weekday": "sunday",
            "start_time": "15:00",
            "end_time": "18:00",
            "every_n_weeks": 2
        }]
    }'''

    cur.execute("""
        INSERT INTO session (name, path, location_name, city, state, country,
                            recurrence, timezone, initiation_date,
                            active_buffer_minutes_before, active_buffer_minutes_after)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """, (
        'TEST: Custom Buffer Session (3pm)',
        'test/custom-buffer-3pm',
        'Test Community Center',
        'Austin',
        'TX',
        'USA',
        recurrence,
        'America/Chicago',
        today,
        30,  # Only 30 min buffer before
        90   # 90 min buffer after
    ))

    session_id = cur.fetchone()[0]

    # Create instance for next Sunday
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    instance_date = today + timedelta(days=days_until_sunday)

    cur.execute("""
        INSERT INTO session_instance (session_id, date, start_time, end_time, is_cancelled)
        VALUES (%s, %s, %s, %s, %s)
    """, (session_id, instance_date, time(15, 0), time(18, 0), False))

    print(f"    ✓ Created custom buffer session for {instance_date}")


if __name__ == '__main__':
    print("\nTest Scenario Generator")
    print("=" * 80)
    create_test_scenarios()
    print("\nTest data created successfully!")
    print("Run: python3 jobs/test_active_sessions.py")
