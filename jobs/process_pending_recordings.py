#!/usr/bin/env python3
"""
Finish recording ingests nobody is working on - manual tool (spec 050)

NOT a cron job. This was declared as one in render.yaml and never created, so
the safety net it describes was a comment for its whole life -- and the reason
given for it was wrong anyway. It said Render's free tier idles a web service
out after ~15 minutes; ceol.io-live is on starter and does not idle. What
actually kills an in-flight ingest is the process restarting: a deploy, an OOM,
or gunicorn recycling a worker at max_requests.

So the sweep lives in the web service now (services/recording_ingest.py's
start_sweeper, started from gunicorn.conf.py's post_fork). Every event that can
interrupt an ingest is followed by a worker booting, which is exactly when a
sweep is worth running -- a deploy-killed transcode resumes seconds later
instead of waiting out a ten-minute cron window, and it costs nothing.

This file remains as the way to run a sweep by hand: from a Render shell when
something is stuck, or locally against a real database. The logic is the same
function the web service calls, so running it here tells you what happens there.

    python3 jobs/process_pending_recordings.py          # sweep one recording
    python3 jobs/process_pending_recordings.py --limit 5

Runs the ingest SYNCHRONOUSLY -- here the work is the point, and there is
nothing to return to.

Needs the AWS_* variables as well as the PG* ones: without object storage it can
download nothing, and the sweep would quietly do nothing at all. It says so and
exits non-zero rather than pretending to work.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

# Load environment variables from .env file (for local development).
# In production on Render, env vars are set in the dashboard.
load_dotenv()

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import recording as rec  # noqa: E402
from services.recording_ingest import sweep_once  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=1,
        help="How many recordings to finish in this run (default 1). Ingest is "
             "minutes per recording and two at once share the box's memory, so "
             "raise this only when you are clearing a backlog by hand.",
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("Sweeping for unfinished recording ingests")
    logger.info(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 80)

    # sweep_once checks this too and skips quietly, which is right for a
    # background thread and wrong for someone who just ran a command: say it
    # plainly and fail.
    problem = rec.check_configured()
    if problem:
        logger.error("Cannot sweep: %s", problem)
        logger.error("Set the AWS_* variables for this environment; nothing was attempted.")
        return 1

    swept = sweep_once(limit=args.limit)
    logger.info("Swept %d recording(s)", swept)
    return 0


if __name__ == "__main__":
    sys.exit(main())
