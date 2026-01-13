#!/usr/bin/env python3
"""
Check Active Sessions - Cron Job Script

This script is run every 15 minutes (at :14, :29, :44, :59 past each hour) to check
which session instances should be active based on their recurrence patterns, timezones,
and buffer windows.

It uses a 1-minute lookahead to ensure sessions scheduled for round times become
active right at that time (e.g., sessions at 7:00pm become active when this runs at 6:59pm).
"""

import sys
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
# In production on Render, env vars should be set in the dashboard
load_dotenv()

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_session_manager import update_active_sessions, auto_create_scheduled_instances

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run the active session check and auto-creation."""
    logger.info("=" * 80)
    logger.info("Starting active session check")
    logger.info(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 80)

    has_errors = False

    try:
        # Update active status for session instances
        active_stats = update_active_sessions()

        logger.info("-" * 80)
        logger.info("Active session check completed")
        logger.info(f"Activated: {len(active_stats['activated'])} sessions")
        if active_stats['activated']:
            for item in active_stats['activated']:
                logger.info(f"  - {item['session_name']} (session_id={item['session_id']}, "
                          f"instance_id={item['instance_id']})")

        logger.info(f"Deactivated: {len(active_stats['deactivated'])} sessions")
        if active_stats['deactivated']:
            for item in active_stats['deactivated']:
                logger.info(f"  - {item['session_name']} (session_id={item['session_id']}, "
                          f"instance_id={item['instance_id']})")

        if active_stats['errors']:
            has_errors = True
            logger.info(f"Errors: {len(active_stats['errors'])}")
            for item in active_stats['errors']:
                logger.error(f"  - Session {item['session_id']}: {item['error']}")

        # Auto-create upcoming instances for configured sessions
        logger.info("-" * 80)
        logger.info("Running auto-create for scheduled instances")

        auto_stats = auto_create_scheduled_instances()

        total_auto_created = sum(item['instances_created'] for item in auto_stats['auto_created'])
        logger.info(f"Auto-created: {total_auto_created} instances")
        if auto_stats['auto_created']:
            for item in auto_stats['auto_created']:
                logger.info(f"  - {item['session_name']} (session_id={item['session_id']}): "
                          f"{item['instances_created']} instances on {', '.join(item['dates'])}")

        if auto_stats['errors']:
            has_errors = True
            logger.info(f"Auto-create errors: {len(auto_stats['errors'])}")
            for item in auto_stats['errors']:
                logger.error(f"  - Session {item['session_id']}: {item['error']}")

        logger.info("=" * 80)

        # Exit with error code if there were errors
        if has_errors:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error during active session check: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
