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

from database import get_db_connection, get_current_user_id, save_to_history
from api_routes import api_login_required, segment_records_into_sets
from fractional_indexing import generate_append_position, generate_position_between


def event_channel(session_instance_id):
    """Postgres LISTEN/NOTIFY channel for one instance's feed (spec 024 §A4)."""
    return f"session_instance_{int(session_instance_id)}"


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


def _handle_add_tune(cur, session_instance_id, data, user_id):
    tune_id = data.get("tune_id")
    name = data.get("name")
    if name is not None:
        name = str(name).strip() or None
    if tune_id is None and not name:
        raise OpRejected("invalid", "add_tune requires tune_id or name.")

    source = data.get("source") or "human"
    confidence = data.get("confidence")
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


HANDLERS = {
    "add_tune": _handle_add_tune,
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

        # Feed write (same txn) + NOTIFY. Truth and feed cannot diverge (§B).
        try:
            cur.execute(
                """
                INSERT INTO session_event (session_instance_id, op_type, payload, op_id, created_by_user_id)
                VALUES (%s, %s, %s, %s, %s) RETURNING event_id
                """,
                (session_instance_id, op_type, json.dumps(payload), op_id, user_id),
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
        cur.execute("SELECT pg_notify(%s, %s)", (event_channel(session_instance_id), str(event_id)))
        cur.execute("COMMIT")

        return jsonify({"success": True, "event_id": event_id, "op_id": op_id,
                        "op_type": op_type, **payload})
    except Exception as e:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


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
