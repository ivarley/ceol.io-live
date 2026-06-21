"""
Live logging — the referee (sync Flask side) for spec 024.

Phase 0 walking skeleton: a single op, `add_tune`, taken through the entire real
pipeline. The referee is server-authoritative (spec 024 §A2): the client sends an
intent-op with a *relational anchor*; the server computes the authoritative
`order_position`, writes the canonical `session_instance_tune` row AND the
`session_event` feed row in ONE transaction, then `pg_notify`s the per-instance
channel with the new event_id. The separate async streaming service LISTENs,
re-reads the event row, and pushes it over SSE (spec 024 §B / §A4).

Later phases add the rest of the op vocabulary (§C), op_id idempotency, set/break
handling, conflict rules, etc. This file deliberately implements only what the
walking skeleton needs to prove the novel infra end-to-end.
"""

import json
from flask import request, jsonify
from flask_login import current_user

from database import get_db_connection, get_current_user_id, save_to_history
from api_routes import api_login_required
from fractional_indexing import generate_append_position, generate_position_between


def event_channel(session_instance_id):
    """Postgres LISTEN/NOTIFY channel for one instance's feed (spec 024 §A4)."""
    return f"session_instance_{int(session_instance_id)}"


def _instance_exists(cur, session_instance_id):
    cur.execute(
        "SELECT 1 FROM session_instance WHERE session_instance_id = %s",
        (session_instance_id,),
    )
    return cur.fetchone() is not None


def _record_to_dict(row):
    """Shape a session_instance_tune row (as a dict-ish tuple) for the feed payload."""
    return {
        "session_instance_tune_id": row[0],
        "tune_id": row[1],
        "name": row[2],
        "order_position": row[3],
        "record_type": row[4],
    }


@api_login_required
def live_bootstrap(session_instance_id):
    """
    Bootstrap snapshot for the live screen (spec 024 §H).

    Returns the current canonical records for the instance plus the feed
    high-water mark (max event_id). The client renders this, then opens the SSE
    stream with `Last-Event-ID: <high_water>` so it receives only the delta.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if not _instance_exists(cur, session_instance_id):
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        cur.execute(
            """
            SELECT session_instance_tune_id, tune_id, name, order_position, record_type
            FROM session_instance_tune
            WHERE session_instance_id = %s
            ORDER BY order_position
            """,
            (session_instance_id,),
        )
        records = [_record_to_dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT COALESCE(MAX(event_id), 0) FROM session_event WHERE session_instance_id = %s",
            (session_instance_id,),
        )
        high_water = cur.fetchone()[0]

        return jsonify(
            {
                "success": True,
                "session_instance_id": int(session_instance_id),
                "current_person": {
                    "person_id": getattr(current_user, "person_id", None),
                    "first_name": getattr(current_user, "first_name", ""),
                    "last_name": getattr(current_user, "last_name", ""),
                },
                "records": records,
                "last_event_id": high_water,
            }
        )
    finally:
        conn.close()


@api_login_required
def add_tune_op(session_instance_id):
    """
    `add_tune` op (spec 024 §C). Append-or-insert a tune, server-authoritative.

    Request JSON:
      - op_id            client-generated UUID (idempotency key; dedup is Phase 1)
      - tune_id          matched tune id, or null for an unlinked raw name
      - name             raw tune name (used when tune_id is null)
      - after_record_id  relational anchor; insert right after this record.
                         Omit/null -> append to the end of the instance.
      - source           'human' (default) | 'audio' (audio is a later task)

    One transaction: assign order_position -> INSERT session_instance_tune ->
    INSERT session_event -> pg_notify. The committed record is returned to the
    caller AND carried in the feed payload for SSE consumers.
    """
    data = request.get_json(silent=True) or {}
    op_id = data.get("op_id")
    tune_id = data.get("tune_id")
    name = data.get("name")
    after_record_id = data.get("after_record_id")
    source = data.get("source") or "human"

    if tune_id is None and not (name and str(name).strip()):
        return jsonify({"success": False, "error": "add_tune requires tune_id or name"}), 400
    if name is not None:
        name = str(name).strip() or None

    user_id = get_current_user_id()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")

        if not _instance_exists(cur, session_instance_id):
            cur.execute("ROLLBACK")
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        # --- Compute the authoritative order_position from the relational anchor. ---
        if after_record_id is not None:
            cur.execute(
                """
                SELECT order_position FROM session_instance_tune
                WHERE session_instance_tune_id = %s AND session_instance_id = %s
                """,
                (after_record_id, session_instance_id),
            )
            anchor = cur.fetchone()
            if not anchor:
                # Anchor vanished -> fall back to append (spec 024 positioning rule:
                # never drop silently). Phase 0 keeps the fallback minimal.
                after_position = None
            else:
                after_position = anchor[0]
        else:
            after_position = None

        if after_position is None:
            cur.execute(
                "SELECT MAX(order_position) FROM session_instance_tune WHERE session_instance_id = %s",
                (session_instance_id,),
            )
            last_position = cur.fetchone()[0]
            new_position = generate_append_position(last_position)
        else:
            # Find the next record after the anchor to insert between.
            cur.execute(
                """
                SELECT MIN(order_position) FROM session_instance_tune
                WHERE session_instance_id = %s AND order_position > %s
                """,
                (session_instance_id, after_position),
            )
            next_position = cur.fetchone()[0]
            new_position = generate_position_between(after_position, next_position)

        # --- Canonical state write. ---
        cur.execute(
            """
            INSERT INTO session_instance_tune (
                session_instance_id, tune_id, name, order_position,
                record_type, inserted_timestamp, created_by_user_id, last_modified_user_id
            ) VALUES (
                %s, %s, %s, %s, 'tune', (NOW() AT TIME ZONE 'UTC'), %s, %s
            )
            RETURNING session_instance_tune_id, tune_id, name, order_position, record_type
            """,
            (session_instance_id, tune_id, name, new_position, user_id, user_id),
        )
        record_row = cur.fetchone()
        new_record_id = record_row[0]

        # Audit history for the canonical table (INSERT just created the row).
        save_to_history(cur, "session_instance_tune", "INSERT", new_record_id, user_id=user_id)

        # --- Feed write (same txn) + NOTIFY. Truth and feed cannot diverge (§B). ---
        payload = {
            "op_id": op_id,
            "source": source,
            "record": _record_to_dict(record_row),
        }
        cur.execute(
            """
            INSERT INTO session_event (session_instance_id, op_type, payload, created_by_user_id)
            VALUES (%s, 'add_tune', %s, %s)
            RETURNING event_id
            """,
            (session_instance_id, json.dumps(payload), user_id),
        )
        event_id = cur.fetchone()[0]

        # id-only NOTIFY; the streaming service re-reads the event row (§A4).
        cur.execute(
            "SELECT pg_notify(%s, %s)",
            (event_channel(session_instance_id), str(event_id)),
        )

        cur.execute("COMMIT")

        return jsonify(
            {
                "success": True,
                "event_id": event_id,
                "op_id": op_id,
                "record": _record_to_dict(record_row),
            }
        )
    except Exception as e:
        cur.execute("ROLLBACK")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()
