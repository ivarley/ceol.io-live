"""
Live logging — the referee (sync Flask side) for spec 024.

Phase 1: the full op vocabulary (§C) over one generic, idempotent op endpoint.
The referee is server-authoritative (§A2): a client POSTs an intent-op carrying a
client-generated `op_id` (UUID) and a relational anchor; the server computes the
authoritative `order_position`, mutates the canonical `session_instance_tune` (or
instance metadata), appends the `session_event` feed row, and `pg_notify`s the
per-instance channel — all in ONE transaction. The async streaming service
re-reads the event and fans it out over SSE (§B / §A4).

Ops (this build):
  Tune/set:  add_tune, remove_tune (soft tombstone), change_tune (relink/rename/
             unlink/key/setting), set_confidence, set_break (insert/remove),
             attribute_set_starter
  Metadata:  edit_notes, mark_complete, mark_incomplete

Idempotency (§C): every op carries `op_id`; a retried POST whose ack was lost
dedupes to the same `session_event` row (UNIQUE on op_id) and returns the cached
ack. Conflicts surface as a "rejected + reason" ack the affected client renders
itself (§E) — no per-recipient channel.

Still ahead (Phase 1 tail / later): attendance ops (they have active-session side
effects), server-generated corroborate/merge detection (§H30), presence (§F).
"""

import json
import uuid

import psycopg2
from flask import request, jsonify
from flask_login import current_user

from database import (
    get_db_connection,
    get_current_user_id,
    save_to_history,
    find_matching_tune,
    normalize_apostrophes,
    check_in_person as db_check_in_person,
    remove_person_attendance as db_remove_person_attendance,
    create_person_with_instruments as db_create_person_with_instruments,
)
from auth import create_session
from api_routes import api_login_required, segment_records_into_sets
from fractional_indexing import generate_append_position, generate_position_between


# One global LISTEN/NOTIFY channel for the whole feed (spec 024 §A4). The payload
# is "<instance_id>:<event_id>"; the streaming service filters by instance. A single
# channel means the streaming service holds ONE listener connection total, instead of
# one per SSE client (which would cap concurrent clients at the DB pool size).
LIVE_EVENT_CHANNEL = "live_session_events"


class OpRejected(Exception):
    """A processed-but-rejected op (§E): no-op, with a machine reason for the actor."""

    def __init__(self, reason, message=None):
        super().__init__(message or reason)
        self.reason = reason
        self.message = message or reason


# --- Serialization --------------------------------------------------------

# Column order for the record SELECTs below; one place to keep them in sync.
_RECORD_COLS = (
    "session_instance_tune_id, tune_id, name, order_position, record_type, "
    "source, confidence, deleted, started_by_person_id, key_override, setting_override"
)


def _record_to_dict(row):
    return {
        "session_instance_tune_id": row[0],
        "tune_id": row[1],
        "name": row[2],
        "order_position": row[3],
        "record_type": row[4],
        "source": row[5],
        "confidence": row[6],
        "deleted": row[7],
        "started_by_person_id": row[8],
        "key_override": row[9],
        "setting_override": row[10],
    }


def _load_record(cur, session_instance_id, record_id):
    cur.execute(
        f"""
        SELECT {_RECORD_COLS} FROM session_instance_tune
        WHERE session_instance_tune_id = %s AND session_instance_id = %s
        """,
        (record_id, session_instance_id),
    )
    return cur.fetchone()


def _reselect(cur, record_id):
    cur.execute(
        f"SELECT {_RECORD_COLS} FROM session_instance_tune WHERE session_instance_tune_id = %s",
        (record_id,),
    )
    return _record_to_dict(cur.fetchone())


def _instance_exists(cur, session_instance_id):
    cur.execute("SELECT 1 FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
    return cur.fetchone() is not None


# --- Positioning (relational anchor -> authoritative order_position, §C) ---


def _position_for(cur, session_instance_id, after_record_id):
    """Insert right after `after_record_id`; if it's gone/None, append to the end.

    Anchor fallback (spec 024 positioning rule): a vanished neighbor degrades to
    append rather than dropping the op silently.
    """
    after_position = None
    if after_record_id is not None:
        cur.execute(
            "SELECT order_position FROM session_instance_tune WHERE session_instance_tune_id = %s AND session_instance_id = %s",
            (after_record_id, session_instance_id),
        )
        row = cur.fetchone()
        after_position = row[0] if row else None

    if after_position is None:
        cur.execute(
            "SELECT MAX(order_position) FROM session_instance_tune WHERE session_instance_id = %s",
            (session_instance_id,),
        )
        return generate_append_position(cur.fetchone()[0])

    cur.execute(
        "SELECT MIN(order_position) FROM session_instance_tune WHERE session_instance_id = %s AND order_position > %s",
        (session_instance_id, after_position),
    )
    return generate_position_between(after_position, cur.fetchone()[0])


# --- Op handlers: (cur, session_instance_id, data, user_id) -> payload dict --
# Each performs the mutation and returns the payload stored in session_event AND
# returned to the caller. Raise OpRejected for a deterministic no-op rejection.


def _require_live_record(cur, session_instance_id, record_id, *, allow_break=False):
    rec = _load_record(cur, session_instance_id, record_id)
    if rec is None:
        raise OpRejected("not_found", "That record no longer exists.")
    if rec[7]:  # deleted -> removal beats a concurrent edit (§E2)
        raise OpRejected("target_deleted", "That tune was removed by someone else.")
    if rec[4] == "break" and not allow_break:
        raise OpRejected("wrong_record_type", "That record is a set break.")
    return rec


# A record is in the "open set" if it sits after the last break (or there is no
# break). One place to express it; the per-instance break subquery is appended.
_OPEN_SET = """order_position > COALESCE(
    (SELECT MAX(order_position) FROM session_instance_tune
     WHERE session_instance_id = %s AND record_type = 'break'), '')"""


def _find_corroboration_target(cur, session_instance_id, tune_id, name):
    """The same tune already live in the *open set* (after the last break).

    The realistic concurrency case (§H30): two loggers both append the same tune
    at once; the second collapses into the first (credit the earliest row). Identity
    is the resolved `tune_id` when linked; otherwise — when tune-matching fully
    failed — an identical normalized raw name among the *also-unlinked* rows. Scoped
    to appends; mid-set anchored inserts are not merged.
    """
    if tune_id is not None:
        cur.execute(
            f"""
            SELECT session_instance_tune_id, created_by_user_id
            FROM session_instance_tune
            WHERE session_instance_id = %s AND record_type = 'tune'
              AND deleted = FALSE AND tune_id = %s AND {_OPEN_SET}
            ORDER BY order_position LIMIT 1
            """,
            (session_instance_id, tune_id, session_instance_id),
        )
    elif name:
        cur.execute(
            f"""
            SELECT session_instance_tune_id, created_by_user_id
            FROM session_instance_tune
            WHERE session_instance_id = %s AND record_type = 'tune'
              AND deleted = FALSE AND tune_id IS NULL
              AND LOWER(unaccent(name)) = LOWER(unaccent(%s)) AND {_OPEN_SET}
            ORDER BY order_position LIMIT 1
            """,
            (session_instance_id, name, session_instance_id),
        )
    else:
        return None
    return cur.fetchone()


def _corroborate(cur, session_instance_id, target_id, data, user_id):
    """Record a corroboration on an existing record + bump its confidence (§H30).

    Emits a server-generated `corroborate` event (op_type override) carrying the
    updated record, instead of inserting a duplicate tune row."""
    source = data.get("source") or "human"
    cur.execute(
        """
        INSERT INTO corroboration (record_id, user_id, source, confidence, client_asserted_ts)
        VALUES (%s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
        ON CONFLICT (record_id, user_id)
        DO UPDATE SET source = EXCLUDED.source, confidence = EXCLUDED.confidence,
                      client_asserted_ts = EXCLUDED.client_asserted_ts
        """,
        (target_id, user_id, source, data.get("confidence")),
    )
    # Two distinct actors agreeing on the same tune/slot = human-verified.
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM corroboration WHERE record_id = %s", (target_id,))
    distinct_corroborators = cur.fetchone()[0]
    save_to_history(cur, "session_instance_tune", "UPDATE", target_id, user_id=user_id)
    cur.execute(
        "UPDATE session_instance_tune SET confidence = 100, last_modified_user_id = %s WHERE session_instance_tune_id = %s",
        (user_id, target_id),
    )
    return {
        "_op_type": "corroborate",
        "record": _reselect(cur, target_id),
        "corroborated_by_user_id": user_id,
        "corroborators": distinct_corroborators,
    }


def _handle_add_tune(cur, session_instance_id, data, user_id):
    tune_id = data.get("tune_id")
    name = data.get("name")
    if name is not None:
        name = normalize_apostrophes(str(name).strip()) or None
    if tune_id is None and not name:
        raise OpRejected("invalid", "add_tune requires tune_id or name.")

    # Name -> tune matching takes priority. Tapping a typeahead result sends a
    # tune_id directly; hitting Enter sends just the text, which we resolve here
    # via the same matching the rest of the app uses. An ambiguous/unknown name
    # stays unlinked (raw name, tune_id NULL).
    if tune_id is None and name:
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        srow = cur.fetchone()
        if srow:
            matched_id, final_name, err = find_matching_tune(cur, srow[0], name)
            if matched_id and not err:
                tune_id, name = matched_id, final_name

    source = data.get("source") or "human"
    confidence = data.get("confidence")

    # Duplicate-in-open-set collapses into a corroboration of the earliest row:
    # by tune_id when linked, else by identical raw name when matching fully failed.
    if data.get("after_record_id") is None:
        target = _find_corroboration_target(cur, session_instance_id, tune_id, name)
        if target is not None:
            return _corroborate(cur, session_instance_id, target[0], data, user_id)

    new_position = _position_for(cur, session_instance_id, data.get("after_record_id"))

    cur.execute(
        """
        INSERT INTO session_instance_tune (
            session_instance_id, tune_id, name, order_position, record_type,
            source, confidence, logged_timestamp, client_device_id,
            inserted_timestamp, created_by_user_id, last_modified_user_id
        ) VALUES (%s, %s, %s, %s, 'tune', %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), %s, %s)
        RETURNING session_instance_tune_id
        """,
        (session_instance_id, tune_id, name, new_position, source, confidence,
         data.get("logged_timestamp"), data.get("client_device_id"), user_id, user_id),
    )
    record_id = cur.fetchone()[0]
    save_to_history(cur, "session_instance_tune", "INSERT", record_id, user_id=user_id)
    return {"record": _reselect(cur, record_id)}


def _handle_remove_tune(cur, session_instance_id, data, user_id):
    """Soft tombstone (§C): undo/restore stays possible; removal beats edits (§E2)."""
    record_id = data.get("record_id")
    rec = _load_record(cur, session_instance_id, record_id)
    if rec is None:
        raise OpRejected("not_found", "That record no longer exists.")
    if rec[7]:
        return {"record": _record_to_dict(rec), "already_removed": True}  # idempotent
    save_to_history(cur, "session_instance_tune", "UPDATE", record_id, user_id=user_id)
    cur.execute(
        "UPDATE session_instance_tune SET deleted = TRUE, last_modified_user_id = %s WHERE session_instance_tune_id = %s",
        (user_id, record_id),
    )
    return {"record": _reselect(cur, record_id)}


def _handle_change_tune(cur, session_instance_id, data, user_id):
    """Identity-preserving relink / rename / unlink / key / setting (§C)."""
    record_id = data.get("record_id")
    _require_live_record(cur, session_instance_id, record_id)

    sets, params = [], []
    if data.get("unlink"):
        sets += ["tune_id = NULL"]
    elif "tune_id" in data:
        sets += ["tune_id = %s"]; params += [data["tune_id"]]
    if "name" in data:
        nm = data["name"]
        sets += ["name = %s"]; params += [str(nm).strip() if nm else None]
    if "key_override" in data:
        sets += ["key_override = %s"]; params += [data["key_override"]]
    if "setting_override" in data:
        sets += ["setting_override = %s"]; params += [data["setting_override"]]
    if not sets:
        raise OpRejected("invalid", "change_tune had no fields to change.")

    save_to_history(cur, "session_instance_tune", "UPDATE", record_id, user_id=user_id)
    sets += ["last_modified_user_id = %s"]; params += [user_id, record_id]
    cur.execute(
        f"UPDATE session_instance_tune SET {', '.join(sets)} WHERE session_instance_tune_id = %s",
        tuple(params),
    )
    return {"record": _reselect(cur, record_id)}


def _handle_set_confidence(cur, session_instance_id, data, user_id):
    """Set confidence (Confirm = ->100/human-verified) and record a corroboration."""
    record_id = data.get("record_id")
    _require_live_record(cur, session_instance_id, record_id)
    confidence = data.get("confidence", 100)

    save_to_history(cur, "session_instance_tune", "UPDATE", record_id, user_id=user_id)
    cur.execute(
        "UPDATE session_instance_tune SET confidence = %s, last_modified_user_id = %s WHERE session_instance_tune_id = %s",
        (confidence, user_id, record_id),
    )
    # The actor corroborates this record (§H30); keyed by user, person derived.
    cur.execute(
        """
        INSERT INTO corroboration (record_id, user_id, source, confidence, client_asserted_ts)
        VALUES (%s, %s, 'human', %s, (NOW() AT TIME ZONE 'UTC'))
        ON CONFLICT (record_id, user_id)
        DO UPDATE SET confidence = EXCLUDED.confidence, client_asserted_ts = EXCLUDED.client_asserted_ts
        """,
        (record_id, user_id, confidence),
    )
    return {"record": _reselect(cur, record_id)}


def _handle_attribute_set_starter(cur, session_instance_id, data, user_id):
    """Set/clear the person who started this set's tune (§C; stays per-tune, 023)."""
    record_id = data.get("record_id")
    _require_live_record(cur, session_instance_id, record_id)
    person_id = data.get("person_id")  # None clears it
    save_to_history(cur, "session_instance_tune", "UPDATE", record_id, user_id=user_id)
    cur.execute(
        "UPDATE session_instance_tune SET started_by_person_id = %s, last_modified_user_id = %s WHERE session_instance_tune_id = %s",
        (person_id, user_id, record_id),
    )
    return {"record": _reselect(cur, record_id)}


def _handle_set_break(cur, session_instance_id, data, user_id):
    """Insert or remove a positioned break record (§C). End-set/Split/Join all
    reduce to placing or removing a break. Breaks lack stable client identity, so
    removal is a hard delete (a tune removal would instead be a tombstone)."""
    action = data.get("action", "insert")
    if action == "remove":
        record_id = data.get("record_id")
        rec = _load_record(cur, session_instance_id, record_id)
        if rec is None:
            return {"record_id": record_id, "removed": True, "already_removed": True}
        if rec[4] != "break":
            raise OpRejected("wrong_record_type", "That record is not a set break.")
        save_to_history(cur, "session_instance_tune", "DELETE", record_id, user_id=user_id)
        cur.execute("DELETE FROM session_instance_tune WHERE session_instance_tune_id = %s", (record_id,))
        return {"record_id": record_id, "removed": True}

    if action != "insert":
        raise OpRejected("invalid", f"unknown set_break action '{action}'.")
    new_position = _position_for(cur, session_instance_id, data.get("after_record_id"))
    cur.execute(
        """
        INSERT INTO session_instance_tune (
            session_instance_id, order_position, record_type, inserted_timestamp,
            created_by_user_id, last_modified_user_id
        ) VALUES (%s, %s, 'break', (NOW() AT TIME ZONE 'UTC'), %s, %s)
        RETURNING session_instance_tune_id
        """,
        (session_instance_id, new_position, user_id, user_id),
    )
    record_id = cur.fetchone()[0]
    save_to_history(cur, "session_instance_tune", "INSERT", record_id, user_id=user_id)
    return {"record": _reselect(cur, record_id)}


def _handle_edit_notes(cur, session_instance_id, data, user_id):
    notes = data.get("notes")
    save_to_history(cur, "session_instance", "UPDATE", session_instance_id, user_id=user_id)
    cur.execute(
        "UPDATE session_instance SET comments = %s, last_modified_user_id = %s WHERE session_instance_id = %s",
        (notes, user_id, session_instance_id),
    )
    return {"notes": notes}


def _set_log_complete(cur, session_instance_id, user_id, complete):
    save_to_history(cur, "session_instance", "UPDATE", session_instance_id, user_id=user_id)
    if complete:
        cur.execute(
            "UPDATE session_instance SET log_complete_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s WHERE session_instance_id = %s",
            (user_id, session_instance_id),
        )
    else:
        cur.execute(
            "UPDATE session_instance SET log_complete_date = NULL, last_modified_user_id = %s WHERE session_instance_id = %s",
            (user_id, session_instance_id),
        )
    cur.execute("SELECT log_complete_date FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
    return {"log_complete": complete, "log_complete_date": str(cur.fetchone()[0]) if complete else None}


def _handle_mark_complete(cur, session_instance_id, data, user_id):
    return _set_log_complete(cur, session_instance_id, user_id, True)


def _handle_mark_incomplete(cur, session_instance_id, data, user_id):
    return _set_log_complete(cur, session_instance_id, user_id, False)


def _person_brief(cur, person_id):
    cur.execute("SELECT person_id, first_name, last_name FROM person WHERE person_id = %s", (person_id,))
    row = cur.fetchone()
    if not row:
        return {"person_id": person_id}
    return {"person_id": row[0], "first_name": row[1], "last_name": row[2],
            "display_name": f"{row[1]} {row[2]}".strip()}


# Attendance ops (§C). These reuse the existing DB helpers, which manage their own
# transaction AND the active_session_manager side effects, so the attendance write
# commits before this op's feed event (acceptable for metadata; a missed event is
# self-healing on the next bootstrap). op_id still guards against double-apply.
def _handle_attendance_add(cur, session_instance_id, data, user_id):
    person_id = data.get("person_id")
    if person_id is None:
        raise OpRejected("invalid", "attendance_add requires person_id.")
    attendance = data.get("attendance", "yes")
    comment = data.get("comment", "")
    ok, message, action = db_check_in_person(session_instance_id, person_id, attendance, comment, user_id=user_id)
    if not ok:
        raise OpRejected("attendance_failed", message)
    return {"attendance": attendance, "comment": comment, "action": action, "person": _person_brief(cur, person_id)}


def _handle_attendance_remove(cur, session_instance_id, data, user_id):
    person_id = data.get("person_id")
    if person_id is None:
        raise OpRejected("invalid", "attendance_remove requires person_id.")
    person = _person_brief(cur, person_id)  # capture name before the row goes
    ok, message, _prev = db_remove_person_attendance(session_instance_id, person_id, user_id=user_id)
    if not ok:
        raise OpRejected("attendance_failed", message)
    return {"removed": True, "person": person}


def _handle_attendance_create_person(cur, session_instance_id, data, user_id):
    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    if not first:
        raise OpRejected("invalid", "attendance_create_person requires first_name.")
    ok, message, person_id, display_name = db_create_person_with_instruments(
        first, last, email=data.get("email"), instruments=data.get("instruments"), user_id=user_id)
    if not ok:
        raise OpRejected("create_failed", message)
    attendance = data.get("attendance", "yes")
    db_check_in_person(session_instance_id, person_id, attendance, data.get("comment", ""), user_id=user_id)
    return {"created": True, "attendance": attendance,
            "person": {"person_id": person_id, "first_name": first, "last_name": last, "display_name": display_name}}


HANDLERS = {
    "add_tune": _handle_add_tune,
    "attendance_add": _handle_attendance_add,
    "attendance_remove": _handle_attendance_remove,
    "attendance_create_person": _handle_attendance_create_person,
    "remove_tune": _handle_remove_tune,
    "change_tune": _handle_change_tune,
    "set_confidence": _handle_set_confidence,
    "attribute_set_starter": _handle_attribute_set_starter,
    "set_break": _handle_set_break,
    "edit_notes": _handle_edit_notes,
    "mark_complete": _handle_mark_complete,
    "mark_incomplete": _handle_mark_incomplete,
}


# --- Endpoints ------------------------------------------------------------


@api_login_required
def live_op(session_instance_id):
    """Generic op endpoint: dispatch by op_type, one atomic txn, idempotent by op_id."""
    data = request.get_json(silent=True) or {}
    op_type = data.get("op_type")
    op_id = data.get("op_id")
    handler = HANDLERS.get(op_type)
    if handler is None:
        return jsonify({"success": False, "error": f"unknown op_type '{op_type}'"}), 400
    if op_id is not None:
        try:
            op_id = str(uuid.UUID(str(op_id)))  # normalize/validate
        except ValueError:
            return jsonify({"success": False, "error": "op_id must be a UUID"}), 400

    user_id = get_current_user_id()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        if not _instance_exists(cur, session_instance_id):
            cur.execute("ROLLBACK")
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        # Idempotency fast path: a known op_id returns its cached ack (§C).
        if op_id is not None:
            cur.execute(
                "SELECT event_id, op_type, payload FROM session_event WHERE op_id = %s",
                (op_id,),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute("ROLLBACK")
                return jsonify({"success": True, "duplicate": True, "event_id": existing[0],
                                "op_id": op_id, "op_type": existing[1], **existing[2]})

        try:
            payload = handler(cur, session_instance_id, data, user_id)
        except OpRejected as r:
            cur.execute("ROLLBACK")
            return jsonify({"success": False, "rejected": True, "reason": r.reason,
                            "message": r.message, "op_id": op_id, "op_type": op_type})

        # Stamp the actor (person, per §D) so observers can render "Sarah added …"
        # notices and, later, attribution colors. user_id is the audit fact; the
        # person is what the UI shows.
        payload["actor"] = {
            "person_id": getattr(current_user, "person_id", None),
            "name": (getattr(current_user, "first_name", "") or ""),
        }

        # A handler may emit a different event type than the client requested
        # (e.g. add_tune that collapsed into a server-generated `corroborate`, §H30).
        event_op_type = payload.pop("_op_type", op_type)

        # Feed write (same txn) + NOTIFY. Truth and feed cannot diverge (§B).
        try:
            cur.execute(
                """
                INSERT INTO session_event (session_instance_id, op_type, payload, op_id, created_by_user_id)
                VALUES (%s, %s, %s, %s, %s) RETURNING event_id
                """,
                (session_instance_id, event_op_type, json.dumps(payload), op_id, user_id),
            )
        except psycopg2.errors.UniqueViolation:
            # Concurrent retry of the same op_id won the race; discard ours, return theirs.
            cur.execute("ROLLBACK")
            cur.execute("SELECT event_id, op_type, payload FROM session_event WHERE op_id = %s", (op_id,))
            row = cur.fetchone()
            if row:
                return jsonify({"success": True, "duplicate": True, "event_id": row[0],
                                "op_id": op_id, "op_type": row[1], **row[2]})
            raise
        event_id = cur.fetchone()[0]
        cur.execute("SELECT pg_notify(%s, %s)", (LIVE_EVENT_CHANNEL, f"{session_instance_id}:{event_id}"))
        cur.execute("COMMIT")

        return jsonify({"success": True, "event_id": event_id, "op_id": op_id,
                        "op_type": event_op_type, **payload})
    except Exception as e:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def live_issue_token():
    """
    Mint a bearer token for a non-cookie client (spec 024 §H).

    A cookie-authenticated user exchanges their session for a bearer token (a
    `user_session` id) that a future native/WKWebView client can present to the
    streaming service and op endpoints instead of the web cookie. Same lifetime
    and revocation as a web session.
    """
    ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR"))
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent")
    token = create_session(current_user.user_id, ip_address=ip, user_agent=user_agent)
    return jsonify({"success": True, "token": token, "token_type": "Bearer"})


@api_login_required
def live_bootstrap(session_instance_id):
    """
    Bootstrap snapshot for the live screen (spec 024 §H).

    Current (non-deleted) records, both flat and segmented into sets, plus the
    feed high-water mark (max event_id). The client renders this, then opens the
    SSE stream with that mark so it receives only the delta.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if not _instance_exists(cur, session_instance_id):
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        cur.execute(
            f"""
            SELECT {_RECORD_COLS} FROM session_instance_tune
            WHERE session_instance_id = %s AND deleted = FALSE
            ORDER BY order_position
            """,
            (session_instance_id,),
        )
        rows = cur.fetchall()
        records = [_record_to_dict(r) for r in rows]
        # record_type is index 4 in _RECORD_COLS; segment into sets, dropping breaks.
        sets = [[_record_to_dict(r) for r in s] for s in segment_records_into_sets(rows, type_index=4)]

        cur.execute("SELECT comments, log_complete_date FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        meta = cur.fetchone()

        cur.execute("SELECT COALESCE(MAX(event_id), 0) FROM session_event WHERE session_instance_id = %s", (session_instance_id,))
        high_water = cur.fetchone()[0]

        return jsonify({
            "success": True,
            "session_instance_id": int(session_instance_id),
            "current_person": {
                "person_id": getattr(current_user, "person_id", None),
                "first_name": getattr(current_user, "first_name", ""),
                "last_name": getattr(current_user, "last_name", ""),
            },
            "notes": meta[0] if meta else None,
            "log_complete": bool(meta[1]) if meta else False,
            "records": records,
            "sets": sets,
            "last_event_id": high_water,
        })
    finally:
        conn.close()
