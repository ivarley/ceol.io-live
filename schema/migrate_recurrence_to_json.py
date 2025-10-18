#!/usr/bin/env python3
"""
Migration script to convert session.recurrence from freeform text to structured JSON.

This script:
1. Reads existing recurrence TEXT values
2. Attempts to parse and convert them to the new JSON format
3. Validates the JSON against the schema
4. Updates records with the new format
5. Reports any that couldn't be auto-converted for manual review

Usage:
    python schema/migrate_recurrence_to_json.py [--dry-run] [--force]

Options:
    --dry-run    Show what would be changed without making changes
    --force      Skip confirmation prompt
"""

import sys
import re
import json
import argparse
from datetime import time
from typing import Optional, Dict, List, Tuple

# Add parent directory to path to import modules
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection
from recurrence_utils import validate_recurrence_json


# Common time patterns
TIME_PATTERNS = [
    r'(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?',
    r'(\d{1,2})\s*(am|pm|AM|PM)',
]

# Day name mappings
DAY_NAMES = {
    'mon': 'monday', 'monday': 'monday', 'mondays': 'monday',
    'tue': 'tuesday', 'tues': 'tuesday', 'tuesday': 'tuesday', 'tuesdays': 'tuesday',
    'wed': 'wednesday', 'wednesday': 'wednesday', 'wednesdays': 'wednesday',
    'thu': 'thursday', 'thur': 'thursday', 'thurs': 'thursday', 'thursday': 'thursday', 'thursdays': 'thursday',
    'fri': 'friday', 'friday': 'friday', 'fridays': 'friday',
    'sat': 'saturday', 'saturday': 'saturday', 'saturdays': 'saturday',
    'sun': 'sunday', 'sunday': 'sunday', 'sundays': 'sunday',
}


def parse_time(time_str: str) -> Optional[str]:
    """
    Parse a time string and return in HH:MM 24-hour format.

    Examples:
        "7pm" -> "19:00"
        "10:30am" -> "10:30"
        "12:00" -> "12:00"
    """
    time_str = time_str.strip().lower()

    for pattern in TIME_PATTERNS:
        match = re.search(pattern, time_str, re.IGNORECASE)
        if match:
            groups = match.groups()

            if len(groups) == 2 and groups[1] in ('am', 'pm'):
                # Format: "7 pm"
                hour = int(groups[0])
                minute = 0
                am_pm = groups[1]
            elif len(groups) == 3:
                # Format: "7:30 pm" or "7:30"
                hour = int(groups[0])
                minute = int(groups[1])
                am_pm = groups[2] if groups[2] else None
            else:
                continue

            # Convert to 24-hour format
            if am_pm:
                if am_pm.lower() == 'pm' and hour != 12:
                    hour += 12
                elif am_pm.lower() == 'am' and hour == 12:
                    hour = 0

            return f"{hour:02d}:{minute:02d}"

    return None


def parse_recurrence_text(text: str) -> Optional[Dict]:
    """
    Attempt to parse freeform recurrence text into structured JSON.

    Returns None if parsing fails or the pattern is too complex.
    """
    if not text or text.strip() == '':
        return None

    text = text.strip()
    text_lower = text.lower()

    # Try to detect day of week
    day_found = None
    for key, value in DAY_NAMES.items():
        if key in text_lower:
            day_found = value
            break

    if not day_found:
        return None  # Can't parse without a day

    # Try to find times
    times = []
    for match in re.finditer(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)', text):
        parsed_time = parse_time(match.group(1))
        if parsed_time:
            times.append(parsed_time)

    if len(times) < 2:
        # Default times if we can't parse them
        times = ["19:00", "22:00"]

    start_time = times[0]
    end_time = times[1] if len(times) > 1 else times[0]

    # Check for "every other" pattern
    every_n_weeks = 1
    if 'every other' in text_lower or 'every 2' in text_lower:
        every_n_weeks = 2

    # Check for monthly patterns
    if 'first' in text_lower or 'third' in text_lower or 'second' in text_lower or 'fourth' in text_lower:
        which = []
        if 'first' in text_lower:
            which.append(1)
        if 'second' in text_lower:
            which.append(2)
        if 'third' in text_lower:
            which.append(3)
        if 'fourth' in text_lower:
            which.append(4)
        if 'last' in text_lower:
            which.append(-1)

        if which:
            # Monthly nth weekday pattern
            return {
                "schedules": [{
                    "type": "monthly_nth_weekday",
                    "weekday": day_found,
                    "which": which,
                    "start_time": start_time,
                    "end_time": end_time,
                }]
            }

    # Default to weekly pattern
    return {
        "schedules": [{
            "type": "weekly",
            "weekday": day_found,
            "start_time": start_time,
            "end_time": end_time,
            "every_n_weeks": every_n_weeks,
        }]
    }


def migrate_recurrence_data(dry_run: bool = False, force: bool = False) -> Tuple[int, int, int]:
    """
    Migrate recurrence data from freeform text to JSON.

    Returns:
        Tuple of (successful_conversions, failed_conversions, already_json)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all sessions with non-null recurrence
    cursor.execute("""
        SELECT session_id, name, recurrence
        FROM session
        WHERE recurrence IS NOT NULL AND recurrence != ''
        ORDER BY session_id
    """)

    rows = cursor.fetchall()

    if not rows:
        print("No sessions with recurrence data found.")
        return (0, 0, 0)

    print(f"Found {len(rows)} sessions with recurrence data.")
    print()

    successful = 0
    failed = 0
    already_json = 0
    failed_sessions = []

    for session_id, name, recurrence in rows:
        # Check if it's already JSON
        try:
            json.loads(recurrence)
            is_valid, error = validate_recurrence_json(recurrence)
            if is_valid:
                print(f"Session {session_id} ({name}): Already valid JSON, skipping")
                already_json += 1
                continue
        except json.JSONDecodeError:
            pass  # Not JSON, need to convert

        # Try to parse and convert
        converted = parse_recurrence_text(recurrence)

        if converted:
            # Validate the converted JSON
            json_str = json.dumps(converted)
            is_valid, error = validate_recurrence_json(json_str)

            if is_valid:
                print(f"Session {session_id} ({name}):")
                print(f"  Original: {recurrence}")
                print(f"  Converted: {json_str}")

                if not dry_run:
                    cursor.execute("""
                        UPDATE session
                        SET recurrence = %s
                        WHERE session_id = %s
                    """, (json_str, session_id))
                    print(f"  ✓ Updated")
                else:
                    print(f"  (Would update in non-dry-run mode)")

                successful += 1
            else:
                print(f"Session {session_id} ({name}): Conversion failed validation - {error}")
                failed += 1
                failed_sessions.append((session_id, name, recurrence))
        else:
            print(f"Session {session_id} ({name}): Could not parse '{recurrence}'")
            failed += 1
            failed_sessions.append((session_id, name, recurrence))

        print()

    if not dry_run and (successful > 0 or failed > 0):
        if not force:
            response = input(f"\nUpdate {successful} sessions? (y/n): ")
            if response.lower() != 'y':
                print("Migration cancelled. Rolling back...")
                conn.rollback()
                cursor.close()
                conn.close()
                return (0, 0, already_json)

        conn.commit()
        print(f"\n✓ Migration committed!")

    # Print summary
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    print(f"Total sessions processed: {len(rows)}")
    print(f"Already valid JSON: {already_json}")
    print(f"Successfully converted: {successful}")
    print(f"Failed to convert: {failed}")

    if failed_sessions:
        print("\nSessions requiring manual review:")
        for session_id, name, recurrence in failed_sessions:
            print(f"  - Session {session_id} ({name}): '{recurrence}'")

    cursor.close()
    conn.close()

    return (successful, failed, already_json)


def main():
    parser = argparse.ArgumentParser(
        description='Migrate session recurrence data from text to JSON format'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making changes'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made\n")

    try:
        successful, failed, already_json = migrate_recurrence_data(
            dry_run=args.dry_run,
            force=args.force
        )

        if failed > 0:
            sys.exit(1)  # Exit with error if any failed
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
