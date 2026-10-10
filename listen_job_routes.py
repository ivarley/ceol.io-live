"""Background work for the listening service (spec 053,
"053 files/find-tunes-on-the-server.md"): an admin asks the segmenter to find a
night's tunes; the listening service claims the job, reports where it has got
to (and when live listening has paused it), and posts the tunes it found,
which go into the night as the segmenter's own logging does (`log_tune`).

The page and admins:
  POST /api/recordings/<id>/find-tunes      queue a job (system admins)
  GET  /api/recordings/<id>/find-tunes      the recording's latest job, or null
  POST /api/listen-jobs/<id>/cancel         stop a waiting or running job
  POST /api/listen-jobs/<id>/retry          queue a failed or cancelled job again
  POST /api/recordings/<id>/find-tunes/undo remove what the listener logged, unchecked
  GET  /api/admin/listen-jobs               every job, newest first

The listening service (Bearer LISTEN_JOB_TOKEN, set on both services):
  POST /api/listen-jobs/claim               the oldest waiting job, with what it needs
  POST /api/listen-jobs/<id>/progress       where it has got to; the heartbeat
  POST /api/listen-jobs/<id>/result         the tunes found
  POST /api/listen-jobs/<id>/fail           it could not

And for live listening, the session's own tunes (the first tier):
  GET  /api/session-instances/<id>/known-tunes
"""

# i18n-converted  (spec 057: every message a person reads goes through _())
import json

from flask import jsonify, request
from flask_babel import gettext as _
from flask_login import current_user

from api_auth import api_login_required, api_service_required
from database import get_db_connection

ACTIVE = ("queued", "running", "paused")
STALE_S = 120  # a held job silent this long went down with its worker
MAX_ATTEMPTS = 3
TOKEN_ENV = "LISTEN_JOB_TOKEN"

_COLS = (
    "j.listen_job_id, j.kind, j.recording_id, j.status, j.phase, j.progress, j.heard_ms, j.total_ms, "
    "j.worker, j.attempts, j.queued_at, j.started_at, j.finished_at, j.running_s, j.paused_s, j.result, "
    "j.error, j.requested_by_user_id, p.first_name, p.last_name, "
    "EXTRACT(EPOCH FROM (COALESCE(j.started_at, NOW()) - j.queued_at)), "
    "EXTRACT(EPOCH FROM (NOW() - j.heartbeat_at)), "
    "r.label, si.session_instance_id, si.date, s.name, s.path"
)
_FROM = (
    "FROM listen_job j "
    "JOIN recording r ON r.recording_id = j.recording_id "
    "JOIN session_instance si ON si.session_instance_id = r.session_instance_id "
    "JOIN session s ON s.session_id = si.session_id "
    "LEFT JOIN user_account u ON u.user_id = j.requested_by_user_id "
    "LEFT JOIN person p ON p.person_id = u.person_id"
)


def _iso(ts):
    return ts.isoformat() if ts is not None else None


def _job(row, ahead=None):
    """The job as the page and the admin list read it."""
    (
        job_id,
        kind,
        recording_id,
        status,
        phase,
        progress,
        heard_ms,
        total_ms,
        worker,
        attempts,
        queued_at,
        started_at,
        finished_at,
        running_s,
        paused_s,
        result,
        error,
        user_id,
        first,
        last,
        waited_s,
        silent_s,
        label,
        instance_id,
        date,
        session_name,
        session_path,
    ) = row
    return {
        "listen_job_id": job_id,
        "kind": kind,
        "recording_id": recording_id,
        "recording_label": label,
        "session_instance_id": instance_id,
        "date": date.isoformat() if date else None,
        "session_name": session_name,
        "session_path": session_path,
        "status": status,
        "phase": phase,
        "progress": progress,
        "heard_ms": heard_ms,
        "total_ms": total_ms,
        "worker": worker,
        "attempts": attempts,
        "queued_at": _iso(queued_at),
        "started_at": _iso(started_at),
        "finished_at": _iso(finished_at),
        # how long it waited to start, worked, and was held for live listening
        "waited_s": round(float(waited_s), 1) if waited_s is not None else None,
        "running_s": round(float(running_s or 0), 1),
        "paused_s": round(float(paused_s or 0), 1),
        "heartbeat_age_s": round(float(silent_s), 1) if silent_s is not None else None,
        "jobs_ahead": ahead,
        "result": result,
        "error": error,
        "requested_by": " ".join(x for x in (first, last) if x) or None,
    }


def _ahead(cur, job_id):
    cur.execute(
        "SELECT COUNT(*) FROM listen_job WHERE status IN ('queued', 'running', 'paused') AND listen_job_id < %s",
        (job_id,),
    )
    return cur.fetchone()[0]


def _load(cur, job_id):
    cur.execute(f"SELECT {_COLS} {_FROM} WHERE j.listen_job_id = %s", (job_id,))
    row = cur.fetchone()
    if not row:
        return None
    return _job(row, _ahead(cur, job_id) if row[3] == "queued" else None)


def _admin():
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": _("Only an admin can do this")}), 403
    return None


def _logged_tunes(cur, instance_id):
    cur.execute(
        "SELECT COUNT(*) FROM session_instance_tune WHERE session_instance_id = %s "
        "AND record_type = 'tune' AND deleted = FALSE",
        (instance_id,),
    )
    return cur.fetchone()[0]


def _recording_facts(cur, recording_id):
    """(instance_id, session_id, date, duration_ms, status, storage_key) or None."""
    cur.execute(
        "SELECT si.session_instance_id, si.session_id, si.date, r.duration_ms, r.status, r.storage_key "
        "FROM recording r JOIN session_instance si ON si.session_instance_id = r.session_instance_id "
        "WHERE r.recording_id = %s",
        (recording_id,),
    )
    return cur.fetchone()


def _requeue_stale(cur):
    """A held job its worker stopped reporting on: back in the queue, or failed
    after MAX_ATTEMPTS."""
    cur.execute(
        "UPDATE listen_job SET status = CASE WHEN attempts >= %s THEN 'failed' ELSE 'queued' END, "
        "error = CASE WHEN attempts >= %s THEN %s ELSE error END, "
        "finished_at = CASE WHEN attempts >= %s THEN NOW() ELSE NULL END, worker = NULL "
        "WHERE status IN ('running', 'paused') AND heartbeat_at < NOW() - make_interval(secs => %s)",
        (
            MAX_ATTEMPTS,
            MAX_ATTEMPTS,
            _("The listening service stopped answering"),
            MAX_ATTEMPTS,
            STALE_S,
        ),
    )


def known_tunes(cur, instance_id):
    """The session's tunes logged before this night (the listener's first tier),
    and the key the session plays each in."""
    cur.execute(
        "SELECT DISTINCT sit.tune_id FROM session_instance_tune sit "
        "JOIN session_instance si ON si.session_instance_id = sit.session_instance_id "
        "JOIN session_instance this ON this.session_instance_id = %s "
        "WHERE si.session_id = this.session_id AND si.date < this.date AND sit.record_type = 'tune' "
        "AND sit.deleted = FALSE AND sit.tune_id IS NOT NULL",
        (instance_id,),
    )
    ids = sorted(r[0] for r in cur.fetchall())
    cur.execute(
        "SELECT st.tune_id, st.key FROM session_tune st "
        "JOIN session_instance this ON this.session_id = st.session_id "
        "WHERE this.session_instance_id = %s AND st.key IS NOT NULL",
        (instance_id,),
    )
    return ids, {str(t): k for t, k in cur.fetchall()}


# --------------------------------------------------------------------------- #
# The page and admins
# --------------------------------------------------------------------------- #


def _queue(cur, recording_id, user_id):
    """Queue a job, or say why not. -> (job_id, None) or (None, (message, status))."""
    facts = _recording_facts(cur, recording_id)
    if facts is None:
        return None, (_("Recording not found"), 404)
    instance_id, _session_id, _date, duration_ms, status, _key = facts
    if status not in (None, "ready") or not duration_ms:
        return None, (_("The recording is still being prepared"), 409)
    if _logged_tunes(cur, instance_id):
        return None, (_("This night already has tunes logged"), 409)
    cur.execute(
        "SELECT 1 FROM listen_job WHERE recording_id = %s AND status IN ('queued', 'running', 'paused')",
        (recording_id,),
    )
    if cur.fetchone():
        return None, (_("The tunes are already being found"), 409)
    cur.execute(
        "INSERT INTO listen_job (recording_id, requested_by_user_id, total_ms) VALUES (%s, %s, %s) "
        "RETURNING listen_job_id",
        (recording_id, user_id, duration_ms),
    )
    return cur.fetchone()[0], None


@api_login_required
def start_find_tunes(recording_id):
    denied = _admin()
    if denied:
        return denied
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        job_id, err = _queue(cur, recording_id, current_user.user_id)
        if err:
            conn.rollback()
            return jsonify({"success": False, "error": err[0]}), err[1]
        conn.commit()
        return jsonify({"success": True, "job": _load(cur, job_id)}), 201
    finally:
        conn.close()


@api_login_required
def get_find_tunes(recording_id):
    denied = _admin()
    if denied:
        return denied
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        _requeue_stale(cur)
        conn.commit()
        cur.execute(
            "SELECT listen_job_id FROM listen_job WHERE recording_id = %s ORDER BY listen_job_id DESC LIMIT 1",
            (recording_id,),
        )
        row = cur.fetchone()
        return jsonify({"success": True, "job": _load(cur, row[0]) if row else None})
    finally:
        conn.close()


@api_login_required
def cancel_listen_job(job_id):
    denied = _admin()
    if denied:
        return denied
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE listen_job SET status = 'cancelled', finished_at = NOW() "
            "WHERE listen_job_id = %s AND status IN ('queued', 'running', 'paused') RETURNING 1",
            (job_id,),
        )
        if not cur.fetchone():
            conn.rollback()
            return (
                jsonify(
                    {"success": False, "error": _("That job has already finished")}
                ),
                409,
            )
        conn.commit()
        return jsonify({"success": True, "job": _load(cur, job_id)})
    finally:
        conn.close()


@api_login_required
def retry_listen_job(job_id):
    denied = _admin()
    if denied:
        return denied
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT recording_id, status FROM listen_job WHERE listen_job_id = %s",
            (job_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": _("Job not found")}), 404
        if row[1] not in ("failed", "cancelled"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": _("Only a failed or cancelled job can be tried again"),
                    }
                ),
                409,
            )
        new_id, err = _queue(cur, row[0], current_user.user_id)
        if err:
            conn.rollback()
            return jsonify({"success": False, "error": err[0]}), err[1]
        conn.commit()
        return jsonify({"success": True, "job": _load(cur, new_id)}), 201
    finally:
        conn.close()


@api_login_required
def undo_find_tunes(recording_id):
    """Take back what the listener logged: its tunes nobody has confirmed or
    corrected (source 'listen', confidence under 100), with their placements,
    as the segmenter's remove does. What a person settled stays."""
    from live_logging_routes import OpRejected, apply_live_op
    from recording_routes import _tunes_response
    from database import save_to_history

    denied = _admin()
    if denied:
        return denied
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        facts = _recording_facts(cur, recording_id)
        if facts is None:
            return jsonify({"success": False, "error": _("Recording not found")}), 404
        instance_id, session_id = facts[0], facts[1]
        cur.execute(
            "SELECT session_instance_tune_id FROM session_instance_tune WHERE session_instance_id = %s "
            "AND source = 'listen' AND confidence < 100 AND deleted = FALSE AND record_type = 'tune'",
            (instance_id,),
        )
        ids = [r[0] for r in cur.fetchall()]
        user_id = current_user.user_id
        try:
            for sit in ids:
                cur.execute(
                    "SELECT recording_tune_segment_id FROM recording_tune_segment "
                    "WHERE recording_id = %s AND session_instance_tune_id = %s",
                    (recording_id, sit),
                )
                seg = cur.fetchone()
                if seg:
                    save_to_history(
                        cur, "recording_tune_segment", "DELETE", seg[0], user_id
                    )
                    cur.execute(
                        "DELETE FROM recording_tune_segment WHERE recording_tune_segment_id = %s",
                        (seg[0],),
                    )
                apply_live_op(
                    cur, instance_id, "remove_tune", {"record_id": sit}, user_id
                )
        except OpRejected as r:
            conn.rollback()
            return jsonify({"success": False, "error": r.message}), 409
        conn.commit()
        return _tunes_response(
            conn, recording_id, instance_id, session_id, removed=len(ids)
        )
    finally:
        conn.close()


@api_login_required
def admin_listen_jobs():
    denied = _admin()
    if denied:
        return denied
    conn = get_db_connection()
    try:
        return jsonify({"success": True, "jobs": list_jobs(conn)})
    finally:
        conn.close()


def list_jobs(conn, limit=200):
    """Every job, newest first (the API and /admin/listen-jobs). A worker gone
    silent loses its job back to the queue first."""
    cur = conn.cursor()
    _requeue_stale(cur)
    conn.commit()
    cur.execute(f"SELECT {_COLS} {_FROM} ORDER BY j.listen_job_id DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    waiting = sorted(r[0] for r in rows if r[3] in ACTIVE)
    return [_job(r, waiting.index(r[0]) if r[3] == "queued" else None) for r in rows]


@api_login_required
def instance_known_tunes(session_instance_id):
    """For live listening (spec 053): the tunes this session logged before the
    night, which the listener prefers, and the session's keys for them."""
    from recording_routes import _instance_gate

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        denied = _instance_gate(cur, session_instance_id)
        if denied:
            return denied
        ids, keys = known_tunes(cur, session_instance_id)
        return jsonify(
            {
                "success": True,
                "session_instance_id": session_instance_id,
                "tune_ids": ids,
                "keys": keys,
            }
        )
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# The listening service
# --------------------------------------------------------------------------- #


@api_service_required(TOKEN_ENV)
def claim_listen_job():
    """The oldest waiting job, now held by this worker, with what it needs: the
    audio (a presigned URL), its length, and the session's tunes and keys.
    {"job": null} when there is none."""
    from recording import generate_presigned_url

    worker = str((request.get_json(silent=True) or {}).get("worker") or "listen")[:64]
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        _requeue_stale(cur)
        while True:
            cur.execute(
                "SELECT listen_job_id, recording_id FROM listen_job WHERE status = 'queued' "
                "ORDER BY queued_at, listen_job_id LIMIT 1 FOR UPDATE SKIP LOCKED"
            )
            row = cur.fetchone()
            if not row:
                conn.commit()
                return jsonify({"success": True, "job": None})
            job_id, recording_id = row
            (
                instance_id,
                _session_id,
                _date,
                duration_ms,
                _status,
                storage_key,
            ) = _recording_facts(cur, recording_id)
            if _logged_tunes(cur, instance_id):
                # someone logged the night while this waited: nothing to find
                cur.execute(
                    "UPDATE listen_job SET status = 'failed', finished_at = NOW(), error = %s WHERE listen_job_id = %s",
                    (
                        _("Tunes were logged for this night while the job waited"),
                        job_id,
                    ),
                )
                continue
            cur.execute(
                "UPDATE listen_job SET status = 'running', worker = %s, heartbeat_at = NOW(), "
                "started_at = COALESCE(started_at, NOW()), attempts = attempts + 1, phase = 'listening', "
                "progress = 0, heard_ms = 0 WHERE listen_job_id = %s",
                (worker, job_id),
            )
            ids, keys = known_tunes(cur, instance_id)
            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "job": {
                        "listen_job_id": job_id,
                        "kind": "find_tunes",
                        "recording_id": recording_id,
                        "session_instance_id": instance_id,
                        "audio_url": generate_presigned_url(storage_key),
                        "duration_ms": duration_ms,
                        "session_tunes": ids,
                        "keys": keys,
                    },
                }
            )
    finally:
        conn.close()


def _held(cur, job_id, worker):
    cur.execute(
        "SELECT status, worker FROM listen_job WHERE listen_job_id = %s FOR UPDATE",
        (job_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return row[0] if row[1] == worker or worker is None else "lost"


@api_service_required(TOKEN_ENV)
def listen_job_progress(job_id):
    """Where the job has got to (and the heartbeat). -> {"stop": true} when it
    was cancelled, or taken from this worker, and should stop."""
    body = request.get_json(silent=True) or {}
    status = (
        body.get("status") if body.get("status") in ("running", "paused") else "running"
    )
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        held = _held(cur, job_id, body.get("worker"))
        if held not in ("running", "paused"):
            conn.commit()
            return jsonify({"success": True, "stop": True, "status": held})
        cur.execute(
            "UPDATE listen_job SET status = %s, phase = %s, progress = %s, heard_ms = %s, "
            "running_s = %s, paused_s = %s, heartbeat_at = NOW() WHERE listen_job_id = %s",
            (
                status,
                body.get("phase"),
                body.get("progress"),
                body.get("heard_ms"),
                float(body.get("running_s") or 0),
                float(body.get("paused_s") or 0),
                job_id,
            ),
        )
        conn.commit()
        return jsonify({"success": True, "stop": False})
    finally:
        conn.close()


def _put_tunes_in(cur, recording_id, instance_id, user_id, drafts, confidence_model):
    """The found tunes into the night, in time order, as the segmenter logs a
    tune at a mark. A tune that cannot go in (an import from thesession.org
    that fails) is left out and said so. -> (logged, [names left out])."""
    from recording_routes import LogTuneError, log_tune

    logged, left_out = 0, []
    for d in sorted(drafts, key=lambda d: d["start_ms"]):
        tid = d.get("tune_id")
        local = False
        if tid is not None:
            cur.execute("SELECT 1 FROM tune WHERE tune_id = %s", (tid,))
            local = cur.fetchone() is not None
        conf = d.get("p_right")
        cur.execute("SAVEPOINT found_tune")
        try:
            log_tune(
                cur,
                recording_id,
                instance_id,
                user_id,
                start_ms=int(d["start_ms"]),
                end_ms=int(d["end_ms"]) if d.get("end_ms") is not None else None,
                from_audio=True,
                tune_id=tid if local else None,
                ts_id=tid if (tid is not None and not local) else None,
                name=d.get("name") or "",
                confidence=min(99, max(0, int(conf)))
                if conf is not None and confidence_model
                else None,
                confidence_model=confidence_model if conf is not None else None,
            )
            cur.execute("RELEASE SAVEPOINT found_tune")
            logged += 1
        except LogTuneError:
            cur.execute("ROLLBACK TO SAVEPOINT found_tune")
            left_out.append(d.get("name") or str(tid))
    return logged, left_out


@api_service_required(TOKEN_ENV)
def listen_job_result(job_id):
    """The tunes found: into the night, as the admin who asked; the job done."""
    body = request.get_json(silent=True) or {}
    drafts = body.get("drafts") or []
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        held = _held(cur, job_id, body.get("worker"))
        if held not in ("running", "paused"):
            conn.rollback()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": _("That job is no longer held by this worker"),
                    }
                ),
                409,
            )
        cur.execute(
            "SELECT recording_id, requested_by_user_id FROM listen_job WHERE listen_job_id = %s",
            (job_id,),
        )
        recording_id, user_id = cur.fetchone()
        instance_id = _recording_facts(cur, recording_id)[0]
        if _logged_tunes(cur, instance_id):
            error = _("Tunes were logged for this night while the job ran")
            cur.execute(
                "UPDATE listen_job SET status = 'failed', finished_at = NOW(), error = %s WHERE listen_job_id = %s",
                (error, job_id),
            )
            conn.commit()
            return jsonify({"success": False, "error": error}), 409
        logged, left_out = _put_tunes_in(
            cur,
            recording_id,
            instance_id,
            user_id,
            drafts,
            body.get("confidence_model"),
        )
        summary = dict(body.get("summary") or {})
        summary.update(
            logged=logged,
            left_out=left_out,
            confidence_model=body.get("confidence_model"),
        )
        cur.execute(
            "UPDATE listen_job SET status = 'done', phase = NULL, progress = 1, finished_at = NOW(), "
            "running_s = %s, paused_s = %s, result = %s, heartbeat_at = NOW() WHERE listen_job_id = %s",
            (
                float(body.get("running_s") or 0),
                float(body.get("paused_s") or 0),
                json.dumps(summary),
                job_id,
            ),
        )
        conn.commit()
        return jsonify({"success": True, "logged": logged, "left_out": left_out})
    finally:
        conn.close()


@api_service_required(TOKEN_ENV)
def listen_job_fail(job_id):
    """It could not. `retry`: put it back in the queue (under MAX_ATTEMPTS)."""
    body = request.get_json(silent=True) or {}
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        held = _held(cur, job_id, body.get("worker"))
        if held not in ("running", "paused"):
            conn.rollback()
            return jsonify({"success": True, "status": held})
        cur.execute(
            "SELECT attempts FROM listen_job WHERE listen_job_id = %s", (job_id,)
        )
        again = bool(body.get("retry")) and cur.fetchone()[0] < MAX_ATTEMPTS
        cur.execute(
            "UPDATE listen_job SET status = %s, worker = NULL, error = %s, "
            "finished_at = CASE WHEN %s THEN NULL ELSE NOW() END, running_s = %s, paused_s = %s "
            "WHERE listen_job_id = %s",
            (
                "queued" if again else "failed",
                str(body.get("error") or "")[:2000],
                again,
                float(body.get("running_s") or 0),
                float(body.get("paused_s") or 0),
                job_id,
            ),
        )
        conn.commit()
        return jsonify({"success": True, "status": "queued" if again else "failed"})
    finally:
        conn.close()
