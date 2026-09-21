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

Authorization is per SESSION, not global (schema/053). A system admin can do
anything; anyone else needs to be an admin of the session this recording belongs
to AND hold that session's `can_manage_recordings` bit. The person who recorded
a night and knows what was played is usually the one running it, not whoever
administers the site — but the grant is opt-in and one session wide, so it never
becomes a way to reach another session's audio. Only the cross-session surfaces
(the site-wide index, the session picker behind it) remain system-admin only.
"""

import base64
import datetime

from flask import jsonify, request, Response
from flask_login import current_user

from api_auth import api_login_required
from database import get_db_connection, get_current_user_id, save_to_history


def _admin_gate():
    """Returns an error response when the caller isn't a system admin, else None.

    Only for the CROSS-SESSION surfaces (/admin/recordings and the session
    picker), which show every night in the system. Anything scoped to one
    recording uses _session_gate below.
    """
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Admin access required"}), 403
    return None


def can_manage_recordings(cur, session_id):
    """May the current user manage THIS session's recordings? (schema/053)

    System admins always. Otherwise it takes an admin of this particular session
    who has also been granted the recordings bit — the two together, never the
    bit alone. A session admin without it is exactly where everyone started, and
    a member with it somehow set has nothing, so "who can do this here" stays
    answerable by looking at the session's admins.
    """
    if not current_user.is_authenticated:
        return False
    if current_user.is_system_admin:
        return True
    person_id = getattr(current_user, "person_id", None)
    if not person_id or not session_id:
        return False
    cur.execute(
        "SELECT 1 FROM session_person "
        "WHERE session_id = %s AND person_id = %s AND is_admin = TRUE AND can_manage_recordings = TRUE",
        (session_id, person_id),
    )
    return cur.fetchone() is not None


def _session_of_recording(cur, recording_id):
    """(session_id, session_instance_id) for a recording, or (None, None)."""
    cur.execute(
        "SELECT si.session_id, si.session_instance_id FROM recording r "
        "JOIN session_instance si ON si.session_instance_id = r.session_instance_id "
        "WHERE r.recording_id = %s",
        (recording_id,),
    )
    row = cur.fetchone()
    return (row[0], row[1]) if row else (None, None)


def _session_of_instance(cur, session_instance_id):
    cur.execute(
        "SELECT session_id FROM session_instance WHERE session_instance_id = %s",
        (session_instance_id,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _recording_gate(cur, recording_id):
    """Gate a per-recording endpoint. Returns an error response, or None to proceed.

    404 for a recording that doesn't exist, 403 for one that does but isn't
    yours -- deliberately distinguishable, because every caller of these
    endpoints is already an admin of SOMETHING and hiding the difference would
    only make a misconfigured permission look like a missing recording.
    """
    session_id, _ = _session_of_recording(cur, recording_id)
    if session_id is None:
        return jsonify({"success": False, "error": "Recording not found"}), 404
    if not can_manage_recordings(cur, session_id):
        return jsonify({"success": False, "error": "You can't manage this session's recordings"}), 403
    return None


def _instance_gate(cur, session_instance_id):
    """Same, for endpoints addressed by session instance rather than recording."""
    session_id = _session_of_instance(cur, session_instance_id)
    if session_id is None:
        return jsonify({"success": False, "error": "Session instance not found"}), 404
    if not can_manage_recordings(cur, session_id):
        return jsonify({"success": False, "error": "You can't manage this session's recordings"}), 403
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
    import os

    import recording as rec

    payload = request.get_json(silent=True) or {}

    try:
        session_instance_id = int(payload.get("session_instance_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "session_instance_id is required"}), 400

    # Permission first, exactly as POST /api/recordings does it. Whether this
    # deployment has object storage configured is not something to tell someone
    # with no business on this session, and answering 503 ahead of the gate also
    # hides the 403 wherever the bucket is unset -- which is every environment
    # without S3 credentials, and is how this ordering went unnoticed.
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _instance_gate(cur, session_instance_id)
        if denied:
            return denied
    finally:
        conn.close()

    problem = rec.check_configured()
    if problem:
        # Verbatim: the message names the missing environment variables, and
        # anything that reshapes it (.capitalize(), say) turns AWS_S3_BUCKET into
        # aws_s3_bucket and throws away the only actionable part.
        return jsonify({"success": False, "error": f"Uploads are unavailable — {problem}"}), 503

    filename = (payload.get("filename") or "").strip()
    if not filename:
        return jsonify({"success": False, "error": "filename is required"}), 400

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
    import recording as rec
    from services.recording_ingest import DETAIL_QUEUED, start_ingest

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

    import os

    label = (payload.get("label") or "").strip() or None
    mime_type = _UPLOAD_MIME_BY_EXTENSION.get(os.path.splitext(storage_key)[1].lower(), "audio/mpeg")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Permission before the object store: an unauthorised caller should be
        # told so without a round trip to S3 on their behalf.
        denied = _instance_gate(cur, session_instance_id)
        if denied:
            return denied

        cur.execute(
            "SELECT si.date, s.name FROM session_instance si "
            "JOIN session s ON s.session_id = si.session_id WHERE si.session_instance_id = %s",
            (session_instance_id,),
        )
        instance = cur.fetchone()

        # Confirm the object is actually there before writing a row that claims it
        # is. A cancelled or failed PUT would otherwise surface much later as a
        # segmenter page that loads and then plays nothing.
        try:
            size = rec.stored_object_size(storage_key)
        except Exception as exc:
            return jsonify({"success": False, "error": str(exc)}), 503
        if size is None:
            return jsonify({"success": False, "error": "That upload didn't finish — nothing is stored under that key"}), 400

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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, 'queued', %s, %s, %s)
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
                DETAIL_QUEUED, user_id, user_id,
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

    `stalled` means nothing is working on this recording: the run that had it
    stopped heartbeating. It is now a note rather than a call to action -- the
    sweeper picks these up on the next worker boot or tick -- but the page says so,
    because "processing" with nobody processing is exactly the state that used to
    leave people watching a spinner for two hours.
    """
    from services.recording_ingest import HEARTBEAT_STALE_SECONDS, INGEST_STEPS, step_index_for

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied
        cur.execute(
            """
            SELECT status, status_detail, duration_ms, (peaks IS NOT NULL) AS has_peaks,
                   (stream_key IS NOT NULL) AS has_proxy, file_size_bytes,
                   EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC') - ingest_heartbeat_at),
                   ingest_attempts
            FROM recording WHERE recording_id = %s
            """,
            (recording_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"success": False, "error": "Recording not found"}), 404

    # No heartbeat at all means nobody has started yet ('queued'), which is not
    # stale -- it is waiting, and the sweeper will take it.
    since_beat = row[6]
    unattended = row[0] in ("queued", "processing") and (
        since_beat is None or float(since_beat) > HEARTBEAT_STALE_SECONDS
    )
    # A finished recording is at the last step; otherwise the step comes from the
    # detail the pipeline last wrote. None means a row from before the stages
    # existed, and the display falls back to the sentence alone.
    step = len(INGEST_STEPS) - 1 if row[0] == "ready" else step_index_for(row[1])
    return jsonify(
        {
            "success": True,
            "recording_id": recording_id,
            "status": row[0],
            "status_detail": row[1],
            "steps": INGEST_STEPS,
            "step": step,
            "duration_ms": int(row[2]),
            "has_peaks": row[3],
            "has_proxy": row[4],
            "file_size_bytes": int(row[5]) if row[5] else None,
            # Kept as `stalled` for the clients that already read it.
            "stalled": unattended,
            "attempts": row[7],
        }
    )


@api_login_required
def reprocess_recording(recording_id):
    """POST /api/recordings/<id>/reprocess — run ingest again.

    Mostly needed now for a recording ingest genuinely could not read — a deploy
    or a restarted dyno is picked up by the sweeper without anyone asking.
    Idempotent: every step of ingest overwrites.

    Resets `ingest_attempts`, because a person choosing to try again is a
    different event from the sweeper looping, and should get a full budget rather
    than inheriting an exhausted one.
    """
    from services.recording_ingest import DETAIL_QUEUED, HEARTBEAT_STALE_SECONDS, start_ingest

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied
        cur.execute(
            "SELECT status, EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC') - ingest_heartbeat_at) "
            "FROM recording WHERE recording_id = %s",
            (recording_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Recording not found"}), 404

        # Refuse to stack a second transcode on top of a live one. "Live" is now
        # a heartbeat rather than a guess at how long a run should take, so this
        # says yes within 90 seconds of a run dying instead of two hours.
        if row[0] == "processing" and row[1] is not None and float(row[1]) <= HEARTBEAT_STALE_SECONDS:
            return jsonify({"success": False, "error": "That recording is already being processed"}), 409

        cur.execute(
            "UPDATE recording SET status = 'queued', status_detail = %s, "
            "ingest_attempts = 0, ingest_heartbeat_at = NULL WHERE recording_id = %s",
            (DETAIL_QUEUED, recording_id),
        )
        conn.commit()
    finally:
        conn.close()

    start_ingest(recording_id, get_current_user_id())
    return jsonify({"success": True, "recording_id": recording_id, "status": "processing"})


@api_login_required
def set_recording_segmenting_complete(recording_id):
    """PUT /api/recordings/<id>/segmenting-complete — "nothing else in here to place".

    Progress on /admin/recordings is placements against the night's logged tunes,
    which silently assumes the audio covers the whole night. Plenty of it does
    not: a phone started an hour in, a battery that died before the last set, a
    file that is deliberately just the good bit. Those recordings can never reach
    their denominator, so without this they sit in the queue advertising work
    that does not exist.

    Nothing here can be derived — only whoever listened knows whether the
    unplaced tunes are missing from the corpus or missing from the audio — so it
    is written down. Same permission as timestamping (schema/053): saying a
    recording is finished IS part of timestamping it.

    Takes a boolean so it can be turned off again; a night that turns out to have
    more in it than it seemed should not need a database session to reopen.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied

        payload = request.get_json(silent=True) or {}
        complete = payload.get("complete", True)
        if not isinstance(complete, bool):
            return jsonify({"success": False, "error": "complete must be true or false"}), 400

        save_to_history(cur, "recording", "UPDATE", recording_id, user_id=get_current_user_id())
        # The timestamp is cleared on the way back down rather than left as a
        # record of a decision that has been withdrawn: "when was this declared
        # finished" has no answer for something that is not.
        cur.execute(
            "UPDATE recording SET segmenting_complete = %s, "
            "segmenting_complete_at = CASE WHEN %s THEN (NOW() AT TIME ZONE 'UTC') ELSE NULL END, "
            "last_modified_user_id = %s WHERE recording_id = %s",
            (complete, complete, get_current_user_id(), recording_id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "recording_id": recording_id, "segmenting_complete": complete})


@api_login_required
def delete_recording(recording_id):
    """DELETE /api/recordings/<id> — remove a recording and its audio.

    This is the one destructive operation in the tool, and what it destroys is
    not the audio (that can be re-uploaded) but the SEGMENTS: every tune the
    operator placed by hand, which is the whole product of an evening's work.
    The count is therefore returned so the UI can say what is about to be lost,
    and every segment is written to history on the way out — recording_tune_segment_history
    has no foreign key to the live rows, so those timestamps survive the delete
    and can be read back if someone asks for them later.

    Order matters. The row goes first and the objects second, because the two
    failure modes are not equal: an object outliving its row costs storage,
    while a row outliving its object is a segmenter page that loads and then
    plays silence. Storage failures are reported alongside a success rather
    than raised, since by then the delete has already happened.
    """
    import recording as rec

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied
        cur.execute(
            "SELECT storage_key, stream_key, label FROM recording WHERE recording_id = %s",
            (recording_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Recording not found"}), 404
        storage_key, stream_key, label = row

        user_id = get_current_user_id()

        cur.execute(
            "SELECT recording_tune_segment_id FROM recording_tune_segment WHERE recording_id = %s",
            (recording_id,),
        )
        segment_ids = [r[0] for r in cur.fetchall()]
        for segment_id in segment_ids:
            save_to_history(cur, "recording_tune_segment", "DELETE", segment_id, user_id)

        save_to_history(cur, "recording", "DELETE", recording_id, user_id)
        # The segments go with it via ON DELETE CASCADE (schema/049); their
        # history rows were just written above and do not.
        cur.execute("DELETE FROM recording WHERE recording_id = %s", (recording_id,))
        conn.commit()
    finally:
        conn.close()

    failures = rec.delete_stored_objects(storage_key, stream_key)

    return jsonify(
        {
            "success": True,
            "recording_id": recording_id,
            "label": label,
            "segments_deleted": len(segment_ids),
            "storage_warning": (
                "The recording is deleted, but its audio could not be removed from storage: "
                + "; ".join(reason for _, reason in failures)
            ) if failures else None,
        }
    )


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
    from serializers import build_recording_segmenter_payload

    conn = get_db_connection()
    try:
        denied = _recording_gate(conn.cursor(), recording_id)
        if denied:
            return denied
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
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied
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

        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied

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


# ---- Logging while segmenting (spec 050) -------------------------------------
#
# A night nobody wrote down still has audio worth timestamping. Once every logged
# tune is placed (or the log is empty), a mark logs a NEW tune -- unidentified,
# named "Gan Ainm" -- and places it in one transaction, through the live logger's
# own op machinery so the log's feed, history and any open live screen see it.
#
#   POST /api/recordings/<id>/segments                  log a new tune starting here
#   PUT  /api/recordings/<id>/segments/<sit_id>/tune    say which tune it was
#   POST /api/recordings/<id>/segments/<sit_id>/unlog   take it back out of the log
#
# Set membership is read off the audio, not typed: a new tune joins the set of the
# placed tune before it when that tune's end is implicit (they abut), and starts a
# fresh set when that end was marked explicitly (the End-set button).

GAN_AINM = "Gan Ainm"


def _recording_for_logging(cur, recording_id):
    """(session_instance_id, session_id, duration_ms) for a READY recording, or an
    error response. A mark validated against a provisional duration is a mark
    validated against nothing (schema/052)."""
    cur.execute(
        "SELECT r.session_instance_id, si.session_id, r.duration_ms, r.status FROM recording r "
        "JOIN session_instance si ON si.session_instance_id = r.session_instance_id "
        "WHERE r.recording_id = %s",
        (recording_id,),
    )
    rec = cur.fetchone()
    if not rec:
        return None, (jsonify({"success": False, "error": "Recording not found"}), 404)
    if rec[3] != "ready":
        return None, (jsonify({"success": False, "error": "That recording is still being processed"}), 409)
    return (rec[0], rec[1], int(rec[2])), None


def _tunes_response(conn, recording_id, instance_id, session_id, **extra):
    from serializers import load_recording_tunes

    return jsonify({"success": True, "tunes": load_recording_tunes(conn, recording_id, instance_id, session_id), **extra})


def _placement_for_new_tune(cur, recording_id, instance_id, start_ms):
    """Where a tune starting at `start_ms` goes in the log: (after_record_id,
    before_record_id, new_set).

    The anchor is the placed tune that starts last before this one. Its end
    decides the set: implicit (NULL) means the two abut and the new tune joins
    its set, directly after it; explicit means that set was closed on purpose --
    the new tune then opens the next set (after the break that already follows,
    or a fresh break when nothing does). With no placed tune before it, the new
    tune goes in front of the whole log and runs into whatever comes next.
    """
    from live_logging_routes import _live_records_in_order

    records = _live_records_in_order(cur, instance_id)  # (id, record_type, order_position)
    cur.execute(
        "SELECT session_instance_tune_id, start_ms, end_ms FROM recording_tune_segment WHERE recording_id = %s",
        (recording_id,),
    )
    segments = {r[0]: (int(r[1]), r[2]) for r in cur.fetchall()}

    anchor = None
    for rid, rtype, _pos in records:
        seg = segments.get(rid)
        if rtype != "tune" or seg is None:
            continue
        if seg[0] == start_ms:
            raise ValueError("A tune already starts at that moment")
        if seg[0] < start_ms and (anchor is None or seg[0] > anchor[1]):
            anchor = (rid, seg[0], seg[1])

    if anchor is None:
        first = records[0][0] if records else None
        return None, first, False

    anchor_id, _start, end_ms = anchor
    if end_ms is None:
        return anchor_id, None, False

    idx = next(i for i, r in enumerate(records) if r[0] == anchor_id)
    following = records[idx + 1] if idx + 1 < len(records) else None
    if following is not None and following[1] == "break":
        return following[0], None, False  # the break is already there; open the next set
    return anchor_id, None, True


@api_login_required
def log_recording_tune(recording_id):
    """POST /api/recordings/<id>/segments -- log a new, unidentified tune starting here.

    Body: {"start_ms": int, "end_ms": int|null}. Returns the whole tune list
    (`tunes`) plus the new row (`tune`): an insert can renumber every set after it.
    """
    from live_logging_routes import OpRejected, apply_live_op

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
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied
        info, err = _recording_for_logging(cur, recording_id)
        if err:
            return err
        instance_id, session_id, duration_ms = info
        if start_ms > duration_ms:
            return jsonify({"success": False, "error": "start_ms is past the end of the recording"}), 400

        user_id = get_current_user_id()
        try:
            after_id, before_id, new_set = _placement_for_new_tune(cur, recording_id, instance_id, start_ms)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 409

        try:
            _eid, _typ, added = apply_live_op(
                cur, instance_id, "add_tune",
                {"name": GAN_AINM, "source": "segmenter", "no_match": True, "no_merge": True,
                 "after_record_id": after_id, "before_record_id": before_id},
                user_id,
            )
            record_id = added["record"]["session_instance_tune_id"]
            if new_set:
                apply_live_op(cur, instance_id, "set_break", {"action": "insert", "before_record_id": record_id}, user_id)
        except OpRejected as r:
            conn.rollback()
            return jsonify({"success": False, "error": r.message}), 409

        cur.execute(
            "INSERT INTO recording_tune_segment "
            "(recording_id, session_instance_tune_id, start_ms, end_ms, created_by_user_id, last_modified_user_id) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING recording_tune_segment_id",
            (recording_id, record_id, start_ms, end_ms, user_id, user_id),
        )
        save_to_history(cur, "recording_tune_segment", "INSERT", cur.fetchone()[0], user_id)
        conn.commit()

        resp = _tunes_response(conn, recording_id, instance_id, session_id)
        body = resp.get_json()
        body["tune"] = next((t for t in body["tunes"] if t["session_instance_tune_id"] == record_id), None)
        return jsonify(body), 201
    finally:
        conn.close()


@api_login_required
def set_recording_tune(recording_id, session_instance_tune_id):
    """PUT /api/recordings/<id>/segments/<sit_id>/tune -- say which tune this is.

    Body: {"tune_id"?, "thesession_id"?, "name", "setting_id"?} -- the same payload
    the live logger's search hands its add. tune_id links; thesession_id imports
    first when the tune isn't local yet; a bare name logs it as-is (unlinked, the
    typed name); setting_id records the setting chosen in the preview.
    """
    from live_logging_routes import (
        OpRejected, TuneImportError, _import_tune_for_live, _maybe_apply_chosen_setting,
        _parse_thesession_id, apply_live_op, emit_change_tune,
    )

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    tune_id = payload.get("tune_id")
    ts_id = _parse_thesession_id(payload.get("thesession_id"))
    if tune_id is None and ts_id is None and not name:
        return jsonify({"success": False, "error": "A tune or a name is required"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied
        info, err = _recording_for_logging(cur, recording_id)
        if err:
            return err
        instance_id, session_id, _duration = info
        cur.execute(
            "SELECT session_instance_id, record_type, deleted FROM session_instance_tune WHERE session_instance_tune_id = %s",
            (session_instance_tune_id,),
        )
        sit = cur.fetchone()
        if not sit or sit[0] != instance_id or sit[2]:
            return jsonify({"success": False, "error": "Tune not found"}), 404
        if sit[1] != "tune":
            return jsonify({"success": False, "error": "That record is a set break, not a tune"}), 400

        user_id = get_current_user_id()
        try:
            if ts_id is not None and tune_id is None:
                cur.execute("SELECT name, redirect_to_tune_id FROM tune WHERE tune_id = %s", (ts_id,))
                row = cur.fetchone()
                if row:
                    tune_id = row[1] or ts_id
                else:
                    imported_name, _tt = _import_tune_for_live(cur, ts_id, user_id)
                    tune_id, name = ts_id, (name or imported_name)
            change = {"record_id": session_instance_tune_id, "name": name or None}
            if tune_id is not None:
                change["tune_id"] = int(tune_id)
            else:
                change["unlink"] = True
            apply_live_op(cur, instance_id, "change_tune", change, user_id)
            applied, failed = _maybe_apply_chosen_setting(cur, session_id, tune_id, session_instance_tune_id, payload, user_id)
            if applied:
                emit_change_tune(cur, instance_id, session_instance_tune_id, user_id)
        except TuneImportError as exc:
            conn.rollback()
            return jsonify({"success": False, "error": exc.message}), 502
        except OpRejected as r:
            conn.rollback()
            return jsonify({"success": False, "error": r.message}), 409
        conn.commit()

        from serializers import load_recording_tunes

        tunes = load_recording_tunes(conn, recording_id, instance_id, session_id)
        tune = next((t for t in tunes if t["session_instance_tune_id"] == session_instance_tune_id), None)
        body = {"success": True, "tune": tune, "tunes": tunes}
        if failed:
            body["setting_failed"] = failed
        return jsonify(body)
    finally:
        conn.close()


@api_login_required
def unlog_recording_tune(recording_id, session_instance_tune_id):
    """POST /api/recordings/<id>/segments/<sit_id>/unlog -- remove a tune the
    segmenter logged, and its placement. Only rows the tool created itself
    (source = 'segmenter'): a tune someone wrote down on the night is unplaced
    with DELETE .../segments/<sit_id>, never removed from here.
    """
    from live_logging_routes import OpRejected, apply_live_op

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied
        instance_id, session_id = _session_of_recording(cur, recording_id)[::-1]
        cur.execute(
            "SELECT session_instance_id, source, deleted FROM session_instance_tune WHERE session_instance_tune_id = %s",
            (session_instance_tune_id,),
        )
        sit = cur.fetchone()
        if not sit or sit[0] != instance_id or sit[2]:
            return jsonify({"success": False, "error": "Tune not found"}), 404
        if sit[1] != "segmenter":
            return jsonify({"success": False, "error": "That tune was logged on the night; unplace it instead"}), 409

        user_id = get_current_user_id()
        cur.execute(
            "SELECT recording_tune_segment_id FROM recording_tune_segment "
            "WHERE recording_id = %s AND session_instance_tune_id = %s",
            (recording_id, session_instance_tune_id),
        )
        seg = cur.fetchone()
        if seg:
            save_to_history(cur, "recording_tune_segment", "DELETE", seg[0], user_id)
            cur.execute("DELETE FROM recording_tune_segment WHERE recording_tune_segment_id = %s", (seg[0],))
        try:
            apply_live_op(cur, instance_id, "remove_tune", {"record_id": session_instance_tune_id}, user_id)
        except OpRejected as r:
            conn.rollback()
            return jsonify({"success": False, "error": r.message}), 409
        conn.commit()
        return _tunes_response(conn, recording_id, instance_id, session_id)
    finally:
        conn.close()


@api_login_required
def delete_recording_segment(recording_id, session_instance_tune_id):
    """DELETE /api/recordings/<id>/segments/<sit_id> — unplace a tune."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _recording_gate(cur, recording_id)
        if denied:
            return denied
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
    from serializers import build_instance_recordings_payload

    conn = get_db_connection()
    try:
        denied = _instance_gate(conn.cursor(), session_instance_id)
        if denied:
            return denied
        payload = build_instance_recordings_payload(conn, session_instance_id)
    finally:
        conn.close()
    return jsonify(payload)


@api_login_required
def download_recording_segment(recording_id, session_instance_tune_id):
    """GET /api/recordings/<id>/segments/<sit_id>/download — one tune, as a file.

    The only place audio passes THROUGH Flask. Everything else in spec 050 is
    browser-to-S3 by design, but a slice cannot be: a byte range out of an
    encoded file is not a playable file, so something has to cut it, and the
    browser can't (the bucket serves no CORS headers, and re-encoding in a tab to
    save ninety seconds of audio is absurd). The cut is a stream copy from a
    range-requested URL, so the cost is a couple of seconds and a couple of
    megabytes, not the whole recording.

    Cut from the MASTER, not the playback proxy. This is a file someone keeps —
    to practise against, or to send to whoever else was in the room — and 32kbps
    mono is a poor thing to be left holding. The proxy exists so playback starts
    quickly, which is not a constraint here.

    The end comes from recording_tune_segment_resolved, so a tune whose end was
    left implicit is cut to exactly where playback would have stopped.
    """
    import os
    import tempfile
    from io import BytesIO

    import psycopg2.extras
    from flask import send_file

    conn = get_db_connection()
    try:
        denied = _recording_gate(conn.cursor(), recording_id)
        if denied:
            return denied
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT v.display_name, v.start_ms, v.resolved_end_ms, v.storage_key, si.date
            FROM recording_tune_segment_resolved v
            JOIN recording r ON r.recording_id = v.recording_id
            JOIN session_instance si ON si.session_instance_id = r.session_instance_id
            WHERE v.recording_id = %s AND v.session_instance_tune_id = %s
            """,
            (recording_id, session_instance_tune_id),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"success": False, "error": "No segment for that tune"}), 404

    suffix = os.path.splitext(row["storage_key"])[1].lower() or ".m4a"
    mime = _UPLOAD_MIME_BY_EXTENSION.get(suffix, "application/octet-stream")
    # "The Bank Of Turf (2025-03-27).mp3" — the tune, and which night it was.
    # send_file does the RFC 5987 encoding, so accented tune names survive.
    stem = (row["display_name"] or f"tune-{session_instance_tune_id}").strip()
    stem = "".join(c for c in stem if c not in '\\/:*?"<>|').strip() or "tune"
    date = row["date"].isoformat() if row["date"] else ""
    download_name = f"{stem}{f' ({date})' if date else ''}{suffix}"

    from recording import generate_presigned_url, slice_segment

    try:
        source = generate_presigned_url(row["storage_key"])
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, f"segment{suffix}")
            slice_segment(source, int(row["start_ms"]), int(row["resolved_end_ms"]), dest)
            with open(dest, "rb") as fh:
                data = fh.read()
    except Exception as exc:
        # The temp dir is gone by now either way; read it into memory first so the
        # response can outlive it.
        return jsonify({"success": False, "error": f"Could not cut that tune: {exc}"}), 500

    return send_file(BytesIO(data), mimetype=mime, as_attachment=True, download_name=download_name)


@api_login_required
def get_instance_audio(session_instance_id):
    """GET /api/session-instances/<id>/audio — playback for the instance page.

    The read side of the segmenter's work: the session-instance page asks this
    once, in the background after bootstrap, and puts a play button on every
    tune that came back with a mark.

    Gated exactly like marking (_instance_gate), not more tightly. Anyone who
    may place these timestamps may obviously hear what they placed, and the
    grant is already per session — a separate, stricter rule for listening would
    only be a second thing to keep in step with the first.

    Deliberately NOT part of /bootstrap: it presigns an S3 URL, which is pointless
    on the great majority of instances that have no audio, and a 6-hour URL has no
    business inside a payload the service worker caches for offline use.
    """
    from serializers import build_instance_audio_payload

    conn = get_db_connection()
    try:
        denied = _instance_gate(conn.cursor(), session_instance_id)
        if denied:
            return denied
        payload = build_instance_audio_payload(conn, session_instance_id)
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
    import psycopg2.extras

    conn = get_db_connection()
    try:
        denied = _recording_gate(conn.cursor(), recording_id)
        if denied:
            return denied
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
