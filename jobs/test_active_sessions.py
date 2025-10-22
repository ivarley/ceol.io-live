#!/usr/bin/env python3
"""
Test Active Sessions - Development Testing Wrapper

This script provides a flexible testing interface for the active session cron job.
It allows testing against different databases, simulating different times, and
running in dry-run mode to see what would happen without making changes.

Usage:
    # Basic test against test database
    python3 jobs/test_active_sessions.py

    # Dry run against production (safe - no changes made)
    python3 jobs/test_active_sessions.py --prod-db --dry-run

    # Simulate running at a specific time
    python3 jobs/test_active_sessions.py --simulate-time "2025-10-23 18:59:00"

    # Set up test data and run
    python3 jobs/test_active_sessions.py --setup-test-data

    # Run a specific scenario
    python3 jobs/test_active_sessions.py --scenario evening
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timedelta
from typing import Optional

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def setup_environment(use_test_db: bool):
    """
    Set up environment variables for testing.

    Args:
        use_test_db: If True, load test database config. Otherwise use production.
    """
    if use_test_db:
        # Load test environment variables
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.test')
        if os.path.exists(env_file):
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print(f"{Colors.OKCYAN}✓ Loaded test database configuration{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}⚠ .env.test not found, using current environment{Colors.ENDC}")
    else:
        # Load production environment variables
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_file):
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print(f"{Colors.WARNING}⚠ Loaded PRODUCTION database configuration{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ .env not found{Colors.ENDC}")


def simulate_time(target_time: str):
    """
    Monkey-patch datetime to simulate running at a specific time.

    Args:
        target_time: ISO format datetime string (YYYY-MM-DD HH:MM:SS)
    """
    from unittest.mock import Mock, patch
    import datetime as dt

    # Parse the target time
    simulated_datetime = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")

    print(f"{Colors.OKCYAN}⏰ Simulating time: {simulated_datetime.isoformat()}{Colors.ENDC}")

    # Create a mock datetime class that returns our simulated time
    class MockDatetime(dt.datetime):
        @classmethod
        def utcnow(cls):
            return simulated_datetime.replace(tzinfo=None)

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return simulated_datetime
            return simulated_datetime.replace(tzinfo=tz)

    # Patch the datetime module in active_session_manager
    import active_session_manager
    active_session_manager.datetime = MockDatetime

    return simulated_datetime


def setup_test_data():
    """Create sample test data for testing the cron job."""
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}Setting Up Test Data{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    try:
        from test_scenarios import create_test_scenarios
        create_test_scenarios()
        print(f"{Colors.OKGREEN}✓ Test data created successfully{Colors.ENDC}")
    except ImportError:
        print(f"{Colors.FAIL}✗ test_scenarios.py not found. Run without --setup-test-data.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.FAIL}✗ Error creating test data: {e}{Colors.ENDC}")
        sys.exit(1)


def run_scenario(scenario: str):
    """
    Run a predefined test scenario.

    Args:
        scenario: Name of scenario ('evening', 'morning', 'overlap')
    """
    scenarios = {
        'evening': {
            'time': (datetime.now().replace(hour=18, minute=59, second=0)).strftime("%Y-%m-%d %H:%M:%S"),
            'description': 'Evening sessions starting (7pm sessions activate at 6:59pm)'
        },
        'morning': {
            'time': (datetime.now().replace(hour=9, minute=0, second=0)).strftime("%Y-%m-%d %H:%M:%S"),
            'description': 'Morning cleanup (deactivate overnight sessions)'
        },
        'overlap': {
            'time': (datetime.now().replace(hour=20, minute=30, second=0)).strftime("%Y-%m-%d %H:%M:%S"),
            'description': 'Overlapping sessions (multiple active at once)'
        }
    }

    if scenario not in scenarios:
        print(f"{Colors.FAIL}✗ Unknown scenario: {scenario}{Colors.ENDC}")
        print(f"Available scenarios: {', '.join(scenarios.keys())}")
        sys.exit(1)

    config = scenarios[scenario]
    print(f"{Colors.OKCYAN}📋 Running scenario: {scenario}{Colors.ENDC}")
    print(f"   {config['description']}")

    return config['time']


def print_summary(stats: dict, dry_run: bool):
    """
    Print a formatted summary of the cron job results.

    Args:
        stats: Statistics dictionary from update_active_sessions
        dry_run: Whether this was a dry run
    """
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}Summary{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    if dry_run:
        print(f"{Colors.WARNING}🔍 DRY RUN MODE - No changes were made to the database{Colors.ENDC}\n")

    # Activated sessions
    if stats['activated']:
        print(f"{Colors.OKGREEN}✓ Activated {len(stats['activated'])} session(s):{Colors.ENDC}")
        for item in stats['activated']:
            print(f"  • {item['session_name']} (session_id={item['session_id']}, instance_id={item['instance_id']})")
        print()
    else:
        print(f"  No sessions activated\n")

    # Deactivated sessions
    if stats['deactivated']:
        print(f"{Colors.OKCYAN}✓ Deactivated {len(stats['deactivated'])} session(s):{Colors.ENDC}")
        for item in stats['deactivated']:
            print(f"  • {item['session_name']} (session_id={item['session_id']}, instance_id={item['instance_id']})")
        print()
    else:
        print(f"  No sessions deactivated\n")

    # Errors
    if stats['errors']:
        print(f"{Colors.FAIL}✗ {len(stats['errors'])} error(s):{Colors.ENDC}")
        for item in stats['errors']:
            print(f"  • Session {item['session_id']}: {item['error']}")
        print()

    # Overall status
    if not stats['activated'] and not stats['deactivated'] and not stats['errors']:
        print(f"{Colors.OKBLUE}ℹ No changes needed{Colors.ENDC}")


def run_dry_run_check():
    """
    Run the active session check in dry-run mode (no database changes).

    Returns:
        Statistics dictionary
    """
    print(f"{Colors.WARNING}Running in DRY RUN mode - simulating changes only{Colors.ENDC}\n")

    # Import and mock the database operations
    from unittest.mock import patch
    import active_session_manager

    # Track what would have been changed
    dry_run_stats = {
        'activated': [],
        'deactivated': [],
        'errors': []
    }

    # Mock the activate/deactivate functions to just log
    original_activate = active_session_manager.activate_session_instance
    original_deactivate = active_session_manager.deactivate_session_instance

    def mock_activate(session_id, instance_id, conn=None):
        print(f"  {Colors.OKGREEN}[DRY RUN] Would activate session {session_id}, instance {instance_id}{Colors.ENDC}")
        # Don't actually call the original function

    def mock_deactivate(session_id, instance_id, conn=None):
        print(f"  {Colors.OKCYAN}[DRY RUN] Would deactivate session {session_id}, instance {instance_id}{Colors.ENDC}")
        # Don't actually call the original function

    active_session_manager.activate_session_instance = mock_activate
    active_session_manager.deactivate_session_instance = mock_deactivate

    try:
        stats = active_session_manager.update_active_sessions()
    finally:
        # Restore original functions
        active_session_manager.activate_session_instance = original_activate
        active_session_manager.deactivate_session_instance = original_deactivate

    return stats


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(
        description='Test wrapper for active session cron job',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test against test database
  python3 jobs/test_active_sessions.py

  # Dry run against production (safe)
  python3 jobs/test_active_sessions.py --prod-db --dry-run

  # Simulate evening sessions starting
  python3 jobs/test_active_sessions.py --scenario evening

  # Simulate specific time
  python3 jobs/test_active_sessions.py --simulate-time "2025-10-23 18:59:00"

  # Set up test data first
  python3 jobs/test_active_sessions.py --setup-test-data
        """
    )

    parser.add_argument(
        '--prod-db',
        action='store_true',
        help='Use production database (default: test database)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would happen without making changes'
    )

    parser.add_argument(
        '--simulate-time',
        type=str,
        metavar='DATETIME',
        help='Simulate running at specific time (format: "YYYY-MM-DD HH:MM:SS")'
    )

    parser.add_argument(
        '--scenario',
        type=str,
        choices=['evening', 'morning', 'overlap'],
        help='Run a predefined test scenario'
    )

    parser.add_argument(
        '--setup-test-data',
        action='store_true',
        help='Create sample test data before running'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Print header
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}Active Session Cron Job Tester{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    # Set up environment
    use_test_db = not args.prod_db
    setup_environment(use_test_db)

    # Set up test data if requested
    if args.setup_test_data:
        if not use_test_db:
            print(f"{Colors.FAIL}✗ Cannot set up test data on production database{Colors.ENDC}")
            sys.exit(1)
        setup_test_data()
        print()

    # Handle scenario
    if args.scenario:
        args.simulate_time = run_scenario(args.scenario)
        print()

    # Simulate time if requested
    if args.simulate_time:
        try:
            simulate_time(args.simulate_time)
        except ValueError as e:
            print(f"{Colors.FAIL}✗ Invalid time format: {e}{Colors.ENDC}")
            print(f"Expected format: YYYY-MM-DD HH:MM:SS")
            sys.exit(1)
    else:
        print(f"{Colors.OKBLUE}🕐 Using current system time: {datetime.utcnow().isoformat()}{Colors.ENDC}")

    print()

    # Import the active session manager
    from active_session_manager import update_active_sessions

    # Run the check
    try:
        print(f"{Colors.BOLD}Running active session check...{Colors.ENDC}\n")

        if args.dry_run:
            stats = run_dry_run_check()
        else:
            stats = update_active_sessions()

        # Print summary
        print_summary(stats, args.dry_run)

        # Exit with appropriate code
        if stats['errors']:
            sys.exit(1)

        print(f"\n{Colors.OKGREEN}✓ Test completed successfully{Colors.ENDC}\n")

    except Exception as e:
        print(f"\n{Colors.FAIL}✗ Fatal error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
