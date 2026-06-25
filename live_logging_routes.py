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
    extract_abc_incipit,
)
from auth import create_session
from api_routes import api_login_required, segment_records_into_sets, render_abc_to_png, bytea_to_base64, match_tune_core
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
# Aliased to `sit` because every SELECT LEFT JOINs `tune t` to surface tune_type
# (the catalog type drives the per-set "Reels/Jigs/Mixed" label in the UI).
_RECORD_COLS = (
    "sit.session_instance_tune_id, sit.tune_id, sit.name, sit.order_position, sit.record_type, "
    "sit.source, sit.confidence, sit.deleted, sit.started_by_person_id, sit.key_override, "
    "sit.setting_override, t.tune_type, sit.inserted_timestamp, cp.first_name, "
    "sp.first_name, sp.last_name, cp.person_id, slc.color, st.alias, t.name"
)
# LEFT JOIN tune (type/name), the creating user -> person (who logged it, for the per-set
# "Logged by X · time" tray AND the per-row logger color tint), the started-by person
# (the set starter; §19/§F), that logger's persisted per-session color (so a row carries
# its logger's color even when they're not currently present; §F), and the session_tune
# alias — so the display name falls back COALESCE(sit.name, st.alias, t.name) like the
# legacy editor (older rows store only tune_id, with sit.name NULL).
_RECORD_FROM = (
    "FROM session_instance_tune sit "
    "LEFT JOIN tune t ON t.tune_id = sit.tune_id "
    "LEFT JOIN user_account cu ON cu.user_id = sit.created_by_user_id "
    "LEFT JOIN person cp ON cp.person_id = cu.person_id "
    "LEFT JOIN person sp ON sp.person_id = sit.started_by_person_id "
    "LEFT JOIN session_instance si ON si.session_instance_id = sit.session_instance_id "
    "LEFT JOIN session_logger_color slc ON slc.session_id = si.session_id AND slc.person_id = cp.person_id "
    "LEFT JOIN session_tune st ON st.session_id = si.session_id AND st.tune_id = sit.tune_id"
)


def _display_name(first, last):
    if not first:
        return None
    return f"{first} {last[0]}" if last else first


def _record_to_dict(row):
    return {
        "session_instance_tune_id": row[0],
        "tune_id": row[1],
        # Display name: per-record override, else session alias, else catalog name
        # (older rows store only tune_id with sit.name NULL — matches the legacy editor).
        "name": row[2] or row[18] or row[19],
        "order_position": row[3],
        "record_type": row[4],
        "source": row[5],
        "confidence": row[6],
        "deleted": row[7],
        "started_by_person_id": row[8],
        "key_override": row[9],
        "setting_override": row[10],
        "tune_type": row[11],
        # ISO string (not a datetime) so the event payload is json.dumps-able and
        # the client can new Date() it.
        "logged_at": row[12].isoformat() if row[12] else None,
        "logged_by": row[13],
        "started_by_name": _display_name(row[14], row[15]),
        "logged_by_person_id": row[16],
        # Persisted palette index of the logger's per-session color (NULL if they have
        # no color yet, e.g. logged via the legacy UI); the client maps index -> color
        # for the subtle per-row attribution tint.
        "logged_by_color": row[17],
    }


def _load_record(cur, session_instance_id, record_id):
    cur.execute(
        f"""
        SELECT {_RECORD_COLS} {_RECORD_FROM}
        WHERE sit.session_instance_tune_id = %s AND sit.session_instance_id = %s
        """,
        (record_id, session_instance_id),
    )
    return cur.fetchone()


def _reselect(cur, record_id):
    cur.execute(
        f"SELECT {_RECORD_COLS} {_RECORD_FROM} WHERE sit.session_instance_tune_id = %s",
        (record_id,),
    )
    return _record_to_dict(cur.fetchone())


def _instance_exists(cur, session_instance_id):
    cur.execute("SELECT 1 FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
    return cur.fetchone() is not None


def emit_change_tune(cur, session_instance_id, record_id, user_id):
    """Append a `change_tune` feed event for a record + NOTIFY, so connected SSE
    clients update in real time. Use this when a session_instance_tune row is edited
    OUTSIDE the op endpoint (e.g. the shared tune-detail modal's REST save) so the
    live screen still stays in sync. Must run inside the editing transaction (so the
    event and the row change commit atomically). No-op if the record vanished.
    Returns the event_id, or None.
    """
    record = _reselect(cur, record_id)
    if not record:
        return None
    payload = {
        "record": record,
        "actor": {
            "person_id": getattr(current_user, "person_id", None),
            "name": (getattr(current_user, "first_name", "") or ""),
        },
    }
    cur.execute(
        """
        INSERT INTO session_event (session_instance_id, op_type, payload, op_id, created_by_user_id)
        VALUES (%s, 'change_tune', %s, NULL, %s) RETURNING event_id
        """,
        (session_instance_id, json.dumps(payload), user_id),
    )
    event_id = cur.fetchone()[0]
    cur.execute("SELECT pg_notify(%s, %s)", (LIVE_EVENT_CHANNEL, f"{session_instance_id}:{event_id}"))
    return event_id


# --- Positioning (relational anchor -> authoritative order_position, §C) ---


def _position_for(cur, session_instance_id, after_record_id, before_record_id=None):
    """Authoritative order_position from a relational anchor (§C):
      - before_record_id: insert just before that record (enables insert-at-start);
      - else after_record_id: insert just after it;
      - else append to the end.
    A vanished anchor degrades to append rather than dropping the op silently.
    """
    if before_record_id is not None:
        cur.execute(
            "SELECT order_position FROM session_instance_tune WHERE session_instance_tune_id = %s AND session_instance_id = %s",
            (before_record_id, session_instance_id),
        )
        row = cur.fetchone()
        if row:
            before_position = row[0]
            cur.execute(
                "SELECT MAX(order_position) FROM session_instance_tune WHERE session_instance_id = %s AND order_position < %s",
                (session_instance_id, before_position),
            )
            pred = cur.fetchone()[0]  # None if before_record is the very first
            return generate_position_between(pred, before_position)
        # before-anchor vanished -> fall through to after/append

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
    # Only for a pure append (a positioned insert is an explicit placement), and not
    # when the actor explicitly chose "keep both" (no_merge, §D16).
    if (data.get("after_record_id") is None and data.get("before_record_id") is None
            and not data.get("no_merge")):
        target = _find_corroboration_target(cur, session_instance_id, tune_id, name)
        if target is not None:
            return _corroborate(cur, session_instance_id, target[0], data, user_id)

    new_position = _position_for(cur, session_instance_id, data.get("after_record_id"), data.get("before_record_id"))

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
    """Set/clear who started this SET (§19; started_by is per-tune in 023 but means
    the whole set). Applies to every tune in the set containing record_id — the run
    of tunes between the surrounding breaks — in one txn/event, so all clients agree.
    """
    record_id = data.get("record_id")
    rec = _require_live_record(cur, session_instance_id, record_id)
    person_id = data.get("person_id")  # None clears it
    pos = rec[3]  # order_position (index 3 in _RECORD_COLS)

    # Bounds of this set: between the nearest break below and the nearest break above.
    cur.execute(
        "SELECT MAX(order_position) FROM session_instance_tune WHERE session_instance_id = %s AND record_type = 'break' AND order_position < %s",
        (session_instance_id, pos),
    )
    lower = cur.fetchone()[0] or ""
    cur.execute(
        "SELECT MIN(order_position) FROM session_instance_tune WHERE session_instance_id = %s AND record_type = 'break' AND order_position > %s",
        (session_instance_id, pos),
    )
    upper = cur.fetchone()[0]  # None if no break after (open/last set)

    cur.execute(
        """
        SELECT session_instance_tune_id FROM session_instance_tune
        WHERE session_instance_id = %s AND record_type = 'tune' AND deleted = FALSE
          AND order_position > %s AND (%s IS NULL OR order_position < %s)
        ORDER BY order_position
        """,
        (session_instance_id, lower, upper, upper),
    )
    ids = [r[0] for r in cur.fetchall()]
    for rid in ids:
        save_to_history(cur, "session_instance_tune", "UPDATE", rid, user_id=user_id)
    cur.execute(
        "UPDATE session_instance_tune SET started_by_person_id = %s, last_modified_user_id = %s WHERE session_instance_tune_id = ANY(%s)",
        (person_id, user_id, ids),
    )
    return {"records": [_reselect(cur, rid) for rid in ids],
            "person": _person_brief(cur, person_id) if person_id else None}


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
    # before_record_id supports the between-sets "new set" gap insert (§C): a break
    # placed just before the next set's first tune, after the new tune we just added.
    new_position = _position_for(cur, session_instance_id, data.get("after_record_id"), data.get("before_record_id"))
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
        # Claim this instance for the live editor (one-way lock): once a live op lands,
        # the legacy editor is read-only for it (spec 024 beta rollout). No-op after the
        # first claim; an admin can reset logging_mode back to 'legacy'.
        cur.execute(
            "UPDATE session_instance SET logging_mode = 'live' WHERE session_instance_id = %s AND logging_mode <> 'live'",
            (session_instance_id,),
        )
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
def live_tune_detail(session_instance_id, tune_id):
    """Detail for the tune-info drawer (spec 021 §18): catalog info + real stats."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        srow = cur.fetchone()
        if not srow:
            return jsonify({"success": False, "error": "Session instance not found"}), 404
        session_id = srow[0]

        cur.execute("SELECT name, tune_type, tunebook_count_cached FROM tune WHERE tune_id = %s", (tune_id,))
        t = cur.fetchone()
        if not t:
            return jsonify({"success": False, "error": "Tune not found"}), 404

        cur.execute(
            """
            SELECT COUNT(*) FROM session_instance_tune sit
            JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s AND sit.record_type = 'tune' AND sit.deleted = FALSE
            """,
            (session_id, tune_id),
        )
        played_here = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM session_instance_tune WHERE tune_id = %s AND record_type = 'tune' AND deleted = FALSE",
            (tune_id,),
        )
        played_global = cur.fetchone()[0]

        cur.execute(
            """
            SELECT DISTINCT si.date FROM session_instance_tune sit
            JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s AND sit.record_type = 'tune' AND sit.deleted = FALSE
            ORDER BY si.date DESC LIMIT 6
            """,
            (session_id, tune_id),
        )
        dates = [str(r[0]) for r in cur.fetchall()]

        return jsonify({
            "success": True,
            "tune_id": tune_id,
            "name": t[0],
            "tune_type": t[1],
            "tunebook_count": t[2],
            "played_here": played_here,
            "played_global": played_global,
            "dates": dates,
        })
    finally:
        conn.close()


def _disambiguate(people):
    """Append (#id) to any display names shared by >1 person."""
    seen = {}
    for pp in people:
        seen.setdefault(pp["display_name"], []).append(pp)
    for dn, group in seen.items():
        if len(group) > 1:
            for pp in group:
                pp["display_name"] = f"{dn} (#{pp['person_id']})"
    return people


@api_login_required
def live_people(session_instance_id):
    """Who's checked in to this instance (attendance='yes') — the 'started by' picker
    candidates and the header attendance list, with disambiguated display names."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT p.person_id, p.first_name, p.last_name
            FROM person p JOIN session_instance_person sip ON p.person_id = sip.person_id
            WHERE sip.session_instance_id = %s AND sip.attendance = 'yes'
            ORDER BY p.first_name, p.last_name
            """,
            (session_instance_id,),
        )
        rows = cur.fetchall()
        people = _disambiguate([{"person_id": r[0], "display_name": _display_name(r[1], r[2]) or f"#{r[0]}"} for r in rows])
        return jsonify({"success": True, "people": people})
    finally:
        conn.close()


@api_login_required
def live_people_search(session_instance_id):
    """Search people to add to attendance (§F editor). Matches active people by name;
    flags who's already checked in to this instance. Empty q -> []."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"success": True, "people": []})
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        like = f"%{q}%"
        cur.execute(
            """
            SELECT p.person_id, p.first_name, p.last_name,
                   COALESCE((SELECT sip.attendance = 'yes' FROM session_instance_person sip
                             WHERE sip.person_id = p.person_id AND sip.session_instance_id = %s), FALSE) AS attending
            FROM person p
            WHERE p.active = TRUE
              AND (p.first_name ILIKE %s OR p.last_name ILIKE %s
                   OR (COALESCE(p.first_name,'') || ' ' || COALESCE(p.last_name,'')) ILIKE %s)
            ORDER BY attending DESC, p.first_name, p.last_name
            LIMIT 15
            """,
            (session_instance_id, like, like, like),
        )
        rows = cur.fetchall()
        people = _disambiguate([
            {"person_id": r[0], "display_name": _display_name(r[1], r[2]) or f"#{r[0]}", "attending": r[3]}
            for r in rows
        ])
        return jsonify({"success": True, "people": people})
    finally:
        conn.close()


# Default meter per tune type, so the incipit ABC bars correctly for abcjs (§D deep search).
_TYPE_METER = {
    "Jig": "6/8", "Slip Jig": "9/8", "Hop Jig": "9/8", "Reel": "4/4",
    "Hornpipe": "4/4", "Barndance": "4/4", "Strathspey": "4/4", "Polka": "2/4",
    "Slide": "12/8", "Waltz": "3/4", "Mazurka": "3/4", "March": "4/4",
    "Three-Two": "3/2", "Set Dance": "4/4", "Air": "4/4",
}


def _wrap_abc(notes, key, tune_type):
    """Wrap bare ABC notes with the headers the renderer needs."""
    notes = (notes or "").strip()
    if not notes:
        return None
    if notes.startswith("X:"):
        return notes
    meter = _TYPE_METER.get(tune_type, "4/4")
    return f"X:1\nM:{meter}\nL:1/8\nK:{key or 'D'}\n{notes}"


def _ensure_incipit(cur, tune_id, want_full=False):
    """Return the cached incipit image (base64), rendering it from ABC via the
    abc-renderer service and caching it if missing (notation is always the service's
    job — the app never renders client-side). Optionally also render+cache the full
    image (for the drawer's incipit/full toggle). None if there's no ABC to render."""
    cur.execute(
        """
        SELECT ts.setting_id, ts.key, ts.incipit_abc, ts.abc, ts.incipit_image, ts.image, t.tune_type
        FROM tune_setting ts JOIN tune t ON t.tune_id = ts.tune_id
        WHERE ts.tune_id = %s ORDER BY (ts.incipit_image IS NULL), ts.setting_id LIMIT 1
        """,
        (tune_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    setting_id, key, incipit_abc, abc, incipit_image, image, tune_type = row
    need_inc = incipit_image is None
    need_full = want_full and image is None
    if not need_inc and not need_full:
        return bytea_to_base64(incipit_image)

    inc_text = (incipit_abc or "").strip() or (extract_abc_incipit(abc, tune_type) if abc else "")
    inc_png = None
    if need_inc and inc_text:
        inc_png = render_abc_to_png(_wrap_abc(inc_text, key, tune_type), is_incipit=True)
    full_png = None
    if need_full and abc:
        full_png = render_abc_to_png(_wrap_abc(abc, key, tune_type), is_incipit=False)

    sets, params = [], []
    if inc_png:
        sets.append("incipit_image = %s"); params.append(psycopg2.Binary(inc_png))
    if full_png:
        sets.append("image = %s"); params.append(psycopg2.Binary(full_png))
    if sets:
        sets.append("cache_updated_date = (NOW() AT TIME ZONE 'UTC')")
        params.append(setting_id)
        cur.execute(f"UPDATE tune_setting SET {', '.join(sets)} WHERE setting_id = %s", params)

    if inc_png:
        import base64
        return base64.b64encode(inc_png).decode()
    return bytea_to_base64(incipit_image)


@api_login_required
def live_deep_search(session_instance_id):
    """Deep catalog search for the live screen (spec 021 §D "search deeper").

    Modes: by name (default) or by ABC (`mode=abc` — matches the notation text).
    `type` is a hard tune-type filter (the popout); `prefer_type` is a soft sort
    preference (the set you're logging into) so matching-type tunes sort first.
    Returns rich cards: popularity, "on your list" / "in this session" flags, plays
    at this session, and a ready-to-render incipit ABC (client renders with abcjs).
    q may be empty to browse by type/popularity.
    """
    q = (request.args.get("q") or "").strip()
    tune_type = (request.args.get("type") or "").strip() or None
    prefer_type = (request.args.get("prefer_type") or "").strip() or None
    mode = "abc" if (request.args.get("mode") or "").strip().lower() == "abc" else "name"
    try:
        limit = min(40, max(1, int(request.args.get("limit", 25))))
    except (ValueError, TypeError):
        limit = 25

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        srow = cur.fetchone()
        if not srow:
            return jsonify({"success": False, "error": "Session instance not found"}), 404
        session_id = srow[0]
        person_id = getattr(current_user, "person_id", None)

        # SELECT-clause params first (subqueries + type_pref), then rank, then WHERE, then LIMIT.
        params = [person_id, session_id, session_id, prefer_type]
        rank = "0"
        order = "type_pref, t.tunebook_count_cached DESC NULLS LAST, t.name"
        if q and mode == "name":
            rank = """CASE WHEN LOWER(unaccent(t.name)) = LOWER(unaccent(%s)) THEN 1
                           WHEN LOWER(unaccent(t.name)) LIKE LOWER(unaccent(%s)) THEN 2 ELSE 3 END"""
            params += [q, f"{q}%"]
            order = "type_pref, rank, t.tunebook_count_cached DESC NULLS LAST, t.name"

        where = ["t.redirect_to_tune_id IS NULL"]
        if q and mode == "abc":
            # match the notation text (ignoring spaces, so "GED" finds "G E D")
            where.append("EXISTS(SELECT 1 FROM tune_setting ts WHERE ts.tune_id = t.tune_id AND REPLACE(ts.abc, ' ', '') ILIKE %s)")
            params.append(f"%{q.replace(' ', '')}%")
        elif q:
            where.append("LOWER(unaccent(t.name)) LIKE LOWER(unaccent(%s))")
            params.append(f"%{q}%")
        if tune_type:
            where.append("t.tune_type = %s")
            params.append(tune_type)
        params.append(limit)

        sql = f"""
            SELECT t.tune_id, t.name, t.tune_type, t.tunebook_count_cached,
                   EXISTS(SELECT 1 FROM person_tune pt WHERE pt.tune_id = t.tune_id AND pt.person_id = %s) AS on_list,
                   EXISTS(SELECT 1 FROM session_tune st WHERE st.tune_id = t.tune_id AND st.session_id = %s) AS in_session,
                   (SELECT COUNT(*) FROM session_instance_tune sit
                      JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
                      WHERE si.session_id = %s AND sit.tune_id = t.tune_id
                        AND sit.record_type = 'tune' AND sit.deleted = FALSE) AS played_here,
                   CASE WHEN t.tune_type = %s THEN 0 ELSE 1 END AS type_pref,
                   {rank} AS rank
            FROM tune t
            WHERE {' AND '.join(where)}
            ORDER BY {order}
            LIMIT %s
        """
        cur.execute(sql, params)
        rows = cur.fetchall()

        results = [
            {"tune_id": r[0], "name": r[1], "tune_type": r[2], "tunebook_count": r[3],
             "on_list": r[4], "in_session": r[5], "played_here": r[6]}
            for r in rows
        ]

        # one pass for the cached incipit IMAGE + whether the tune is renderable (has
        # ABC). Notation is rendered server-side by the abc-renderer service; the card
        # shows the cached image inline, or lazily asks the incipit endpoint to render
        # + cache it (no client-side rendering).
        if results:
            ids = [r["tune_id"] for r in results]
            cur.execute(
                """
                SELECT DISTINCT ON (tune_id) tune_id, incipit_image,
                       ((incipit_abc IS NOT NULL AND incipit_abc <> '') OR abc IS NOT NULL) AS can_render
                FROM tune_setting WHERE tune_id = ANY(%s)
                ORDER BY tune_id, (incipit_image IS NULL), setting_id
                """,
                (ids,),
            )
            settings = {row[0]: row for row in cur.fetchall()}
            for r in results:
                s = settings.get(r["tune_id"])
                r["incipit_image"] = bytea_to_base64(s[1]) if (s and s[1]) else None
                r["can_render"] = bool(s[2]) if s else False

        return jsonify({"success": True, "results": results})
    finally:
        conn.close()


@api_login_required
def live_match(session_instance_id):
    """Type-ahead + Enter-gate matching for the live screen, IDENTICAL to the legacy
    pill editor (shares `match_tune_core` -> find_matching_tune + wildcard), so a typed
    string resolves the same way in both UIs.

    GET ?q=&prefer_type=&limit= -> {success, matched, exact_match, results:[...]}.
    `prefer_type` is the type of the set being logged into (soft sort preference).
    """
    q = (request.args.get("q") or "").strip()
    prefer_type = (request.args.get("prefer_type") or "").strip() or None
    try:
        limit = min(20, max(1, int(request.args.get("limit", 8))))
    except (ValueError, TypeError):
        limit = 8
    if len(q) < 2:
        return jsonify({"success": True, "matched": False, "exact_match": False, "results": []})

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        srow = cur.fetchone()
        if not srow:
            return jsonify({"success": False, "error": "Session instance not found"}), 404
        result = match_tune_core(cur, srow[0], q, prefer_type, limit)
        return jsonify({"success": True, **result})
    finally:
        conn.close()


@api_login_required
def live_incipit(session_instance_id, tune_id):
    """Incipit image (base64) for a tune, rendered+cached on demand via the renderer
    service if missing. `?kind=both` also renders the full image (drawer toggle).
    Used by the deep-search cards (lazy, background) so notation is always service-
    rendered, never client-side."""
    kind = (request.args.get("kind") or "").strip().lower()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            img = _ensure_incipit(cur, tune_id, want_full=(kind == "both"))
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            img = None
        return jsonify({"success": True, "image": img})
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
            SELECT {_RECORD_COLS} {_RECORD_FROM}
            WHERE sit.session_instance_id = %s AND sit.deleted = FALSE
            ORDER BY sit.order_position
            """,
            (session_instance_id,),
        )
        rows = cur.fetchall()
        records = [_record_to_dict(r) for r in rows]
        # record_type is index 4 in _RECORD_COLS; segment into sets, dropping breaks.
        sets = [[_record_to_dict(r) for r in s] for s in segment_records_into_sets(rows, type_index=4)]

        cur.execute(
            """
            SELECT si.session_id, si.comments, si.log_complete_date, si.date, s.name, s.path, s.timezone
            FROM session_instance si JOIN session s ON s.session_id = si.session_id
            WHERE si.session_instance_id = %s
            """,
            (session_instance_id,),
        )
        meta = cur.fetchone()
        session_date = meta[3].strftime("%a · %b %-d, %Y") if meta and meta[3] else ""

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
            # Display tz for "logged at" times: viewer's own tz wins, session tz is
            # the fallback (mirrors the app's format_datetime_tz precedence).
            "user_timezone": getattr(current_user, "timezone", None),
            "session_timezone": meta[6] if meta else None,
            "session_id": meta[0] if meta else None,
            "notes": meta[1] if meta else None,
            "log_complete": bool(meta[2]) if meta else False,
            "session_name": meta[4] if meta else "",
            "session_path": meta[5] if meta else None,
            "session_date": session_date,
            "records": records,
            "sets": sets,
            "last_event_id": high_water,
        })
    finally:
        conn.close()
