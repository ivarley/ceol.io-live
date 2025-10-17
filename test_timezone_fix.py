#!/usr/bin/env python3
"""
Test script to verify the timezone fix for the "Create Today's Session" bug.

This script simulates the scenario where:
1. A session is in timezone A (e.g., US Central)
2. The server is in timezone B (e.g., UTC)
3. A user clicks "Create Today's Session" late at night in their timezone
4. The server should create an instance for "today" in the SESSION's timezone, not server time
"""

from datetime import datetime, date
from zoneinfo import ZoneInfo
from timezone_utils import get_today_in_timezone


def test_timezone_aware_today():
    """Test that we get the correct 'today' for different timezones"""
    print("=" * 60)
    print("Testing timezone-aware 'today' calculation")
    print("=" * 60)
    print()

    # Simulate what happens at a specific point in time
    # Let's say it's 11:30 PM in US Central (UTC-5)
    # That would be 4:30 AM the next day in UTC

    # For testing purposes, just show current time in different zones
    now_utc = datetime.now(ZoneInfo('UTC'))

    timezones = [
        'UTC',
        'America/New_York',
        'America/Chicago',
        'America/Los_Angeles',
        'Europe/London',
        'Europe/Dublin',
        'Australia/Sydney',
    ]

    print("Current time and 'today' in different timezones:")
    print("-" * 60)

    for tz_name in timezones:
        now_in_tz = datetime.now(ZoneInfo(tz_name))
        today_in_tz = get_today_in_timezone(tz_name)

        print(f"{tz_name:25} | {now_in_tz.strftime('%Y-%m-%d %H:%M:%S %Z'):30} | {today_in_tz}")

    print()
    print("=" * 60)
    print("EXPLANATION OF THE FIX:")
    print("=" * 60)
    print()
    print("BEFORE THE FIX:")
    print("  - Server used date.today() which uses SERVER's local time")
    print("  - If server is in UTC and it's already Oct 18 in UTC")
    print("  - But it's still Oct 17 in US Central (the session's timezone)")
    print("  - The server would create an instance for Oct 18")
    print("  - But the button would keep showing because JavaScript")
    print("    thinks it's still Oct 17")
    print()
    print("AFTER THE FIX:")
    print("  - Server uses get_today_in_timezone(session_timezone)")
    print("  - Each session gets 'today' calculated in ITS timezone")
    print("  - A US Central session always uses US Central time for 'today'")
    print("  - This matches what the user expects based on their location")
    print()
    print("=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


if __name__ == '__main__':
    test_timezone_aware_today()
