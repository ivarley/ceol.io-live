#!/usr/bin/env python3
"""
Finish recording ingests nobody is working on - Cron Job Script (spec 050)

Uploading audio starts a background thread on the web dyno, which is fast and
usually enough. It is not a guarantee: Render's free tier idles a web service out
after ~15 minutes without traffic, so closing the tab on a long recording can put
the dyno to sleep mid-transcode, and a deploy does the same thing. The row is
left saying 'processing' while nothing is processing it.

This is the safety net. Every ten minutes it looks for recordings that are either
waiting to start or were abandoned by a run that has stopped heartbeating, claims
them, and finishes the job here instead. That is what makes it safe to upload
something and walk away.

Runs the ingest SYNCHRONOUSLY -- in a cron process the work is the point, and
there is nothing to return to.

Needs the AWS_* variables as well as the PG* ones: without object storage it can
download nothing, and every sweep would quietly do nothing at all.
"""

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
from services.recording_ingest import (  # noqa: E402
    MAX_INGEST_ATTEMPTS,
    abandon_exhausted_recordings,
    find_pending_recordings,
    ingest_recording,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# How many to take in one run. Ingest is minutes per recording and the cron comes
# round every ten, so a small number keeps one long file from eating a window
# that a second upload is waiting in.
BATCH_SIZE = 2


def main():
    logger.info("=" * 80)
    logger.info("Sweeping for unfinished recording ingests")
    logger.info(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 80)

    # Check this first: without object storage every claim below would burn an
    # attempt on a download that cannot work, and three sweeps would exhaust the
    # budget of a perfectly good recording for a reason that has nothing to do
    # with it.
    problem = rec.check_configured()
    if problem:
        logger.error("Cannot sweep: %s", problem)
        logger.error("Set the AWS_* variables on this cron service; nothing was attempted.")
        return 1

    abandoned = abandon_exhausted_recordings()
    for recording_id in abandoned:
        logger.warning(
            "Recording %s has used all %s attempts; marked failed for a human to look at",
            recording_id, MAX_INGEST_ATTEMPTS,
        )

    pending = find_pending_recordings(limit=BATCH_SIZE)
    if not pending:
        logger.info("Nothing to do.")
        return 0

    logger.info("Found %d recording(s) to finish", len(pending))

    processed = 0
    for item in pending:
        logger.info(
            "Ingesting recording %s (%s) — attempt %s of %s",
            item["recording_id"], item["label"] or "unlabelled",
            item["attempts"] + 1, MAX_INGEST_ATTEMPTS,
        )
        try:
            # Claims internally and returns immediately if the web dyno picked it
            # back up between our query and now -- a race worth losing.
            ingest_recording(item["recording_id"])
            processed += 1
        except Exception:
            # ingest_recording records its own failure on the row; this is only
            # so one bad recording cannot stop the rest of the batch.
            logger.exception("Recording %s raised out of ingest", item["recording_id"])

    logger.info("Swept %d recording(s)", processed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
