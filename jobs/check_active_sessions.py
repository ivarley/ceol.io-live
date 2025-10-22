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
from datetime import datetime

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_session_manager import update_active_sessions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run the active session check."""
    logger.info("=" * 80)
    logger.info("Starting active session check")
    logger.info(f"Current UTC time: {datetime.utcnow().isoformat()}")
    logger.info("=" * 80)

    try:
        stats = update_active_sessions()

        logger.info("-" * 80)
        logger.info("Active session check completed successfully")
        logger.info(f"Activated: {len(stats['activated'])} sessions")
        if stats['activated']:
            for item in stats['activated']:
                logger.info(f"  - {item['session_name']} (session_id={item['session_id']}, "
                          f"instance_id={item['instance_id']})")

        logger.info(f"Deactivated: {len(stats['deactivated'])} sessions")
        if stats['deactivated']:
            for item in stats['deactivated']:
                logger.info(f"  - {item['session_name']} (session_id={item['session_id']}, "
                          f"instance_id={item['instance_id']})")

        logger.info(f"Errors: {len(stats['errors'])}")
        if stats['errors']:
            for item in stats['errors']:
                logger.error(f"  - Session {item['session_id']}: {item['error']}")

        logger.info("=" * 80)

        # Exit with error code if there were errors
        if stats['errors']:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error during active session check: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
