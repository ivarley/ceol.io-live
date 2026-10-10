#!/usr/bin/env python3
"""
Publish the phone's decider file - weekly, riding along on the active-sessions cron

The app decides what tune is playing on the phone itself (spec 053, "Listening
on the phone, offline"), from a file built from thesession.org's corpus. This
rebuilds it from each Sunday's dump and publishes it for the app to fetch
(services/decider_data_service.py), after the merge sync's Monday 06:00 window.

Gated on when the published manifest was last checked: due once each week from
Monday 07:00 UTC, so a missed Monday is caught up at the next run. An unchanged
week (the same dump, repertoire and configuration) builds nothing and only
records the check. Without object storage configured it does nothing, quietly:
the cron service needs AWS_S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
(and AWS_S3_REGION) for this, the same values as the web service's.

Run by hand, now, whatever the schedule:

    python3 jobs/publish_decider_data.py [--force]
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection  # noqa: E402

logger = logging.getLogger(__name__)


def run_weekly_if_due(now_utc=None):
    """Rebuild and publish if this week's check hasn't been done. Returns True
    if a check ran."""
    from recording import check_configured
    from services import decider_data_service as dd

    if check_configured():
        return False
    from lab.corpus.decider_file import FORMAT_VERSION

    if not dd.is_due(dd.current_manifest(FORMAT_VERSION), now_utc):
        return False
    logger.info("the phone's decider file is due a weekly check; running it")
    run(force=False)
    return True


def run(force=False):
    conn = get_db_connection()
    try:
        from services import decider_data_service as dd

        outcome, manifest = dd.rebuild_and_publish(conn, force=force)
    finally:
        conn.close()
    logger.info(
        f"decider data {outcome}: {manifest['key']} built {manifest['built_at']}, "
        f"checked {manifest['checked_at']}"
    )
    return outcome


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    from recording import check_configured

    problem = check_configured()
    if problem:
        logger.error(problem)
        return 1
    run(force="--force" in sys.argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
