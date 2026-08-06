"""Turn an uploaded audio file into a segmentable recording (spec 050).

The CLI importer does probe -> peaks -> proxy -> upload -> INSERT in one breath,
because it runs on a laptop with the file already on disk. In-app upload cannot:
the browser has put the audio in S3 and the row already exists, and the same
pipeline now has to run on the server, where it takes minutes on a long file.

So it runs on a background thread and the row carries its state:

    processing -> ready      the normal path
    processing -> failed     status_detail says what broke; the operator retries

Deliberately not a job queue. There is no worker dyno and no broker, this fires
at most a few times a week, and a thread on the web dyno is the honest size of
the problem. What that costs is stated rather than hidden:

  * A deploy or a restart mid-ingest strands the row in 'processing' forever.
    /admin/recordings can retry it, and RESUMABLE_AFTER_SECONDS below is what
    lets the page offer that rather than spinning indefinitely.
  * Render's free tier idles a service out after ~15 minutes without traffic.
    The upload page polls while it waits, which keeps the dyno awake for as long
    as someone is watching -- and if they close the tab on a long file, that is
    exactly the stranding case above.

Only one ingest runs at a time (_SLOT). Two three-hour transcodes at once on a
512MB dyno is how you find out what the OOM killer does to a Flask worker.
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

# A row that has been 'processing' longer than this is presumed dead -- almost
# always a deploy that killed the thread. Generous, because it is measuring the
# worst case (a three-hour master on a shared-CPU dyno) and calling a live ingest
# dead just makes an operator start a second one on top of it.
RESUMABLE_AFTER_SECONDS = 2 * 60 * 60


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
DETAIL_WAITING = "Waiting for a free slot"
DETAIL_DOWNLOADING = "Downloading from object storage"
DETAIL_PROBING = "Reading the audio"
DETAIL_PEAKS = "Computing the waveform"
DETAIL_ENCODING = "Encoding the playback proxy"
DETAIL_UPLOADING = "Uploading the playback proxy"

INGEST_STEPS = ["Queued", "Download", "Inspect", "Waveform", "Proxy", "Ready"]

_STEP_OF_DETAIL = {
    DETAIL_QUEUED: 0,
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
        "UPDATE recording SET status = %s, status_detail = %s WHERE recording_id = %s",
        (status, detail, recording_id),
    )
    conn.commit()


def ingest_recording(recording_id, user_id=None):
    """Fill in everything the segmenter needs for an already-uploaded recording.

    Downloads the master back from S3, probes it, computes the waveform envelope,
    transcodes and uploads the playback proxy, and marks the row ready. Safe to
    re-run: every step overwrites, and the proxy lands on a key derived from the
    master's, so a retry replaces rather than accumulates.

    Runs on a background thread (see start_ingest) and therefore opens its own
    connection and touches no request state.
    """
    import recording as rec
    from database import get_db_connection, save_to_history

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

        with _SLOT:
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


def start_ingest(recording_id, user_id=None):
    """Kick off ingest_recording on a daemon thread and return immediately.

    Daemon so a shutdown is never held up by an in-flight transcode: the row is
    left 'processing' and retried from the admin page, which is a better outcome
    than a deploy that hangs for twenty minutes.
    """
    thread = threading.Thread(
        target=ingest_recording,
        args=(recording_id, user_id),
        name=f"ingest-recording-{recording_id}",
        daemon=True,
    )
    thread.start()
    return thread
