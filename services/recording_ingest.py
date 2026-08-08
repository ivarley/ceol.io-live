"""Turn an uploaded audio file into a segmentable recording (spec 050).

The CLI importer does probe -> peaks -> proxy -> upload -> INSERT in one breath,
because it runs on a laptop with the file already on disk. In-app upload cannot:
the browser has put the audio in S3 and the row already exists, and the same
pipeline now has to run on the server, where it takes minutes on a long file.

So it runs in the background and the row carries its state:

    queued -> processing -> ready      the normal path
    queued -> processing -> failed     status_detail says what broke

Still not a broker-backed job queue -- there is no worker dyno, and this fires a
few times a week -- but it no longer depends on anyone watching. The thread is
the fast path; a ten-minute cron (jobs/process_pending_recordings.py) is the
safety net, and the two coordinate through the row itself:

  * **A heartbeat, not an inference.** Whoever is running an ingest refreshes
    `ingest_heartbeat_at` every 30 seconds. Liveness used to be read off
    last_modified_date, which only moves at stage boundaries -- Waveform and
    Proxy each run for minutes on a long file -- so "presumed dead" had to be two
    hours or a live run would be reaped. With a real heartbeat it is 90 seconds.
  * **A claim, not a check-then-act.** claim_recording_for_ingest is one
    conditional UPDATE, so the web thread and the cron cannot both take the same
    recording however their timing lines up.
  * **A budget.** ingest_attempts caps automatic retries, so a file ffmpeg simply
    cannot read fails visibly instead of being re-attempted every ten minutes
    forever.

This is the same shape as the spec-031 merge scan (tune_merge_scan.heartbeat_at,
HEARTBEAT_STALE_SECONDS, claim-or-skip), deliberately: one mechanism in the
codebase for "long job, thread plus cron, might get killed".

Only one ingest runs at a time per process (_SLOT). Two three-hour transcodes at
once on a 512MB dyno is how you find out what the OOM killer does to a Flask
worker.
"""

import base64
import logging
import os
import shutil
import tempfile
import threading

logger = logging.getLogger(__name__)

# One at a time. Additional uploads queue on this rather than running concurrently.
_SLOT = threading.Semaphore(1)

# An ingest whose heartbeat is older than this is presumed dead and may be
# claimed by someone else. 90s matches spec 031's HEARTBEAT_STALE_SECONDS: three
# missed 30-second beats, which is slack enough for a stalled dyno or a slow
# query without being long enough to leave a stranded upload sitting there.
HEARTBEAT_STALE_SECONDS = 90

# How often the running ingest says it is still alive.
HEARTBEAT_INTERVAL_SECONDS = 30

# Automatic attempts before a recording is left alone. The sweeper re-runs
# anything stale, so without this a file ffmpeg cannot read would be retried
# every ten minutes for ever. Three is enough to ride out a deploy or a dyno
# sleeping mid-run, and few enough that a genuinely broken file fails visibly.
# An explicit Retry from the UI resets the count -- a person choosing to try
# again is a different event from a machine looping.
MAX_INGEST_ATTEMPTS = 3


# -----------------------------------------------------------------------------
# The stages, defined once
# -----------------------------------------------------------------------------
# Ingest is a fixed sequence and takes long enough on a real recording that "how
# far along is it" is a fair question. The stages are declared here rather than
# inferred in the browser from prose, so the progress display cannot drift from
# what the pipeline actually does.
#
# `detail` is the sentence shown to the operator; `label` is the one word under
# the circle. Several details can share a step -- queuing and waiting for the
# slot are one wait as far as anyone watching is concerned, and encoding then
# uploading the proxy are one "Proxy".
DETAIL_QUEUED = "Queued"
# Set when the fast-path thread could not be started (or died before it began).
# Reads as progress rather than breakage, because the sweeper will pick it up.
DETAIL_WAITING_FOR_SWEEP = "Waiting to be picked up"
DETAIL_WAITING = "Waiting for a free slot"
DETAIL_DOWNLOADING = "Downloading from object storage"
DETAIL_PROBING = "Reading the audio"
DETAIL_PEAKS = "Computing the waveform"
DETAIL_ENCODING = "Encoding the playback proxy"
DETAIL_UPLOADING = "Uploading the playback proxy"

INGEST_STEPS = ["Queued", "Download", "Inspect", "Waveform", "Proxy", "Ready"]

_STEP_OF_DETAIL = {
    DETAIL_QUEUED: 0,
    DETAIL_WAITING_FOR_SWEEP: 0,
    DETAIL_WAITING: 0,
    DETAIL_DOWNLOADING: 1,
    DETAIL_PROBING: 2,
    DETAIL_PEAKS: 3,
    DETAIL_ENCODING: 4,
    DETAIL_UPLOADING: 4,
}

# A failure is recorded as "<the detail it died on> — <the error>", so the step
# survives into the failed row and the display can mark WHICH circle broke.
# Exact-matching the prefix, not fuzzy-matching prose: both sides are written here.
FAILURE_SEPARATOR = " — "


def step_index_for(detail):
    """Which stage a status_detail describes, or None if it isn't one of ours.

    None is normal for rows written before this existed, and the UI falls back
    to showing the sentence on its own.
    """
    if not detail:
        return None
    return _STEP_OF_DETAIL.get(detail.split(FAILURE_SEPARATOR, 1)[0])


def _set_status(conn, recording_id, status, detail=None):
    cur = conn.cursor()
    cur.execute(
        "UPDATE recording SET status = %s, status_detail = %s, "
        "ingest_heartbeat_at = (NOW() AT TIME ZONE 'UTC') WHERE recording_id = %s",
        (status, detail, recording_id),
    )
    conn.commit()


def claim_recording_for_ingest(recording_id):
    """Take ownership of a recording's ingest. True if we got it.

    One conditional UPDATE rather than a read followed by a write: the web
    thread and the sweeper cron both come through here, and check-then-act would
    let two of them start the same three-hour transcode whenever their timing
    lined up. A row is claimable when it is waiting ('queued') or when whoever
    had it has stopped saying they are alive.

    Claiming spends an attempt. That is deliberate even though it counts a run
    that then succeeds: the budget is there to stop a file being retried for
    ever, and only a completed ingest or a human Retry clears it.
    """
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE recording
               SET status = 'processing',
                   ingest_heartbeat_at = (NOW() AT TIME ZONE 'UTC'),
                   ingest_attempts = ingest_attempts + 1
             WHERE recording_id = %s
               AND (status = 'queued'
                    OR (status = 'processing'
                        AND (ingest_heartbeat_at IS NULL
                             OR ingest_heartbeat_at
                                < (NOW() AT TIME ZONE 'UTC') - make_interval(secs => %s))))
            RETURNING recording_id
            """,
            (recording_id, HEARTBEAT_STALE_SECONDS),
        )
        claimed = cur.fetchone() is not None
        conn.commit()
        return claimed
    finally:
        conn.close()


class _Heartbeat:
    """Says "still alive" every 30s for as long as an ingest is running.

    A separate ticker rather than beats sprinkled through the pipeline: the two
    long stages are single calls into recording.py (compute_peaks,
    transcode_for_streaming) that block for minutes, and threading a callback
    into them would mean changing code the CLI importer shares for a reason that
    is purely about the server.

    Its own connection, because the ingest's connection is busy and psycopg2
    connections are not thread-safe to share.
    """

    def __init__(self, recording_id):
        self.recording_id = recording_id
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        from database import get_db_connection

        while not self._stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            try:
                conn = get_db_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE recording SET ingest_heartbeat_at = (NOW() AT TIME ZONE 'UTC') "
                        "WHERE recording_id = %s",
                        (self.recording_id,),
                    )
                    conn.commit()
                finally:
                    conn.close()
            except Exception:
                # A missed beat is survivable -- three in a row is what marks a
                # run dead, and the next tick may well succeed. Never let this
                # take down the ingest it is only reporting on.
                logger.warning("heartbeat failed for recording %s", self.recording_id, exc_info=True)

    def __enter__(self):
        self._thread = threading.Thread(
            target=self._run, name=f"ingest-heartbeat-{self.recording_id}", daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        return False


def ingest_recording(recording_id, user_id=None):
    """Fill in everything the segmenter needs for an already-uploaded recording.

    Downloads the master back from S3, probes it, computes the waveform envelope,
    transcodes and uploads the playback proxy, and marks the row ready. Safe to
    re-run: every step overwrites, and the proxy lands on a key derived from the
    master's, so a retry replaces rather than accumulates.

    Runs on a background thread (see start_ingest) or in the sweeper cron, and
    therefore opens its own connection and touches no request state.

    Claims the row first and returns immediately if it cannot: whoever holds a
    live claim is already doing this work.
    """
    import recording as rec
    from database import get_db_connection, save_to_history

    if not claim_recording_for_ingest(recording_id):
        logger.info("ingest: recording %s is already being processed; leaving it alone", recording_id)
        return

    workdir = None
    # Tracks the stage in flight so a failure can say where it happened, both in
    # the message and by marking the right circle.
    stage = DETAIL_QUEUED
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT storage_key, mime_type, label FROM recording WHERE recording_id = %s",
            (recording_id,),
        )
        row = cur.fetchone()
        if not row:
            logger.warning("ingest: recording %s vanished before it could be processed", recording_id)
            return
        storage_key, mime_type, label = row

        stage = DETAIL_WAITING
        _set_status(conn, recording_id, "processing", stage)

        # The beat starts before _SLOT, so a run queued behind another ingest is
        # not mistaken for a dead one while it waits its turn.
        with _Heartbeat(recording_id), _SLOT:
            workdir = tempfile.mkdtemp(prefix=f"ingest-{recording_id}-")
            local_path = os.path.join(workdir, os.path.basename(storage_key) or "audio")

            stage = DETAIL_DOWNLOADING
            _set_status(conn, recording_id, "processing", stage)
            rec.download_recording(storage_key, local_path)
            size = os.path.getsize(local_path)

            stage = DETAIL_PROBING
            _set_status(conn, recording_id, "processing", stage)
            info = rec.probe_audio(local_path)

            # The duration on the row until now was whatever the browser read off
            # the file's own metadata, which for a VBR MP3 without a Xing header
            # can be badly wrong. This one comes from the container, so it wins.
            stage = DETAIL_PEAKS
            _set_status(conn, recording_id, "processing", stage)
            peaks, peaks_hz = rec.compute_peaks(local_path)

            stage = DETAIL_ENCODING
            _set_status(conn, recording_id, "processing", stage)
            stream_path = os.path.join(workdir, "proxy" + rec.STREAM_SUFFIX)
            rec.transcode_for_streaming(local_path, stream_path)
            stream_size = os.path.getsize(stream_path)

            stream_key = storage_key + rec.STREAM_SUFFIX
            stage = DETAIL_UPLOADING
            _set_status(conn, recording_id, "processing", stage)
            rec.upload_recording(stream_path, stream_key, mime_type=rec.STREAM_MIME)

            cur = conn.cursor()
            save_to_history(cur, "recording", "UPDATE", recording_id, user_id)
            cur.execute(
                """
                UPDATE recording
                   SET duration_ms = %s, file_size_bytes = %s, sample_rate = %s, channels = %s,
                       peaks = %s, peaks_hz = %s,
                       stream_key = %s, stream_mime_type = %s, stream_size_bytes = %s,
                       status = 'ready', status_detail = NULL,
                       -- Finishing clears the budget: the next Retry, if there
                       -- ever is one, starts from a full count rather than
                       -- inheriting however many goes this took.
                       ingest_attempts = 0, ingest_heartbeat_at = NULL,
                       last_modified_user_id = COALESCE(%s, last_modified_user_id)
                 WHERE recording_id = %s
                """,
                (
                    info["duration_ms"], size, info["sample_rate"], info["channels"],
                    base64.b64encode(peaks).decode("ascii"), peaks_hz,
                    stream_key, rec.STREAM_MIME, stream_size,
                    user_id, recording_id,
                ),
            )
            conn.commit()

        logger.info(
            "ingest: recording %s (%s) ready — %.1f min, %d peak buckets, proxy %.1f MB",
            recording_id, label, info["duration_ms"] / 60000.0, len(peaks), stream_size / 1e6,
        )
    except Exception as exc:
        logger.exception("ingest: recording %s failed", recording_id)
        try:
            conn.rollback()
            # Prefixed with the stage so the failure says WHERE it broke, which
            # is most of the diagnosis: "Download — ..." and "Proxy — ..." point
            # at completely different problems. Kept short enough to read in a
            # table cell; the traceback is in the server log for anything more.
            reason = str(exc)[:500] or exc.__class__.__name__
            _set_status(conn, recording_id, "failed", f"{stage}{FAILURE_SEPARATOR}{reason}")
        except Exception:
            logger.exception("ingest: could not even record the failure for recording %s", recording_id)
    finally:
        conn.close()
        if workdir:
            # The master and the proxy together can be 400MB of ephemeral disk.
            shutil.rmtree(workdir, ignore_errors=True)


def find_pending_recordings(limit=2):
    """Recordings that need ingesting and nobody live is working on.

    The sweeper's whole query: waiting to start, or abandoned by a run that has
    stopped beating, and still inside the retry budget. Ordered oldest first so a
    recording cannot be starved by newer uploads, and limited so one large file
    cannot eat a whole cron window.
    """
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT recording_id, label, ingest_attempts
              FROM recording
             WHERE (status = 'queued'
                    OR (status = 'processing'
                        AND (ingest_heartbeat_at IS NULL
                             OR ingest_heartbeat_at
                                < (NOW() AT TIME ZONE 'UTC') - make_interval(secs => %s))))
               AND ingest_attempts < %s
             ORDER BY created_date
             LIMIT %s
            """,
            (HEARTBEAT_STALE_SECONDS, MAX_INGEST_ATTEMPTS, limit),
        )
        return [
            {"recording_id": r[0], "label": r[1], "attempts": r[2]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def abandon_exhausted_recordings():
    """Mark rows that have used up their attempts as failed. Returns how many.

    Without this they would sit at 'processing' forever, looking busy while
    nothing is working on them -- the exact state this whole mechanism exists to
    get rid of. Saying so plainly, with the count, is what tells an operator this
    needs a human rather than more waiting.
    """
    from database import get_db_connection

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE recording
               SET status = 'failed',
                   status_detail = %s
             WHERE status IN ('queued', 'processing')
               AND ingest_attempts >= %s
               AND (ingest_heartbeat_at IS NULL
                    OR ingest_heartbeat_at
                       < (NOW() AT TIME ZONE 'UTC') - make_interval(secs => %s))
            RETURNING recording_id
            """,
            (
                f"Gave up after {MAX_INGEST_ATTEMPTS} attempts — "
                "check the server log, then use Retry to try again.",
                MAX_INGEST_ATTEMPTS,
                HEARTBEAT_STALE_SECONDS,
            ),
        )
        abandoned = [r[0] for r in cur.fetchall()]
        conn.commit()
        return abandoned
    finally:
        conn.close()


def start_ingest(recording_id, user_id=None):
    """Kick off ingest_recording on a daemon thread and return immediately.

    The FAST PATH, not the guarantee. A daemon thread means a shutdown is never
    held up by an in-flight transcode, and the sweeper cron picks up whatever a
    shutdown interrupted -- so this is free to be best-effort.
    """
    try:
        thread = threading.Thread(
            target=ingest_recording,
            args=(recording_id, user_id),
            name=f"ingest-recording-{recording_id}",
            daemon=True,
        )
        thread.start()
        return thread
    except Exception:
        # Out of threads, or a runtime that will not spawn one. Not fatal any
        # more: the row is already 'queued', so say what is going to happen and
        # let the sweeper do it.
        logger.exception("ingest: could not start a thread for recording %s; leaving it queued", recording_id)
        try:
            from database import get_db_connection

            conn = get_db_connection()
            try:
                _set_status(conn, recording_id, "queued", DETAIL_WAITING_FOR_SWEEP)
            finally:
                conn.close()
        except Exception:
            logger.exception("ingest: could not even mark recording %s as waiting", recording_id)
        return None
