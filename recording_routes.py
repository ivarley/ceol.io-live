"""Recording segmenter API (spec 050).

The write vocabulary is deliberately tiny, because the UI's whole interaction is
one keystroke: "the tune I'm pointing at starts HERE".

    PUT    /api/recordings/<id>/segments/<session_instance_tune_id>   place/move
    DELETE /api/recordings/<id>/segments/<session_instance_tune_id>   unplace

PUT is an upsert keyed on (recording, tune) rather than a create-then-update
pair, so a re-mark of the same tune is the same call as the first mark and the
client never has to track whether a segment already exists.

Every endpoint is system-admin only: this is a data-prep tool for building an ML
training corpus, not a member-facing feature.
"""

import base64

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
            "SELECT session_instance_id, duration_ms FROM recording WHERE recording_id = %s",
            (recording_id,),
        )
        rec = cur.fetchone()
        if not rec:
            return jsonify({"success": False, "error": "Recording not found"}), 404
        instance_id, duration_ms = rec[0], int(rec[1])

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
