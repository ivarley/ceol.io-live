"""Recording segmenter API (spec 050).

The write vocabulary is deliberately tiny, because the UI's whole interaction is
one keystroke: "the tune I'm pointing at starts HERE".

    PUT    /api/recordings/<id>/segments/<session_instance_tune_id>   place/move
    DELETE /api/recordings/<id>/segments/<session_instance_tune_id>   unplace

PUT is an upsert keyed on (recording, tune) rather than a create-then-update
pair, so a re-mark of the same tune is the same call as the first mark and the
client never has to track whether a segment already exists.

Getting audio IN is three calls rather than one, because the file never passes
through Flask:

    POST /api/recordings/upload-url    sign a direct-to-S3 PUT
    (the browser uploads to S3 itself)
    POST /api/recordings               confirm it landed; row + background ingest
    GET  /api/recordings/<id>/status   poll while the waveform is built

Every endpoint is system-admin only: this is a data-prep tool for building an ML
training corpus, not a member-facing feature.
"""

import base64
import datetime

from flask import jsonify, request, Response
from flask_login import current_user

from api_auth import api_login_required
from database import get_db_connection, get_current_user_id, save_to_history


def _admin_gate():
    """Returns an error response when the caller isn't a system admin, else None."""
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Admin access required"}), 403
    return None


def _int_or_none(payload, key):
    """Read an optional integer field. Raises ValueError with a usable message."""
    if key not in payload or payload[key] is None:
        return None
    try:
        return int(payload[key])
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be an integer number of milliseconds")


# Audio types the browser can hand us. The list is not about what ffmpeg can
# read -- it reads nearly everything -- but about refusing to sign an upload for
# something that plainly is not audio, since the signed URL is a write to the
# bucket.
_UPLOAD_MIME_BY_EXTENSION = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


def _instance_exists(cur, session_instance_id):
    cur.execute(
        "SELECT 1 FROM session_instance WHERE session_instance_id = %s",
        (session_instance_id,),
    )
    return cur.fetchone() is not None


@api_login_required
def create_recording_upload_url():
    """POST /api/recordings/upload-url — sign a direct-to-S3 upload.

    Body: {"session_instance_id": int, "filename": str, "content_type": str?}

    The browser PUTs the audio to the returned URL itself. It does not come
    through Flask: a three-hour master is ~350MB, and proxying that would hold a
    worker for the whole transfer, spool the file onto the dyno's disk, and end
    up putting it in exactly the same place.

    Nothing is written here — the row is created afterwards by POST
    /api/recordings, once the object is confirmed to exist. An abandoned upload
    therefore leaves an orphaned S3 object and no database row, which is the
    right way round.
    """
    denied = _admin_gate()
    if denied:
        return denied

    import os

    import recording as rec

    problem = rec.check_configured()
    if problem:
        # Verbatim: the message names the missing environment variables, and
        # anything that reshapes it (.capitalize(), say) turns AWS_S3_BUCKET into
        # aws_s3_bucket and throws away the only actionable part.
        return jsonify({"success": False, "error": f"Uploads are unavailable — {problem}"}), 503

    payload = request.get_json(silent=True) or {}
    filename = (payload.get("filename") or "").strip()
    if not filename:
        return jsonify({"success": False, "error": "filename is required"}), 400

    try:
        session_instance_id = int(payload.get("session_instance_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "session_instance_id is required"}), 400

    extension = os.path.splitext(filename)[1].lower()
    if extension not in _UPLOAD_MIME_BY_EXTENSION:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"{extension or 'That file'} isn't an audio type this accepts "
                             f"({', '.join(sorted(_UPLOAD_MIME_BY_EXTENSION))})",
                }
            ),
            400,
        )
    # The extension decides, not the browser's guess: Content-Type is signed into
    # the URL, so it has to match byte for byte what the client then sends, and
    # the client is told which value to use rather than asked.
    content_type = _UPLOAD_MIME_BY_EXTENSION[extension]

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if not _instance_exists(cur, session_instance_id):
            return jsonify({"success": False, "error": "Session instance not found"}), 404
    finally:
        conn.close()

    storage_key = rec.build_storage_key(filename)
    try:
        upload_url = rec.generate_presigned_upload(storage_key, content_type)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 503

    return jsonify(
        {
            "success": True,
            "upload_url": upload_url,
            "storage_key": storage_key,
            "content_type": content_type,
        }
    )


@api_login_required
def create_recording():
    """POST /api/recordings — confirm an upload landed and start ingest.

    Body: {"session_instance_id": int, "storage_key": str, "label": str?,
           "started_at": ISO8601 with offset?, "person_id": int?,
           "duration_ms": int?, "notes": str?}

    Creates the row immediately and returns, rather than waiting: probing,
    computing the envelope and encoding the proxy take minutes on a long file.
    The row starts as 'processing' and a background thread fills the rest in
    (services/recording_ingest).
    """
    denied = _admin_gate()
    if denied:
        return denied

    import recording as rec
    from services.recording_ingest import start_ingest

    payload = request.get_json(silent=True) or {}

    try:
        session_instance_id = int(payload.get("session_instance_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "session_instance_id is required"}), 400

    storage_key = (payload.get("storage_key") or "").strip()
    if not storage_key:
        return jsonify({"success": False, "error": "storage_key is required"}), 400
    # Only keys this app minted. Signing is admin-gated anyway, but it keeps a
    # typo from attaching some unrelated object in the bucket to a session.
    if not storage_key.startswith("recordings/"):
        return jsonify({"success": False, "error": "That isn't an upload key from this app"}), 400

    started_at = None
    if payload.get("started_at"):
        try:
            started_at = datetime.datetime.fromisoformat(str(payload["started_at"]).replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"success": False, "error": "started_at must be an ISO-8601 timestamp"}), 400
        if started_at.tzinfo is None:
            # Same rule the CLI importer enforces: without an offset the anchor
            # is ambiguous, and being wrong by a timezone silently misaligns
            # every absolute timestamp in the export.
            return jsonify({"success": False, "error": "started_at needs a UTC offset"}), 400

    try:
        person_id = _int_or_none(payload, "person_id")
        provisional_duration = _int_or_none(payload, "duration_ms")
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    # Confirm the object is actually there before writing a row that claims it
    # is. A cancelled or failed PUT would otherwise surface much later as a
    # segmenter page that loads and then plays nothing.
    try:
        size = rec.stored_object_size(storage_key)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
    if size is None:
        return jsonify({"success": False, "error": "That upload didn't finish — nothing is stored under that key"}), 400

    import os

    label = (payload.get("label") or "").strip() or None
    mime_type = _UPLOAD_MIME_BY_EXTENSION.get(os.path.splitext(storage_key)[1].lower(), "audio/mpeg")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT si.date, s.name FROM session_instance si "
            "JOIN session s ON s.session_id = si.session_id WHERE si.session_instance_id = %s",
            (session_instance_id,),
        )
        instance = cur.fetchone()
        if not instance:
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        if not label:
            label = f"{instance[1]} {instance[0]}"

        # First recording on an instance becomes the clock anchor whether or not
        # it was asked for: an instance timeline with no zero point is
        # meaningless. Later ones sit at offset 0 until someone says otherwise —
        # the multi-recording case has no UI yet (spec 050).
        cur.execute(
            "SELECT 1 FROM recording WHERE session_instance_id = %s AND is_clock_anchor",
            (session_instance_id,),
        )
        is_anchor = cur.fetchone() is None

        user_id = get_current_user_id()

        cur.execute(
            """
            INSERT INTO recording
                (session_instance_id, person_id, label, storage_key, mime_type, duration_ms,
                 file_size_bytes, is_clock_anchor, clock_offset_ms, started_at, notes,
                 status, status_detail, created_by_user_id, last_modified_user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, 'processing', %s, %s, %s)
            RETURNING recording_id
            """,
            (
                session_instance_id, person_id, label, storage_key, mime_type,
                # Provisional: whatever the browser read off the file's metadata,
                # or 1ms when it could not. Ingest replaces it with the container's
                # own duration, and `status` is what tells anyone reading this row
                # not to trust it yet.
                max(1, provisional_duration or 1),
                size, is_anchor, started_at, (payload.get("notes") or "").strip() or None,
                "Queued", user_id, user_id,
            ),
        )
        recording_id = cur.fetchone()[0]
        save_to_history(cur, "recording", "INSERT", recording_id, user_id)
        conn.commit()
    finally:
        conn.close()

    start_ingest(recording_id, user_id)

    return (
        jsonify(
            {
                "success": True,
                "recording_id": recording_id,
                "status": "processing",
                "is_clock_anchor": is_anchor,
                "label": label,
            }
        ),
        201,
    )


@api_login_required
def get_recording_status(recording_id):
    """GET /api/recordings/<id>/status — what ingest is doing, for polling.

    `stalled` means the row has been 'processing' for longer than any real ingest
    takes, which in practice means the thread died with the dyno under it. The
    page offers a retry instead of spinning forever.
    """
    denied = _admin_gate()
    if denied:
        return denied

    from services.recording_ingest import RESUMABLE_AFTER_SECONDS

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, status_detail, duration_ms, (peaks IS NOT NULL) AS has_peaks,
                   (stream_key IS NOT NULL) AS has_proxy, file_size_bytes,
                   EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC') - last_modified_date)
            FROM recording WHERE recording_id = %s
            """,
            (recording_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"success": False, "error": "Recording not found"}), 404

    idle_seconds = float(row[6] or 0)
    return jsonify(
        {
            "success": True,
            "recording_id": recording_id,
            "status": row[0],
            "status_detail": row[1],
            "duration_ms": int(row[2]),
            "has_peaks": row[3],
            "has_proxy": row[4],
            "file_size_bytes": int(row[5]) if row[5] else None,
            "stalled": row[0] == "processing" and idle_seconds > RESUMABLE_AFTER_SECONDS,
        }
    )


@api_login_required
def reprocess_recording(recording_id):
    """POST /api/recordings/<id>/reprocess — run ingest again.

    For the two ways this ends up needed: ingest raised (bad file, S3 hiccup, no
    ffmpeg), or a deploy killed the thread mid-run and left the row 'processing'
    forever. Idempotent — every step of ingest overwrites.
    """
    denied = _admin_gate()
    if denied:
        return denied

    from services.recording_ingest import RESUMABLE_AFTER_SECONDS, start_ingest

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC') - last_modified_date) "
            "FROM recording WHERE recording_id = %s",
            (recording_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Recording not found"}), 404

        # Refuse to stack a second transcode on top of a live one; allow it once
        # the first is old enough to be presumed dead.
        if row[0] == "processing" and float(row[1] or 0) <= RESUMABLE_AFTER_SECONDS:
            return jsonify({"success": False, "error": "That recording is already being processed"}), 409

        cur.execute(
            "UPDATE recording SET status = 'processing', status_detail = %s WHERE recording_id = %s",
            ("Queued", recording_id),
        )
        conn.commit()
    finally:
        conn.close()

    start_ingest(recording_id, get_current_user_id())
    return jsonify({"success": True, "recording_id": recording_id, "status": "processing"})


@api_login_required
def get_session_instances_for_admin(session_id):
    """GET /api/admin/sessions/<id>/instances — dates to attach a recording to.

    Carries the logged-tune count per instance because that is the number that
    decides whether a night is worth uploading: a recording of an instance with
    no log has nothing to segment against.
    """
    denied = _admin_gate()
    if denied:
        return denied

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            -- location_override is the instance's name (spec 047): at a festival
            -- several instances share a date, so it is the only thing that tells
            -- them apart in the picker.
            SELECT si.session_instance_id, si.date, si.location_override,
                   (SELECT count(*) FROM session_instance_tune sit
                     WHERE sit.session_instance_id = si.session_instance_id
                       AND sit.deleted = FALSE AND sit.record_type <> 'break') AS tunes,
                   (SELECT count(*) FROM recording r
                     WHERE r.session_instance_id = si.session_instance_id) AS recordings
            FROM session_instance si
            WHERE si.session_id = %s
            ORDER BY si.date DESC
            """,
            (session_id,),
        )
        instances = [
            {
                "session_instance_id": row[0],
                "date": row[1].isoformat(),
                "name": row[2],
                "tune_count": row[3],
                "recording_count": row[4],
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()

    return jsonify({"success": True, "session_id": session_id, "instances": instances})


@api_login_required
def get_recording_segmenter(recording_id):
    """GET /api/recordings/<id>/segmenter — the full segmenter payload.

    Identical to what the page shell embeds (serializers.build_recording_segmenter_payload).
    """
    denied = _admin_gate()
    if denied:
        return denied

    from serializers import build_recording_segmenter_payload

    conn = get_db_connection()
    try:
        payload = build_recording_segmenter_payload(conn, recording_id)
    finally:
        conn.close()

    if payload is None:
        return jsonify({"success": False, "error": "Recording not found"}), 404
    return jsonify(payload)


@api_login_required
def get_recording_peaks(recording_id):
    """GET /api/recordings/<id>/peaks — the waveform envelope as raw bytes.

    One 0-255 byte per bucket at the recording's peaks_hz. Served as binary
    rather than inside the JSON payload because it is ~230KB for a long night:
    base64 in the page blob would cost a third again in bytes and block first
    paint, where this streams alongside the audio and caches.
    """
    denied = _admin_gate()
    if denied:
        return denied

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT peaks, peaks_hz FROM recording WHERE recording_id = %s", (recording_id,))
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"success": False, "error": "Recording not found"}), 404
    if not row[0]:
        return jsonify({"success": False, "error": "This recording has no waveform yet"}), 404

    data = base64.b64decode(row[0])
    resp = Response(data, mimetype="application/octet-stream")
    resp.headers["X-Peaks-Hz"] = str(row[1])
    # Immutable in practice: peaks only change if the audio is re-imported, and
    # that mints a new payload anyway. Private — it is admin-gated content.
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@api_login_required
def put_recording_segment(recording_id, session_instance_tune_id):
    """PUT /api/recordings/<id>/segments/<sit_id> — place or move one tune's segment.

    Body: {"start_ms": int, "end_ms": int|null}

    end_ms omitted/null is the NORMAL case, not a missing value: the next tune's
    start implies it. An explicit end is only meaningful at the end of a set,
    where a stretch of chatter follows.
    """
    denied = _admin_gate()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    try:
        start_ms = _int_or_none(payload, "start_ms")
        end_ms = _int_or_none(payload, "end_ms")
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    if start_ms is None:
        return jsonify({"success": False, "error": "start_ms is required"}), 400
    if start_ms < 0:
        return jsonify({"success": False, "error": "start_ms cannot be negative"}), 400
    if end_ms is not None and end_ms <= start_ms:
        return jsonify({"success": False, "error": "end_ms must be after start_ms"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT session_instance_id, duration_ms, status FROM recording WHERE recording_id = %s",
            (recording_id,),
        )
        rec = cur.fetchone()
        if not rec:
            return jsonify({"success": False, "error": "Recording not found"}), 404
        instance_id, duration_ms = rec[0], int(rec[1])

        # While ingest runs, duration_ms is the browser's provisional guess
        # (schema/052), so the bounds check below would be measuring against a
        # number that is about to change. Refuse rather than accept a mark whose
        # validity depends on a value in flight.
        if rec[2] != "ready":
            return jsonify({"success": False, "error": "That recording is still being processed"}), 409

        if start_ms > duration_ms:
            return jsonify({"success": False, "error": "start_ms is past the end of the recording"}), 400

        # The tune must belong to the instance this recording covers. Without this
        # check a stray id would happily attach a tune from another night.
        cur.execute(
            "SELECT session_instance_id, record_type, deleted FROM session_instance_tune "
            "WHERE session_instance_tune_id = %s",
            (session_instance_tune_id,),
        )
        sit = cur.fetchone()
        if not sit:
            return jsonify({"success": False, "error": "Tune not found"}), 404
        if sit[0] != instance_id:
            return jsonify({"success": False, "error": "That tune belongs to a different session instance"}), 400
        if sit[1] == "break":
            return jsonify({"success": False, "error": "That record is a set break, not a tune"}), 400
        if sit[2]:
            return jsonify({"success": False, "error": "That tune has been deleted from the log"}), 400

        user_id = get_current_user_id()

        cur.execute(
            "SELECT recording_tune_segment_id FROM recording_tune_segment "
            "WHERE recording_id = %s AND session_instance_tune_id = %s",
            (recording_id, session_instance_tune_id),
        )
        existing = cur.fetchone()

        if existing:
            save_to_history(cur, "recording_tune_segment", "UPDATE", existing[0], user_id)
            cur.execute(
                "UPDATE recording_tune_segment SET start_ms = %s, end_ms = %s, last_modified_user_id = %s "
                "WHERE recording_tune_segment_id = %s",
                (start_ms, end_ms, user_id, existing[0]),
            )
            segment_id = existing[0]
            created = False
        else:
            cur.execute(
                "INSERT INTO recording_tune_segment "
                "(recording_id, session_instance_tune_id, start_ms, end_ms, created_by_user_id, last_modified_user_id) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING recording_tune_segment_id",
                (recording_id, session_instance_tune_id, start_ms, end_ms, user_id, user_id),
            )
            segment_id = cur.fetchone()[0]
            save_to_history(cur, "recording_tune_segment", "INSERT", segment_id, user_id)
            created = True

        conn.commit()
    finally:
        conn.close()

    return (
        jsonify(
            {
                "success": True,
                "segment": {
                    "recording_tune_segment_id": segment_id,
                    "session_instance_tune_id": session_instance_tune_id,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                },
            }
        ),
        201 if created else 200,
    )


@api_login_required
def delete_recording_segment(recording_id, session_instance_tune_id):
    """DELETE /api/recordings/<id>/segments/<sit_id> — unplace a tune."""
    denied = _admin_gate()
    if denied:
        return denied

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT recording_tune_segment_id FROM recording_tune_segment "
            "WHERE recording_id = %s AND session_instance_tune_id = %s",
            (recording_id, session_instance_tune_id),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "No segment for that tune"}), 404

        save_to_history(cur, "recording_tune_segment", "DELETE", row[0], get_current_user_id())
        cur.execute("DELETE FROM recording_tune_segment WHERE recording_tune_segment_id = %s", (row[0],))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True})


@api_login_required
def get_instance_recordings(session_instance_id):
    """GET /api/session-instances/<id>/recordings — recordings + segmenting progress."""
    denied = _admin_gate()
    if denied:
        return denied

    from serializers import build_instance_recordings_payload

    conn = get_db_connection()
    try:
        payload = build_instance_recordings_payload(conn, session_instance_id)
    finally:
        conn.close()
    return jsonify(payload)


@api_login_required
def export_recording_segments(recording_id):
    """GET /api/recordings/<id>/export — the training-corpus slice list.

    This is the artifact the whole tool exists to produce: one row per placed
    tune with its end resolved (implicit ends become the next tune's start,
    a trailing implicit end becomes the end of the file), ready to cut with
    ffmpeg and feed to a model. Reads the recording_tune_segment_resolved view
    so the export and the DB agree on that resolution by construction.
    """
    denied = _admin_gate()
    if denied:
        return denied

    import psycopg2.extras

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT storage_key, duration_ms, label FROM recording WHERE recording_id = %s",
            (recording_id,),
        )
        rec = cur.fetchone()
        if not rec:
            return jsonify({"success": False, "error": "Recording not found"}), 404

        cur.execute(
            """
            SELECT session_instance_tune_id, tune_id, display_name, tune_type,
                   start_ms, resolved_end_ms, end_is_explicit, instance_start_ms, absolute_start
            FROM recording_tune_segment_resolved
            WHERE recording_id = %s
            ORDER BY start_ms
            """,
            (recording_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    segments = [
        {
            "session_instance_tune_id": r["session_instance_tune_id"],
            "tune_id": r["tune_id"],
            "name": r["display_name"],
            "tune_type": r["tune_type"],
            "start_ms": int(r["start_ms"]),
            "end_ms": int(r["resolved_end_ms"]),
            "duration_ms": int(r["resolved_end_ms"]) - int(r["start_ms"]),
            "end_is_explicit": r["end_is_explicit"],
            "instance_start_ms": int(r["instance_start_ms"]),
            "absolute_start": r["absolute_start"].isoformat() if r["absolute_start"] else None,
        }
        for r in rows
    ]

    return jsonify(
        {
            "success": True,
            "recording_id": recording_id,
            "label": rec["label"],
            "storage_key": rec["storage_key"],
            "duration_ms": int(rec["duration_ms"]),
            "segment_count": len(segments),
            "segments": segments,
        }
    )
