from flask import request, jsonify, session, send_file
from collections import Counter
import requests
import re
import os
import base64
import psycopg2
from api_auth import api_login_required, api_admin_or_self_required, public_api
from database import (
    get_db_connection,
    get_current_user_id,
    save_to_history,
    find_matching_tune,
    normalize_override_name,
    normalize_quotes,
    normalize_quotes_sql,
    check_in_person as db_check_in_person,
)
from email_utils import send_email_via_sendgrid, send_update_email
from instruments import normalize_instrument, normalize_instruments
from session_path import normalize_session_path
from timezone_utils import now_utc, format_datetime_with_timezone, utc_to_local
from flask_login import current_user
from functools import wraps
import qrcode
from io import BytesIO
from recurrence_utils import validate_recurrence_json, to_human_readable
from fractional_indexing import generate_append_position, generate_position_between
from services import person_scope
from recording import upload_chunk_to_s3, generate_presigned_url, get_recording_timeline, compute_checksum, chunk_audio_file


def can_view_session_people(cur, session_id, person_id):
    """May this person see the session's PEOPLE? (spec 034)

    `is_admin OR confirmed` — the single gate on the People tab, person detail sheets, and
    every attendance list. It replaced two contradictory predicates: auth.py granted access
    to any member, while this module required `is_regular OR is_admin`.

    Note what it is NOT: membership. Anyone with an account can self-join any session, so if
    membership granted roster access, joining would hand a stranger every member's name.
    People-visibility is granted BY the session (an admin confirms you), never claimed by
    joining it. `confirmed` is orthogonal to member/visitor — a confirmed visitor (a known
    friend of the session who lives elsewhere) can see people; an unconfirmed member cannot.

    System admins bypass this, as everywhere.
    """
    from flask import session as flask_session

    if flask_session.get("is_system_admin", False):
        return True
    if not person_id:
        return False
    cur.execute(
        """
        SELECT 1 FROM session_person
        WHERE session_id = %s AND person_id = %s
          AND (confirmed = TRUE OR is_admin = TRUE)
        """,
        (session_id, person_id),
    )
    return cur.fetchone() is not None


def is_session_admin_for(cur, session_id, person_id):
    """Session admin (or system admin) — the gate on confirming, archiving, and managing
    other people's relationship to the session."""
    from flask import session as flask_session

    if flask_session.get("is_system_admin", False):
        return True
    if not person_id:
        return False
    cur.execute(
        "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s AND is_admin = TRUE",
        (session_id, person_id),
    )
    return cur.fetchone() is not None


def is_session_member_for(cur, session_id, person_id):
    """Any row in session_person (or a system admin) — the weaker grant the tune
    drawer's Session tab needs (spec 037). A member may say what was played on a
    night they were in the room; only an admin may say what the session plays in
    general."""
    from flask import session as flask_session

    if flask_session.get("is_system_admin", False):
        return True
    if not person_id:
        return False
    cur.execute(
        "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
        (session_id, person_id),
    )
    return cur.fetchone() is not None


def instance_logging_locked(cur, session_instance_id):
    """True if the live editor owns this instance (logging_mode='live'); the classic
    editor's tune-mutation endpoints must refuse so they can't clobber live-editor data."""
    cur.execute(
        "SELECT logging_mode FROM session_instance WHERE session_instance_id = %s",
        (session_instance_id,),
    )
    row = cur.fetchone()
    return bool(row) and row[0] == "live"


def follow_tune_redirect(cur, tune_id):
    """Resolve a possibly-merged tune_id to its canonical id (spec 030).

    Read endpoints serve the merged-into tune's data instead of 404ing on a stale
    permalink; write endpoints proceed against the canonical id ("remap") because a
    post-merge write with the old id has exactly one sensible meaning. Returns
    (effective_tune_id, redirected_from) where redirected_from is None if the id
    was already canonical (or unknown). Chains can't exist (DB trigger), so one
    hop is authoritative.
    """
    cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
    row = cur.fetchone()
    if row and row[0] is not None:
        return row[0], tune_id
    return tune_id, None


@public_api  # THE tune-detail drawer feed, offered to logged-out users too; everything
# here is public catalog data — the viewer/person_tune_status blocks are
# is_authenticated-guarded personalization.
def get_tune_detail_global(tune_id):
    """The tune-detail drawer payload (see serializers.build_tune_detail_payload).

    GET /api/tunes/<tune_id>/detail
        ?session=<path>       — merge in that session's session_tune scope block
        &instance=<date|id>   — plus that instance's overrides

    The drawer derives its mode (my-tunes variant / session / instance / admin /
    read-only) from viewer + person_tune_status + session_scope, so this one
    endpoint replaces the per-context feeds the drawer used to pick between."""
    from serializers import build_tune_detail_payload, SessionNotFound, SessionInstanceNotFound

    session_path = request.args.get("session") or None
    date_or_id = request.args.get("instance") or None
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        tune_id, redirected_from = follow_tune_redirect(cur, tune_id)
        person_id = current_user.person_id if current_user.is_authenticated else None
        try:
            payload = build_tune_detail_payload(
                conn,
                tune_id,
                person_id=person_id,
                logged_in=current_user.is_authenticated,
                is_admin=bool(current_user.is_authenticated and current_user.is_system_admin),
                session_path=session_path,
                date_or_id=date_or_id,
                redirected_from=redirected_from,
            )
        except SessionNotFound:
            return jsonify({"success": False, "message": "Session not found"}), 404
        except SessionInstanceNotFound:
            return jsonify({"success": False, "message": "Session instance not found"}), 404
        if payload is None:
            return jsonify({"success": False, "message": "Tune not found"}), 404
        return jsonify(payload)
    finally:
        conn.close()


@public_api  # backs the tune-detail modal's History tab (tunesheet bundle, loaded app-wide via base.html incl. logged-out session pages); the ?scope= variants have an inline 401 below
def get_tune_history(tune_id):
    """Play history for the tune-detail modal's History tab, fetched lazily on first
    view (the set/position windowing below is too expensive to run on every modal open).

    GET /api/tunes/<tune_id>/history
        ?session_path=<path>  — only plays at that session
        ?scope=member         — only plays at the viewer's sessions (spec 033 R3:
                                session_person.relationship='member')
        ?scope=attended       — only plays at instances the viewer attended (R4:
                                session_instance_person.attendance='yes')
        ?person=me            — deprecated alias of scope=member (its old
                                bare-attendance meaning was the spec 033 bug)

    Positions are humane 'Set N, Tune M' coordinates: rows are ordered by the
    fractional order_position, break records split the sets (spec 023) and are
    excluded from the tune numbering.
    """
    session_path = request.args.get("session_path") or None
    scope = request.args.get("scope") or None
    # "While I was there" is a FILTER, not a scope (spec 037). It ANDs on top of whatever
    # else is selected, so "nights at Mueller I was actually there for" is expressible —
    # it wasn't when attended was one of a set of mutually-exclusive scopes.
    # ?scope=attended is still accepted, and means the same as ?attended=1 with no other
    # person filter.
    attended_only = request.args.get("attended") in ("1", "true", "yes")
    if scope == "attended":
        scope, attended_only = None, True
    if scope is None and request.args.get("person") == "me":
        scope = "member"
    if scope is not None and scope not in ("member",):
        return jsonify({"success": False, "error": f"Invalid scope: {scope}"}), 400
    needs_person = bool(scope) or attended_only
    if needs_person and not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Login required"}), 401

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        tune_id, redirected_from = follow_tune_redirect(cur, tune_id)

        person_id = None
        if current_user.is_authenticated:
            cur.execute(
                "SELECT person_id FROM user_account WHERE user_id = %s",
                (current_user.user_id,),
            )
            pr = cur.fetchone()
            if not pr and needs_person:
                return jsonify({"success": False, "error": "No person record"}), 403
            person_id = pr[0] if pr else None

        attended_pred = person_scope.attended_instance_predicate("si.session_instance_id")
        preds = []
        member_pred = person_scope.scope_instance_predicate(scope, "si.session_instance_id")
        if member_pred:
            preds.append(member_pred)
        if attended_only:
            preds.append(attended_pred)
        scope_filter = "".join(f"AND ({p}) " for p in preds)
        # The same predicate, selected rather than filtered, so the list can MARK the
        # nights you were there instead of only hiding the ones you weren't.
        attended_select = f"({attended_pred})" if person_id else "FALSE"

        instance_limit = 100
        cur.execute(
            f"""
            WITH target_instances AS (
                SELECT si.session_instance_id, si.date, s.name AS session_name, s.path AS session_path,
                       {attended_select} AS attended
                FROM session_instance si
                JOIN session s ON si.session_id = s.session_id
                WHERE EXISTS (
                          SELECT 1 FROM session_instance_tune x
                          WHERE x.session_instance_id = si.session_instance_id
                            AND x.tune_id = %(tune_id)s AND x.deleted = FALSE
                      )
                  AND (%(session_path)s::text IS NULL OR s.path = %(session_path)s)
                  {scope_filter}
                ORDER BY si.date DESC, si.session_instance_id DESC
                LIMIT %(instance_limit)s
            ),
            instance_rows AS (
                SELECT sit.session_instance_tune_id, sit.session_instance_id, sit.tune_id,
                       sit.name, sit.key_override, sit.setting_override,
                       sit.record_type, sit.order_position,
                       SUM(CASE WHEN sit.record_type = 'break' THEN 1 ELSE 0 END)
                           OVER (PARTITION BY sit.session_instance_id
                                 ORDER BY sit.order_position, sit.session_instance_tune_id) AS set_idx
                FROM session_instance_tune sit
                JOIN target_instances ti ON sit.session_instance_id = ti.session_instance_id
                WHERE sit.deleted = FALSE
            ),
            positioned AS (
                SELECT *,
                       set_idx + 1 AS set_number,
                       ROW_NUMBER() OVER (PARTITION BY session_instance_id, set_idx
                                          ORDER BY order_position, session_instance_tune_id) AS position_in_set
                FROM instance_rows
                WHERE record_type <> 'break'
            )
            SELECT ti.session_name, ti.session_path, ti.date, ti.attended,
                   p.name, p.key_override, p.setting_override,
                   p.session_instance_id, p.session_instance_tune_id,
                   p.set_number, p.position_in_set
            FROM positioned p
            JOIN target_instances ti ON p.session_instance_id = ti.session_instance_id
            WHERE p.tune_id = %(tune_id)s
            ORDER BY ti.date DESC, p.session_instance_id DESC, p.set_number, p.position_in_set
            """,
            {
                "tune_id": tune_id,
                "session_path": session_path,
                "person_id": person_id,
                "instance_limit": instance_limit,
            },
        )
        rows = cur.fetchall()

        play_instances = []
        instance_ids = set()
        for (session_name, s_path, date, attended, name_override, key_override, setting_override,
             session_instance_id, session_instance_tune_id, set_number, position_in_set) in rows:
            instance_ids.add(session_instance_id)
            date_str = date.strftime("%Y-%m-%d") if date else None
            play_instances.append({
                "full_name": f"{session_name} - {date_str}" if date_str else session_name,
                "session_name": session_name,
                "session_path": s_path,
                "date": date.isoformat() if date else None,
                "set_number": set_number,
                "position_in_set": position_in_set,
                "name_override": name_override,
                "key_override": key_override,
                "setting_id_override": setting_override,
                "session_instance_id": session_instance_id,
                "session_instance_tune_id": session_instance_tune_id,
                # Was I there? Marks the night in the list, rather than only being able to
                # hide the ones I wasn't at.
                "attended": bool(attended),
                # highlight= scrolls to the exact record; tune= lets the legacy
                # page (no per-record ids client-side) highlight by tune instead.
                "link": f"/sessions/{s_path}/{session_instance_id}"
                        f"?highlight={session_instance_tune_id}&tune={tune_id}",
            })

        return jsonify({
            "success": True,
            "redirected_from": redirected_from,
            "play_instances": play_instances,
            # limit is per-instance; flag truncation so the UI can say so
            "truncated": len(instance_ids) >= instance_limit,
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Error retrieving history: {str(e)}"}), 500
    finally:
        conn.close()


@public_api  # backs the tune-detail modal's Played With tab (tunesheet bundle on logged-out session pages)
def get_tune_played_with(tune_id):
    """Companion tunes for the tune-detail modal's Played With tab, fetched lazily on
    first view.

    GET /api/tunes/<tune_id>/played-with
        ?session_path=<path>  — only count sets played at that session
        ?scope=member         — only sets at the viewer's sessions (spec 033 R3)
        ?scope=attended       — only sets at instances the viewer attended (R4)

    Counts how often each other tune appeared in the same set as this one (sets are
    delimited by break records within an instance, spec 023).
    Unlinked log rows (tune_id NULL) are skipped — the tab's rows open the companion
    tune's detail modal, which needs a canonical tune.
    """
    session_path = request.args.get("session_path") or None
    scope = request.args.get("scope") or None
    if scope is not None and scope not in ("member", "attended"):
        return jsonify({"success": False, "error": f"Invalid scope: {scope}"}), 400
    if scope and not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Login required"}), 401

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        tune_id, redirected_from = follow_tune_redirect(cur, tune_id)

        person_id = None
        if scope:
            cur.execute(
                "SELECT person_id FROM user_account WHERE user_id = %s",
                (current_user.user_id,),
            )
            pr = cur.fetchone()
            if not pr:
                return jsonify({"success": False, "error": "No person record"}), 403
            person_id = pr[0]

        scope_pred = person_scope.scope_instance_predicate(scope, "si.session_instance_id")
        scope_filter = f"AND ({scope_pred})" if scope_pred else ""

        cur.execute(
            f"""
            WITH target_instances AS (
                SELECT DISTINCT sit.session_instance_id
                FROM session_instance_tune sit
                JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
                JOIN session s ON s.session_id = si.session_id
                WHERE sit.tune_id = %(tune_id)s AND sit.deleted = FALSE
                  AND (%(session_path)s::text IS NULL OR s.path = %(session_path)s)
                  {scope_filter}
            ),
            instance_rows AS (
                SELECT sit.session_instance_id, sit.tune_id, sit.record_type,
                       SUM(CASE WHEN sit.record_type = 'break' THEN 1 ELSE 0 END)
                           OVER (PARTITION BY sit.session_instance_id
                                 ORDER BY sit.order_position, sit.session_instance_tune_id) AS set_idx
                FROM session_instance_tune sit
                JOIN target_instances ti ON sit.session_instance_id = ti.session_instance_id
                WHERE sit.deleted = FALSE
            ),
            target_sets AS (
                SELECT DISTINCT session_instance_id, set_idx
                FROM instance_rows
                WHERE tune_id = %(tune_id)s
            )
            SELECT r.tune_id, t.name, t.tune_type, COUNT(*) AS times_together
            FROM instance_rows r
            JOIN target_sets ts ON r.session_instance_id = ts.session_instance_id
                               AND r.set_idx = ts.set_idx
            JOIN tune t ON t.tune_id = r.tune_id
            WHERE r.record_type <> 'break'
              AND r.tune_id IS NOT NULL
              AND r.tune_id <> %(tune_id)s
            GROUP BY r.tune_id, t.name, t.tune_type
            ORDER BY times_together DESC, t.name
            """,
            {"tune_id": tune_id, "session_path": session_path, "person_id": person_id},
        )
        tunes = [
            {"tune_id": row[0], "name": row[1], "tune_type": row[2], "count": row[3]}
            for row in cur.fetchall()
        ]

        return jsonify({
            "success": True,
            "redirected_from": redirected_from,
            "tunes": tunes,
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Error retrieving played-with tunes: {str(e)}"}), 500
    finally:
        conn.close()


@api_login_required
def set_beta_logging(user_id):
    """Set a user's tune-logger preference. enabled=True (the default for every
    account) means the live logger; False drops them back to the legacy pill editor,
    which is otherwise unreachable. System admins can set it for anyone; users can set
    their own. Endpoint/flag names date from the spec 024 beta rollout.
    POST /api/users/<user_id>/beta-logging  body {enabled: bool}"""
    is_self = getattr(current_user, "user_id", None) == user_id
    if not (current_user.is_system_admin or is_self):
        return jsonify({"success": False, "error": "Not authorized"}), 403
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_account SET beta_live_logging = %s WHERE user_id = %s",
            (enabled, user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "User not found"}), 404
        conn.commit()
        return jsonify({"success": True, "user_id": user_id, "beta_live_logging": enabled})
    finally:
        conn.close()


@api_login_required
def admin_reset_logging_mode(session_instance_id):
    """System-admin only: reset an instance to the classic editor (undo the one-way lock).
    POST /api/admin/instances/<id>/logging-mode  body {mode: 'legacy'|'live'}"""
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Not authorized"}), 403
    mode = (request.get_json(silent=True) or {}).get("mode", "legacy")
    if mode not in ("legacy", "live"):
        return jsonify({"success": False, "error": "mode must be 'legacy' or 'live'"}), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE session_instance SET logging_mode = %s WHERE session_instance_id = %s",
            (mode, session_instance_id),
        )
        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Session instance not found"}), 404
        conn.commit()
        return jsonify({"success": True, "session_instance_id": session_instance_id, "logging_mode": mode})
    finally:
        conn.close()


def _get_update_email_payload():
    """Validated {subject, body_markdown} from the request, or (None, None)."""
    data = request.get_json(silent=True) or {}
    subject = (data.get("subject") or "").strip()
    body_markdown = (data.get("body_markdown") or "").strip()
    return subject, body_markdown


@api_login_required
def admin_email_updates_test():
    """System-admin only: send the composed update email to yourself (spec 027).
    POST /api/admin/email-updates/test  body {subject, body_markdown}.
    Test sends are not recorded in email_message."""
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Not authorized"}), 403
    subject, body_markdown = _get_update_email_payload()
    if not subject or not body_markdown:
        return jsonify({"success": False, "error": "Subject and body are required"}), 400

    # Send to the account's user_email — the same address a real send would use.
    # (current_user.email is person.email, which can differ.)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_email FROM user_account WHERE user_id = %s",
            (current_user.user_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    to_email = row[0] if row else None
    if not to_email:
        return jsonify({"success": False, "error": "Your account has no email address"}), 400

    if send_update_email(current_user.user_id, to_email, subject, body_markdown):
        return jsonify({"success": True, "message": f"Test sent to {to_email}"})
    return jsonify({"success": False, "error": "Send failed — check server logs"}), 502


@api_login_required
def admin_email_updates_send():
    """System-admin only: send the update email to every opted-in user (spec 027).
    POST /api/admin/email-updates/send  body {subject, body_markdown}.
    Records an email_message row plus one email_message_recipient row per user;
    an individual failure is recorded and skipped, never aborts the send."""
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Not authorized"}), 403
    subject, body_markdown = _get_update_email_payload()
    if not subject or not body_markdown:
        return jsonify({"success": False, "error": "Subject and body are required"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, user_email FROM user_account
            WHERE receive_update_emails = TRUE AND is_active = TRUE AND user_email IS NOT NULL
            ORDER BY user_id
            """
        )
        recipients = cur.fetchall()

        cur.execute(
            """
            INSERT INTO email_message (subject, body_markdown, sent_by_user_id, recipient_count)
            VALUES (%s, %s, %s, %s)
            RETURNING email_message_id
            """,
            (subject, body_markdown, current_user.user_id, len(recipients)),
        )
        email_message_id = cur.fetchone()[0]

        success_count = 0
        failure_count = 0
        for recipient_user_id, recipient_email in recipients:
            try:
                sent = send_update_email(recipient_user_id, recipient_email, subject, body_markdown)
                error_message = None if sent else "SendGrid send failed"
            except Exception as e:
                sent = False
                error_message = str(e)
            if sent:
                success_count += 1
            else:
                failure_count += 1
            cur.execute(
                """
                INSERT INTO email_message_recipient (email_message_id, user_id, email, status, error_message)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (email_message_id, recipient_user_id, recipient_email,
                 "sent" if sent else "failed", error_message),
            )

        cur.execute(
            "UPDATE email_message SET success_count = %s, failure_count = %s WHERE email_message_id = %s",
            (success_count, failure_count, email_message_id),
        )
        conn.commit()
        return jsonify({
            "success": True,
            "recipient_count": len(recipients),
            "success_count": success_count,
            "failure_count": failure_count,
        })
    finally:
        conn.close()


def segment_records_into_sets(rows, type_index=None):
    """Group ordered session_instance_tune rows into sets (spec 023).

    `rows` must already be ordered by order_position. Each row is a tuple/list whose
    element at `type_index` is the record_type ('tune' | 'break'). A 'break' row closes
    the current set and is dropped from the output; 'tune' rows accumulate into the
    current set. A trailing break leaves no empty set behind, and leading/consecutive
    breaks are no-ops.

    If `type_index` is None, every row is treated as a tune (no breaks present) -- this
    lets callers reuse the function on legacy row shapes.

    Returns a list of sets, where each set is a list of the original tune rows.
    """
    sets = []
    current = []
    for row in rows:
        if type_index is not None and row[type_index] == "break":
            if current:
                sets.append(current)
                current = []
        else:
            current.append(row)
    if current:
        sets.append(current)
    return sets


def reconcile_break_records(cur, session_instance_id, set_position_lists, audit_user_id=None):
    """Delete all break rows for an instance and reinsert exactly one break per set (spec 023).

    `set_position_lists` is the ordered list of sets, each given as the ordered list of its
    tune order_position strings (their final positions). One break is placed in the gap
    after each set -- between a set's last tune and the next set's first tune -- including a
    trailing break after the final set. Net effect: one break per set.

    Breaks have no stable client identity, so reconciling them by delete-and-reinsert is
    simpler than diffing. When `audit_user_id` is supplied, each delete/insert is audited.
    Returns the number of break rows inserted.
    """
    cur.execute(
        """
        SELECT session_instance_tune_id FROM session_instance_tune
        WHERE session_instance_id = %s AND record_type = 'break'
        """,
        (session_instance_id,),
    )
    for (break_id,) in cur.fetchall():
        if audit_user_id is not None:
            save_to_history(cur, "session_instance_tune", "DELETE", break_id, user_id=audit_user_id)
        cur.execute(
            "DELETE FROM session_instance_tune WHERE session_instance_tune_id = %s",
            (break_id,),
        )

    sets = [positions for positions in set_position_lists if positions]
    for i, positions in enumerate(sets):
        last_pos = positions[-1]
        next_first = sets[i + 1][0] if i + 1 < len(sets) else None
        if next_first is not None:
            break_pos = generate_position_between(last_pos, next_first)
        else:
            break_pos = generate_append_position(last_pos)
        cur.execute(
            """
            INSERT INTO session_instance_tune
                (session_instance_id, order_position, record_type, created_date, last_modified_date, created_by_user_id)
            VALUES (%s, %s, 'break', NOW(), NOW(), %s)
            RETURNING session_instance_tune_id
            """,
            (session_instance_id, break_pos, audit_user_id),
        )
        new_id = cur.fetchone()[0]
        if audit_user_id is not None:
            save_to_history(cur, "session_instance_tune", "INSERT", new_id, user_id=audit_user_id)
    return len(sets)


def default_setting_id(cur, tune_id):
    """The tune's default setting (lowest setting_id), or None if it has none.

    session_tune.setting_id is always populated with this on enrollment (spec 032:
    "there is always a setting id, even if it's just the default") so the setting in
    use is visible/linkable everywhere. A session-level setting equal to the default
    is treated as replaceable by an explicitly chosen one (see _apply_chosen_setting)."""
    if not tune_id:
        return None
    cur.execute("SELECT setting_id FROM tune_setting WHERE tune_id = %s ORDER BY setting_id LIMIT 1", (tune_id,))
    row = cur.fetchone()
    return row[0] if row else None


def bytea_to_base64(data):
    """
    Convert PostgreSQL bytea data to base64 string.
    Handles different return formats: bytes, memoryview, hex string.
    """
    if not data:
        return None

    if isinstance(data, memoryview):
        data = data.tobytes()
    elif isinstance(data, str):
        # PostgreSQL returns bytea as hex string starting with \x
        if data.startswith('\\x'):
            data = bytes.fromhex(data[2:])
        else:
            data = data.encode('latin1')
    elif not isinstance(data, bytes):
        data = bytes(data)

    return base64.b64encode(data).decode('utf-8')


def insert_session_instance_tune(cur, session_id, date, tune_id, setting_id, name, starts_set):
    """
    Insert a tune into session_instance_tune with fractional indexing.

    This replaces the SQL stored procedure to use Python-based fractional
    position generation for CRDT compatibility.

    Args:
        cur: Database cursor
        session_id: Session ID
        date: Date of the session instance
        tune_id: Tune ID (can be None for unlinked tunes)
        setting_id: Setting ID override (can be None)
        name: Tune name (used when tune_id is None)
        starts_set: True if this tune starts a new set

    Returns:
        The new session_instance_tune_id
    """
    # Look up the session_instance_id
    cur.execute(
        """
        SELECT session_instance_id
        FROM session_instance
        WHERE session_id = %s AND date = %s
        ORDER BY session_instance_id DESC
        LIMIT 1
        """,
        (session_id, date),
    )
    result = cur.fetchone()
    if not result:
        raise ValueError(f"No session instance found for session_id {session_id} on date {date}")
    session_instance_id = result[0]

    # If tune_id is provided, remap merged ids and ensure it exists in session_tune.
    # A write with a merged-away id is a stale client (spec 030): proceed against the
    # canonical tune rather than rejecting.
    if tune_id is not None:
        tune_id, _ = follow_tune_redirect(cur, tune_id)

        cur.execute(
            """
            INSERT INTO session_tune (session_id, tune_id, setting_id, key, alias)
            VALUES (%s, %s, %s, NULL, NULL)
            ON CONFLICT (session_id, tune_id) DO NOTHING
            """,
            (session_id, tune_id, setting_id if setting_id is not None else default_setting_id(cur, tune_id)),
        )

    # Find the current last record in this instance (could be a tune or a break).
    cur.execute(
        """
        SELECT session_instance_tune_id, order_position, record_type
        FROM session_instance_tune
        WHERE session_instance_id = %s
        ORDER BY order_position DESC
        LIMIT 1
        """,
        (session_instance_id,),
    )
    last_row = cur.fetchone()
    last_order_position = last_row[1] if last_row else None
    last_is_break = last_row is not None and last_row[2] == "break"

    # Maintain set boundaries with explicit break records (spec 023).
    if starts_set and last_row is not None and not last_is_break:
        # Close the previous (open) set with a break before this new set's first tune.
        break_position = generate_append_position(last_order_position)
        cur.execute(
            """
            INSERT INTO session_instance_tune (
                session_instance_id, order_position, record_type, inserted_timestamp
            ) VALUES (%s, %s, 'break', CURRENT_TIMESTAMP)
            """,
            (session_instance_id, break_position),
        )
        last_order_position = break_position
    elif not starts_set and last_is_break:
        # Continuing the current set, but it was closed by a trailing break -- reopen it
        # by removing that break so the new tune joins the last set.
        cur.execute(
            "DELETE FROM session_instance_tune WHERE session_instance_tune_id = %s",
            (last_row[0],),
        )
        # Recompute the trailing position now that the break is gone.
        cur.execute(
            "SELECT MAX(order_position) FROM session_instance_tune WHERE session_instance_id = %s",
            (session_instance_id,),
        )
        last_order_position = cur.fetchone()[0]
    # (starts_set with an existing trailing break reuses that break as the boundary.)

    # Generate new fractional position
    new_order_position = generate_append_position(last_order_position)

    # Insert the new record
    cur.execute(
        """
        INSERT INTO session_instance_tune (
            session_instance_id, tune_id, name, order_position,
            record_type, inserted_timestamp, setting_override
        ) VALUES (
            %s, %s, %s, %s, 'tune', CURRENT_TIMESTAMP, %s
        )
        RETURNING session_instance_tune_id
        """,
        (
            session_instance_id,
            tune_id,
            name,
            new_order_position,
            setting_id,
        ),
    )
    new_id = cur.fetchone()[0]
    return new_id


def render_abc_to_png(abc_notation, is_incipit=False):
    """
    Call the ABC renderer microservice to convert ABC notation to PNG image.
    Returns the PNG image as bytes, or None if rendering fails.

    Args:
        abc_notation: ABC notation string to render
        is_incipit: If True, uses minimal padding for compact rendering (default: False)
    """
    try:
        abc_renderer_url = os.getenv('ABC_RENDERER_URL')
        if not abc_renderer_url:
            print("Warning: ABC_RENDERER_URL not configured")
            return None

        print(f"Calling ABC renderer with {len(abc_notation)} chars of ABC notation (isIncipit={is_incipit})")
        response = requests.post(
            f'{abc_renderer_url}/api/render',
            json={'abc': abc_notation, 'isIncipit': is_incipit},
            timeout=15
        )

        print(f"ABC renderer response: status={response.status_code}, content-type={response.headers.get('content-type')}")

        if response.status_code == 200:
            if response.headers.get('content-type') == 'image/png':
                print(f"Successfully got PNG image ({len(response.content)} bytes)")
                return response.content
            else:
                print(f"Unexpected content type: {response.headers.get('content-type')}")
                print(f"Response body: {response.text[:200]}")
                return None
        else:
            print(f"ABC renderer returned status {response.status_code}: {response.text[:200]}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error calling ABC renderer: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in render_abc_to_png: {e}")
        import traceback
        traceback.print_exc()
        return None


def cache_default_tune_setting(tune_id, tune_data, user_id, sync=True, target_setting_id=None):
    """
    Fetch and cache a setting for a tune from thesession.org.
    Creates the tune_setting record and generates PNG images for both full ABC and incipit.

    This function should be called whenever a new tune is added to the tune table
    from thesession.org, to ensure the default setting and images are immediately available.

    Args:
        tune_id: The tune ID (thesession.org tune ID)
        tune_data: Dict containing tune data from thesession.org API response.
                   Must include 'settings' array and 'type' field.
                   If None, will fetch from thesession.org API.
        user_id: ID of user who triggered the operation (for audit trail)
        sync: If True, process synchronously. If False, skip processing (placeholder for future async).
        target_setting_id: If provided, cache this specific setting instead of the default (first) one.

    Returns:
        Tuple of (success: bool, message: str, setting_id: int or None)
    """
    # ============================================================================
    # ASYNC PROCESSING PLACEHOLDER
    # When sync=False, this is where we would enqueue the setting cache job
    # for background/async processing. For now, we just skip and return.
    # Future implementation: Add to a job queue (e.g., Celery, RQ, or custom)
    # that processes tune settings in the background.
    # ============================================================================
    if not sync:
        print(f"[cache_default_tune_setting] Skipping tune {tune_id} - async processing not yet implemented")
        return True, "Skipped (async not implemented)", None

    try:
        from database import extract_abc_incipit

        # If tune_data not provided, fetch from API
        if tune_data is None:
            api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
            response = requests.get(api_url, timeout=10)
            if response.status_code != 200:
                return False, f"Failed to fetch tune data (status: {response.status_code})", None
            tune_data = response.json()

        # Check if settings exist in the response
        if "settings" not in tune_data or not tune_data["settings"]:
            return False, "No settings found for this tune", None

        # Use the targeted setting if specified, otherwise the first (default)
        setting = None
        if target_setting_id:
            setting = next((s for s in tune_data["settings"] if s["id"] == target_setting_id), None)
        if not setting:
            setting = tune_data["settings"][0]
        setting_id = setting["id"]
        key = setting.get("key", "")
        abc = setting.get("abc", "")
        tune_type = tune_data.get("type", "").title()

        # Replace "!" with newline for proper staff line breaks
        # thesession.org uses "!" as a line break marker
        abc = abc.replace("!", "\n")

        # Extract incipit from ABC notation
        incipit_abc = extract_abc_incipit(abc, tune_type)

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # Check if this setting already exists
            cur.execute(
                "SELECT setting_id FROM tune_setting WHERE setting_id = %s",
                (setting_id,)
            )
            existing_setting = cur.fetchone()

            if existing_setting:
                # Setting already cached, nothing to do
                cur.close()
                conn.close()
                return True, f"Setting {setting_id} already cached", setting_id

            # Insert new setting
            cur.execute("""
                INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc, cache_updated_date,
                                          created_by_user_id, last_modified_user_id)
                VALUES (%s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), %s, %s)
            """, (setting_id, tune_id, key, abc, incipit_abc, user_id, user_id))

            # Log INSERT to history
            cur.execute("""
                INSERT INTO tune_setting_history
                (setting_id, operation, changed_by_user_id, tune_id, key, abc, image, incipit_abc,
                 incipit_image, cache_updated_date, created_date, last_modified_date,
                 created_by_user_id, last_modified_user_id)
                SELECT setting_id, %s, %s, tune_id, key, abc, image, incipit_abc,
                       incipit_image, cache_updated_date, created_date, last_modified_date,
                       created_by_user_id, last_modified_user_id
                FROM tune_setting WHERE setting_id = %s
            """, ('INSERT', user_id, setting_id))

            conn.commit()

            # Generate PNG images for both full ABC and incipit
            full_image = None
            incipit_image = None

            # Construct full ABC notation with headers for rendering
            abc_with_headers = abc
            if not abc.startswith('X:'):
                abc_with_headers = f"X:1\nM:4/4\nL:1/8\nK:{key if key else 'D'}\n{abc}"

            # Render full ABC image
            full_image = render_abc_to_png(abc_with_headers)

            # Render incipit image
            if incipit_abc:
                incipit_with_headers = incipit_abc
                if not incipit_abc.startswith('X:'):
                    incipit_with_headers = f"X:1\nM:4/4\nL:1/8\nK:{key if key else 'D'}\n{incipit_abc}"
                incipit_image = render_abc_to_png(incipit_with_headers, is_incipit=True)

            # Update database with images if they were generated
            if full_image or incipit_image:
                cur.execute("""
                    UPDATE tune_setting
                    SET image = %s, incipit_image = %s, last_modified_date = (NOW() AT TIME ZONE 'UTC')
                    WHERE setting_id = %s
                """, (
                    psycopg2.Binary(full_image) if full_image else None,
                    psycopg2.Binary(incipit_image) if incipit_image else None,
                    setting_id
                ))
                conn.commit()

            cur.close()
            conn.close()

            return True, f"Cached setting {setting_id} with images", setting_id

        except Exception as db_error:
            conn.rollback()
            cur.close()
            conn.close()
            return False, f"Database error: {str(db_error)}", None

    except requests.exceptions.RequestException as e:
        return False, f"Error connecting to thesession.org: {str(e)}", None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error caching tune setting: {str(e)}", None


def get_session_instance_id(cur, session_id, date_or_id):
    """
    Helper function to get session_instance_id from either date or ID.
    CRITICAL: Always use this for API endpoints that accept date_or_id parameter.

    Args:
        cur: Database cursor
        session_id: The session ID
        date_or_id: Either a date string (YYYY-MM-DD) or numeric ID

    Returns:
        session_instance_id (int) or None if not found
    """
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    id_pattern = r"^\d+$"

    if re.match(id_pattern, date_or_id) and not re.match(date_pattern, date_or_id):
        # It's an ID - verify it belongs to this session
        session_instance_id = int(date_or_id)
        cur.execute(
            "SELECT session_instance_id FROM session_instance WHERE session_instance_id = %s AND session_id = %s",
            (session_instance_id, session_id),
        )
        result = cur.fetchone()
        return result[0] if result else None
    else:
        # It's a date - get the first instance on that date
        cur.execute(
            """
            SELECT session_instance_id FROM session_instance
            WHERE session_id = %s AND date = %s
            ORDER BY session_instance_id ASC
            LIMIT 1
        """,
            (session_id, date_or_id),
        )
        result = cur.fetchone()
        return result[0] if result else None


def get_timezone_for_display(session_path=None, user_timezone=None):
    """
    Get appropriate timezone for display based on context:
    - If user is logged in, use user's timezone
    - If session_path provided and no user, use session's timezone
    - Otherwise use UTC
    """
    if user_timezone:
        return user_timezone

    # If user is logged in, use their timezone
    try:
        if hasattr(current_user, "timezone") and current_user.timezone:
            return current_user.timezone
    except Exception:
        pass

    # If session_path provided, get session timezone
    if session_path:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT timezone FROM session WHERE path = %s", (session_path,))
            result = cur.fetchone()
            conn.close()
            if result and result[0]:
                return result[0]
        except Exception:
            pass

    return "UTC"


def format_datetime_for_api(dt, timezone_name, include_timezone=True):
    """Format datetime for API response with timezone conversion"""
    if not dt:
        return None

    if include_timezone:
        return format_datetime_with_timezone(dt, timezone_name)
    else:
        # Just convert to local timezone without showing timezone abbreviation
        local_dt = utc_to_local(dt, timezone_name)
        return local_dt.strftime("%Y-%m-%d %H:%M")


@api_login_required
def update_session_ajax(session_path):
    """Update session details from admin page"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Validate recurrence if provided
        if "recurrence" in data and data["recurrence"]:
            is_valid, error_msg = validate_recurrence_json(data["recurrence"])
            if not is_valid:
                return jsonify({
                    "success": False,
                    "error": f"Invalid recurrence pattern: {error_msg}"
                }), 400

        # Only some callers send a path at all (the cache and recurrence saves send
        # a partial payload) — but one that does must send a usable one. Writing a
        # blank or unresolvable path here locks the session out of its own admin
        # screen, and this endpoint is the only way back.
        new_path = None
        if "path" in data:
            new_path, path_error = normalize_session_path(data["path"])
            if path_error:
                return jsonify({"success": False, "error": path_error}), 400
            data = {**data, "path": new_path}

        # The four fields that had no editor before: thesession_id, session_type and the
        # two active-window buffers. Coerced up front (shared with POST /api/add-session)
        # so a bad value is a 400 with a sentence, not a psycopg error or a silently
        # stored string. Absent keys are left absent — every caller here sends partials.
        from session_fields import (
            normalize_active_buffer,
            normalize_session_type,
            parse_thesession_session_id,
        )

        new_thesession_id = None
        if "thesession_id" in data:
            new_thesession_id, ts_error = parse_thesession_session_id(data["thesession_id"])
            if ts_error:
                return jsonify({"success": False, "error": ts_error}), 400
            data = {**data, "thesession_id": new_thesession_id}
        if "session_type" in data:
            session_type, type_error = normalize_session_type(data["session_type"])
            if type_error:
                return jsonify({"success": False, "error": type_error}), 400
            data = {**data, "session_type": session_type}
        for buffer_field, label in (
            ("active_buffer_minutes_before", "Minutes before"),
            ("active_buffer_minutes_after", "Minutes after"),
        ):
            if buffer_field in data:
                minutes, buffer_error = normalize_active_buffer(data[buffer_field], label)
                if buffer_error:
                    return jsonify({"success": False, "error": buffer_error}), 400
                data = {**data, buffer_field: minutes}

        conn = get_db_connection()
        cur = conn.cursor()

        # Get current session details for history tracking
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Session not found"}), 404

        session_id = session_result[0]

        # Paths are unique; without this the UNIQUE index raises and the caller
        # gets a raw "duplicate key" string instead of something actionable.
        if new_path is not None:
            cur.execute(
                "SELECT name FROM session WHERE path = %s AND session_id != %s",
                (new_path, session_id),
            )
            collision = cur.fetchone()
            if collision:
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "error": f'Path "{new_path}" is already used by "{collision[0]}"',
                    }
                ), 400

        # One thesession.org session maps to one of ours (the create path checks the
        # same thing). Without this the admin form would happily point two sessions at
        # the same upstream id, which the import/lookup path resolves by picking one.
        if new_thesession_id is not None:
            cur.execute(
                "SELECT name FROM session WHERE thesession_id = %s AND session_id != %s",
                (new_thesession_id, session_id),
            )
            ts_collision = cur.fetchone()
            if ts_collision:
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "error": f'TheSession.org session {new_thesession_id} is already linked to "{ts_collision[0]}"',
                    }
                ), 400

        # Save to history before making changes
        save_to_history(
            cur, "session", "UPDATE", session_id, user_id=get_current_user_id()
        )

        # Prepare the update query
        update_fields = []
        update_values = []

        # Map form fields to database columns
        field_mapping = {
            "name": "name",
            "path": "path",
            # Coerced above; NULLable on purpose — clearing the link is a real edit.
            "thesession_id": "thesession_id",
            "session_type": "session_type",
            "active_buffer_minutes_before": "active_buffer_minutes_before",
            "active_buffer_minutes_after": "active_buffer_minutes_after",
            "location_name": "location_name",
            "location_street": "location_street",
            "city": "city",
            "state": "state",
            "country": "country",
            "timezone": "timezone",
            "location_website": "location_website",
            "location_phone": "location_phone",
            "initiation_date": "initiation_date",
            "termination_date": "termination_date",
            "unlisted_address": "unlisted_address",
            "recurrence": "recurrence",
            "comments": "comments",
            "auto_create_instances": "auto_create_instances",
            "auto_create_hours_ahead": "auto_create_hours_ahead",
            "live_cache_session_limit": "live_cache_session_limit",
            "live_cache_global_limit": "live_cache_global_limit",
            # People-tracking flags (spec 039).
            "show_people_list": "show_people_list",
            "track_attendance": "track_attendance",
            "track_set_starters": "track_set_starters",
        }

        # Starters imply attendance (spec 039 CHECK). Normalize before building the update
        # so a client that sends an inconsistent pair — or only one of them — can never
        # land the session in a state the DB would reject: turning attendance off forces
        # starters off too.
        if "track_attendance" in data and not bool(data["track_attendance"]):
            data = {**data, "track_set_starters": False}

        # Build update query dynamically based on provided fields
        for form_field, db_field in field_mapping.items():
            if form_field in data:
                value = data[form_field]
                # Handle empty strings and convert them to NULL for appropriate fields
                if value == "" and form_field in [
                    "location_street",
                    "location_website",
                    "location_phone",
                    "initiation_date",
                    "termination_date",
                    "recurrence",
                    "comments",
                ]:
                    value = None
                elif form_field in [
                    "unlisted_address",
                    "auto_create_instances",
                    "show_people_list",
                    "track_attendance",
                    "track_set_starters",
                ]:
                    value = bool(value)
                elif form_field == "auto_create_hours_ahead":
                    value = int(value) if value else 24
                elif form_field == "live_cache_session_limit":
                    value = max(0, min(2000, int(value))) if value not in (None, "") else 200
                elif form_field == "live_cache_global_limit":
                    value = max(0, min(1000, int(value))) if value not in (None, "") else 25

                update_fields.append(f"{db_field} = %s")
                update_values.append(value)

        if not update_fields:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "No valid fields to update"}), 400

        # Add audit fields
        update_fields.append("last_modified_date = CURRENT_TIMESTAMP")
        update_fields.append("last_modified_user_id = %s")
        update_values.append(get_current_user_id())

        # Execute the update
        update_query = f"UPDATE session SET {', '.join(update_fields)} WHERE path = %s"
        update_values.append(session_path)

        cur.execute(update_query, update_values)

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"success": True, "message": "Session details updated successfully"}
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"Error updating session: {str(e)}"})


def session_tune_cache_preview(session_path):
    """Preview the live-logging local-cache vocabulary for a session at given N/M sizes,
    for the session-admin "Local Cache" tab (spec 024). Read-only — does NOT change the
    saved limits (the form's Save does that via update_session_ajax). Returns the full
    tune list (each with `tier` and its ranking number) plus tier counts, so the leader
    sees exactly what will be cached as they tune N/M.

    `?n=` / `?m=` override the saved limits for a live preview (clamped to the same
    bounds as the save path); omitted, the saved values are used. Session-admin gated.
    """
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    # Imported lazily: live_logging_routes imports from this module, so a top-level
    # import would be circular.
    from live_logging_routes import compute_session_vocabulary, get_session_cache_limits

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,),
        )
        urow = cur.fetchone()
        is_system_admin = urow and urow[0]

        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        srow = cur.fetchone()
        if not srow:
            return jsonify({"success": False, "error": "Session not found"}), 404
        session_id = srow[0]

        if not is_system_admin:
            cur.execute(
                "SELECT is_admin FROM session_person WHERE session_id = %s AND person_id = %s",
                (session_id, current_user.person_id),
            )
            arow = cur.fetchone()
            if not (arow and arow[0]):
                return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        saved_n, saved_m = get_session_cache_limits(cur, session_id)

        def _clamp(v, default, hi):
            try:
                return max(0, min(hi, int(v)))
            except (TypeError, ValueError):
                return default

        n = _clamp(request.args.get("n"), saved_n, 2000)
        m = _clamp(request.args.get("m"), saved_m, 1000)

        tunes, aliases = compute_session_vocabulary(cur, session_id, n, m, include_meta=True)
        session_count = sum(1 for t in tunes if t["tier"] == "session")
        return jsonify({
            "success": True,
            "n": n,
            "m": m,
            "saved_n": saved_n,
            "saved_m": saved_m,
            "session_count": session_count,
            "global_count": len(tunes) - session_count,
            "alias_count": len(aliases),
            "tunes": tunes,
        })
    finally:
        conn.close()


@api_login_required
def refresh_tunebook_count_ajax(session_path, tune_id):
    try:
        # Fetch data from thesession.org API
        api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
        response = requests.get(api_url, timeout=10)

        if response.status_code != 200:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to fetch data from thesession.org (status: {response.status_code})",
                }
            )

        data = response.json()

        # Check if tunebooks property exists in the response
        if "tunebooks" not in data:
            return jsonify(
                {"success": False, "message": "No tunebooks data found in API response"}
            )

        new_tunebook_count = data["tunebooks"]

        # Update the database
        conn = get_db_connection()
        cur = conn.cursor()

        # Get current cached count
        cur.execute(
            "SELECT tunebook_count_cached FROM tune WHERE tune_id = %s", (tune_id,)
        )
        result = cur.fetchone()

        if not result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found in database"})

        current_count = result[0]

        # Always update the cached date, and update count if different
        if current_count != new_tunebook_count:
            cur.execute(
                "UPDATE tune SET tunebook_count_cached = %s, tunebook_count_cached_date = CURRENT_DATE WHERE tune_id = %s",
                (new_tunebook_count, tune_id),
            )
            message = (
                f"Updated tunebook count from {current_count} to {new_tunebook_count}"
            )
        else:
            cur.execute(
                "UPDATE tune SET tunebook_count_cached_date = CURRENT_DATE WHERE tune_id = %s",
                (tune_id,),
            )
            message = f"Tunebook count unchanged ({current_count})"

        conn.commit()

        # Get the current cached date (whether updated or not)
        cur.execute(
            "SELECT tunebook_count_cached_date FROM tune WHERE tune_id = %s", (tune_id,)
        )
        cached_date_result = cur.fetchone()
        cached_date = cached_date_result[0] if cached_date_result else None

        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": message,
                "old_count": current_count,
                "new_count": new_tunebook_count,
                "cached_date": cached_date.isoformat() if cached_date else None,
            }
        )

    except requests.exceptions.RequestException as e:
        return jsonify(
            {
                "success": False,
                "message": f"Error connecting to thesession.org: {str(e)}",
            }
        )
    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error updating tunebook count: {str(e)}"}
        )


@api_login_required
def cache_tune_setting_ajax(tune_id):
    """
    Fetch and cache a tune setting from thesession.org.
    If setting_id is provided in query params, cache that specific setting.
    If not provided, cache the first setting in the list.
    """
    try:
        # Get optional setting_id from query parameters
        setting_id = request.args.get('setting_id', type=int)

        # Fetch data from thesession.org API
        api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
        response = requests.get(api_url, timeout=10)

        if response.status_code != 200:
            return jsonify({
                "success": False,
                "message": f"Failed to fetch data from thesession.org (status: {response.status_code})",
            })

        data = response.json()

        # Check if settings exist in the response
        if "settings" not in data or not data["settings"]:
            return jsonify({
                "success": False,
                "message": "No settings found for this tune"
            })

        settings = data["settings"]

        # Find the setting to cache
        setting_to_cache = None
        if setting_id:
            # Look for the specific setting_id
            setting_to_cache = next((s for s in settings if s["id"] == setting_id), None)
            if not setting_to_cache:
                return jsonify({
                    "success": False,
                    "message": f"Setting {setting_id} not found for this tune"
                })
        else:
            # Use the first setting
            setting_to_cache = settings[0]
            setting_id = setting_to_cache["id"]

        # Extract the data we need
        key = setting_to_cache.get("key", "")
        abc = setting_to_cache.get("abc", "")
        tune_type = data.get("type", "").title()  # Convert to title case (jig -> Jig)

        # Replace "!" with newline for proper staff line breaks
        # thesession.org uses "!" as a line break marker
        abc = abc.replace("!", "\n")

        # Extract incipit from ABC notation
        from database import extract_abc_incipit
        incipit_abc = extract_abc_incipit(abc, tune_type)

        # Update the database
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if this setting already exists
        cur.execute(
            "SELECT setting_id FROM tune_setting WHERE setting_id = %s",
            (setting_id,)
        )
        existing_setting = cur.fetchone()

        audit_user_id = get_current_user_id()

        if existing_setting:
            # Save to history before updating
            save_to_history(cur, 'tune_setting', 'UPDATE', setting_id, user_id=audit_user_id)

            # Update existing setting
            cur.execute("""
                UPDATE tune_setting
                SET key = %s, abc = %s, incipit_abc = %s, cache_updated_date = (NOW() AT TIME ZONE 'UTC'),
                    last_modified_date = (NOW() AT TIME ZONE 'UTC'), last_modified_user_id = %s
                WHERE setting_id = %s
            """, (key, abc, incipit_abc, audit_user_id, setting_id))
            action = "updated"
        else:
            # Insert new setting
            cur.execute("""
                INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc, cache_updated_date,
                                          created_by_user_id, last_modified_user_id)
                VALUES (%s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), %s, %s)
            """, (setting_id, tune_id, key, abc, incipit_abc, audit_user_id, audit_user_id))

            # Log INSERT to history (manually since record was just created)
            cur.execute("""
                INSERT INTO tune_setting_history
                (setting_id, operation, changed_by_user_id, tune_id, key, abc, image, incipit_abc,
                 incipit_image, cache_updated_date, created_date, last_modified_date,
                 created_by_user_id, last_modified_user_id)
                SELECT setting_id, %s, %s, tune_id, key, abc, image, incipit_abc,
                       incipit_image, cache_updated_date, created_date, last_modified_date,
                       created_by_user_id, last_modified_user_id
                FROM tune_setting WHERE setting_id = %s
            """, ('INSERT', audit_user_id, setting_id))
            action = "cached"

        conn.commit()

        # Generate PNG images for both full ABC and incipit
        full_image = None
        incipit_image = None

        # We need to construct full ABC notation with headers for rendering
        # ABC notation needs headers (X, T, M, L, K) to render properly
        abc_with_headers = abc
        if not abc.startswith('X:'):
            # Construct minimal headers if not present (T: title omitted to avoid text in image)
            abc_with_headers = f"X:1\nM:4/4\nL:1/8\nK:{key if key else 'D'}\n{abc}"

        # Render full ABC image
        full_image = render_abc_to_png(abc_with_headers)

        # Render incipit image
        if incipit_abc:
            incipit_with_headers = incipit_abc
            if not incipit_abc.startswith('X:'):
                incipit_with_headers = f"X:1\nM:4/4\nL:1/8\nK:{key if key else 'D'}\n{incipit_abc}"
            incipit_image = render_abc_to_png(incipit_with_headers, is_incipit=True)

        # Update database with images if they were generated
        if full_image or incipit_image:
            print(f"Updating database with images: full_image={len(full_image) if full_image else 0} bytes, incipit_image={len(incipit_image) if incipit_image else 0} bytes")
            cur.execute("""
                UPDATE tune_setting
                SET image = %s, incipit_image = %s, last_modified_date = (NOW() AT TIME ZONE 'UTC')
                WHERE setting_id = %s
            """, (
                psycopg2.Binary(full_image) if full_image else None,
                psycopg2.Binary(incipit_image) if incipit_image else None,
                setting_id
            ))
            conn.commit()
            print("Database updated successfully")

        # Get the cached setting data
        cur.execute("""
            SELECT setting_id, tune_id, key, abc, incipit_abc, cache_updated_date, image, incipit_image
            FROM tune_setting
            WHERE setting_id = %s
        """, (setting_id,))

        cached_setting = cur.fetchone()

        cur.close()
        conn.close()

        # Encode images as base64 for JSON transport
        image_base64 = bytea_to_base64(cached_setting[6])
        incipit_image_base64 = bytea_to_base64(cached_setting[7])

        return jsonify({
            "success": True,
            "message": f"Successfully {action} setting {setting_id}",
            "action": action,
            "setting": {
                "setting_id": cached_setting[0],
                "tune_id": cached_setting[1],
                "key": cached_setting[2],
                "abc": cached_setting[3],
                "incipit_abc": cached_setting[4],
                "cache_updated_date": cached_setting[5].isoformat() if cached_setting[5] else None,
                "image": image_base64,
                "incipit_image": incipit_image_base64
            }
        })

    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "message": f"Error connecting to thesession.org: {str(e)}",
        })
    except Exception as e:
        import traceback
        print("=" * 80)
        print("ERROR in cache_tune_setting_ajax:")
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception message: {str(e)}")
        print("Full traceback:")
        traceback.print_exc()
        print("=" * 80)

        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return jsonify({
            "success": False,
            "message": f"Error caching tune setting: {str(e)}"
        })


@api_login_required
def get_tune_incipit(tune_id):
    """
    GET /api/tunes/<tune_id>/incipit

    Return the incipit for a tune. Checks local cache first, then falls back
    to fetching from thesession.org if not cached.

    Query Parameters:
        - setting_id (int, optional): Specific setting to fetch incipit for

    Returns:
        JSON with incipit_image (base64 PNG) and/or incipit_abc (text).
    """
    try:
        setting_id = request.args.get('setting_id', type=int)

        # First, check local cache
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            if setting_id:
                cur.execute(
                    "SELECT incipit_image, incipit_abc FROM tune_setting WHERE setting_id = %s",
                    (setting_id,)
                )
            else:
                cur.execute(
                    """SELECT incipit_image, incipit_abc
                       FROM tune_setting
                       WHERE tune_id = %s
                       ORDER BY setting_id ASC
                       LIMIT 1""",
                    (tune_id,)
                )
            row = cur.fetchone()
            if row and (row[0] or row[1]):
                result = {"success": True, "incipit_image": None, "incipit_abc": None}
                if row[0]:
                    result["incipit_image"] = bytea_to_base64(row[0])
                if row[1]:
                    result["incipit_abc"] = row[1]
                return jsonify(result), 200
        finally:
            conn.close()

        # Not cached locally - fetch from thesession.org
        from database import extract_abc_incipit
        api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
        resp = requests.get(api_url, timeout=10)
        if resp.status_code != 200:
            return jsonify({"success": True, "incipit_image": None, "incipit_abc": None}), 200

        data = resp.json()
        settings = data.get("settings", [])
        if not settings:
            return jsonify({"success": True, "incipit_image": None, "incipit_abc": None}), 200

        # Find the requested setting, or use the first one
        setting = None
        if setting_id:
            setting = next((s for s in settings if s.get("id") == setting_id), None)
        if not setting:
            setting = settings[0]

        abc = setting.get("abc", "")
        key = setting.get("key", "")
        tune_type = data.get("type", "").title()

        # Replace "!" with newline (thesession.org line break marker)
        abc = abc.replace("!", "\n")

        incipit_abc = extract_abc_incipit(abc, tune_type)
        if not incipit_abc:
            return jsonify({"success": True, "incipit_image": None, "incipit_abc": None}), 200

        result = {"success": True, "incipit_image": None, "incipit_abc": incipit_abc}

        # Try to render to PNG
        incipit_with_headers = incipit_abc
        if not incipit_abc.startswith('X:'):
            incipit_with_headers = f"X:1\nM:4/4\nL:1/8\nK:{key if key else 'D'}\n{incipit_abc}"
        incipit_image = render_abc_to_png(incipit_with_headers, is_incipit=True)
        if incipit_image:
            result["incipit_image"] = base64.b64encode(incipit_image).decode('utf-8')

        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error fetching incipit: {str(e)}"
        }), 500


@public_api  # backs the tune-detail modal on the logged-out session Tunes tab; current_user use is personalization only
def get_session_tune_detail(session_path, tune_id):
    """Session-scoped tune detail — the same drawer payload as
    /api/tunes/<id>/detail?session=<path> (one builder, so the shapes can't
    drift); kept routed for legacy callers. Error bodies stay 200-with-message
    as they always were here."""
    from serializers import build_tune_detail_payload, SessionNotFound

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        tune_id, redirected_from = follow_tune_redirect(cur, tune_id)
        person_id = current_user.person_id if current_user.is_authenticated else None
        try:
            payload = build_tune_detail_payload(
                conn,
                tune_id,
                person_id=person_id,
                logged_in=current_user.is_authenticated,
                is_admin=bool(current_user.is_authenticated and current_user.is_system_admin),
                session_path=session_path,
                redirected_from=redirected_from,
            )
        except SessionNotFound:
            return jsonify({"success": False, "message": "Session not found"})
        if payload is None:
            return jsonify({"success": False, "message": "Tune not found"})
        return jsonify(payload)
    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error retrieving tune details: {str(e)}"}
        )
    finally:
        conn.close()


@api_login_required
def update_session_tune_details(session_path, tune_id):
    """Update session-specific tune details (setting_id, key, alias, and aliases).

    Session admins only (spec 037). This is the session making a canonical statement
    about its own repertoire; before 037 the endpoint was merely @api_login_required,
    so any logged-in user could rewrite the alias/setting/key of any tune at any
    session they had never attended. A member who wants to record what was played on
    a given night edits that instance instead.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"})

        # Build dynamic update - only update fields that are explicitly present in request
        update_fields = []
        update_values = []

        # Handle setting_id if present in request
        if "setting_id" in data:
            setting_id_raw = data.get("setting_id")
            if setting_id_raw is None or setting_id_raw == "":
                update_fields.append("setting_id = %s")
                update_values.append(None)
            else:
                setting_id_str = str(setting_id_raw).strip()
                if setting_id_str:
                    try:
                        update_fields.append("setting_id = %s")
                        update_values.append(int(setting_id_str))
                    except ValueError:
                        return jsonify(
                            {
                                "success": False,
                                "message": "Setting ID must be a number",
                            }
                        )
                else:
                    update_fields.append("setting_id = %s")
                    update_values.append(None)

        # Handle key if present in request
        if "key" in data:
            key_raw = data.get("key")
            if key_raw is None or key_raw == "":
                update_fields.append("key = %s")
                update_values.append(None)
            else:
                key_str = str(key_raw).strip()
                update_fields.append("key = %s")
                update_values.append(key_str if key_str else None)

        # Handle alias if present in request
        if "alias" in data:
            alias_raw = data.get("alias")
            if alias_raw is None or alias_raw == "":
                update_fields.append("alias = %s")
                update_values.append(None)
            else:
                alias_str = str(alias_raw).strip()
                update_fields.append("alias = %s")
                update_values.append(alias_str if alias_str else None)

        # Parse aliases for session_tune_alias table (if present)
        new_aliases = []
        if "aliases" in data:
            aliases_str = data.get("aliases", "")
            if aliases_str:
                aliases_str = str(aliases_str).strip()
                new_aliases = [a.strip() for a in aliases_str.split(",") if a.strip()]

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        if not is_session_admin_for(cur, session_id, current_user.person_id):
            cur.close()
            conn.close()
            return jsonify(
                {"success": False, "message": "Only session admins can change what a session plays"}
            ), 403

        # Enroll on the fly if the tune has no session_tune row (spec 037). Stating
        # "we play this in Ador here" is the strongest possible evidence the tune
        # belongs to the repertoire; asking to confirm would be a silly question.
        # Since spec 025 this should only be reachable for a tune that has never
        # been played here.
        cur.execute(
            "SELECT tune_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (session_id, tune_id),
        )
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO session_tune (session_id, tune_id, setting_id, created_by_user_id)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (session_id, tune_id) DO NOTHING""",
                (session_id, tune_id, default_setting_id(cur, tune_id), get_current_user_id()),
            )

        # Save to history before making changes
        save_to_history(cur, "session_tune", "UPDATE", (session_id, tune_id), user_id=get_current_user_id())

        # Update session_tune - only update fields that were in the request
        if update_fields:
            # Always update last_modified_user_id
            update_fields.append("last_modified_user_id = %s")
            update_values.append(get_current_user_id())
            update_values.extend([session_id, tune_id])

            cur.execute(
                f"""
                UPDATE session_tune
                SET {', '.join(update_fields)}
                WHERE session_id = %s AND tune_id = %s
            """,
                tuple(update_values),
            )

        # Now handle aliases in session_tune_alias table
        # First, get existing aliases
        cur.execute(
            """
            SELECT session_tune_alias_id, alias
            FROM session_tune_alias
            WHERE session_id = %s AND tune_id = %s
        """,
            (session_id, tune_id),
        )
        existing_aliases = cur.fetchall()
        existing_alias_map = {row[1]: row[0] for row in existing_aliases}

        # Determine which aliases to add and which to remove
        existing_alias_set = set(existing_alias_map.keys())
        new_alias_set = set(new_aliases)

        aliases_to_add = new_alias_set - existing_alias_set
        aliases_to_remove = existing_alias_set - new_alias_set

        # Add new aliases
        for alias in aliases_to_add:
            cur.execute(
                """
                INSERT INTO session_tune_alias (session_id, tune_id, alias, created_by_user_id)
                VALUES (%s, %s, %s, %s)
                RETURNING session_tune_alias_id
            """,
                (session_id, tune_id, alias, get_current_user_id()),
            )
            alias_id = cur.fetchone()[0]
            save_to_history(cur, "session_tune_alias", "INSERT", alias_id, user_id=get_current_user_id())

        # Remove old aliases
        for alias in aliases_to_remove:
            alias_id = existing_alias_map[alias]
            save_to_history(cur, "session_tune_alias", "DELETE", alias_id, user_id=get_current_user_id())
            cur.execute(
                "DELETE FROM session_tune_alias WHERE session_tune_alias_id = %s",
                (alias_id,),
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": "Tune details saved successfully",
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error updating tune details: {str(e)}"}
        )


@api_login_required
def delete_session_tune(session_path, tune_id):
    """Un-enroll a tune from a session's repertoire (session admins only).

    Refuses when the tune has ever been played here (spec 037). The invariant is
    that every tune played at an instance is in that session's repertoire, and this
    endpoint used to break it: it deleted the session_tune row and left the
    session_instance_tune plays orphaned. So it now means exactly one narrow thing —
    un-enrolling a tune that was added to the repertoire and never actually played.
    Fix the history, not the summary.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id = session_result[0]

        # Check permissions - must be system admin or session admin
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        is_system_admin = user_row and user_row[0]

        if not is_system_admin:
            cur.execute(
                "SELECT is_admin FROM session_person WHERE session_id = %s AND person_id = %s",
                (session_id, current_user.person_id)
            )
            admin_row = cur.fetchone()
            is_session_admin = admin_row and admin_row[0]

            if not is_session_admin:
                cur.close()
                conn.close()
                return jsonify({"success": False, "message": "Only session admins can remove tunes from the session"}), 403

        # Get tune name for response message
        cur.execute("SELECT name FROM tune WHERE tune_id = %s", (tune_id,))
        tune_row = cur.fetchone()
        tune_name = tune_row[0] if tune_row else f"Tune {tune_id}"

        # Check if tune exists in session_tune
        cur.execute(
            "SELECT tune_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (session_id, tune_id)
        )
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found in this session"}), 404

        # Plays outrank the repertoire. The UI hides the link entirely in this case,
        # but the endpoint is reachable directly, so it's enforced here too.
        cur.execute(
            """
            SELECT COUNT(*) FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s AND sit.deleted = FALSE
            """,
            (session_id, tune_id),
        )
        play_count = cur.fetchone()[0]
        if play_count:
            cur.close()
            conn.close()
            return jsonify({
                "success": False,
                "message": (
                    f'"{tune_name}" has been played at this session {play_count} '
                    f'time{"s" if play_count != 1 else ""}. Remove those plays first.'
                ),
            }), 409

        # Delete associated aliases first (foreign key constraint)
        cur.execute(
            "DELETE FROM session_tune_alias WHERE session_id = %s AND tune_id = %s",
            (session_id, tune_id)
        )

        # Save to history before deleting
        save_to_history(cur, "session_tune", "DELETE", (session_id, tune_id), user_id=get_current_user_id())

        # Delete from session_tune
        cur.execute(
            "DELETE FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (session_id, tune_id)
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f'"{tune_name}" removed from session tune list'
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Error removing tune: {str(e)}"}), 500


@api_login_required
def add_session_tune(session_path):
    """Add a tune to a session's session_tune table"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        tune_id = data.get("tune_id")

        # thesession.org import (spec 026 pattern, same as POST /api/my-tunes): a
        # thesession_id (int, numeric string, or tunes URL) doubles as the tune_id —
        # thesession ids ARE our tune ids — and, when the tune isn't local yet, we
        # import it server-side below (the add pane's remote picks + paste-a-URL).
        from live_logging_routes import _parse_thesession_id
        thesession_id = _parse_thesession_id(data.get("thesession_id"))
        if not tune_id and thesession_id is not None:
            tune_id = thesession_id
        if not tune_id:
            return jsonify({"success": False, "error": "tune_id is required"}), 400

        alias = (data.get("alias") or "").strip() or None
        setting_id = data.get("setting_id")
        key = (data.get("key") or "").strip() or None

        # Parse setting_id
        parsed_setting_id = None
        if setting_id:
            try:
                parsed_setting_id = int(setting_id)
            except (ValueError, TypeError):
                return jsonify({"success": False, "error": "Invalid setting_id"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Session not found"}), 404

        session_id = session_result[0]

        # Check if tune exists; a merged-away id remaps to the canonical tune
        # (spec 030) — a stale write means the merged tune, so proceed rather
        # than reject.
        cur.execute("SELECT tune_id, redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
        tune_check = cur.fetchone()

        remapped_from = None
        if tune_check and tune_check[1] is not None:
            remapped_from = tune_id
            tune_id = tune_check[1]
            cur.execute("SELECT tune_id, redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
            tune_check = cur.fetchone()

        # Check if tune exists in tune table
        new_tune_inserted = False
        if not tune_check and thesession_id is not None:
            # Identified by thesession_id but not local: import it (tune row + default
            # setting ABC; notation images render lazily). Same helper the live logger
            # and POST /api/my-tunes use, so imports behave identically everywhere.
            from live_logging_routes import _import_tune_for_live
            try:
                _import_tune_for_live(cur, tune_id, get_current_user_id())
            except TuneImportError as e:
                conn.rollback()
                cur.close()
                conn.close()
                return jsonify({
                    "success": False,
                    "error": f"Could not import tune from thesession.org: {e.message}",
                }), 502
            cur.execute("SELECT tune_id, redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
            tune_check = cur.fetchone()
        if not tune_check:
            # If new_tune data provided, insert it
            if data.get("new_tune"):
                new_tune_data = data.get("new_tune")
                cur.execute(
                    """
                    INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date, created_by_user_id)
                    VALUES (%s, %s, %s, %s, CURRENT_DATE, %s)
                    ON CONFLICT (tune_id) DO NOTHING
                    RETURNING tune_id
                """,
                    (
                        new_tune_data.get("tune_id"),
                        new_tune_data.get("name"),
                        new_tune_data.get("tune_type"),
                        new_tune_data.get("tunebook_count", 0),
                        get_current_user_id(),
                    ),
                )
                # Track if a new tune was actually inserted (not a conflict)
                new_tune_inserted = cur.fetchone() is not None
            else:
                cur.close()
                conn.close()
                return jsonify({"success": False, "error": "Tune not found"}), 404

        # Check if tune already exists in session_tune
        cur.execute(
            "SELECT tune_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (session_id, tune_id),
        )
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Tune already exists in this session"}), 409

        # No specific setting requested -> store the tune's default so the setting in
        # use is always visible/linkable (spec 032).
        if parsed_setting_id is None:
            parsed_setting_id = default_setting_id(cur, tune_id)

        # Insert into session_tune
        cur.execute(
            """
            INSERT INTO session_tune (session_id, tune_id, alias, setting_id, key, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (session_id, tune_id, alias, parsed_setting_id, key, get_current_user_id()),
        )

        # Save to history
        save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id), user_id=get_current_user_id())

        conn.commit()
        cur.close()
        conn.close()

        # If a new tune was inserted, cache the default setting and generate images
        # This must happen after commit so the tune exists for foreign key constraints
        if new_tune_inserted:
            cache_default_tune_setting(tune_id, None, get_current_user_id(), sync=True)

        # A specific setting may not be cached yet (e.g. chosen from the preview's
        # backfilled pager, spec 032): fetch + cache it, same as POST /api/my-tunes.
        if parsed_setting_id:
            conn_check = get_db_connection()
            try:
                cur_check = conn_check.cursor()
                cur_check.execute("SELECT setting_id FROM tune_setting WHERE setting_id = %s", (parsed_setting_id,))
                setting_cached = cur_check.fetchone() is not None
            finally:
                conn_check.close()
            if not setting_cached:
                cache_default_tune_setting(tune_id, None, get_current_user_id(), sync=True, target_setting_id=parsed_setting_id)

        return jsonify({
            "success": True,
            "message": "Tune added to session successfully",
            "tune_id": tune_id,
            "remapped_from": remapped_from,
        }), 201

    except Exception as e:
        return jsonify({"success": False, "error": f"Error adding tune: {str(e)}"}), 500


@api_login_required  # no anonymous caller found (POST/DELETE alias siblings are gated too)
def get_session_tune_aliases(session_path, tune_id):
    """Get all aliases for a tune in a session"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Get all aliases for this tune in this session
        cur.execute(
            """
            SELECT session_tune_alias_id, alias, created_date
            FROM session_tune_alias
            WHERE session_id = %s AND tune_id = %s
            ORDER BY created_date ASC
        """,
            (session_id, tune_id),
        )

        aliases = cur.fetchall()
        cur.close()
        conn.close()

        aliases_list = [
            {"id": alias[0], "alias": alias[1], "created_date": alias[2].isoformat()}
            for alias in aliases
        ]

        return jsonify({"success": True, "aliases": aliases_list})

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error retrieving aliases: {str(e)}"}
        )


@api_login_required
def add_session_tune_alias(session_path, tune_id):
    """Add a new alias for a tune in a session"""
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    alias = request.json.get("alias", "").strip()
    if not alias:
        return jsonify({"success": False, "message": "Please enter an alias"})

    # Normalize the alias
    normalized_alias = normalize_quotes(alias)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Check if alias already exists for this session
        cur.execute(
            """
            SELECT tune_id
            FROM session_tune_alias
            WHERE session_id = %s AND LOWER(alias) = LOWER(%s)
        """,
            (session_id, normalized_alias),
        )

        existing_alias = cur.fetchone()
        if existing_alias:
            cur.close()
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "message": f'Alias "{normalized_alias}" already exists in this session',
                }
            )

        # Check if this would conflict with session_tune aliases
        cur.execute(
            """
            SELECT tune_id
            FROM session_tune
            WHERE session_id = %s AND LOWER(alias) = LOWER(%s)
        """,
            (session_id, normalized_alias),
        )

        existing_session_tune_alias = cur.fetchone()
        if existing_session_tune_alias:
            cur.close()
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "message": f'Alias "{normalized_alias}" already exists as a session tune alias',
                }
            )

        # Insert the new alias
        cur.execute(
            """
            INSERT INTO session_tune_alias (session_id, tune_id, alias, created_date, last_modified_date, created_by_user_id)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)
            RETURNING session_tune_alias_id, created_date
        """,
            (session_id, tune_id, normalized_alias, get_current_user_id()),
        )

        result = cur.fetchone()
        if not result:
            return jsonify({"success": False, "message": "Failed to create alias"})
        new_id, created_date = result

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f'Alias "{normalized_alias}" added successfully',
                "alias": {
                    "id": new_id,
                    "alias": normalized_alias,
                    "created_date": created_date.isoformat(),
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Error adding alias: {str(e)}"})


@api_login_required
def delete_session_tune_alias(session_path, tune_id, alias_id):
    """Delete an alias for a tune in a session"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Get the alias info before deleting for the response message
        cur.execute(
            """
            SELECT alias
            FROM session_tune_alias
            WHERE session_tune_alias_id = %s AND session_id = %s AND tune_id = %s
        """,
            (alias_id, session_id, tune_id),
        )

        alias_info = cur.fetchone()
        if not alias_info:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Alias not found"})

        alias_name = alias_info[0]

        # Delete the alias
        cur.execute(
            """
            DELETE FROM session_tune_alias
            WHERE session_tune_alias_id = %s AND session_id = %s AND tune_id = %s
        """,
            (alias_id, session_id, tune_id),
        )

        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Alias not found"})

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"success": True, "message": f'Alias "{alias_name}" deleted successfully'}
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Error deleting alias: {str(e)}"})


@api_login_required
def add_session_instance_ajax(session_path):
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    date = request.json.get("date", "").strip()
    start_time = (
        request.json.get("start_time", "").strip()
        if request.json.get("start_time")
        else None
    )
    end_time = (
        request.json.get("end_time", "").strip()
        if request.json.get("end_time")
        else None
    )
    location = (
        request.json.get("location", "").strip()
        if request.json.get("location")
        else None
    )
    comments = (
        request.json.get("comments", "").strip()
        if request.json.get("comments")
        else None
    )
    cancelled = request.json.get("cancelled", False)

    if not date:
        return jsonify({"success": False, "message": "Please enter a session date"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id and location_name for this session_path
        cur.execute(
            "SELECT session_id, location_name FROM session WHERE path = %s",
            (session_path,),
        )
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id, session_location_name = session_result

        # Determine location_override: only set if location is provided AND different from session's location_name
        location_override = None
        if location and location != session_location_name:
            location_override = location

        # Insert new session instance
        cur.execute(
            """
            INSERT INTO session_instance (session_id, date, start_time, end_time, location_override, is_cancelled, comments, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING session_instance_id
        """,
            (session_id, date, start_time, end_time, location_override, cancelled, comments, get_current_user_id()),
        )

        session_instance_result = cur.fetchone()
        if not session_instance_result:
            cur.close()
            conn.close()
            return jsonify(
                {"success": False, "message": "Failed to create session instance"}
            )

        session_instance_id = session_instance_result[0]

        # Save the newly created session instance to history
        save_to_history(cur, "session_instance", "INSERT", session_instance_id, user_id=get_current_user_id())

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f"Session instance for {date} created successfully!",
                "session_instance_id": session_instance_id,
                "date": date,
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": f"Failed to create session instance: {str(e)}",
            }
        )


@api_login_required
def get_next_session_instance_suggestion_ajax(session_path):
    """
    Get the next suggested session instance based on recurrence pattern.
    Returns the next occurrence from the recurrence that doesn't already exist.
    """
    try:
        from datetime import datetime, timedelta
        from recurrence_utils import SessionRecurrence
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session details including recurrence pattern
        cur.execute(
            """
            SELECT session_id, recurrence, timezone
            FROM session
            WHERE path = %s
        """,
            (session_path,),
        )
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id, recurrence_json, session_timezone = session_result

        # If no recurrence, return today's date with no times
        if not recurrence_json:
            cur.close()
            conn.close()
            return jsonify({
                "success": True,
                "date": datetime.now().date().isoformat(),
                "start_time": None,
                "end_time": None
            })

        # Parse recurrence pattern
        try:
            tz = ZoneInfo(session_timezone or 'UTC')
            session_recurrence = SessionRecurrence(recurrence_json)
        except (ValueError, TypeError) as e:
            cur.close()
            conn.close()
            return jsonify({
                "success": False,
                "message": f"Invalid recurrence pattern: {str(e)}"
            })

        # Get occurrences for the next 90 days
        today = datetime.now(tz).date()
        end_date = today + timedelta(days=90)

        occurrences = session_recurrence.get_occurrences_in_range(
            today, end_date, tz, reference_date=None
        )

        if not occurrences:
            cur.close()
            conn.close()
            return jsonify({
                "success": True,
                "date": datetime.now().date().isoformat(),
                "start_time": None,
                "end_time": None
            })

        # Check which instances already exist
        occurrence_dates = [occ[0].date() for occ in occurrences]
        placeholders = ','.join(['%s'] * len(occurrence_dates))

        cur.execute(f"""
            SELECT date, start_time, end_time
            FROM session_instance
            WHERE session_id = %s AND date IN ({placeholders})
        """, [session_id] + occurrence_dates)

        existing_instances = {}
        for row in cur.fetchall():
            date_val = row[0]
            start_time_val = row[1]
            end_time_val = row[2]
            # Store as key with tuple of (start_time, end_time)
            if date_val not in existing_instances:
                existing_instances[date_val] = []
            existing_instances[date_val].append((start_time_val, end_time_val))

        cur.close()
        conn.close()

        # Find first occurrence that doesn't exist
        for start_dt, end_dt in occurrences:
            occ_date = start_dt.date()
            occ_start_time = start_dt.time()
            occ_end_time = end_dt.time()

            # Check if this exact combination exists
            if occ_date in existing_instances:
                # Check if this specific time slot exists
                time_exists = any(
                    (existing_start == occ_start_time and existing_end == occ_end_time)
                    for existing_start, existing_end in existing_instances[occ_date]
                )
                if not time_exists:
                    # Date exists but different time - this is the next one
                    return jsonify({
                        "success": True,
                        "date": occ_date.isoformat(),
                        "start_time": occ_start_time.strftime("%H:%M"),
                        "end_time": occ_end_time.strftime("%H:%M")
                    })
            else:
                # Date doesn't exist at all - this is the next one
                return jsonify({
                    "success": True,
                    "date": occ_date.isoformat(),
                    "start_time": occ_start_time.strftime("%H:%M"),
                    "end_time": occ_end_time.strftime("%H:%M")
                })

        # No non-existent occurrences found in next 90 days
        # Return the first occurrence anyway
        first_start_dt, first_end_dt = occurrences[0]
        return jsonify({
            "success": True,
            "date": first_start_dt.date().isoformat(),
            "start_time": first_start_dt.time().strftime("%H:%M"),
            "end_time": first_end_dt.time().strftime("%H:%M")
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to get suggestion: {str(e)}"
        })


@api_login_required
def update_session_instance_ajax(session_path, date_or_id):
    """
    Update session instance. Accepts either date (YYYY-MM-DD) or numeric ID.
    CRITICAL: Always use ID when multiple instances exist on the same date.
    """
    import re

    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    new_date = request.json.get("date", "").strip()
    start_time = (
        request.json.get("start_time", "").strip()
        if request.json.get("start_time")
        else None
    )
    end_time = (
        request.json.get("end_time", "").strip()
        if request.json.get("end_time")
        else None
    )
    location = (
        request.json.get("location", "").strip()
        if request.json.get("location")
        else None
    )
    comments = (
        request.json.get("comments", "").strip()
        if request.json.get("comments")
        else None
    )
    cancelled = request.json.get("cancelled", False)

    if not new_date:
        return jsonify({"success": False, "message": "Please enter a session date"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id and location_name for this session_path
        cur.execute(
            "SELECT session_id, location_name FROM session WHERE path = %s",
            (session_path,),
        )
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id, session_location_name = session_result

        # Determine if date_or_id is a date or an ID
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        id_pattern = r"^\d+$"

        if re.match(id_pattern, date_or_id) and not re.match(date_pattern, date_or_id):
            # It's an ID
            session_instance_id = int(date_or_id)
            # Verify this instance belongs to this session
            cur.execute(
                """
                SELECT session_instance_id FROM session_instance
                WHERE session_instance_id = %s AND session_id = %s
            """,
                (session_instance_id, session_id),
            )
            instance_result = cur.fetchone()
        else:
            # It's a date - get the first instance on that date
            cur.execute(
                """
                SELECT session_instance_id FROM session_instance
                WHERE session_id = %s AND date = %s
                ORDER BY session_instance_id ASC
                LIMIT 1
            """,
                (session_id, date_or_id),
            )
            instance_result = cur.fetchone()

        if not instance_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id = instance_result[0]

        # Determine location_override: only set if location is provided AND different from session's location_name
        location_override = None
        if location and location != session_location_name:
            location_override = location

        # Save current state to history before update
        save_to_history(cur, "session_instance", "UPDATE", session_instance_id, user_id=get_current_user_id())

        # Update the session instance
        cur.execute(
            """
            UPDATE session_instance
            SET date = %s, start_time = %s, end_time = %s, location_override = %s, is_cancelled = %s, comments = %s
            WHERE session_instance_id = %s
        """,
            (new_date, start_time, end_time, location_override, cancelled, comments, session_instance_id),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"success": True, "message": "Session instance updated successfully!"}
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": f"Failed to update session instance: {str(e)}",
            }
        )


@api_login_required  # zero callers found in templates/, static/js/, frontend/src/ — gated by default
def get_session_tune_count_ajax(session_path, date):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get tune count for this session instance (exclude break records)
        cur.execute(
            """
            SELECT COUNT(*)
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s AND sit.record_type = 'tune'
        """,
            (session_path, date),
        )

        result = cur.fetchone()
        tune_count = result[0] if result else 0

        cur.close()
        conn.close()

        return jsonify({"success": True, "tune_count": tune_count})

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Failed to get tune count: {str(e)}"}
        )


@api_login_required
def delete_session_instance_ajax(session_path, date_or_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id for this session_path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Get the session instance ID
        cur.execute(
            """
            SELECT session_instance_id FROM session_instance
            WHERE session_id = %s AND date = %s
        """,
            (session_id, date_or_id),
        )
        instance_result = cur.fetchone()

        if not instance_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id = instance_result[0]

        # Save to history before deletion
        audit_user_id = get_current_user_id()
        save_to_history(cur, "session_instance", "DELETE", session_instance_id, user_id=audit_user_id)

        # Get all session_instance_tune records to save to history before deletion
        cur.execute(
            """
            SELECT session_instance_tune_id FROM session_instance_tune
            WHERE session_instance_id = %s
        """,
            (session_instance_id,),
        )
        tune_records = cur.fetchall()

        # Save each tune record to history before deletion
        for tune_record in tune_records:
            save_to_history(cur, "session_instance_tune", "DELETE", tune_record[0], user_id=audit_user_id)

        # Get all session_instance_person records to save to history before deletion
        cur.execute(
            """
            SELECT session_instance_id, person_id FROM session_instance_person
            WHERE session_instance_id = %s
        """,
            (session_instance_id,),
        )
        person_records = cur.fetchall()

        # Save each person record to history before deletion
        # record_id should be a tuple (session_instance_id, person_id)
        for person_record in person_records:
            save_to_history(cur, "session_instance_person", "DELETE", person_record, user_id=audit_user_id)

        # Delete session_instance_person records first (attendance)
        cur.execute(
            """
            DELETE FROM session_instance_person WHERE session_instance_id = %s
        """,
            (session_instance_id,),
        )

        # Delete session_instance_tune records
        cur.execute(
            """
            DELETE FROM session_instance_tune WHERE session_instance_id = %s
        """,
            (session_instance_id,),
        )

        # Finally delete the session instance
        cur.execute(
            """
            DELETE FROM session_instance WHERE session_instance_id = %s
        """,
            (session_instance_id,),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f"Session instance for {date_or_id} deleted successfully!",
            }
        )

    except Exception as e:
        # Rollback on error
        if 'conn' in locals():
            conn.rollback()
            if 'cur' in locals():
                cur.close()
            conn.close()

        # Log the full error for debugging
        import traceback
        error_details = traceback.format_exc()
        print(f"Error deleting session instance: {error_details}")

        return jsonify(
            {
                "success": False,
                "message": f"Failed to delete session instance: {str(e)}",
            }
        ), 500


@api_login_required
def mark_session_log_complete_ajax(session_path, date_or_id):
    """Mark session log as complete. Accepts either date (YYYY-MM-DD) or numeric ID."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id for this session_path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Get session_instance_id (works with both date and ID)
        session_instance_id = get_session_instance_id(cur, session_id, date_or_id)
        if not session_instance_id:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        # Check current log_complete_date
        cur.execute(
            "SELECT log_complete_date FROM session_instance WHERE session_instance_id = %s",
            (session_instance_id,),
        )
        result = cur.fetchone()
        current_log_complete_date = result[0] if result else None

        # Check if already marked complete
        if current_log_complete_date is not None:
            cur.close()
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "message": "Session log is already marked as complete",
                }
            )

        # Mark the session log as complete
        cur.execute(
            """
            UPDATE session_instance
            SET log_complete_date = CURRENT_TIMESTAMP
            WHERE session_instance_id = %s
        """,
            (session_instance_id,),
        )

        # Record in history table
        save_to_history(cur, "session_instance", "UPDATE", session_instance_id, user_id=get_current_user_id())

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": "This session log has been marked as complete.",
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": f"Failed to mark session log complete: {str(e)}",
            }
        )


@api_login_required
def mark_session_log_incomplete_ajax(session_path, date_or_id):
    """Mark session log as incomplete. Accepts either date (YYYY-MM-DD) or numeric ID."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id for this session_path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Get session_instance_id (works with both date and ID)
        session_instance_id = get_session_instance_id(cur, session_id, date_or_id)
        if not session_instance_id:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        # Check current log_complete_date
        cur.execute(
            "SELECT log_complete_date FROM session_instance WHERE session_instance_id = %s",
            (session_instance_id,),
        )
        result = cur.fetchone()
        current_log_complete_date = result[0] if result else None

        # Check if not marked complete
        if current_log_complete_date is None:
            cur.close()
            conn.close()
            return jsonify(
                {"success": False, "message": "Session log is not marked as complete"}
            )

        # Mark the session log as incomplete
        cur.execute(
            """
            UPDATE session_instance
            SET log_complete_date = NULL
            WHERE session_instance_id = %s
        """,
            (session_instance_id,),
        )

        # Record in history table
        save_to_history(cur, "session_instance", "UPDATE", session_instance_id, user_id=get_current_user_id())

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": "This session log has been marked as not complete.",
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": f"Failed to mark session log as not complete: {str(e)}",
            }
        )


@public_api  # backs the /add-session page, which has no @login_required (only the final POST /api/add-session is gated) — TODO tighten?
def check_existing_session_ajax():
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    session_id = request.json.get("session_id")
    if not session_id:
        return jsonify({"success": False, "message": "Session ID is required"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if session ID already exists in our database
        cur.execute("SELECT path FROM session WHERE thesession_id = %s", (session_id,))
        existing_session = cur.fetchone()

        cur.close()
        conn.close()

        if existing_session:
            return jsonify(
                {"exists": True, "session_path": f"/sessions/{existing_session[0]}"}
            )
        else:
            return jsonify({"exists": False})

    except Exception as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"})


@public_api  # backs the /add-session page, which has no @login_required (only the final POST /api/add-session is gated) — TODO tighten?
def search_sessions_ajax():
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    search_query = request.json.get("query")
    if not search_query:
        return jsonify({"success": False, "message": "Search query is required"})

    try:
        # Search sessions on thesession.org API (perpage=50 is the max allowed)
        api_url = f"https://thesession.org/sessions/search?q={search_query}&format=json&perpage=50"
        response = requests.get(api_url, timeout=10)

        if response.status_code != 200:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to search sessions (status: {response.status_code})",
                }
            )

        data = response.json()
        sessions = data.get("sessions", [])

        # Get database connection to check existing sessions
        conn = get_db_connection()
        cur = conn.cursor()

        # Return first 50 results with formatted data and existence check
        results = []
        for session_item in sessions[:50]:
            session_id = session_item.get("id")
            venue_name = (
                session_item.get("venue", {}).get("name", "")
                if session_item.get("venue")
                else ""
            )
            city = (
                session_item.get("town", {}).get("name", "")
                if session_item.get("town")
                else ""
            )
            state = (
                session_item.get("area", {}).get("name", "")
                if session_item.get("area")
                else ""
            )
            country = (
                session_item.get("country", {}).get("name", "")
                if session_item.get("country")
                else ""
            )

            # Check if this session already exists in our database
            cur.execute(
                "SELECT path FROM session WHERE thesession_id = %s", (session_id,)
            )
            existing_session = cur.fetchone()

            result = {
                "id": session_id,
                "name": venue_name,
                "city": city,
                "state": state,
                "country": country,
                "display_text": f"{venue_name}, {city}, {state}, {country}".replace(
                    ", , ", ", "
                ).strip(", "),
                "exists_in_db": existing_session is not None,
                "session_path": f"/sessions/{existing_session[0]}"
                if existing_session
                else None,
            }
            results.append(result)

        cur.close()
        conn.close()

        return jsonify({"success": True, "results": results})

    except requests.exceptions.RequestException as e:
        return jsonify(
            {
                "success": False,
                "message": f"Error connecting to TheSession.org: {str(e)}",
            }
        )
    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error processing search results: {str(e)}"}
        )


@public_api  # backs the /add-session page, which has no @login_required (only the final POST /api/add-session is gated) — TODO tighten?
def fetch_session_data_ajax():
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    session_id = request.json.get("session_id")
    if not session_id:
        return jsonify({"success": False, "message": "Session ID is required"})

    try:
        # Fetch data from thesession.org API
        api_url = f"https://thesession.org/sessions/{session_id}?format=json"
        response = requests.get(api_url, timeout=10)

        if response.status_code == 404:
            return jsonify(
                {"success": False, "message": "Session not found on TheSession.org"}
            )
        elif response.status_code != 200:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to fetch session data (status: {response.status_code})",
                }
            )

        data = response.json()

        # Map TheSession.org data to our format
        venue_name = data.get("venue", {}).get("name", "") if data.get("venue") else ""

        # Extract just the date part from the datetime string (format: "2017-04-21 16:33:23")
        date_str = data.get("date", "")
        inception_date = date_str.split(" ")[0] if date_str else ""

        # Extract comments (sorted by date, most recent first)
        comments = data.get("comments", [])
        comments_list = []
        for comment in comments:
            comments_list.append({
                "date": comment.get("date", ""),
                "content": comment.get("content", "")
            })
        # Sort by date descending (most recent first)
        comments_list.sort(key=lambda x: x.get("date", ""), reverse=True)

        session_data = {
            "id": data.get("id"),
            "name": venue_name,  # Default session name to location name
            "inception_date": inception_date,
            "location_name": venue_name,
            "location_phone": data.get("venue", {}).get("phone", "")
            if data.get("venue")
            else "",
            "location_website": data.get("venue", {}).get("web", "")
            if data.get("venue")
            else "",
            "city": data.get("town", {}).get("name", "") if data.get("town") else "",
            "state": data.get("area", {}).get("name", "") if data.get("area") else "",
            "country": data.get("country", {}).get("name", "")
            if data.get("country")
            else "",
            "recurrence": data.get("schedule", ""),
            "comments": comments_list,
        }

        return jsonify({"success": True, "session_data": session_data})

    except requests.exceptions.RequestException as e:
        return jsonify(
            {
                "success": False,
                "message": f"Error connecting to TheSession.org: {str(e)}",
            }
        )
    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error processing session data: {str(e)}"}
        )


@api_login_required
def add_session_ajax():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "No JSON data provided"})

    # Validate required fields. Anything non-string is a malformed payload — treat
    # it as missing rather than letting .strip() raise (that used to 500).
    required_fields = ["name", "path", "city", "state", "country"]
    for field in required_fields:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            return jsonify(
                {"success": False, "message": f"{field.title()} is required"}
            )

    # The path is the session's URL, and a malformed one strands the session:
    # every admin route is keyed on the path, so there'd be no way back in.
    new_path, path_error = normalize_session_path(data.get("path"))
    if path_error:
        return jsonify({"success": False, "message": path_error})

    # Same coercion the admin update uses (session_fields), so a session can be created
    # with the values the admin form can later edit — including a thesession.org link
    # pasted as a URL rather than a bare id.
    from session_fields import (
        normalize_active_buffer,
        normalize_session_type,
        parse_thesession_session_id,
    )

    thesession_id, ts_error = parse_thesession_session_id(data.get("thesession_id"))
    if ts_error:
        return jsonify({"success": False, "message": ts_error})
    session_type, type_error = normalize_session_type(data.get("session_type"))
    if type_error:
        return jsonify({"success": False, "message": type_error})
    buffer_before, before_error = normalize_active_buffer(
        data.get("active_buffer_minutes_before"), "Minutes before"
    )
    if before_error:
        return jsonify({"success": False, "message": before_error})
    buffer_after, after_error = normalize_active_buffer(
        data.get("active_buffer_minutes_after"), "Minutes after"
    )
    if after_error:
        return jsonify({"success": False, "message": after_error})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if path is already taken
        cur.execute("SELECT session_id FROM session WHERE path = %s", (new_path,))
        existing_session = cur.fetchone()
        if existing_session:
            cur.close()
            conn.close()
            return jsonify(
                {"success": False, "message": f'Path "{new_path}" is already taken'}
            )

        # Check if TheSession.org ID is already used
        if thesession_id is not None:
            cur.execute(
                "SELECT session_id FROM session WHERE thesession_id = %s",
                (thesession_id,),
            )
            existing_thesession = cur.fetchone()
            if existing_thesession:
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "message": f"TheSession.org session {thesession_id} is already in the database",
                    }
                )

        # Insert new session with timezone
        timezone = data.get("timezone") or "America/Chicago"  # Default to Central Time
        # People-tracking flags (spec 039): default TRUE (all three checkboxes are
        # pre-checked on the create form), so a session is opt-OUT. Starters imply
        # attendance — turning attendance off forces starters off, matching the CHECK.
        show_people_list = bool(data.get("show_people_list", True))
        track_attendance = bool(data.get("track_attendance", True))
        track_set_starters = bool(data.get("track_set_starters", True)) and track_attendance
        cur.execute(
            """
            INSERT INTO session (
                thesession_id, name, path, location_name, location_phone, location_website,
                city, state, country, timezone, initiation_date, recurrence,
                session_type, active_buffer_minutes_before, active_buffer_minutes_after,
                show_people_list, track_attendance, track_set_starters,
                created_date, last_modified_date, created_by_user_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s
            ) RETURNING session_id
        """,
            (
                thesession_id,
                data["name"],
                new_path,
                data.get("location_name") or None,
                data.get("location_phone") or None,
                data.get("location_website") or None,
                data["city"],
                data["state"],
                data["country"],
                timezone,
                data.get("inception_date") or None,
                data.get("recurrence") or None,
                session_type,
                buffer_before,
                buffer_after,
                show_people_list,
                track_attendance,
                track_set_starters,
                get_current_user_id(),
            ),
        )

        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Failed to create session"})

        session_id = session_result[0]

        # Save the newly created session to history
        save_to_history(cur, "session", "INSERT", session_id, user_id=get_current_user_id())

        # Optionally add the creating user as a member of the session
        user_id = get_current_user_id()
        add_current_user = data.get("add_current_user", True)  # Default to True for backwards compatibility
        if add_current_user and user_id and hasattr(current_user, 'person_id') and current_user.person_id:
            role = data.get("add_current_user_role", "admin")  # Default to admin
            # Spec 034: whoever creates a session is by definition a confirmed member of it.
            # The only axis the caller still chooses is whether they're also an admin.
            is_admin = role == "admin"
            cur.execute(
                """
                INSERT INTO session_person
                    (session_id, person_id, relationship, confirmed, archived, is_admin, created_by_user_id)
                VALUES (%s, %s, 'member', TRUE, FALSE, %s, %s)
                """,
                (session_id, current_user.person_id, is_admin, user_id)
            )
            save_to_history(
                cur, "session_person", "INSERT", (session_id, current_user.person_id), user_id=user_id
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f'Session "{data["name"]}" created successfully!',
                "session_path": new_path,
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Failed to create session: {str(e)}"}
        )


@api_login_required
def add_tune_ajax(session_path, date):
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    tune_names_input = request.json.get("tune_name", "").strip()
    if not tune_names_input:
        return jsonify({"success": False, "message": "Please enter tune name(s)"})

    # Parse newline-separated sets, with comma-separated tune names within each set
    lines = [line.strip() for line in tune_names_input.split("\n") if line.strip()]

    if not lines:
        return jsonify({"success": False, "message": "Please enter tune name(s)"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id for this session_path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Check if the very first line starts with a delimiter
        first_line_starts_with_delimiter = lines[0].startswith((",", ";", "/"))

        # If first line starts with delimiter, we need to append to the existing last set
        if first_line_starts_with_delimiter:
            # Get the last tune to find the last set
            cur.execute(
                """
                SELECT session_instance_tune_id
                FROM session_instance_tune sit
                JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                WHERE si.session_id = %s AND si.date = %s
                ORDER BY sit.order_position DESC
                LIMIT 1
            """,
                (session_id, date),
            )

            last_tune_result = cur.fetchone()
            if last_tune_result:
                # There are existing tunes, so we can append to the last set
                # Parse all the tune names from all lines and add them to the existing last set
                all_tune_names = []
                for line in lines:
                    tune_names_in_line = [
                        normalize_quotes(name.strip())
                        for name in re.split("[,;/]", line)
                        if name.strip()
                    ]
                    all_tune_names.extend(tune_names_in_line)

                if all_tune_names:
                    # Use the add_tunes_to_set logic
                    total_tunes_added = 0
                    for tune_name in all_tune_names:
                        # Use the refactored tune matching function
                        tune_id, final_name, error_message = find_matching_tune(
                            cur, session_id, tune_name
                        )

                        if error_message:
                            cur.close()
                            conn.close()
                            return jsonify({"success": False, "message": error_message})

                        # Add tune to continue the existing set
                        insert_session_instance_tune(
                            cur,
                            session_id,
                            date,
                            tune_id,
                            None,
                            final_name if tune_id is None else None,
                            False,  # starts_set = False (continues existing set)
                        )
                        total_tunes_added += 1

                    conn.commit()
                    cur.close()
                    conn.close()

                    if total_tunes_added == 1:
                        message = "Tune added to existing set successfully!"
                    else:
                        message = f"{total_tunes_added} tunes added to existing set successfully!"

                    return jsonify({"success": True, "message": message})
            # If no existing tunes, fall through to normal processing (treat as if no delimiter)

        # Build sets structure: list of lists, where each inner list is tunes in a set
        tune_sets = []
        for line in lines:
            # Check if line starts with a delimiter (comma, semicolon, or slash)
            starts_with_delimiter = line.startswith((",", ";", "/"))

            # Split by comma, semicolon, or forward slash
            tune_names_in_set = [
                normalize_quotes(name.strip())
                for name in re.split("[,;/]", line)
                if name.strip()
            ]

            if tune_names_in_set:
                if starts_with_delimiter and tune_sets:
                    # Add to the previous set if line starts with delimiter and there's a previous set
                    tune_sets[-1].extend(tune_names_in_set)
                else:
                    # Create a new set
                    tune_sets.append(tune_names_in_set)

        if not tune_sets:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Please enter tune name(s)"})

        # Process each set of tunes
        total_tunes_added = 0

        for set_index, tune_names_in_set in enumerate(tune_sets):
            # Process each tune name in this set to determine tune_id or use as name-only
            tune_data = []  # List of (tune_id, name) tuples for this set

            for tune_name in tune_names_in_set:
                # Use the refactored tune matching function
                tune_id, final_name, error_message = find_matching_tune(
                    cur, session_id, tune_name
                )

                if error_message:
                    cur.close()
                    conn.close()
                    return jsonify({"success": False, "message": error_message})

                tune_data.append((tune_id, final_name))

            # Add all tunes in this set
            for i, (tune_id, name) in enumerate(tune_data):
                # First tune in each set starts a new set (a break is inserted before it
                # when the instance already has tunes); subsequent tunes continue the set.
                starts_set = i == 0

                # Insert tune with fractional indexing
                insert_session_instance_tune(
                    cur,
                    session_id,
                    date,
                    tune_id,
                    None,
                    name if tune_id is None else None,
                    starts_set,
                )
                total_tunes_added += 1

        conn.commit()
        cur.close()
        conn.close()

        if len(tune_sets) == 1 and len(tune_sets[0]) == 1:
            message = "Tune added successfully!"
        elif len(tune_sets) == 1:
            message = f"Set of {len(tune_sets[0])} tunes added successfully!"
        else:
            message = f"{total_tunes_added} tunes in {len(tune_sets)} sets added successfully!"

        return jsonify({"success": True, "message": message})

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Failed to add tune(s): {str(e)}"}
        )


@api_login_required
def delete_tune_ajax(session_instance_tune_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the tune info for the history record and the response message.
        cur.execute(
            """
            SELECT
                COALESCE(sit.name, st.alias, t.name) AS tune_name
            FROM session_instance_tune sit
            LEFT JOIN tune t ON sit.tune_id = t.tune_id
            LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                SELECT si.session_id
                FROM session_instance si
                WHERE si.session_instance_id = sit.session_instance_id
            )
            WHERE sit.session_instance_tune_id = %s
        """,
            (session_instance_tune_id,),
        )

        tune_info = cur.fetchone()
        if not tune_info:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found"})

        (tune_name,) = tune_info

        # One-way lock (spec 024 beta): refuse if the live editor owns this instance.
        cur.execute(
            "SELECT session_instance_id FROM session_instance_tune WHERE session_instance_tune_id = %s",
            (session_instance_tune_id,),
        )
        _sii_row = cur.fetchone()
        if _sii_row and instance_logging_locked(cur, _sii_row[0]):
            cur.close(); conn.close()
            return jsonify({"success": False, "locked": True, "message": LEGACY_LOCKED_MSG}), 409

        # Save to history before making changes
        audit_user_id = get_current_user_id()
        save_to_history(
            cur, "session_instance_tune", "DELETE", session_instance_tune_id, user_id=audit_user_id
        )

        # Set boundaries are explicit break records (spec 023), so deleting a tune no longer
        # mutates a neighbour's flag. Any break left adjacent to another break (or at the
        # start/end) is harmless -- segment_records_into_sets ignores it, and the next bulk
        # save reconciles breaks fully.

        # Delete the tune by ID (reliable regardless of ordering scheme)
        cur.execute(
            """
            DELETE FROM session_instance_tune
            WHERE session_instance_tune_id = %s
        """,
            (session_instance_tune_id,),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f"{tune_name} deleted from the set.",
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Failed to delete tune: {str(e)}"}
        )


class TuneImportError(Exception):
    """thesession.org import failed (404 / timeout / bad data). Carries an HTTP status so
    API callers can map it to a response code."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.message = message
        self.status = status


def _fetch_thesession_tune(tune_id):
    """GET tune #tune_id from thesession.org and return the validated JSON dict.

    Raises TuneImportError on 404 / non-200 / timeout / invalid payload. Shared by the legacy
    link_tune_ajax import and the live logger's in-transaction import (spec 026)."""
    try:
        api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
        response = requests.get(api_url, timeout=10)
    except requests.exceptions.Timeout:
        raise TuneImportError("Timeout connecting to thesession.org", 504)
    except requests.exceptions.RequestException as e:
        raise TuneImportError(f"Error connecting to thesession.org: {e}", 502)

    if response.status_code == 404:
        raise TuneImportError(f"Tune #{tune_id} not found on thesession.org", 404)
    elif response.status_code != 200:
        raise TuneImportError(
            f"Failed to fetch tune data from thesession.org (status: {response.status_code})",
            502,
        )

    try:
        data = response.json()
    except ValueError:
        raise TuneImportError("Invalid tune data received from thesession.org", 502)

    if "name" not in data or "type" not in data:
        raise TuneImportError("Invalid tune data received from thesession.org", 502)

    return data


def _import_tune_from_thesession(cur, tune_id, user_id):
    """Fetch tune #tune_id from thesession.org, INSERT the local `tune` row, and cache its
    default setting + notation PNGs. Returns (name, tune_type).

    The caller owns the transaction/commit and any session_tune / session_instance_tune
    writes. Raises TuneImportError on 404 / non-200 / timeout / invalid payload. Used by the
    legacy link_tune_ajax path, whose connection semantics let cache_default_tune_setting
    (a separate connection) see the tune row. The live logger uses its own in-transaction
    importer instead (see live_logging_routes._import_tune_for_live)."""
    data = _fetch_thesession_tune(tune_id)

    tune_name_from_api = data["name"]
    tune_type = data["type"].title()  # Convert to title case
    tunebook_count = data.get("tunebooks", 0)  # Default to 0 if not present

    # Insert the new tune into the tune table.
    cur.execute(
        """
        INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date, created_by_user_id)
        VALUES (%s, %s, %s, %s, CURRENT_DATE, %s)
    """,
        (tune_id, tune_name_from_api, tune_type, tunebook_count, user_id),
    )
    save_to_history(cur, "tune", "INSERT", tune_id, user_id=user_id)

    # Cache the default setting + generate images (reuse the data we already fetched).
    cache_default_tune_setting(tune_id, data, user_id, sync=True)

    return tune_name_from_api, tune_type


@api_login_required
def link_tune_ajax(session_path, date_or_id):
    """
    Link a tune to a thesession.org tune ID.
    Accepts either date (YYYY-MM-DD) or session_instance_id as the second URL parameter.
    """
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    tune_input = request.json.get("tune_id", "").strip()
    tune_name = normalize_quotes(request.json.get("tune_name", "").strip())
    session_instance_tune_id = request.json.get("session_instance_tune_id")

    if not tune_input or not tune_name or session_instance_tune_id is None:
        return jsonify({"success": False, "message": "Missing required parameters"})

    # Parse tune ID and setting ID from input
    # Check if it's a URL with setting
    url_pattern = r".*thesession\.org\/tunes\/(\d+)(?:#setting(\d+))?"
    url_match = re.search(url_pattern, tune_input)

    if url_match:
        tune_id = url_match.group(1)
        setting_id = int(url_match.group(2)) if url_match.group(2) else None
    elif re.match(r"^\d+$", tune_input):
        # Just a tune ID number
        tune_id = tune_input
        setting_id = None
    else:
        return jsonify({"success": False, "message": "Invalid tune ID or URL format"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id for this session_path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Get session instance ID (works with both date and ID)
        session_instance_id = get_session_instance_id(cur, session_id, date_or_id)
        if not session_instance_id:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        # A merged-away id remaps to the canonical tune BEFORE any other processing
        # (spec 030): a stale link means the merged tune, so proceed rather than reject.
        remapped_from = None
        cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
        tune_redirect_check = cur.fetchone()
        if tune_redirect_check and tune_redirect_check[0] is not None:
            remapped_from = int(tune_id)
            tune_id = tune_redirect_check[0]

        # Check if tune_id is already in session_tune for this session
        cur.execute(
            """
            SELECT tune_id FROM session_tune
            WHERE session_id = %s AND tune_id = %s
        """,
            (session_id, tune_id),
        )
        session_tune_exists = cur.fetchone()

        # Track tune metadata to return to frontend
        tune_name_canonical = None
        tune_type_result = None

        if session_tune_exists:
            # Get tune metadata from tune table
            cur.execute(
                "SELECT name, tune_type FROM tune WHERE tune_id = %s",
                (tune_id,),
            )
            tune_meta = cur.fetchone()
            if tune_meta:
                tune_name_canonical = tune_meta[0]
                tune_type_result = tune_meta[1]

            # Save history before update
            save_to_history(cur, "session_instance_tune", "UPDATE", session_instance_tune_id, user_id=get_current_user_id())

            # Tune already in session_tune, just update session_instance_tune.
            # Use setting_id as setting_override if provided. name is override-only:
            # keep the row's typed name only when it differs from the display
            # fallbacks (the other branches preserve it via session_tune.alias, but
            # this session already has its own row — the per-row slot is the only home).
            cur.execute(
                """
                UPDATE session_instance_tune
                SET tune_id = %s, name = %s, setting_override = %s, last_modified_user_id = %s
                WHERE session_instance_tune_id = %s
            """,
                (tune_id, normalize_override_name(cur, session_id, tune_id, tune_name),
                 setting_id, get_current_user_id(), session_instance_tune_id),
            )

            setting_msg = f" with setting #{setting_id}" if setting_id else ""
            message = f'Linked "{tune_name}" to existing tune in session{setting_msg}'
        else:
            # Check if tune exists in tune table (redirect already checked above)
            cur.execute("SELECT name, tune_type FROM tune WHERE tune_id = %s", (tune_id,))
            tune_exists = cur.fetchone()

            if tune_exists:
                # Extract tune metadata
                tune_name_canonical = tune_exists[0]
                tune_type_result = tune_exists[1]

                # Add to session_tune with alias and setting_id
                cur.execute(
                    """
                    INSERT INTO session_tune (session_id, tune_id, alias, setting_id, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (session_id, tune_id, tune_name, setting_id, get_current_user_id()),
                )

                # Save the newly inserted record to history
                save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id), user_id=get_current_user_id())

                # Save history before update
                save_to_history(cur, "session_instance_tune", "UPDATE", session_instance_tune_id, user_id=get_current_user_id())

                # Update session_instance_tune
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET tune_id = %s, name = NULL, last_modified_user_id = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (tune_id, get_current_user_id(), session_instance_tune_id),
                )

                setting_msg = f" with setting #{setting_id}" if setting_id else ""
                message = f'Added "{tune_name}" to session and linked{setting_msg}'
            else:
                # Tune doesn't exist in our database — import it from thesession.org.
                try:
                    tune_name_from_api, tune_type = _import_tune_from_thesession(
                        cur, tune_id, get_current_user_id()
                    )
                except TuneImportError as e:
                    cur.close()
                    conn.close()
                    return jsonify({"success": False, "message": e.message})

                # Store for response
                tune_name_canonical = tune_name_from_api
                tune_type_result = tune_type

                # Determine if we need to use an alias
                alias = tune_name if tune_name != tune_name_from_api else None

                # Add to session_tune with alias and setting_id
                cur.execute(
                    """
                    INSERT INTO session_tune (session_id, tune_id, alias, setting_id, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (session_id, tune_id, alias, setting_id, get_current_user_id()),
                )

                # Save the newly inserted session_tune to history
                save_to_history(
                    cur, "session_tune", "INSERT", (session_id, tune_id), user_id=get_current_user_id()
                )

                # Update session_instance_tune
                save_to_history(cur, "session_instance_tune", "UPDATE", session_instance_tune_id, user_id=get_current_user_id())
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET tune_id = %s, name = NULL, last_modified_user_id = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (tune_id, get_current_user_id(), session_instance_tune_id),
                )

                setting_msg = f" with setting #{setting_id}" if setting_id else ""
                message = f'Fetched "{tune_name_from_api}" from thesession.org and added to session{setting_msg}'

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": message,
            "tune_id": int(tune_id),
            "tune_name": tune_name_canonical,
            "tune_type": tune_type_result,
            "remapped_from": remapped_from,
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to link tune: {str(e)}"})


@api_login_required  # zero callers found in templates/, static/js/, frontend/src/ — gated by default
def get_session_tunes_ajax(session_path, date):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session instance ID
        cur.execute(
            """
            SELECT si.session_instance_id
            FROM session_instance si
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s
        """,
            (session_path, date),
        )
        session_instance = cur.fetchone()

        if not session_instance:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        session_instance_id = session_instance[0]

        # Get tunes played in this session instance
        cur.execute(
            """
            SELECT
                sit.record_type,
                sit.tune_id,
                COALESCE(sit.name, st.alias, t.name) AS tune_name,
                COALESCE(sit.setting_override, st.setting_id) AS setting,
                t.tune_type,
                sit.order_position
            FROM session_instance_tune sit
            LEFT JOIN tune t ON sit.tune_id = t.tune_id
            LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                SELECT si2.session_id
                FROM session_instance si2
                WHERE si2.session_instance_id = %s
            )
            WHERE sit.session_instance_id = %s
            ORDER BY sit.order_position
        """,
            (session_instance_id, session_instance_id),
        )

        tunes = cur.fetchall()
        cur.close()
        conn.close()

        # Group tunes into sets by break records, then rebuild each tune tuple with a
        # synthesized continues_set at index 0 to preserve the response shape.
        sets = []
        for tune_set in segment_records_into_sets(tunes, type_index=0):
            sets.append(
                [
                    [tune_idx > 0, row[1], row[2], row[3], row[4], row[5]]
                    for tune_idx, row in enumerate(tune_set)
                ]
            )

        return jsonify({"success": True, "tune_sets": sets})

    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to get tunes: {str(e)}"}), 500


def get_session_people_list(session_path):
    """This session's roster (spec 034).

    GET /api/sessions/<session_path>/people

    Gated on people-visibility -- is_admin OR confirmed -- NOT on mere membership. Joining
    a session does not hand you its roster; the session has to vouch for you first.

    Rows come from the one shared loader (serializers.load_session_people), ordered by
    computed regular-ness. Archived people ARE included; hiding them is the client's job,
    because archived means "not in the default list", never "unfindable".
    """
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    from serializers import load_session_people

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id = session_result[0]

        user_person_id = getattr(current_user, "person_id", None)
        if not user_person_id:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "User not linked to person"}), 403

        if not can_view_session_people(cur, session_id, user_person_id):
            cur.close()
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "message": "A session admin needs to confirm you before you can see this session's people.",
                }
            ), 403

        cur.close()
        people = load_session_people(conn, session_id)
        conn.close()

        return jsonify({"success": True, "people": people})

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to get people: {str(e)}"}), 500


def get_session_person_detail(session_path, person_id):
    """
    Get detailed information about a person in a session, including attendance history.

    GET /api/sessions/<session_path>/people/<person_id>

    Returns:
    {
        "success": true,
        "person": {
            "person_id": int,
            "first_name": str,
            "last_name": str,
            "city": str or null,
            "state": str or null,
            "country": str or null,
            "thesession_user_id": int or null,
            "has_user_account": bool,
            "instruments": [str],
            "attended_instances": [
                {
                    "date": "YYYY-MM-DD",
                    "session_instance_id": int
                }
            ]
        }
    }
    """
    # Check authentication
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID from path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()

        if not session_result:
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id = session_result[0]

        # Verify current user is a member of this session
        user_person_id = getattr(current_user, 'person_id', None)
        if not user_person_id:
            return jsonify({"success": False, "message": "User not linked to person"}), 403

        cur.execute(
            "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, user_person_id)
        )
        if not cur.fetchone():
            return jsonify({"success": False, "message": "Not a member of this session"}), 403

        # Fetch person details with attendance
        cur.execute(
            """
            SELECT p.person_id, p.first_name, p.last_name, p.city, p.state, p.country, p.thesession_user_id,
                   CASE WHEN u.user_id IS NOT NULL THEN true ELSE false END as has_user_account,
                   COALESCE(
                       array_agg(DISTINCT pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                       '{}'::text[]
                   ) as instruments,
                   COALESCE(
                       json_agg(
                           json_build_object('date', si.date, 'session_instance_id', si.session_instance_id)
                           ORDER BY si.date DESC
                       ) FILTER (WHERE sip.attendance = 'yes' AND si.session_instance_id IS NOT NULL),
                       '[]'::json
                   ) as attended_instances
            FROM person p
            LEFT JOIN user_account u ON p.person_id = u.person_id
            LEFT JOIN person_instrument pi ON p.person_id = pi.person_id
            LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id
            LEFT JOIN session_instance si ON sip.session_instance_id = si.session_instance_id AND si.session_id = %s
            WHERE p.person_id = %s
            GROUP BY p.person_id, p.first_name, p.last_name, p.city, p.state, p.country, p.thesession_user_id, u.user_id
            """,
            (session_id, person_id)
        )

        person_row = cur.fetchone()

        if not person_row:
            return jsonify({"success": False, "message": "Person not found"}), 404

        person = {
            'person_id': person_row[0],
            'first_name': person_row[1],
            'last_name': person_row[2],
            'city': person_row[3],
            'state': person_row[4],
            'country': person_row[5],
            'thesession_user_id': person_row[6],
            'has_user_account': person_row[7],
            'instruments': person_row[8] if person_row[8] else [],
            'attended_instances': person_row[9] if person_row[9] else []
        }

        cur.close()
        conn.close()

        return jsonify({"success": True, "person": person})

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to get person details: {str(e)}"}), 500


def add_person_to_session_people_tab(session_path):
    """Add a person to this session's roster (spec 034).

    POST /api/sessions/<session_path>/people/add
    Body: {first_name, last_name, email?, instruments?[], thesession_user_id?, relationship?}

    Two rules worth stating, because both changed in 034:

    1. DEDUPE ON EMAIL ONLY. This used to match an existing person by case-insensitive
       first+last name, silently reusing that row. That was cross-session person discovery
       through the back door (type a name, learn whether they exist) and it merged two
       different John Smiths into one human. Email is now the sole identity key; a name
       collision creates a genuinely new person. (The admin person-merge action —
       POST /api/admin/people/merge — exists for cleanup.)

    2. CONFIRMED IS A VOUCH, so only a session admin can grant it. A confirmed non-admin
       member may still add people -- they just land unconfirmed, for an admin to confirm.
       Otherwise a confirmed member could confirm their friend, and the gate would mean
       nothing.

    Roster-adds are always members; `visitor` arises from check-in, not from here.
    """
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip() if data.get('email') else None
        instruments = data.get('instruments', [])
        thesession_user_id = data.get('thesession_user_id')
        relationship = data.get('relationship', 'member')
        if relationship not in ('member', 'visitor'):
            return jsonify({"success": False, "message": "relationship must be 'member' or 'visitor'"}), 400

        if not first_name or not last_name:
            return jsonify({"success": False, "message": "First name and last name are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "message": "Session not found"}), 404
        session_id = session_result[0]

        user_person_id = getattr(current_user, 'person_id', None)
        if not user_person_id:
            return jsonify({"success": False, "message": "User not linked to person"}), 403

        if not can_view_session_people(cur, session_id, user_person_id):
            return jsonify({"success": False, "message": "Not allowed to manage this session's people"}), 403

        # The adder vouches only if they are an admin of this session.
        confirmed = is_session_admin_for(cur, session_id, user_person_id)

        person_id = None
        if email:
            # Match on either person.email (accountless) or the account email —
            # person.email is nulled once connected, so a connected person must
            # still be found by user_account.user_email to avoid a duplicate.
            cur.execute(
                """
                SELECT p.person_id, p.active
                FROM person p
                LEFT JOIN user_account ua ON ua.person_id = p.person_id
                WHERE LOWER(p.email) = LOWER(%s) OR LOWER(ua.user_email) = LOWER(%s)
                LIMIT 1
                """,
                (email, email),
            )
            existing = cur.fetchone()
            if existing:
                person_id, active = existing
                if not active:
                    return jsonify({
                        "success": False,
                        "message": f"{first_name} {last_name} is deactivated and cannot be added to sessions",
                    }), 400
                cur.execute(
                    "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
                    (session_id, person_id),
                )
                if cur.fetchone():
                    return jsonify({
                        "success": False,
                        "message": f"{first_name} {last_name} is already in this session",
                    }), 400

        if person_id is None:
            cur.execute(
                """
                INSERT INTO person (first_name, last_name, email, thesession_user_id, created_by_user_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING person_id
                """,
                (first_name, last_name, email, thesession_user_id, get_current_user_id()),
            )
            person_id = cur.fetchone()[0]

            for instrument in normalize_instruments(instruments):
                cur.execute(
                    """
                    INSERT INTO person_instrument (person_id, instrument, created_by_user_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (person_id, instrument) DO NOTHING
                    """,
                    (person_id, instrument, get_current_user_id()),
                )

        cur.execute(
            """
            INSERT INTO session_person
                (session_id, person_id, relationship, confirmed, archived, is_admin, created_by_user_id)
            VALUES (%s, %s, %s, %s, FALSE, FALSE, %s)
            """,
            (session_id, person_id, relationship, confirmed, get_current_user_id()),
        )
        save_to_history(cur, "session_person", "INSERT", (session_id, person_id),
                        user_id=get_current_user_id())

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "person_id": person_id,
            "confirmed": confirmed,
            "message": f"{first_name} {last_name} added to session",
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to add person: {str(e)}"}), 500


@api_login_required
def move_set_ajax(session_path, date):
    data = request.get_json()
    session_instance_tune_id = data.get("session_instance_tune_id")
    direction = data.get("direction")  # 'up' or 'down'

    if not session_instance_tune_id or not direction or direction not in ["up", "down"]:
        return jsonify({"success": False, "message": "Invalid parameters"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session instance ID
        cur.execute(
            """
            SELECT si.session_instance_id
            FROM session_instance si
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s
        """,
            (session_path, date),
        )
        session_instance = cur.fetchone()

        if not session_instance:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id = session_instance[0]

        # Get all records (tunes + breaks) ordered by order_position
        cur.execute(
            """
            SELECT record_type, session_instance_tune_id, order_position
            FROM session_instance_tune
            WHERE session_instance_id = %s
            ORDER BY order_position
        """,
            (session_instance_id,),
        )

        all_records = cur.fetchall()
        if not all_records:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "No tunes found"})

        # Group tunes into sets to identify set boundaries. Break records delimit sets and
        # are dropped here; they are re-derived after the move (positions change).
        # Each set entry is a list of (record_type, session_instance_tune_id, order_position).
        sets = segment_records_into_sets(all_records, type_index=0)

        # Find which set the target tune belongs to
        target_set_index = -1
        for set_index, tune_set in enumerate(sets):
            if any(tune[1] == session_instance_tune_id for tune in tune_set):
                target_set_index = set_index
                break

        if target_set_index == -1:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune set not found"})

        # Check if move is possible
        if direction == "up" and target_set_index == 0:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Cannot move first set up"})

        if direction == "down" and target_set_index == len(sets) - 1:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Cannot move last set down"})

        # Save to history before making changes - only for the moving set
        audit_user_id = get_current_user_id()
        target_set = sets[target_set_index]
        for tune in target_set:
            save_to_history(
                cur, "session_instance_tune", "UPDATE", tune[1], user_id=audit_user_id
            )

        # Perform the move using fractional indexing
        # Only the moving set gets new positions; adjacent sets stay in place
        if direction == "up":
            # Move set up - generate positions before the previous set
            prev_set = sets[target_set_index - 1]

            # Position before prev_set (None if prev_set is first)
            if target_set_index - 1 > 0:
                before_prev_set = sets[target_set_index - 2]
                before_position = before_prev_set[-1][2]  # Last tune of set before prev
            else:
                before_position = None

            # Position of first tune in prev_set
            after_position = prev_set[0][2]

            # Generate new positions for each tune in target_set
            current_pos = before_position
            for i, tune in enumerate(target_set):
                if i == len(target_set) - 1:
                    # Last tune in set: position between current and after_position
                    new_position = generate_position_between(current_pos, after_position)
                else:
                    # Generate position, leaving room for remaining tunes
                    new_position = generate_position_between(current_pos, after_position)
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET order_position = %s, last_modified_user_id = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_position, audit_user_id, tune[1]),
                )
                current_pos = new_position

        else:  # direction == 'down'
            # Move set down - generate positions after the next set
            next_set = sets[target_set_index + 1]

            # Position of last tune in next_set
            before_position = next_set[-1][2]

            # Position after next_set (None if next_set is last)
            if target_set_index + 1 < len(sets) - 1:
                after_next_set = sets[target_set_index + 2]
                after_position = after_next_set[0][2]  # First tune of set after next
            else:
                after_position = None

            # Generate new positions for each tune in target_set
            current_pos = before_position
            for tune in target_set:
                new_position = generate_position_between(current_pos, after_position)
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET order_position = %s, last_modified_user_id = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_position, audit_user_id, tune[1]),
                )
                current_pos = new_position

        # Reposition break records to match the new set order. Compute the new ordering of
        # sets, look up each tune's final position, and re-derive one break per set.
        new_order = list(sets)
        if direction == "up":
            new_order[target_set_index - 1], new_order[target_set_index] = (
                new_order[target_set_index],
                new_order[target_set_index - 1],
            )
        else:
            new_order[target_set_index], new_order[target_set_index + 1] = (
                new_order[target_set_index + 1],
                new_order[target_set_index],
            )

        cur.execute(
            """
            SELECT session_instance_tune_id, order_position
            FROM session_instance_tune
            WHERE session_instance_id = %s AND record_type = 'tune'
            """,
            (session_instance_id,),
        )
        position_by_id = {row[0]: row[1] for row in cur.fetchall()}
        set_position_lists = [
            sorted(position_by_id[tune[1]] for tune in tune_set) for tune_set in new_order
        ]
        reconcile_break_records(cur, session_instance_id, set_position_lists, audit_user_id)

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"success": True, "message": f"Set moved {direction} successfully"}
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to move set: {str(e)}"})


@api_login_required
def move_tune_ajax(session_path, date):
    data = request.get_json()
    session_instance_tune_id = data.get("session_instance_tune_id")
    direction = data.get("direction")  # 'left' or 'right'

    if not session_instance_tune_id or not direction or direction not in ["left", "right"]:
        return jsonify({"success": False, "message": "Invalid parameters"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session instance ID
        cur.execute(
            """
            SELECT si.session_instance_id
            FROM session_instance si
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s
        """,
            (session_path, date),
        )
        session_instance = cur.fetchone()

        if not session_instance:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id = session_instance[0]

        # Get all records (tunes + breaks) ordered by order_position. A tune moves within
        # its set by swapping positions with the adjacent tune; an adjacent break record
        # marks a set boundary the tune may not cross (spec 023).
        cur.execute(
            """
            SELECT record_type, session_instance_tune_id, order_position
            FROM session_instance_tune
            WHERE session_instance_id = %s
            ORDER BY order_position
        """,
            (session_instance_id,),
        )

        all_records = cur.fetchall()

        # Find the target tune by session_instance_tune_id
        target_tune_index = next(
            (i for i, rec in enumerate(all_records) if rec[1] == session_instance_tune_id), -1
        )
        if target_tune_index == -1:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found"})

        target_tune = all_records[target_tune_index]

        if direction == "left":
            # Move tune left within its set
            if target_tune_index == 0:
                cur.close()
                conn.close()
                return jsonify(
                    {"success": False, "message": "Cannot move first tune left"}
                )

            prev_tune = all_records[target_tune_index - 1]

            # A break to the left means we're at the start of the set.
            if prev_tune[0] == "break":
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "message": "Cannot move tune left across set boundary",
                    }
                )

            # Save to history
            audit_user_id = get_current_user_id()
            save_to_history(
                cur, "session_instance_tune", "UPDATE", target_tune[1], user_id=audit_user_id
            )
            save_to_history(
                cur, "session_instance_tune", "UPDATE", prev_tune[1], user_id=audit_user_id
            )

            # Swap order positions with the previous tune
            cur.execute(
                """
                UPDATE session_instance_tune
                SET order_position = %s, last_modified_user_id = %s
                WHERE session_instance_tune_id = %s
            """,
                (prev_tune[2], audit_user_id, target_tune[1]),
            )

            cur.execute(
                """
                UPDATE session_instance_tune
                SET order_position = %s, last_modified_user_id = %s
                WHERE session_instance_tune_id = %s
            """,
                (target_tune[2], audit_user_id, prev_tune[1]),
            )

        else:  # direction == 'right'
            # Move tune right within its set
            if target_tune_index == len(all_records) - 1:
                cur.close()
                conn.close()
                return jsonify(
                    {"success": False, "message": "Cannot move last tune right"}
                )

            next_tune = all_records[target_tune_index + 1]

            # A break to the right means we're at the end of the set.
            if next_tune[0] == "break":
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "message": "Cannot move tune right across set boundary",
                    }
                )

            # Save to history
            audit_user_id = get_current_user_id()
            save_to_history(
                cur, "session_instance_tune", "UPDATE", target_tune[1], user_id=audit_user_id
            )
            save_to_history(
                cur, "session_instance_tune", "UPDATE", next_tune[1], user_id=audit_user_id
            )

            # Swap order positions with the next tune
            cur.execute(
                """
                UPDATE session_instance_tune
                SET order_position = %s, last_modified_user_id = %s
                WHERE session_instance_tune_id = %s
            """,
                (next_tune[2], audit_user_id, target_tune[1]),
            )

            cur.execute(
                """
                UPDATE session_instance_tune
                SET order_position = %s, last_modified_user_id = %s
                WHERE session_instance_tune_id = %s
            """,
                (target_tune[2], audit_user_id, next_tune[1]),
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"success": True, "message": f"Tune moved {direction} successfully"}
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to move tune: {str(e)}"})


@api_login_required
def add_tunes_to_set_ajax(session_path, date):
    data = request.get_json()
    tune_names_input = data.get("tune_names", "").strip()
    reference_session_instance_tune_id = data.get("reference_session_instance_tune_id")

    if not tune_names_input or reference_session_instance_tune_id is None:
        return jsonify({"success": False, "message": "Missing required parameters"})

    # Parse comma-separated tune names
    tune_names = [
        normalize_quotes(name.strip())
        for name in re.split("[,;/]", tune_names_input)
        if name.strip()
    ]

    if not tune_names:
        return jsonify({"success": False, "message": "Please enter tune name(s)"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id for this session_path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        total_tunes_added = 0
        for tune_name in tune_names:
            # Use the refactored tune matching function
            tune_id, final_name, error_message = find_matching_tune(
                cur, session_id, tune_name
            )

            if error_message:
                cur.close()
                conn.close()
                return jsonify({"success": False, "message": error_message})

            # Add tune to continue the set (starts_set = False)
            insert_session_instance_tune(
                cur,
                session_id,
                date,
                tune_id,
                None,  # setting_id
                final_name if tune_id is None else None,
                False,  # starts_set
            )
            total_tunes_added += 1

        conn.commit()
        cur.close()
        conn.close()

        if total_tunes_added == 1:
            message = "Tune added to set successfully!"
        else:
            message = f"{total_tunes_added} tunes added to set successfully!"

        return jsonify({"success": True, "message": message})

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Failed to add tunes to set: {str(e)}"}
        )


@api_login_required
def edit_tune_ajax(session_path, date):
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    session_instance_tune_id = request.json.get("session_instance_tune_id")
    new_name = normalize_quotes(request.json.get("new_name", "").strip())
    original_name = request.json.get("original_name", "").strip()
    tune_id = request.json.get("tune_id")
    setting_id = request.json.get("setting_id")
    key_override = (
        request.json.get("key_override", "").strip()
        if request.json.get("key_override")
        else None
    )

    if session_instance_tune_id is None or not new_name:
        return jsonify({"success": False, "message": "Missing required parameters"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id for this session_path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Get session instance ID and current tune info
        cur.execute(
            """
            SELECT si.session_instance_id, sit.session_instance_tune_id, sit.tune_id, sit.name
            FROM session_instance si
            JOIN session_instance_tune sit ON si.session_instance_id = sit.session_instance_id
            WHERE sit.session_instance_tune_id = %s
        """,
            (session_instance_tune_id,),
        )

        result = cur.fetchone()
        if not result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found"})

        (
            session_instance_id,
            session_instance_tune_id,
            current_tune_id,
            current_name,
        ) = result

        # Save to history before making changes
        save_to_history(
            cur, "session_instance_tune", "UPDATE", session_instance_tune_id, user_id=get_current_user_id()
        )

        if current_tune_id:
            # This is a linked tune - update as name override or potentially update alias
            if tune_id and current_tune_id == int(tune_id):
                # Same tune - update name override and setting override
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET name = %s, setting_override = %s, key_override = %s, last_modified_user_id = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (
                        new_name if new_name != original_name else None,
                        setting_id,
                        key_override,
                        get_current_user_id(),
                        session_instance_tune_id,
                    ),
                )

                message = f'Updated tune display name to "{new_name}"'
                if setting_id:
                    message += f" with setting #{setting_id}"
            else:
                # Convert to name-only tune
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET tune_id = NULL, name = %s, setting_override = NULL, key_override = %s, last_modified_user_id = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_name, key_override, get_current_user_id(), session_instance_tune_id),
                )

                message = f'Converted to unlinked tune: "{new_name}"'
        else:
            # This is a name-only tune - update the name and try to link it
            # First, try to find a matching tune
            tune_id_match, final_name, error_message = find_matching_tune(
                cur, session_id, new_name
            )

            if tune_id_match and not error_message:
                # Found a match - link the tune
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET tune_id = %s, name = NULL, key_override = %s, last_modified_user_id = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (tune_id_match, key_override, get_current_user_id(), session_instance_tune_id),
                )

                message = f'Linked tune to "{final_name}"'

                conn.commit()
                cur.close()
                conn.close()

                return jsonify(
                    {
                        "success": True,
                        "message": message,
                        "linked": True,
                        "tune_id": tune_id_match,
                        "final_name": final_name,
                    }
                )
            else:
                # No match or multiple matches - just update the name
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET name = %s, key_override = %s, last_modified_user_id = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_name, key_override, get_current_user_id(), session_instance_tune_id),
                )

                if error_message:
                    message = f'Updated to "{new_name}" - {error_message}'
                else:
                    message = f'Updated tune name to "{new_name}"'

                conn.commit()
                cur.close()
                conn.close()

                return jsonify({"success": True, "message": message, "linked": False})

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": message})

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to edit tune: {str(e)}"})


def get_session_players_ajax(session_path):
    """Get all players associated with a session"""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    # Check if current user is a system admin or session admin
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        is_system_admin = user_row and user_row[0]

        # Get session ID first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"error": "Session not found"}), 404

        session_id = session_result[0]

        # If not system admin, check if they're a session admin
        if not is_system_admin:
            cur.execute(
                """SELECT sp.is_admin FROM session_person sp
                   WHERE sp.session_id = %s AND sp.person_id = %s""",
                (session_id, current_user.person_id)
            )
            admin_row = cur.fetchone()
            is_session_admin = admin_row and admin_row[0]
            if not is_session_admin:
                return jsonify({"success": False, "message": "Insufficient permissions"}), 403

        # Get session players with person details and attendance stats
        cur.execute(
            """
            SELECT
                sp.session_person_id,
                sp.person_id,
                p.first_name,
                p.last_name,
                p.email,
                sp.relationship,
                sp.is_admin,
                sp.gets_email_reminder,
                sp.gets_email_followup,
                u.username,
                u.is_system_admin,
                COALESCE(person_session_count.attendance_count, 0) as attendance_count,
                person_session_count.last_attended,
                sp.confirmed,
                sp.archived
            FROM session_person sp
            INNER JOIN person p ON sp.person_id = p.person_id
            LEFT OUTER JOIN user_account u ON p.person_id = u.person_id
            LEFT OUTER JOIN (
                SELECT
                    sip.person_id,
                    si.session_id,
                    COUNT(*) as attendance_count,
                    MAX(si.date) as last_attended
                FROM session_instance si
                INNER JOIN session_instance_person sip ON si.session_instance_id = sip.session_instance_id
                WHERE si.session_id = %s AND sip.attendance = 'yes'
                GROUP BY sip.person_id, si.session_id
            ) person_session_count ON p.person_id = person_session_count.person_id
            WHERE sp.session_id = %s
            -- Spec 034: "regulars first" is now computed from attendance, not a stored flag.
            ORDER BY sp.archived, COALESCE(person_session_count.attendance_count, 0) DESC,
                     p.last_name, p.first_name
        """,
            (session_id, session_id),
        )

        players = []
        for row in cur.fetchall():
            players.append(
                {
                    "session_person_id": row[0],
                    "person_id": row[1],
                    "name": f"{row[2]} {row[3]}",
                    "email": row[4] or "",
                    "relationship": row[5],
                    "is_admin": row[6],
                    "gets_email_reminder": row[7],
                    "gets_email_followup": row[8],
                    "username": row[9] or "",
                    "is_system_admin": row[10] or False,
                    "attendance_count": row[11] or 0,
                    "last_attended": row[12].isoformat() if row[12] else None,
                    "confirmed": row[13],
                    "archived": row[14],
                }
            )

        cur.close()
        conn.close()

        return jsonify({"players": players})

    except Exception as e:
        return jsonify({"error": f"Failed to get session members: {str(e)}"}), 500


@public_api  # serves the session detail Logs tab, which is public for logged-out viewers
def get_session_logs_ajax(session_path):
    """Get session instance logs with tune counts"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"error": "Session not found"}), 404

        session_id = session_result[0]

        # Get session instances with tune counts and attendance counts
        cur.execute(
            """
            SELECT
                si.session_instance_id,
                si.date,
                si.start_time,
                si.end_time,
                si.is_cancelled,
                si.comments,
                COUNT(DISTINCT sit.session_instance_tune_id) as tune_count,
                COUNT(DISTINCT sip.session_instance_person_id) as attendance_count
            FROM session_instance si
            LEFT JOIN session_instance_tune sit ON si.session_instance_id = sit.session_instance_id
                AND sit.record_type = 'tune'
            LEFT JOIN session_instance_person sip ON si.session_instance_id = sip.session_instance_id
                AND sip.attendance = 'yes'
            WHERE si.session_id = %s
            GROUP BY si.session_instance_id, si.date, si.start_time, si.end_time,
                     si.is_cancelled, si.comments
            ORDER BY si.date DESC
        """,
            (session_id,),
        )

        logs = []
        for row in cur.fetchall():
            logs.append(
                {
                    "session_instance_id": row[0],
                    "date": row[1].isoformat(),
                    "start_time": row[2].strftime("%H:%M") if row[2] else None,
                    "end_time": row[3].strftime("%H:%M") if row[3] else None,
                    "is_cancelled": row[4],
                    "comments": row[5] or "",
                    "tune_count": row[6] or 0,
                    "attendance_count": row[7] or 0,
                }
            )

        cur.close()
        conn.close()

        return jsonify({"logs": logs})

    except Exception as e:
        return jsonify({"error": f"Failed to get session logs: {str(e)}"}), 500


def get_session_tunes_grid_ajax(session_path):
    """Get all tunes played at a session with statistics for the admin tunes grid"""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401

    # Check if current user is a system admin or session admin
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        is_system_admin = user_row and user_row[0]

        # Get session ID first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "error": "Session not found"}), 404

        session_id = session_result[0]

        # If not system admin, check if they're a session admin
        if not is_system_admin:
            cur.execute(
                """SELECT sp.is_admin FROM session_person sp
                   WHERE sp.session_id = %s AND sp.person_id = %s""",
                (session_id, current_user.person_id)
            )
            admin_row = cur.fetchone()
            is_session_admin = admin_row and admin_row[0]
            if not is_session_admin:
                return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        # Get all unique tunes that have been played at this session
        # along with session_tune settings if they exist, play counts, and tunebook stats
        cur.execute(
            """
            WITH session_tune_plays AS (
                -- Count how many times each tune has been played at this session
                SELECT
                    sit.tune_id,
                    COUNT(DISTINCT si.session_instance_id) as play_count
                FROM session_instance_tune sit
                INNER JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                WHERE si.session_id = %s AND sit.tune_id IS NOT NULL
                GROUP BY sit.tune_id
            ),
            session_members AS (
                -- Spec 034: the session's community -- everyone who belongs to it and is
                -- still around. Visitors are excluded (this session isn't theirs, so their
                -- tunebook says nothing about what this session is learning); archived people
                -- are excluded (they're gone). It used to be regulars-only, which undercounted:
                -- someone who comes twice a month is exactly whose learning you want to see.
                SELECT person_id
                FROM session_person
                WHERE session_id = %s AND relationship = 'member' AND archived = FALSE
            ),
            tunebook_stats AS (
                -- How many of this session's members have each tune, by status
                SELECT
                    pt.tune_id,
                    COUNT(CASE WHEN pt.learn_status = 'want to learn' THEN 1 END) as want_to_learn_count,
                    COUNT(CASE WHEN pt.learn_status = 'learning' THEN 1 END) as learning_count,
                    COUNT(CASE WHEN pt.learn_status = 'learned' THEN 1 END) as learned_count
                FROM person_tune pt
                INNER JOIN session_members sm ON pt.person_id = sm.person_id
                GROUP BY pt.tune_id
            )
            SELECT
                t.tune_id,
                t.name as tune_name,
                t.tune_type,
                st.alias as session_alias,
                st.setting_id,
                st.key as session_key,
                ts.key as setting_key,
                COALESCE(stp.play_count, 0) as play_count,
                COALESCE(tbs.want_to_learn_count, 0) as want_to_learn_count,
                COALESCE(tbs.learning_count, 0) as learning_count,
                COALESCE(tbs.learned_count, 0) as learned_count
            FROM session_tune_plays stp
            INNER JOIN tune t ON stp.tune_id = t.tune_id
            LEFT JOIN session_tune st ON t.tune_id = st.tune_id AND st.session_id = %s
            LEFT JOIN tune_setting ts ON st.setting_id = ts.setting_id
            LEFT JOIN tunebook_stats tbs ON t.tune_id = tbs.tune_id
            ORDER BY t.name
        """,
            (session_id, session_id, session_id),
        )

        tunes = []
        for row in cur.fetchall():
            tunes.append(
                {
                    "tune_id": row[0],
                    "tune_name": row[1],
                    "tune_type": row[2],
                    "session_alias": row[3] or "",
                    "setting_id": row[4],
                    "session_key": row[5] or "",
                    "setting_key": row[6] or "",
                    "play_count": row[7],
                    "want_to_learn_count": row[8],
                    "learning_count": row[9],
                    "learned_count": row[10],
                }
            )

        cur.close()
        conn.close()

        return jsonify({"success": True, "tunes": tunes})

    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to get session tunes: {str(e)}"}), 500


@api_admin_or_self_required
def get_person_attendance_ajax(person_id):
    """Get attendance records for a person"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get all session instances this person was associated with
        cur.execute(
            """
            SELECT
                s.name as session_name,
                si.date as instance_date,
                sip.attendance
            FROM session_instance_person sip
            JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
            JOIN session s ON si.session_id = s.session_id
            WHERE sip.person_id = %s
              -- Spec 039: a session that stopped tracking attendance shows nothing about
              -- who attended, historic included — so its rows drop out of the person's
              -- own Attended tab too, or the profile would leak what the session hides.
              AND s.track_attendance
            ORDER BY si.date DESC
        """,
            (person_id,),
        )

        attendance_records = []
        for row in cur.fetchall():
            session_name, instance_date, attendance_status = row
            attendance_records.append(
                {
                    "session_name": session_name,
                    "instance_date": instance_date.strftime("%Y-%m-%d"),
                    "attendance": attendance_status,
                }
            )

        cur.close()
        conn.close()

        return jsonify({"success": True, "attendance": attendance_records})

    except Exception as e:
        return (
            jsonify(
                {"success": False, "error": f"Failed to get attendance data: {str(e)}"}
            ),
            500,
        )


@api_admin_or_self_required  # login_history rows carry IPs + user agents: PII
def get_person_logins_ajax(person_id):
    """Get login history for a person"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # First get the user_id for this person
        cur.execute(
            "SELECT user_id FROM user_account WHERE person_id = %s", (person_id,)
        )
        user_row = cur.fetchone()

        if not user_row:
            return jsonify(
                {
                    "success": True,
                    "logins": [],
                    "debug": f"No user_account found for person_id {person_id}",
                }
            )

        user_id = user_row[0]

        # Get login history (focusing on successful logins)
        cur.execute(
            """
            SELECT timestamp, ip_address, user_agent, event_type
            FROM login_history
            WHERE user_id = %s
            ORDER BY timestamp DESC
            LIMIT 100
        """,
            (user_id,),
        )

        logins = []
        for row in cur.fetchall():
            timestamp, ip_address, user_agent, event_type = row
            logins.append(
                {
                    "login_time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "ip_address": str(ip_address) if ip_address else "Unknown",
                    "user_agent": user_agent or "Unknown",
                    "event_type": event_type,
                }
            )

        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "logins": logins,
                "debug": f"Found user_id {user_id}, {len(logins)} login records",
            }
        )

    except Exception as e:
        return (
            jsonify(
                {"success": False, "error": f"Failed to get login history: {str(e)}"}
            ),
            500,
        )


@api_admin_or_self_required
def get_person_tunes_stats(person_id):
    """Get tune statistics for a person (total counts, by status, by type)

    Optional query parameters:
    - start_date: Filter tunes added on or after this date (YYYY-MM-DD)
    - end_date: Filter tunes added on or before this date (YYYY-MM-DD)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get optional date range filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Build date filter clause
        date_filter = ""
        date_params = [person_id]
        if start_date:
            date_filter += " AND pt.created_date >= %s"
            date_params.append(start_date)
        if end_date:
            date_filter += " AND pt.created_date < %s::date + interval '1 day'"
            date_params.append(end_date)

        # Get total count and counts by learn_status
        cur.execute(
            f"""
            SELECT
                COUNT(*) as total_tunes,
                COUNT(CASE WHEN learn_status = 'learned' THEN 1 END) as learned,
                COUNT(CASE WHEN learn_status = 'learning' THEN 1 END) as learning,
                COUNT(CASE WHEN learn_status = 'bookmarked' THEN 1 END) as bookmarked,
                MIN(pt.created_date) as earliest_date,
                MAX(pt.created_date) as latest_date
            FROM person_tune pt
            WHERE pt.person_id = %s{date_filter}
            """,
            tuple(date_params),
        )
        row = cur.fetchone()
        total_tunes, learned, learning, bookmarked, earliest_date, latest_date = row if row else (0, 0, 0, 0, None, None)

        # Get counts by tune type (for the filter dropdown)
        cur.execute(
            f"""
            SELECT
                COALESCE(t.tune_type, 'Unknown') as tune_type,
                COUNT(*) as count
            FROM person_tune pt
            JOIN tune t ON pt.tune_id = t.tune_id
            WHERE pt.person_id = %s{date_filter}
            GROUP BY t.tune_type
            ORDER BY count DESC
            """,
            tuple(date_params),
        )
        by_type = {}
        for type_row in cur.fetchall():
            by_type[type_row[0] or 'Unknown'] = type_row[1]

        # Get detailed breakdown by type and status (for filtering)
        cur.execute(
            f"""
            SELECT
                COALESCE(t.tune_type, 'Unknown') as tune_type,
                COUNT(*) as total,
                COUNT(CASE WHEN pt.learn_status = 'learned' THEN 1 END) as learned,
                COUNT(CASE WHEN pt.learn_status = 'learning' THEN 1 END) as learning,
                COUNT(CASE WHEN pt.learn_status = 'bookmarked' THEN 1 END) as bookmarked
            FROM person_tune pt
            JOIN tune t ON pt.tune_id = t.tune_id
            WHERE pt.person_id = %s{date_filter}
            GROUP BY t.tune_type
            ORDER BY COUNT(*) DESC
            """,
            tuple(date_params),
        )
        by_type_detailed = {}
        for row in cur.fetchall():
            tune_type = row[0] or 'Unknown'
            by_type_detailed[tune_type] = {
                'total': row[1],
                'learned': row[2],
                'learning': row[3],
                'bookmarked': row[4]
            }

        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "stats": {
                    "total_tunes": total_tunes or 0,
                    "learned": learned or 0,
                    "learning": learning or 0,
                    "bookmarked": bookmarked or 0,
                    "by_type": by_type,
                    "by_type_detailed": by_type_detailed,
                    "date_range": {
                        "earliest": earliest_date.strftime('%Y-%m-%d') if earliest_date else None,
                        "latest": latest_date.strftime('%Y-%m-%d') if latest_date else None,
                    }
                },
            }
        )

    except Exception as e:
        return (
            jsonify(
                {"success": False, "error": f"Failed to get tune statistics: {str(e)}"}
            ),
            500,
        )


@api_admin_or_self_required
def get_person_tunes_list(person_id):
    """
    GET /api/person/<person_id>/tunes — the person's tune collection, in the
    same shape as GET /api/my-tunes (shared serializer). Feeds the tunes grid
    on the admin person page; admin-or-self, so /me could use it too.

    Optional query parameters: tune_type, learn_status, search, sort, page, per_page.
    """
    from serializers import build_my_tunes_payload, VALID_PERSON_TUNE_SORTS

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(2000, max(1, int(request.args.get("per_page", 2000))))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid pagination parameter"}), 400
    learn_status = request.args.get("learn_status")
    if learn_status and learn_status not in ("want to learn", "learning", "learned"):
        return jsonify({"success": False, "error": "Invalid learn_status"}), 400
    sort = request.args.get("sort", "alpha-asc")
    if sort not in VALID_PERSON_TUNE_SORTS:
        return jsonify({"success": False, "error": "Invalid sort"}), 400
    search = request.args.get("search", "").strip()

    conn = get_db_connection()
    try:
        payload = build_my_tunes_payload(
            conn,
            person_id,
            learn_status=learn_status,
            tune_type=request.args.get("tune_type"),
            search=search or None,
            sort=sort,
            page=page,
            per_page=per_page,
        )
    finally:
        conn.close()
    return jsonify(payload)


@api_admin_or_self_required
def get_person_logged_tunes(person_id):
    """
    GET /api/person/<person_id>/logged-tunes — tune records this person logged
    at sessions (rows they created, via the live logger's attribution join:
    created_by_user_id -> user_account -> person), newest first.

    Breaks and soft-deleted rows are excluded. Display name falls back
    per-record override -> session alias -> catalog name, like the loggers.

    Optional query parameters:
    - view: 'detail' (default; one row per logged tune) or 'summary'
      (one row per session instance with a count)
    - limit (default 1000, max 2000)
    """
    try:
        limit = min(2000, max(1, int(request.args.get("limit", 1000))))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid limit"}), 400
    view = request.args.get("view", "detail")
    if view not in ("detail", "summary"):
        return jsonify({"success": False, "error": "Invalid view"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if view == "summary":
            cur.execute(
                """
                SELECT s.name AS session_name, s.path AS session_path, si.date,
                       COUNT(*) AS tune_count,
                       MAX(COALESCE(sit.inserted_timestamp, sit.created_date)) AS last_logged_at
                FROM session_instance_tune sit
                JOIN user_account cu ON cu.user_id = sit.created_by_user_id
                JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
                JOIN session s ON s.session_id = si.session_id
                WHERE cu.person_id = %s
                  AND sit.record_type = 'tune'
                  AND sit.deleted IS NOT TRUE
                GROUP BY si.session_instance_id, s.name, s.path, si.date
                ORDER BY MAX(COALESCE(sit.inserted_timestamp, sit.created_date)) DESC NULLS LAST,
                         si.session_instance_id DESC
                LIMIT %s
                """,
                (person_id, limit),
            )
            instances = [
                {
                    "session_name": r[0],
                    "session_path": r[1],
                    "date": r[2].isoformat() if r[2] else None,
                    "tune_count": r[3],
                    "last_logged_at": r[4].isoformat() if r[4] else None,
                }
                for r in cur.fetchall()
            ]
            return jsonify({"success": True, "view": "summary", "instances": instances})
        cur.execute(
            """
            SELECT sit.session_instance_tune_id, sit.tune_id,
                   COALESCE(sit.name, st.alias, t.name) AS tune_name,
                   COALESCE(sit.inserted_timestamp, sit.created_date) AS logged_at,
                   s.name AS session_name, s.path AS session_path, si.date
            FROM session_instance_tune sit
            JOIN user_account cu ON cu.user_id = sit.created_by_user_id
            JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
            JOIN session s ON s.session_id = si.session_id
            LEFT JOIN tune t ON t.tune_id = sit.tune_id
            LEFT JOIN session_tune st
                   ON st.session_id = si.session_id AND st.tune_id = sit.tune_id
            WHERE cu.person_id = %s
              AND sit.record_type = 'tune'
              AND sit.deleted IS NOT TRUE
            ORDER BY COALESCE(sit.inserted_timestamp, sit.created_date) DESC NULLS LAST,
                     sit.session_instance_tune_id DESC
            LIMIT %s
            """,
            (person_id, limit),
        )
        rows = cur.fetchall()
        cur.execute(
            """
            SELECT COUNT(*)
            FROM session_instance_tune sit
            JOIN user_account cu ON cu.user_id = sit.created_by_user_id
            WHERE cu.person_id = %s
              AND sit.record_type = 'tune'
              AND sit.deleted IS NOT TRUE
            """,
            (person_id,),
        )
        total_count = cur.fetchone()[0]
    finally:
        conn.close()

    return jsonify(
        {
            "success": True,
            "total_count": total_count,
            "tunes": [
                {
                    "session_instance_tune_id": r[0],
                    "tune_id": r[1],
                    "tune_name": r[2],
                    "logged_at": r[3].isoformat() if r[3] else None,
                    "session_name": r[4],
                    "session_path": r[5],
                    "date": r[6].isoformat() if r[6] else None,
                }
                for r in rows
            ],
        }
    )


@api_login_required  # only caller is the profile tab on /me and /admin/people/<id> (both @login_required pages)
def check_username_availability():
    """Check if a username is available"""
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        current_user_id = data.get(
            "current_user_id"
        )  # To exclude current user from check

        if not username:
            return jsonify({"available": False, "message": "Username cannot be empty"})

        if len(username) < 3:
            return jsonify(
                {
                    "available": False,
                    "message": "Username must be at least 3 characters long",
                }
            )

        conn = get_db_connection()
        cur = conn.cursor()

        # Check if username exists (case-insensitive), excluding current user if provided
        if current_user_id:
            cur.execute(
                "SELECT user_id FROM user_account WHERE LOWER(username) = LOWER(%s) AND user_id != %s",
                (username, current_user_id),
            )
        else:
            cur.execute(
                "SELECT user_id FROM user_account WHERE LOWER(username) = LOWER(%s)", (username,)
            )

        existing_user = cur.fetchone()
        cur.close()
        conn.close()

        if existing_user:
            return jsonify({"available": False, "message": "Username already taken"})
        else:
            return jsonify({"available": True, "message": "Username is available"})

    except Exception as e:
        return (
            jsonify(
                {"available": False, "message": f"Error checking username: {str(e)}"}
            ),
            500,
        )


@api_login_required
def update_person_details(person_id):
    """Update person and user details. Profile owner or system admin only."""
    try:
        if not current_user.is_system_admin and current_user.person_id != person_id:
            return jsonify({"success": False, "message": "Not authorized"}), 403

        data = request.get_json()

        if not person_id:
            return jsonify({"success": False, "message": "Person ID is required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Update person details
        person_data = data.get("person", {})
        if person_data:
            save_to_history(cur, "person", "UPDATE", person_id, user_id=get_current_user_id())
            cur.execute(
                """
                UPDATE person
                SET first_name = %s, last_name = %s, email = %s, sms_number = %s,
                    city = %s, state = %s, country = %s, thesession_user_id = %s, last_modified_date = %s
                WHERE person_id = %s
            """,
                (
                    person_data.get("first_name"),
                    person_data.get("last_name"),
                    person_data.get("email") or None,
                    person_data.get("sms_number") or None,
                    person_data.get("city") or None,
                    person_data.get("state") or None,
                    person_data.get("country") or None,
                    person_data.get("thesession_user_id") or None,
                    now_utc(),
                    person_id,
                ),
            )

        # Update user details if provided
        user_data = data.get("user", {})
        if user_data and user_data.get("user_id"):
            user_id = user_data.get("user_id")

            # The user block may only touch the account attached to this person —
            # otherwise an owner could smuggle another user's user_id into the payload.
            cur.execute(
                "SELECT user_id FROM user_account WHERE person_id = %s", (person_id,)
            )
            person_account = cur.fetchone()
            if not person_account or person_account[0] != user_id:
                cur.close()
                conn.close()
                return (
                    jsonify(
                        {"success": False, "message": "User account does not match this person"}
                    ),
                    403,
                )

            # Check if username is being changed and is available (case-insensitive)
            username = user_data.get("username")
            if username:
                cur.execute(
                    "SELECT user_id FROM user_account WHERE LOWER(username) = LOWER(%s) AND user_id != %s",
                    (username, user_id),
                )
                if cur.fetchone():
                    cur.close()
                    conn.close()
                    return (
                        jsonify(
                            {"success": False, "message": "Username already taken"}
                        ),
                        400,
                    )

            # Opt-in to update emails (spec 027): only touch the flag when the
            # payload mentions it — the admin edit form omits it and must not
            # clobber the user's own setting (COALESCE keeps the current value).
            receive_update_emails = user_data.get("receive_update_emails")
            if receive_update_emails is not None:
                receive_update_emails = bool(receive_update_emails)

            # is_active is intentionally NOT set here: a person and their account
            # share one active status, controlled only by the person deactivate/
            # reactivate action (toggle_person_active). Setting it from this form
            # would let a routine profile save silently flip login access.
            save_to_history(cur, "user_account", "UPDATE", user_id, user_id=get_current_user_id())
            cur.execute(
                """
                UPDATE user_account
                SET username = %s, user_email = %s, timezone = %s,
                    receive_update_emails = COALESCE(%s, receive_update_emails),
                    last_modified_date = %s
                WHERE user_id = %s
            """,
                (
                    username,
                    user_data.get("user_email") or None,
                    user_data.get("timezone") or "UTC",
                    receive_update_emails,
                    now_utc(),
                    user_id,
                ),
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Details updated successfully"})

    except Exception as e:
        return (
            jsonify(
                {"success": False, "message": f"Failed to update details: {str(e)}"}
            ),
            500,
        )


@api_login_required
def admin_verify_email(user_id):
    """Admin endpoint to manually verify a user's email"""
    # Check if current user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "message": "Unauthorized. Admin access required."}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if user exists and email is not already verified
        cur.execute(
            """
            SELECT user_id, username, email_verified
            FROM user_account
            WHERE user_id = %s
            """,
            (user_id,),
        )
        user_data = cur.fetchone()

        if not user_data:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "User not found"}), 404

        user_id_db, username, email_verified = user_data

        if email_verified:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Email is already verified"}), 400

        # Mark email as verified and clear token
        save_to_history(
            cur, "user_account", "UPDATE", user_id_db, user_id=get_current_user_id()
        )
        cur.execute(
            """
            UPDATE user_account
            SET email_verified = TRUE,
                verification_token = NULL,
                verification_token_expires = NULL,
                last_modified_date = %s
            WHERE user_id = %s
            """,
            (now_utc(), user_id_db),
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Email verified successfully for user '{username}'"
        })

    except Exception as e:
        return (
            jsonify(
                {"success": False, "message": f"Failed to verify email: {str(e)}"}
            ),
            500,
        )


@api_login_required
def toggle_person_active(person_id):
    """
    Toggle a person's active status (deactivate/reactivate).

    PUT /api/admin/person/<person_id>/active

    Request body:
    {
        "active": bool
    }

    Returns:
    {
        "success": true,
        "message": str,
        "active": bool
    }

    Requires system admin access.
    """
    # Check if current user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "message": "Unauthorized. Admin access required."}), 403

    try:
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "message": "No data provided"}), 400

        active = data.get("active")
        if active is None:
            return jsonify({"success": False, "message": "'active' field is required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Check if person exists and get their name + connected account (if any).
        # A person and their login account share one active status: deactivating a
        # connected person also disables their login, and reactivating re-enables it.
        cur.execute(
            """
            SELECT p.first_name, p.last_name, p.active, ua.user_id, ua.is_active
            FROM person p
            LEFT JOIN user_account ua ON ua.person_id = p.person_id
            WHERE p.person_id = %s
            """,
            (person_id,),
        )
        person_row = cur.fetchone()

        if not person_row:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Person not found"}), 404

        first_name, last_name, current_active, account_user_id, account_active = person_row
        person_name = f"{first_name} {last_name}"

        # "Already X" only when nothing needs changing — for a connected person that
        # means both flags already match the target (a legacy desync still needs a write).
        person_matches = current_active == active
        account_matches = account_user_id is None or account_active == active
        if person_matches and account_matches:
            status_word = "active" if active else "deactivated"
            cur.close()
            conn.close()
            return jsonify({
                "success": False,
                "message": f"{person_name} is already {status_word}"
            }), 400

        # Save to history before update
        save_to_history(cur, "person", "UPDATE", person_id, user_id=get_current_user_id())

        # Update the person's active status
        cur.execute(
            """
            UPDATE person
            SET active = %s, last_modified_date = %s
            WHERE person_id = %s
            """,
            (active, now_utc(), person_id),
        )

        # Keep the connected account's login status in lockstep.
        if account_user_id is not None:
            save_to_history(cur, "user_account", "UPDATE", account_user_id, user_id=get_current_user_id())
            cur.execute(
                """
                UPDATE user_account
                SET is_active = %s, last_modified_date = %s
                WHERE user_id = %s
                """,
                (active, now_utc(), account_user_id),
            )

        conn.commit()
        cur.close()
        conn.close()

        action_word = "reactivated" if active else "deactivated"
        return jsonify({
            "success": True,
            "message": f"{person_name} has been {action_word}",
            "active": active
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to update person status: {str(e)}"
        }), 500


@api_admin_or_self_required
def get_available_sessions_for_person(person_id):
    """Get sessions available for a person to join, prioritizing same location sessions"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get person's location info
        cur.execute(
            "SELECT city, state, country FROM person WHERE person_id = %s", (person_id,)
        )
        person_row = cur.fetchone()
        if not person_row:
            return jsonify({"success": False, "message": "Person not found"}), 404

        person_city, person_state, person_country = person_row

        # Get sessions the person is NOT already in, prioritizing same location
        query = """
            SELECT s.session_id, s.name, s.location_name, s.city, s.state, s.country,
                   CASE
                       WHEN s.city = %s AND s.state = %s AND s.country = %s THEN 1
                       WHEN s.city = %s AND s.country = %s THEN 2
                       WHEN s.country = %s THEN 3
                       ELSE 4
                   END as location_priority
            FROM session s
            WHERE s.session_id NOT IN (
                SELECT sp.session_id
                FROM session_person sp
                WHERE sp.person_id = %s
            )
            AND s.termination_date IS NULL
            ORDER BY location_priority, s.name
            LIMIT 20
        """

        cur.execute(
            query,
            (
                person_city,
                person_state,
                person_country,  # Exact match
                person_city,
                person_country,  # City + country match
                person_country,  # Country match
                person_id,  # Exclude existing sessions
            ),
        )

        sessions = []
        for row in cur.fetchall():
            session_id, name, location_name, city, state, country, priority = row

            # Format location display
            location_parts = []
            if city:
                location_parts.append(city)
            if state:
                location_parts.append(state)
            if country:
                location_parts.append(country)
            location_display = (
                ", ".join(location_parts) if location_parts else "Unknown"
            )

            sessions.append(
                {
                    "session_id": session_id,
                    "name": name,
                    "location_name": location_name,
                    "location_display": location_display,
                    "city": city,
                    "state": state,
                    "country": country,
                    "priority": priority,
                }
            )

        cur.close()
        conn.close()

        return jsonify({"success": True, "sessions": sessions})

    except Exception as e:
        return (
            jsonify({"success": False, "message": f"Failed to get sessions: {str(e)}"}),
            500,
        )


@api_admin_or_self_required
def search_sessions_for_person(person_id):
    """Search sessions for a person based on search term"""
    try:
        data = request.get_json()
        search_term = data.get("search_term", "").strip()

        conn = get_db_connection()
        cur = conn.cursor()

        # Base query to exclude sessions person is already in
        base_where = """
            s.session_id NOT IN (
                SELECT sp.session_id
                FROM session_person sp
                WHERE sp.person_id = %s
            )
            AND s.termination_date IS NULL
        """

        params = [person_id]

        if search_term:
            # Add search criteria
            search_where = """
                AND (
                    LOWER(s.name) LIKE LOWER(%s) OR
                    LOWER(s.location_name) LIKE LOWER(%s) OR
                    LOWER(s.city) LIKE LOWER(%s) OR
                    LOWER(s.state) LIKE LOWER(%s) OR
                    LOWER(s.country) LIKE LOWER(%s)
                )
            """
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern] * 5)
        else:
            search_where = ""

        query = f"""
            SELECT s.session_id, s.name, s.location_name, s.city, s.state, s.country
            FROM session s
            WHERE {base_where} {search_where}
            ORDER BY s.name
            LIMIT 10
        """

        cur.execute(query, params)

        sessions = []
        for row in cur.fetchall():
            session_id, name, location_name, city, state, country = row

            # Format location display
            location_parts = []
            if city:
                location_parts.append(city)
            if state:
                location_parts.append(state)
            if country:
                location_parts.append(country)
            location_display = (
                ", ".join(location_parts) if location_parts else "Unknown"
            )

            sessions.append(
                {
                    "session_id": session_id,
                    "name": name,
                    "location_name": location_name,
                    "location_display": location_display,
                    "city": city,
                    "state": state,
                    "country": country,
                }
            )

        cur.close()
        conn.close()

        return jsonify({"success": True, "sessions": sessions})

    except Exception as e:
        return (
            jsonify(
                {"success": False, "message": f"Failed to search sessions: {str(e)}"}
            ),
            500,
        )


@api_login_required  # only caller is the person page Sessions tab (/me, /admin/people/<id> — both @login_required pages)
def add_person_to_session():
    """Add a person to a session and send notification email"""
    try:
        data = request.get_json()
        person_id = data.get("person_id")
        session_id = data.get("session_id")
        # Spec 034: 'member' | 'visitor'. This is a self-declaration (or an admin acting for
        # someone), so it does NOT confirm -- see below.
        relationship = data.get("relationship", "member")
        if relationship not in ("member", "visitor"):
            return (
                jsonify({"success": False, "message": "relationship must be 'member' or 'visitor'"}),
                400,
            )

        if not person_id or not session_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Person ID and Session ID are required",
                    }
                ),
                400,
            )

        conn = get_db_connection()
        cur = conn.cursor()

        # Check if person is already in this session
        cur.execute(
            "SELECT 1 FROM session_person WHERE person_id = %s AND session_id = %s",
            (person_id, session_id),
        )
        if cur.fetchone():
            return (
                jsonify(
                    {"success": False, "message": "Person is already in this session"}
                ),
                400,
            )

        # Get person and session details for email
        cur.execute(
            """
            SELECT p.first_name, p.last_name, COALESCE(p.email, ua.user_email), p.active
            FROM person p
            LEFT JOIN user_account ua ON ua.person_id = p.person_id
            WHERE p.person_id = %s
            """,
            (person_id,),
        )
        person_row = cur.fetchone()
        if not person_row:
            return jsonify({"success": False, "message": "Person not found"}), 404

        person_first_name, person_last_name, person_email, person_active = person_row
        person_name = f"{person_first_name} {person_last_name}"

        if not person_active:
            return jsonify({"success": False, "message": f"{person_name} is deactivated and cannot be added to sessions"}), 400

        cur.execute(
            "SELECT name, city, state, country, path FROM session WHERE session_id = %s",
            (session_id,),
        )
        session_row = cur.fetchone()
        if not session_row:
            return jsonify({"success": False, "message": "Session not found"}), 404

        (
            session_name,
            session_city,
            session_state,
            session_country,
            session_path,
        ) = session_row

        # Add person to session. confirmed=FALSE: this is someone adding THEMSELVES to a
        # session (or a system admin adding them), which is exactly the path that must not
        # grant people-visibility -- otherwise anyone could join a session and read its
        # roster. A session admin confirms them afterwards.
        cur.execute(
            """
            INSERT INTO session_person
                (person_id, session_id, relationship, confirmed, archived, is_admin, created_by_user_id)
            VALUES (%s, %s, %s, FALSE, FALSE, FALSE, %s)
        """,
            (person_id, session_id, relationship, get_current_user_id()),
        )
        save_to_history(cur, "session_person", "INSERT", (session_id, person_id),
                        user_id=get_current_user_id())

        # Get session admins for email notification. Prefer the account email
        # (user_account.user_email) — person.email is being retired for connected
        # people — but fall back to person.email for admins with no account.
        cur.execute(
            """
            SELECT p.first_name, p.last_name, COALESCE(ua.user_email, p.email)
            FROM person p
            JOIN session_person sp ON p.person_id = sp.person_id
            LEFT JOIN user_account ua ON ua.person_id = p.person_id
            WHERE sp.session_id = %s AND sp.is_admin = TRUE
              AND COALESCE(ua.user_email, p.email) IS NOT NULL
        """,
            (session_id,),
        )

        session_admins = cur.fetchall()

        # If no session admins, get system admins (always account holders).
        if not session_admins:
            cur.execute(
                """
                SELECT p.first_name, p.last_name, ua.user_email
                FROM person p
                JOIN user_account ua ON p.person_id = ua.person_id
                WHERE ua.is_system_admin = TRUE AND ua.user_email IS NOT NULL
            """,
                (),
            )
            session_admins = cur.fetchall()

        conn.commit()
        cur.close()
        conn.close()

        # Send notification emails
        if session_admins:
            # Format session location
            location_parts = []
            if session_city:
                location_parts.append(session_city)
            if session_state:
                location_parts.append(session_state)
            if session_country:
                location_parts.append(session_country)
            session_location = (
                ", ".join(location_parts) if location_parts else "Unknown"
            )

            subject = f"New person added to session: {session_name}"

            for admin_first, admin_last, admin_email in session_admins:
                admin_name = f"{admin_first} {admin_last}"

                body = f"""Hello {admin_name},

{person_name} has been added to the session "{session_name}" in {session_location} as a {relationship}.

Person Details:
- Name: {person_name}
- Email: {person_email or 'Not provided'}

You can review and modify this person's role in the session admin interface: https://ceol.io/admin/sessions/{session_path}/people

Best regards,
The Ceol.io Session Management System"""

                try:
                    send_email_via_sendgrid(admin_email, subject, body)
                except Exception as email_error:
                    print(f"Failed to send email to {admin_email}: {email_error}")

        return jsonify(
            {
                "success": True,
                "message": f"{person_name} has been added to {session_name} as a {relationship}",
            }
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Failed to add person to session: {str(e)}",
                }
            ),
            500,
        )


@api_login_required  # only caller is templates/admin_people.html (admin page)
def validate_thesession_entity():
    """Validate and get info from thesession.org (member or session)"""
    try:
        data = request.get_json()
        user_input = data.get("user_input", "").strip()

        # Extract ID from URL or use direct ID
        thesession_id = None
        if user_input.startswith("https://thesession.org/"):
            try:
                # Handle both /members/ and /sessions/ URLs
                if "/members/" in user_input:
                    thesession_id = int(user_input.split("/members/")[-1].split("/")[0])
                elif "/sessions/" in user_input:
                    thesession_id = int(user_input.split("/sessions/")[-1].split("/")[0])
                else:
                    return jsonify(
                        {"success": False, "message": "Invalid TheSession.org URL format"}
                    )
            except ValueError:
                return jsonify(
                    {"success": False, "message": "Invalid TheSession.org URL format"}
                )
        elif user_input.isdigit():
            thesession_id = int(user_input)
        else:
            return jsonify(
                {
                    "success": False,
                    "message": "Please enter a valid name or TheSession.org URL/ID",
                }
            )

        # Check if this thesession_user_id already exists in our database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT person_id, first_name, last_name FROM person WHERE thesession_user_id = %s",
            (thesession_id,),
        )
        existing_person = cur.fetchone()
        cur.close()
        conn.close()

        if existing_person:
            person_id, first_name, last_name = existing_person
            return jsonify(
                {
                    "success": False,
                    "message": f"A person with TheSession.org ID {thesession_id} already exists: {first_name} {last_name} (Person ID: {person_id})",
                }
            )

        # Fetch user data from thesession.org API
        api_url = f"https://thesession.org/members/{thesession_id}?format=json"
        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code != 200:
                return jsonify(
                    {
                        "success": False,
                        "message": f"TheSession.org user ID {thesession_id} not found",
                    }
                )

            user_data = response.json()
            if "name" not in user_data:
                return jsonify(
                    {
                        "success": False,
                        "message": "Unable to retrieve user name from TheSession.org",
                    }
                )

            name = user_data["name"]

            # Parse name into first and last
            name_parts = name.strip().split()
            if len(name_parts) == 1:
                first_name = name_parts[0]
                last_name = ""
            else:
                first_name = " ".join(name_parts[:-1])
                last_name = name_parts[-1]

            return jsonify(
                {
                    "success": True,
                    "thesession_user_id": thesession_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "source": "thesession",
                }
            )

        except requests.RequestException as e:
            return jsonify(
                {
                    "success": False,
                    "message": f"Error connecting to TheSession.org: {str(e)}",
                }
            )

    except Exception as e:
        return (
            jsonify({"success": False, "message": f"Error validating user: {str(e)}"}),
            500,
        )


@api_login_required  # only caller is templates/admin_people.html (admin page)
def parse_person_name():
    """Parse a person's name into first and last name"""
    try:
        data = request.get_json()
        full_name = data.get("name", "").strip()

        if not full_name:
            return jsonify({"success": False, "message": "Name cannot be empty"})

        # Parse name into first and last
        name_parts = full_name.split()
        if len(name_parts) == 1:
            first_name = name_parts[0]
            last_name = ""
        else:
            first_name = " ".join(name_parts[:-1])
            last_name = name_parts[-1]

        return jsonify(
            {
                "success": True,
                "first_name": first_name,
                "last_name": last_name,
                "source": "manual",
            }
        )

    except Exception as e:
        return (
            jsonify({"success": False, "message": f"Error parsing name: {str(e)}"}),
            500,
        )


@api_login_required  # only caller is templates/admin_people.html (admin page)
def create_new_person():
    """Create a new person and optionally add to a session"""
    try:
        data = request.get_json()

        # Required fields
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()

        if not first_name:
            return jsonify({"success": False, "message": "First name is required"}), 400

        # Optional fields
        email = data.get("email", "").strip() or None
        sms_number = data.get("sms_number", "").strip() or None
        city = data.get("city", "").strip() or None
        state = data.get("state", "").strip() or None
        country = data.get("country", "").strip() or None
        thesession_user_id = data.get("thesession_user_id") or None
        session_id = data.get("session_id") or None

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # Insert new person
            audit_user_id = get_current_user_id()
            cur.execute(
                """
                INSERT INTO person (first_name, last_name, email, sms_number, city, state, country, thesession_user_id,
                                    created_by_user_id, last_modified_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING person_id
            """,
                (
                    first_name,
                    last_name,
                    email,
                    sms_number,
                    city,
                    state,
                    country,
                    thesession_user_id,
                    audit_user_id,
                    audit_user_id,
                ),
            )

            result = cur.fetchone()
            if not result:
                return jsonify({"success": False, "message": "Failed to create person"})
            person_id = result[0]

            # Save to history after INSERT (we now have person_id)
            save_to_history(cur, "person", "INSERT", person_id, user_id=audit_user_id)

            # Add to session if specified. An admin creating a person against a session is a
            # deliberate roster act, so it vouches for them (spec 034).
            if session_id:
                cur.execute(
                    """
                    INSERT INTO session_person
                        (person_id, session_id, relationship, confirmed, archived, is_admin, created_by_user_id)
                    VALUES (%s, %s, 'member', TRUE, FALSE, FALSE, %s)
                """,
                    (person_id, session_id, audit_user_id),
                )
                save_to_history(cur, "session_person", "INSERT", (session_id, person_id),
                                user_id=audit_user_id)

            conn.commit()

            # Get session name for response message
            session_name = None
            if session_id:
                cur.execute(
                    "SELECT name FROM session WHERE session_id = %s", (session_id,)
                )
                session_row = cur.fetchone()
                if session_row:
                    session_name = session_row[0]

            cur.close()
            conn.close()

            # Create success message
            message = f"{first_name} {last_name} has been created successfully"
            if session_name:
                message += f' and added to session "{session_name}"'

            return jsonify(
                {"success": True, "message": message, "person_id": person_id}
            )

        except Exception as db_error:
            conn.rollback()
            cur.close()
            conn.close()
            return (
                jsonify(
                    {"success": False, "message": f"Database error: {str(db_error)}"}
                ),
                500,
            )

    except Exception as e:
        return (
            jsonify(
                {"success": False, "message": f"Failed to create person: {str(e)}"}
            ),
            500,
        )


@api_login_required  # only caller is templates/admin_people.html (admin page dropdown)
def get_available_sessions():
    """Get list of all active sessions for dropdown"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT session_id, name, city, state, country
            FROM session
            WHERE termination_date IS NULL
            ORDER BY name
        """
        )

        sessions = []
        for row in cur.fetchall():
            session_id, name, city, state, country = row

            # Format location display
            location_parts = []
            if city:
                location_parts.append(city)
            if state:
                location_parts.append(state)
            if country:
                location_parts.append(country)
            location_display = ", ".join(location_parts) if location_parts else ""

            display_name = f"{name}"
            if location_display:
                display_name += f" ({location_display})"

            sessions.append(
                {"session_id": session_id, "name": name, "display_name": display_name}
            )

        cur.close()
        conn.close()

        return jsonify({"success": True, "sessions": sessions})

    except Exception as e:
        return (
            jsonify({"success": False, "message": f"Failed to get sessions: {str(e)}"}),
            500,
        )


@api_login_required
def _set_session_person_field(session_path, person_id, column, value, *, admin_only):
    """Shared body for the three session_person setters (spec 034).

    `admin_only` distinguishes the two write policies:
      * relationship -- the person themselves OR a session admin. It says whose session this
        is, and that is a claim the person is entitled to make about their own life.
      * confirmed / archived -- session admins only. These are the SESSION's statements about
        its own roster (who it vouches for, who it still counts as around), so letting the
        subject set them would be self-dealing: confirming yourself would defeat the gate.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Session not found"}), 404
        session_id = row[0]

        actor_person_id = getattr(current_user, "person_id", None)
        is_admin = is_session_admin_for(cur, session_id, actor_person_id)
        is_self = actor_person_id is not None and actor_person_id == person_id

        if admin_only:
            allowed = is_admin
        else:
            allowed = is_admin or is_self
        if not allowed:
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403

        # History BEFORE the update -- it snapshots the pre-change row.
        save_to_history(cur, "session_person", "UPDATE", (session_id, person_id),
                        user_id=get_current_user_id())

        cur.execute(
            f"""
            UPDATE session_person
            SET {column} = %s, last_modified_date = (NOW() AT TIME ZONE 'UTC'),
                last_modified_user_id = %s
            WHERE session_id = %s AND person_id = %s
            """,
            (value, get_current_user_id(), session_id, person_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"success": False, "message": "Person not found in this session"}), 404

        conn.commit()
        return jsonify({"success": True, column: value})

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@api_login_required
def set_session_person_relationship(session_path, person_id):
    """PUT /api/sessions/<path>/people/<person_id>/relationship  {relationship}

    'member' | 'visitor' -- whose session is this? Settable by the person OR a session admin
    (a walk-in lands as a visitor and needs someone to promote her; she may have no account
    at all, so requiring her consent would leave rosters permanently wrong).

    Grants no access. Access is `confirmed`, which is a different question and a different
    endpoint.
    """
    data = request.get_json() or {}
    relationship = data.get("relationship")
    if relationship not in ("member", "visitor"):
        return jsonify({"success": False, "message": "relationship must be 'member' or 'visitor'"}), 400
    return _set_session_person_field(
        session_path, person_id, "relationship", relationship, admin_only=False
    )


@api_login_required
def set_session_person_confirmed(session_path, person_id):
    """PUT /api/sessions/<path>/people/<person_id>/confirmed  {confirmed}

    Does the session vouch for this person? Admin-only, and the ONLY way people-visibility is
    granted. The UI must say what it does at the point of click ("...she'll be able to see
    this session's people list and attendance records"), never a bare toggle.
    """
    data = request.get_json() or {}
    confirmed = bool(data.get("confirmed", False))
    return _set_session_person_field(
        session_path, person_id, "confirmed", confirmed, admin_only=True
    )


@api_login_required
def set_session_person_archived(session_path, person_id):
    """PUT /api/sessions/<path>/people/<person_id>/archived  {archived}

    Admin roster hygiene: hide someone who moved away. Hidden from DEFAULT lists only --
    still findable by typing, everywhere, always. Check-in never clears this: a visit means
    "she's here tonight", not "she's back".
    """
    data = request.get_json() or {}
    archived = bool(data.get("archived", False))
    return _set_session_person_field(
        session_path, person_id, "archived", archived, admin_only=True
    )


@api_login_required
def update_session_player_admin_status(session_path, person_id):
    """Update the admin status for a person in a specific session"""
    # Check if current user is a system admin
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        if not user_row or not user_row[0]:
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403

        data = request.get_json()
        is_admin = data.get("is_admin", False)

        # Get session ID first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "error": "Session not found"}), 404

        session_id = session_result[0]

        # History BEFORE the update -- it snapshots the pre-change row.
        save_to_history(
            cur,
            "session_person",
            "UPDATE",
            (session_id, person_id),
            user_id=get_current_user_id(),
        )

        # Update the admin status
        cur.execute(
            """
            UPDATE session_person
            SET is_admin = %s
            WHERE session_id = %s AND person_id = %s
        """,
            (is_admin, session_id, person_id),
        )

        if cur.rowcount == 0:
            return (
                jsonify(
                    {"success": False, "error": "Person not found in this session"}
                ),
                404,
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def update_session_player_details(session_path, person_id):
    """Update person details for session admins"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if current user is a system admin or session admin
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        is_system_admin = user_row and user_row[0]
        
        # If not system admin, check if they're a session admin
        is_session_admin = False
        if not is_system_admin:
            cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
            session_result = cur.fetchone()
            if not session_result:
                return jsonify({"success": False, "error": "Session not found"}), 404
            
            session_id = session_result[0]
            cur.execute(
                """SELECT sp.is_admin FROM session_person sp 
                   WHERE sp.session_id = %s AND sp.person_id = %s""",
                (session_id, current_user.person_id)
            )
            admin_row = cur.fetchone()
            is_session_admin = admin_row and admin_row[0]
        
        if not is_system_admin and not is_session_admin:
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403

        # Get session ID if we don't have it yet
        if 'session_id' not in locals():
            cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
            session_result = cur.fetchone()
            if not session_result:
                return jsonify({"success": False, "error": "Session not found"}), 404
            session_id = session_result[0]

        # Check if person has a linked user account
        cur.execute(
            """SELECT p.person_id, u.user_id FROM person p 
               LEFT JOIN user_account u ON p.person_id = u.person_id 
               WHERE p.person_id = %s""",
            (person_id,)
        )
        person_row = cur.fetchone()
        if not person_row:
            return jsonify({"success": False, "error": "Person not found"}), 404
        
        has_user_account = person_row[1] is not None

        data = request.get_json()
        
        # If person has user account, only allow updating regular status
        if has_user_account:
            # Spec 034: relationship replaces is_regular. (This UPDATE is duplicated in the
            # has-account / no-account branches of this one function -- change both.)
            if 'relationship' in data:
                if data['relationship'] not in ('member', 'visitor'):
                    return jsonify({"success": False, "message": "relationship must be 'member' or 'visitor'"}), 400
                # History BEFORE the update -- it snapshots the pre-change row.
                save_to_history(
                    cur,
                    "session_person",
                    "UPDATE",
                    (session_id, person_id),
                    user_id=get_current_user_id(),
                )
                cur.execute(
                    """UPDATE session_person SET relationship = %s, last_modified_user_id = %s
                       WHERE session_id = %s AND person_id = %s""",
                    (data['relationship'], get_current_user_id(), session_id, person_id)
                )
        else:
            # Person doesn't have user account - allow updating additional fields
            updates = []
            params = []
            
            # Fields that can be updated for non-user accounts
            editable_fields = ['first_name', 'last_name', 'email', 'sms_number', 'city', 'state', 'country', 'thesession_user_id']
            
            for field in editable_fields:
                if field in data:
                    updates.append(f"{field} = %s")
                    params.append(data[field])
            
            if updates:
                updates.append("last_modified_date = NOW()")
                updates.append("last_modified_user_id = %s")
                params.append(get_current_user_id())
                params.append(person_id)

                update_sql = f"""
                    UPDATE person
                    SET {', '.join(updates)}
                    WHERE person_id = %s
                """
                cur.execute(update_sql, params)

                save_to_history(
                    cur,
                    "person",
                    "UPDATE",
                    person_id,
                    user_id=get_current_user_id(),
                )

            # Spec 034: relationship replaces is_regular. (This UPDATE is duplicated in the
            # has-account / no-account branches of this one function -- change both.)
            if 'relationship' in data:
                if data['relationship'] not in ('member', 'visitor'):
                    return jsonify({"success": False, "message": "relationship must be 'member' or 'visitor'"}), 400
                # History BEFORE the update -- it snapshots the pre-change row.
                save_to_history(
                    cur,
                    "session_person",
                    "UPDATE",
                    (session_id, person_id),
                    user_id=get_current_user_id(),
                )
                cur.execute(
                    """UPDATE session_person SET relationship = %s, last_modified_user_id = %s
                       WHERE session_id = %s AND person_id = %s""",
                    (data['relationship'], get_current_user_id(), session_id, person_id)
                )

        conn.commit()
        return jsonify({"success": True})

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@api_login_required
def delete_session_player(session_path, person_id):
    """Delete a player from a session and potentially the person record if orphaned"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if current user is a system admin or session admin
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        is_system_admin = user_row and user_row[0]
        
        # If not system admin, check if they're a session admin
        is_session_admin = False
        if not is_system_admin:
            cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
            session_result = cur.fetchone()
            if not session_result:
                return jsonify({"success": False, "message": "Session not found"}), 404
            
            session_id = session_result[0]
            cur.execute(
                """SELECT sp.is_admin FROM session_person sp 
                   WHERE sp.session_id = %s AND sp.person_id = %s""",
                (session_id, current_user.person_id)
            )
            admin_row = cur.fetchone()
            is_session_admin = admin_row and admin_row[0]
        
        if not is_system_admin and not is_session_admin:
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403

        # Get session ID if we don't have it yet
        if 'session_id' not in locals():
            cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
            session_result = cur.fetchone()
            if not session_result:
                return jsonify({"success": False, "message": "Session not found"}), 404
            session_id = session_result[0]

        # Check if person exists and get info about user account
        cur.execute(
            """SELECT p.person_id, u.user_id FROM person p 
               LEFT JOIN user_account u ON p.person_id = u.person_id 
               WHERE p.person_id = %s""",
            (person_id,)
        )
        person_row = cur.fetchone()
        if not person_row:
            return jsonify({"success": False, "message": "Person not found"}), 404
        
        has_user_account = person_row[1] is not None

        # Check if person is actually in this session
        cur.execute(
            "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id)
        )
        if not cur.fetchone():
            return jsonify({"success": False, "message": "Person is not in this session"}), 404

        # If person has no user account, check if they should be deleted entirely BEFORE we delete from session_person
        person_deleted = False
        other_sessions_count = 0  # Initialize to 0, only matters if no user account
        if not has_user_account:
            # Check if person is associated with any other sessions (excluding this one)
            cur.execute(
                "SELECT COUNT(*) FROM session_person WHERE person_id = %s AND session_id != %s",
                (person_id, session_id)
            )
            result = cur.fetchone()
            other_sessions_count = result[0] if result else 0

        # Remove from session_person table
        cur.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id)
        )
        # TODO: Add session_person history tracking

        # Remove from session_instance_person table (all instances for this session)
        cur.execute(
            """DELETE FROM session_instance_person 
               WHERE person_id = %s AND session_instance_id IN (
                   SELECT session_instance_id FROM session_instance WHERE session_id = %s
               )""",
            (person_id, session_id)
        )
        # TODO: Add session_instance_person history tracking with proper record_id tuple

        # Complete the orphan cleanup if needed
        if not has_user_account and other_sessions_count == 0:
            # No other session associations - delete the person record entirely
            
            # First delete person_instrument records
            cur.execute(
                "DELETE FROM person_instrument WHERE person_id = %s",
                (person_id,)
            )
            # TODO: Add person_instrument history tracking with proper record_id tuple
            
            # Then delete the person record
            cur.execute(
                "DELETE FROM person WHERE person_id = %s",
                (person_id,)
            )
            save_to_history(
                cur,
                "person",
                "DELETE",
                person_id,
                user_id=get_current_user_id(),
            )
            person_deleted = True

        conn.commit()
        
        response_data = {"success": True}
        if person_deleted:
            response_data["message"] = "Member removed from session and person record deleted (no other session associations)"
        else:
            response_data["message"] = "Member successfully removed from session"
            
        return jsonify(response_data)

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@api_login_required
def leave_session_membership(session_path):
    """Allow user to remove themselves from a session membership.

    This only removes them from session_person (membership), preserving
    all historical data like attendance records in session_instance_person.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get session ID
        cur.execute("SELECT session_id, name FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id, session_name = session_result
        person_id = current_user.person_id

        # Check if user is actually a member of this session
        cur.execute(
            "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id)
        )
        if not cur.fetchone():
            return jsonify({"success": False, "message": "You are not a member of this session"}), 404

        # Remove from session_person table only (preserves attendance history)
        cur.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id)
        )

        conn.commit()

        return jsonify({
            "success": True,
            "message": f"You have been removed from {session_name}"
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@api_login_required
def terminate_session(session_path):
    """Set the termination date for a session"""
    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        termination_date = data.get("termination_date")

        if not termination_date:
            return (
                jsonify({"success": False, "error": "Termination date is required"}),
                400,
            )

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "error": "Session not found"}), 404

        session_id = session_result[0]

        # Update the termination date
        cur.execute(
            """
            UPDATE session
            SET termination_date = %s
            WHERE session_id = %s
        """,
            (termination_date, session_id),
        )

        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Failed to update session"}), 404

        # Save to history
        save_to_history(
            cur,
            "session",
            "UPDATE",
            session_id,
            user_id=get_current_user_id(),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def reactivate_session(session_path):
    """Clear the termination date for a session to reactivate it"""
    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "error": "Session not found"}), 404

        session_id = session_result[0]

        # Clear the termination date
        cur.execute(
            """
            UPDATE session
            SET termination_date = NULL
            WHERE session_id = %s
        """,
            (session_id,),
        )

        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Failed to update session"}), 404

        # Save to history
        save_to_history(
            cur, "session", "UPDATE", session_id, user_id=get_current_user_id()
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def match_tune_core(cur, session_id, tune_name, previous_tune_type=None, limit=5):
    """Shared tune-name matcher used by BOTH the legacy pill editor (match_tune_ajax)
    and the live logger (live_match), so a typed string resolves IDENTICALLY in both.

    Returns: {matched, exact_match, results:[{tune_id, tune_name, tune_type, in_session_tune}]}.
      - exact_match=True with one result when find_matching_tune resolves a unique exact
        match (session aliases -> session_tune_alias -> tune name w/ "The", accent-insensitive).
      - otherwise a wildcard candidate list ranked by preferred type, this session's
        play-count, then tunebook count (the "pick one" / red state on the client).
    """
    tune_name = normalize_quotes((tune_name or "").strip())
    if not tune_name:
        return {"matched": False, "exact_match": False, "results": []}

    tune_id, final_name, error_message = find_matching_tune(cur, session_id, tune_name)
    if tune_id and not error_message:
        cur.execute(
            "SELECT t.tune_type, (st.session_id IS NOT NULL) "
            "FROM tune t LEFT JOIN session_tune st ON st.tune_id = t.tune_id AND st.session_id = %s "
            "WHERE t.tune_id = %s",
            (session_id, tune_id),
        )
        row = cur.fetchone()
        return {
            "matched": True,
            "exact_match": True,
            "results": [{
                "tune_id": tune_id,
                "tune_name": final_name,
                "tune_type": row[0] if row else None,
                "in_session_tune": bool(row[1]) if row else False,
            }],
        }

    # Wildcard candidate list. Split into two branches so the catalog-wide name search is
    # index-backed (idx_tune_name_trgm via tune_search_key) instead of a full scan; session
    # aliases (small, session-scoped) are matched separately. This preserves the original
    # COALESCE(st.alias, t.name) semantics exactly: a tune with a session alias is searched
    # by its alias, a tune without one by its name.
    like_pattern = f"%{tune_name.lower()}%"
    cur.execute(
        """
        WITH cand AS (
            -- name branch: effective search target is the tune name (no session alias)
            SELECT t.tune_id, t.name AS display_name, t.tune_type, t.tunebook_count_cached
            FROM tune t
            LEFT JOIN session_tune st ON st.tune_id = t.tune_id AND st.session_id = %s
            WHERE t.redirect_to_tune_id IS NULL
              AND st.alias IS NULL
              AND tune_search_key(t.name) LIKE %s
            UNION
            -- alias branch: session-scoped, small
            SELECT t.tune_id, st.alias AS display_name, t.tune_type, t.tunebook_count_cached
            FROM session_tune st
            JOIN tune t ON t.tune_id = st.tune_id
            WHERE st.session_id = %s
              AND st.alias IS NOT NULL
              AND t.redirect_to_tune_id IS NULL
              AND tune_search_key(st.alias) LIKE %s
        )
        SELECT c.tune_id, c.display_name, c.tune_type,
               CASE WHEN c.tune_type = %s THEN 0 ELSE 1 END AS preferred_tune_type,
               pc.plays, (st2.session_id IS NOT NULL) AS in_session
        FROM cand c
        LEFT JOIN session_tune st2 ON st2.tune_id = c.tune_id AND st2.session_id = %s
        LEFT JOIN (
            SELECT sit.tune_id, COUNT(*) AS plays
            FROM session_instance si
            INNER JOIN session_instance_tune sit ON si.session_instance_id = sit.session_instance_id
            WHERE si.session_id = %s
            GROUP BY sit.tune_id
        ) pc ON pc.tune_id = c.tune_id
        ORDER BY preferred_tune_type ASC,
                 pc.plays DESC NULLS LAST,
                 c.tunebook_count_cached DESC NULLS LAST,
                 LOWER(unaccent(c.display_name)) ASC
        LIMIT %s
        """,
        (session_id, like_pattern, session_id, like_pattern,
         previous_tune_type, session_id, session_id, limit),
    )
    results = [
        {"tune_id": m[0], "tune_name": m[1], "tune_type": m[2], "in_session_tune": bool(m[5])}
        for m in cur.fetchall()
    ]
    return {"matched": len(results) == 1, "exact_match": False, "results": results}


@api_login_required
def match_tune_ajax(session_path, date_or_id):
    """
    Match a tune name against the database without saving anything.
    Used by the beta tune pill editor for auto-matching typed text.
    Returns either a single exact match or up to 5 possible matches with wildcard search.

    NOTE: date_or_id parameter accepted for API consistency but not currently used
    (matching is session-scoped, not instance-scoped).
    """
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    tune_name = normalize_quotes(request.json.get("tune_name", "").strip())
    previous_tune_type = request.json.get(
        "previous_tune_type", None
    )  # For preferencing matching tune types in sets
    if not tune_name:
        return jsonify({"success": False, "message": "Please provide a tune name"})

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id for this session_path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        # Shared matcher (also used by the live logger) so results are identical.
        result = match_tune_core(cur, session_result[0], tune_name, previous_tune_type, limit=5)
        cur.close()
        conn.close()
        return jsonify({"success": True, **result})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def test_match_tune_ajax(session_path, date):
    """
    Test endpoint for the enhanced match_tune functionality.
    Accepts GET requests with query parameters for easier testing.
    """
    tune_name = normalize_quotes(request.args.get("tune_name", "").strip())
    previous_tune_type = request.args.get("previous_tune_type", None)

    if not tune_name:
        return jsonify(
            {"success": False, "message": "Please provide a tune_name query parameter"}
        )

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the session_id from the session_path and date
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()

        if not session_result:
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Use find_matching_tune from database module
        result = find_matching_tune(cur, tune_name, previous_tune_type, session_id)

        cur.close()
        conn.close()

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def ensure_tune_exists_in_table(cur, tune_id, user_provided_name):
    """
    Ensure a tune exists in the tune table. If not, fetch from thesession.org.

    Returns:
        tuple: (success, error_message, final_name_for_alias, new_tune_api_data)
            - success: True if tune exists/was created, False if failed
            - error_message: Error message if failed, None if successful
            - final_name_for_alias: Name to use as alias if different from API name
            - new_tune_api_data: If a new tune was inserted, the API data for caching settings
                                 (caller should cache after commit); None if tune already existed
    """
    if not tune_id:
        return True, None, None, None  # No tune_id to validate

    try:
        # Check if tune already exists in tune table
        cur.execute("SELECT name FROM tune WHERE tune_id = %s", (tune_id,))
        tune_exists = cur.fetchone()

        if tune_exists:
            # Tune exists, determine if we need an alias
            api_name = tune_exists[0]
            alias_needed = user_provided_name and user_provided_name != api_name
            return True, None, user_provided_name if alias_needed else None, None

        # Tune doesn't exist, fetch from thesession.org
        api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
        response = requests.get(api_url, timeout=10)

        if response.status_code == 404:
            return False, f"Tune #{tune_id} not found on thesession.org", None, None
        elif response.status_code != 200:
            return False, f"Failed to fetch tune data from thesession.org (status: {response.status_code})", None, None

        data = response.json()

        # Extract required fields
        if "name" not in data or "type" not in data:
            return False, "Invalid tune data received from thesession.org", None, None

        tune_name_from_api = data["name"]
        tune_type = data["type"].title()  # Convert to title case
        tunebook_count = data.get("tunebooks", 0)  # Default to 0 if not present

        # Track if we actually inserted a new tune
        new_tune_inserted = False

        # Try to insert new tune into tune table (handle race condition gracefully)
        try:
            cur.execute(
                """
                INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date, created_by_user_id)
                VALUES (%s, %s, %s, %s, CURRENT_DATE, %s)
            """,
                (tune_id, tune_name_from_api, tune_type, tunebook_count, get_current_user_id()),
            )

            # Save the newly inserted tune to history
            save_to_history(cur, "tune", "INSERT", tune_id, user_id=get_current_user_id())
            new_tune_inserted = True

            # NOTE: Setting caching is NOT done here because we haven't committed yet.
            # The caller must cache the setting after commit using the returned api_data.

        except Exception as insert_error:
            # Check if this was a duplicate key error (race condition - someone else inserted it)
            if "duplicate key" in str(insert_error).lower() or "already exists" in str(insert_error).lower():
                # Someone else inserted it, that's fine - just get the name they used
                cur.execute("SELECT name FROM tune WHERE tune_id = %s", (tune_id,))
                existing_tune = cur.fetchone()
                if existing_tune:
                    tune_name_from_api = existing_tune[0]
                else:
                    return False, f"Race condition error inserting tune {tune_id}", None, None
            else:
                # Some other database error
                return False, f"Database error inserting tune {tune_id}: {str(insert_error)}", None, None

        # Determine if we need to use an alias
        alias_needed = user_provided_name and user_provided_name != tune_name_from_api
        # Return api_data only if we inserted a new tune (so caller can cache settings after commit)
        return True, None, user_provided_name if alias_needed else None, data if new_tune_inserted else None

    except requests.exceptions.Timeout:
        return False, "Timeout connecting to thesession.org", None, None
    except requests.exceptions.RequestException as e:
        return False, f"Error connecting to thesession.org: {str(e)}", None, None
    except Exception as e:
        return False, f"Error processing tune data: {str(e)}", None, None


@api_login_required
def save_session_instance_tunes_ajax(session_path, date_or_id):
    """
    Save the complete tune list for a session instance from the beta page.
    Minimizes database modifications by only updating/inserting/deleting where necessary.
    Accepts either date (YYYY-MM-DD) or numeric ID.
    """
    try:
        data = request.get_json()
        tune_sets = data.get("tune_sets", [])

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"})

        session_id = session_result[0]

        # Get session_instance_id (works with both date and ID)
        session_instance_id = get_session_instance_id(cur, session_id, date_or_id)
        if not session_instance_id:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        # One-way lock (spec 024 beta): refuse if the live editor owns this instance —
        # this bulk save hard-deletes rows absent from its set and emits no events, which
        # would silently destroy live-editor data.
        if instance_logging_locked(cur, session_instance_id):
            cur.close(); conn.close()
            return jsonify({"success": False, "locked": True, "message": LEGACY_LOCKED_MSG}), 409

        # Get all existing tunes for this session instance. Break records are reconciled
        # separately (they have no stable client identity), so only diff tune rows here.
        cur.execute(
            """
            SELECT session_instance_tune_id, tune_id, name, started_by_person_id, order_position
            FROM session_instance_tune
            WHERE session_instance_id = %s AND record_type = 'tune'
            ORDER BY order_position
        """,
            (session_instance_id,),
        )

        existing_tunes = cur.fetchall()
        # Dict by session_instance_tune_id for identity-based matching
        # Row shape: (sit_id, tune_id, name, started_by_person_id, order_position)
        existing_by_id = {row[0]: row for row in existing_tunes}

        # Build new tune list from the sets
        new_tunes = []

        for set_idx, tune_set in enumerate(tune_sets):
            # First pass: collect all started_by_person_id values in this set
            set_started_by_values = []
            for tune_data in tune_set:
                started_by = tune_data.get("started_by_person_id")
                if started_by:
                    set_started_by_values.append(started_by)

            # Calculate majority started_by for propagation
            # (most common value, or None if no values exist)
            majority_started_by = None
            if set_started_by_values:
                value_counts = Counter(set_started_by_values)
                majority_started_by = value_counts.most_common(1)[0][0]

            for tune_idx, tune_data in enumerate(tune_set):
                # Extract tune data
                tune_id = tune_data.get("tune_id")
                tune_name = tune_data.get("name") or tune_data.get("tune_name")

                # Extract started_by_person_id, propagate if not set
                started_by_person_id = tune_data.get("started_by_person_id")
                if not started_by_person_id and majority_started_by:
                    # Propagate majority value to tunes without a value
                    started_by_person_id = majority_started_by

                # Ensure we have either tune_id or name (required by database constraint)
                if not tune_id and not tune_name:
                    # Skip empty pills or provide a default name
                    tune_name = "Unknown tune"

                # Keep the user-provided name even if there's a tune_id
                # This allows us to save aliases
                # Only set tune_name to None if there's a tune_id AND no user-provided name
                if tune_id and not tune_name:
                    tune_name = None

                # Get session_instance_tune_id and order_position from frontend
                session_instance_tune_id = tune_data.get("session_instance_tune_id")
                order_position = tune_data.get("order_position")

                new_tunes.append(
                    {
                        "tune_id": tune_id,
                        "name": tune_name,
                        "set_idx": set_idx,
                        "started_by_person_id": started_by_person_id,
                        "session_instance_tune_id": session_instance_tune_id,
                        "order_position": order_position,
                    }
                )

        # Validate and ensure all linked tunes exist in the tune table
        # This handles the race condition where tunes were linked but may not exist yet
        tunes_to_add_to_session = {}  # Dict to track unique tunes we need to add to session_tune table (tune_id -> alias_name)
        aliases_to_create = []  # Track aliases we need to add to session_tune_alias table
        new_tunes_to_cache = []  # Track newly inserted tunes that need setting cache after commit

        for new_tune in new_tunes:
            tune_id = new_tune.get("tune_id")
            user_provided_name = new_tune.get("name")

            if tune_id:
                # A merged-away id remaps to the canonical tune (spec 030): a stale
                # save means the merged tune, so proceed rather than reject the batch.
                # The user-provided name rides along, preserving the displayed name.
                cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
                redirect_check = cur.fetchone()
                if redirect_check and redirect_check[0] is not None:
                    tune_id = redirect_check[0]
                    new_tune["tune_id"] = tune_id

                # Ensure tune exists in tune table, get alias info and API data for new tunes
                success, error_message, alias_name, new_tune_api_data = ensure_tune_exists_in_table(cur, tune_id, user_provided_name)

                if not success:
                    cur.close()
                    conn.close()
                    return jsonify({"success": False, "message": f"Failed to validate tune #{tune_id}: {error_message}"})

                # Track new tunes that need setting cache after commit
                if new_tune_api_data:
                    new_tunes_to_cache.append((tune_id, new_tune_api_data))

                # Check if tune needs to be added to session_tune table
                cur.execute(
                    "SELECT tune_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
                    (session_id, tune_id)
                )
                if not cur.fetchone():
                    # Use dict to automatically deduplicate if same tune appears multiple times
                    tunes_to_add_to_session[tune_id] = alias_name

                # If there's an alias, track it to add to session_tune_alias table
                if alias_name:
                    # Check if this alias already exists
                    cur.execute(
                        """
                        SELECT session_tune_alias_id FROM session_tune_alias
                        WHERE session_id = %s AND alias = %s
                        """,
                        (session_id, alias_name)
                    )
                    existing_alias = cur.fetchone()

                    if not existing_alias:
                        # New alias - add it to our list
                        aliases_to_create.append((session_id, tune_id, alias_name))
                    else:
                        # Alias exists - verify it points to the same tune_id
                        cur.execute(
                            """
                            SELECT tune_id FROM session_tune_alias
                            WHERE session_tune_alias_id = %s
                            """,
                            (existing_alias[0],)
                        )
                        existing_tune_id = cur.fetchone()
                        if existing_tune_id and existing_tune_id[0] != tune_id:
                            # Alias exists but points to a different tune - this is an error
                            cur.close()
                            conn.close()
                            return jsonify({
                                "success": False,
                                "message": f"Alias '{alias_name}' already exists for a different tune in this session"
                            })

        # Begin transaction
        cur.execute("BEGIN")

        try:
            modifications = 0

            # Add any missing tunes to session_tune table
            for tune_id, alias_name in tunes_to_add_to_session.items():
                try:
                    cur.execute(
                        """
                        INSERT INTO session_tune (session_id, tune_id, alias, setting_id, created_by_user_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (session_id, tune_id) DO NOTHING
                    """,
                        (session_id, tune_id, alias_name, None, get_current_user_id()),
                    )
                    # Only save to history and count modification if row was actually inserted
                    if cur.rowcount > 0:
                        save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id), user_id=get_current_user_id())
                        modifications += 1
                except Exception as e:
                    # Log the error but continue - this shouldn't fail the entire save
                    print(f"Warning: Failed to insert tune {tune_id} into session_tune: {str(e)}")
                    # If it's already there, that's fine; if it's a different error, we'll catch it in the outer try-except

            # Add any new aliases to session_tune_alias table
            for session_id_val, tune_id, alias_name in aliases_to_create:
                cur.execute(
                    """
                    INSERT INTO session_tune_alias (session_id, tune_id, alias, created_by_user_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (session_id_val, tune_id, alias_name, get_current_user_id()),
                )
                modifications += 1

            # Track which existing tunes are still present
            remaining_tune_ids = set()

            # First pass: determine order_positions for all tunes
            # For existing tunes, use their database order_position (NEVER change it)
            # For new tunes, generate order_position based on neighbors
            processed_tunes = []
            for idx, new_tune in enumerate(new_tunes):
                if not new_tune:
                    continue

                sit_id = new_tune.get("session_instance_tune_id")

                if sit_id and sit_id in existing_by_id:
                    # Existing tune - use order_position from database
                    existing = existing_by_id[sit_id]
                    remaining_tune_ids.add(sit_id)
                    processed_tunes.append({
                        **new_tune,
                        "order_position": existing[4],  # Get order_position from DB
                        "is_new": False,
                    })
                else:
                    # New tune - will generate order_position based on neighbors
                    processed_tunes.append({
                        **new_tune,
                        "order_position": None,  # Will be calculated
                        "is_new": True,
                    })

            # Check if existing tunes have been reordered
            # If existing positions are not in sorted order, we need to rebalance
            MAX_POSITION_LENGTH = 32
            needs_rebalance = False

            existing_positions = [t["order_position"] for t in processed_tunes if not t.get("is_new", False)]
            if existing_positions != sorted(existing_positions):
                # Existing tunes were reordered - must regenerate all positions
                needs_rebalance = True

            # Second pass: generate order_positions for new tunes (if no rebalance needed)
            if not needs_rebalance:
                for idx, tune in enumerate(processed_tunes):
                    if not tune["is_new"]:
                        continue

                    # Find prev and next order_positions
                    prev_position = None
                    next_position = None
                    prev_is_new = False

                    # Look backward for prev position
                    for j in range(idx - 1, -1, -1):
                        if processed_tunes[j]["order_position"]:
                            prev_position = processed_tunes[j]["order_position"]
                            prev_is_new = processed_tunes[j].get("is_new", False)
                            break

                    # Look forward for next position (only from existing tunes)
                    for j in range(idx + 1, len(processed_tunes)):
                        if processed_tunes[j]["order_position"] and not processed_tunes[j].get("is_new", False):
                            next_position = processed_tunes[j]["order_position"]
                            break

                    # If previous tune was also new, use sequential append instead of bisect
                    # This gives us JI, JJ, JK instead of JI, JII, JIII
                    if prev_is_new and prev_position:
                        new_position = generate_append_position(prev_position)
                        # Make sure it's still less than next_position
                        if next_position and new_position >= next_position:
                            # Fall back to bisect if append would exceed next
                            new_position = generate_position_between(prev_position, next_position)
                    else:
                        # First new tune in a sequence - bisect between existing positions
                        new_position = generate_position_between(prev_position, next_position)

                    # Check if position is too long - if so, we need to rebalance all positions
                    if len(new_position) > MAX_POSITION_LENGTH:
                        needs_rebalance = True
                        break

                    tune["order_position"] = new_position

            # If any position would be too long, regenerate ALL positions from scratch
            if needs_rebalance:
                current_position = None
                for tune in processed_tunes:
                    current_position = generate_append_position(current_position)
                    tune["order_position"] = current_position
                    tune["position_changed"] = True  # Mark for position update

            # Third pass: perform database operations
            for tune in processed_tunes:
                sit_id = tune.get("session_instance_tune_id")

                # name is override-only: the pill client echoes the resolved display
                # name for every pill, linked or not. Normalize (after the session_tune/
                # alias inserts above, so a just-created alias counts) before diffing,
                # so a redundant copy neither persists nor reads as a change — else
                # every legacy save would rewrite all linked rows and their history.
                if tune["tune_id"]:
                    tune["name"] = normalize_override_name(cur, session_id, tune["tune_id"], tune["name"])

                if tune["is_new"]:
                    # Insert new record with generated order_position
                    cur.execute(
                        """
                        INSERT INTO session_instance_tune
                        (session_instance_id, tune_id, name, record_type, started_by_person_id, order_position, created_date, last_modified_date, created_by_user_id)
                        VALUES (%s, %s, %s, 'tune', %s, %s, NOW(), NOW(), %s)
                        RETURNING session_instance_tune_id
                    """,
                        (
                            session_instance_id,
                            tune["tune_id"],
                            tune["name"],
                            tune["started_by_person_id"],
                            tune["order_position"],
                            get_current_user_id(),
                        ),
                    )

                    result = cur.fetchone()
                    if result:
                        new_id = result[0]
                        save_to_history(cur, "session_instance_tune", "INSERT", new_id, user_id=get_current_user_id())
                        modifications += 1
                else:
                    # Existing tune - check what needs updating
                    existing = existing_by_id[sit_id]
                    # existing: (sit_id, tune_id, name, started_by_person_id, order_position)
                    position_changed = tune.get("position_changed", False)
                    data_changed = (
                        existing[1] != tune["tune_id"]
                        or existing[2] != tune["name"]
                        or existing[3] != tune["started_by_person_id"]
                    )

                    if data_changed or position_changed:
                        save_to_history(
                            cur, "session_instance_tune", "UPDATE", sit_id, user_id=get_current_user_id()
                        )

                        if position_changed:
                            # Update everything INCLUDING order_position (rebalance case)
                            cur.execute(
                                """
                                UPDATE session_instance_tune
                                SET tune_id = %s, name = %s, started_by_person_id = %s,
                                    order_position = %s, last_modified_date = NOW(), last_modified_user_id = %s
                                WHERE session_instance_tune_id = %s
                            """,
                                (
                                    tune["tune_id"],
                                    tune["name"],
                                    tune["started_by_person_id"],
                                    tune["order_position"],
                                    get_current_user_id(),
                                    sit_id,
                                ),
                            )
                        else:
                            # Update everything EXCEPT order_position (normal case)
                            cur.execute(
                                """
                                UPDATE session_instance_tune
                                SET tune_id = %s, name = %s, started_by_person_id = %s,
                                    last_modified_date = NOW(), last_modified_user_id = %s
                                WHERE session_instance_tune_id = %s
                            """,
                                (
                                    tune["tune_id"],
                                    tune["name"],
                                    tune["started_by_person_id"],
                                    get_current_user_id(),
                                    sit_id,
                                ),
                            )
                        modifications += 1

            # Delete tunes that are no longer in the list
            for existing in existing_tunes:
                if existing[0] not in remaining_tune_ids:
                    save_to_history(cur, "session_instance_tune", "DELETE", existing[0], user_id=get_current_user_id())
                    cur.execute(
                        """
                        DELETE FROM session_instance_tune
                        WHERE session_instance_tune_id = %s
                    """,
                        (existing[0],),
                    )
                    modifications += 1

            # Reconcile break records: derive one break per set from the final tune
            # positions (interior breaks plus a trailing break that closes the last set).
            sets_positions = {}
            for tune in processed_tunes:
                sets_positions.setdefault(tune["set_idx"], []).append(tune["order_position"])
            set_position_lists = [sorted(positions) for positions in sets_positions.values()]
            reconcile_break_records(
                cur, session_instance_id, set_position_lists, get_current_user_id()
            )

            # Commit transaction
            cur.execute("COMMIT")

            # Fetch the updated tune list to return to frontend
            # This allows the frontend to sync session_instance_tune_id and order_position values
            cur.execute(
                """
                SELECT
                    sit.record_type,
                    sit.tune_id,
                    COALESCE(sit.name, st.alias, t.name) AS tune_name,
                    COALESCE(sit.setting_override, st.setting_id) AS setting,
                    t.tune_type,
                    sit.started_by_person_id,
                    created_by_person.last_name,
                    created_by_person.first_name,
                    sit.order_position,
                    sit.session_instance_tune_id
                FROM session_instance_tune sit
                LEFT JOIN tune t ON sit.tune_id = t.tune_id
                LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = %s
                LEFT JOIN person created_by_person ON sit.started_by_person_id = created_by_person.person_id
                WHERE sit.session_instance_id = %s
                ORDER BY sit.order_position
                """,
                (session_id, session_instance_id),
            )
            updated_tunes = cur.fetchall()

            # Group by break records, then rebuild each tune row with a synthesized
            # continues_set at index 0 (False for the first tune of a set) to preserve the
            # response shape the frontend expects.
            # row: (record_type, tune_id, tune_name, setting, tune_type,
            #       started_by_person_id, last_name, first_name, order_position, session_instance_tune_id)
            tune_sets = []
            for tune_set in segment_records_into_sets(updated_tunes, type_index=0):
                tune_sets.append([
                    [
                        tune_idx > 0,   # continues_set (synthesized)
                        row[1],   # tune_id
                        row[2],   # tune_name
                        row[3] or '',   # setting
                        row[4] or '',   # tune_type
                        row[5],   # started_by_person_id
                        row[6],   # last_name
                        row[7],   # first_name
                        row[8],   # order_position
                        row[9],   # session_instance_tune_id
                    ]
                    for tune_idx, row in enumerate(tune_set)
                ])

            cur.close()
            conn.close()

            # Cache settings for any newly inserted tunes (must happen after commit)
            for tune_id, api_data in new_tunes_to_cache:
                cache_default_tune_setting(tune_id, api_data, get_current_user_id(), sync=True)

            return jsonify(
                {
                    "success": True,
                    "message": f"Session saved successfully ({modifications} modifications)",
                    "modifications": modifications,
                    "tune_sets": tune_sets,  # Return updated tunes for frontend sync
                    "rebalanced": needs_rebalance,  # True if positions were regenerated
                }
            )

        except Exception as e:
            cur.execute("ROLLBACK")
            raise e

    except Exception as e:
        if "cur" in locals():
            cur.close()
        if "conn" in locals():
            conn.close()
        return jsonify(
            {"success": False, "message": f"Failed to save session: {str(e)}"}
        )


def update_auto_save_preference():
    """Update the auto-save preference for logged-in users"""
    try:
        # Check if user is logged in
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "User not authenticated"}), 401

        # Get the preference value from request
        data = request.get_json()
        auto_save = data.get("auto_save", False)
        auto_save_interval = data.get("auto_save_interval", 60)
        
        # Validate interval value
        if auto_save_interval not in [10, 30, 60]:
            auto_save_interval = 60

        # Update user preference in database
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE user_account
            SET auto_save_tunes = %s,
                auto_save_interval = %s,
                last_modified_date = NOW() AT TIME ZONE 'UTC'
            WHERE user_id = %s
        """,
            (auto_save, auto_save_interval, current_user.user_id),
        )

        save_to_history(cur, "user_account", "UPDATE", current_user.user_id, user_id=current_user.user_id)

        cur.close()
        conn.commit()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": "Auto-save preference updated",
                "auto_save": auto_save,
                "auto_save_interval": auto_save_interval,
            }
        )

    except Exception as e:
        if "conn" in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


# Session Attendance API Endpoints

def can_view_attendance(session_instance_id, user_person_id):
    """May this user see who was at this instance? (spec 034)

    `is_admin OR confirmed` on the parent session -- the same single predicate as
    can_view_session_people, just reached via an instance id.

    Two clauses were removed here, and both were self-grants:
      * `is_regular OR is_admin` -- is_regular is gone, and it disagreed with auth.py's
        version of this same check, which granted access to any member.
      * "...or you are attending this instance" -- checking IN to a session must not hand you
        its attendance list. Self-check-in exists, so that clause let anyone who turned up
        (or said they might) read the roster. Being present is not the session vouching for
        you; only an admin confirming you is.
    """
    if not current_user.is_authenticated:
        return False

    if current_user.is_system_admin:
        return True

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT session_id FROM session_instance WHERE session_instance_id = %s",
            (session_instance_id,),
        )
        session_result = cur.fetchone()
        if not session_result:
            return False

        return can_view_session_people(cur, session_result[0], user_person_id)

    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


@api_login_required
def get_session_attendees(session_instance_id):
    """Get attendance list for a session instance"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # First verify session instance exists (before checking permissions)
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "error": "Session instance not found"}), 404
        
        user_person_id = current_user.person_id if hasattr(current_user, 'person_id') else None
        
        # Check permissions
        if not can_view_attendance(session_instance_id, user_person_id):
            return jsonify({"success": False, "error": "Not authorized to view attendance"}), 403
        
        session_id = session_result[0]
        
        # Get all attendees who have been explicitly added to this session instance
        # Don't pre-populate with regulars - only show those who have actually been added
        cur.execute("""
            SELECT DISTINCT
                p.person_id,
                p.first_name,
                p.last_name,
                sip.attendance,
                sip.comment,
                COALESCE(sp.relationship, 'visitor') as relationship,
                COALESCE(sp.is_admin, false) as is_admin,
                ARRAY_AGG(pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL) as instruments
            FROM person p
            JOIN session_instance_person sip ON p.person_id = sip.person_id
            LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
            LEFT JOIN person_instrument pi ON p.person_id = pi.person_id
            WHERE sip.session_instance_id = %s
            GROUP BY p.person_id, p.first_name, p.last_name, sip.attendance, sip.comment, sp.relationship, sp.is_admin
            ORDER BY p.first_name, p.last_name
        """, (session_id, session_instance_id))

        attendees_data = cur.fetchall()
        attendees = []

        for row in attendees_data:
            person_id, first_name, last_name, attendance, comment, relationship, is_admin, instruments = row
            attendees.append({
                'person_id': person_id,
                'first_name': first_name,
                'last_name': last_name,
                'display_name': f"{first_name} {last_name[0]}" if last_name else first_name,
                'instruments': instruments or [],
                'attendance': attendance,
                'relationship': relationship,
                'is_admin': is_admin,
                'comment': comment
            })

        # Return empty for regulars since we're not pre-populating
        regulars = []
        
        # Combine all attendees for disambiguation
        all_attendees = regulars + attendees
        
        # Handle display name disambiguation
        display_name_counts = {}
        for attendee in all_attendees:
            display_name = attendee['display_name']
            if display_name in display_name_counts:
                display_name_counts[display_name].append(attendee)
            else:
                display_name_counts[display_name] = [attendee]
        
        # Apply disambiguation to duplicates
        for display_name, attendees_with_name in display_name_counts.items():
            if len(attendees_with_name) > 1:
                # Sort by person_id for consistent disambiguation
                attendees_with_name.sort(key=lambda x: x['person_id'])
                for i, attendee in enumerate(attendees_with_name):
                    # Add person_id for disambiguation
                    attendee['display_name'] = f"{attendee['first_name']} {attendee['last_name'][0]} (#{attendee['person_id']})"
        
        # Remove temporary fields used for disambiguation
        for attendee in all_attendees:
            attendee.pop('first_name', None)
            attendee.pop('last_name', None)
        
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "regulars": regulars,
                "attendees": attendees
            }
        })
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def check_in_person(session_instance_id):
    """
    Check a person into a session instance or update their attendance status.
    
    Expected JSON payload:
    {
        "person_id": int,
        "attendance": "yes" | "maybe" | "no",
        "comment": "optional comment"
    }
    
    Returns JSON response with success status.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No JSON data provided"}), 400
        
        person_id = data.get('person_id')
        attendance = data.get('attendance')
        comment = data.get('comment', '')
        
        # Validate required fields
        if not person_id or not attendance:
            return jsonify({"success": False, "message": "person_id and attendance are required"}), 400
        
        # Validate attendance value
        valid_attendance = ['yes', 'maybe', 'no']
        if attendance not in valid_attendance:
            return jsonify({"success": False, "message": f"attendance must be one of: {valid_attendance}"}), 400
        
        # Get database connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if session instance exists
        cur.execute(
            "SELECT session_id FROM session_instance WHERE session_instance_id = %s",
            (session_instance_id,)
        )
        
        result = cur.fetchone()
        if not result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"}), 404
        
        session_id = result[0]
        
        # Check if person exists and is active
        cur.execute(
            "SELECT person_id, first_name, last_name, active FROM person WHERE person_id = %s",
            (person_id,)
        )

        person_result = cur.fetchone()
        if not person_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Person not found"}), 404

        person_active = person_result[3]
        if not person_active:
            person_name = f"{person_result[1]} {person_result[2]}"
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": f"{person_name} is deactivated and cannot be checked in"}), 400

        # Permission check - need to verify user can manage this person's attendance
        current_user_id = current_user.user_id
        current_person_id = current_user.person_id
        
        # Get current user's admin status for this session
        cur.execute(
            """
            SELECT is_admin 
            FROM session_person 
            WHERE session_id = %s AND person_id = %s
            """,
            (session_id, current_person_id)
        )
        
        user_session_record = cur.fetchone()
        is_session_member = user_session_record is not None
        is_system_admin = current_user.is_system_admin
        is_self_checkin = (person_id == current_person_id)

        # Permission rules:
        # - System admins can manage anyone
        # - Session members can manage anyone in their session
        # - Regular users can only manage themselves
        if not (is_system_admin or is_session_member or is_self_checkin):
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Insufficient permissions to manage this person's attendance"}), 403
        
        # Close the connection since we'll use the database function
        cur.close()
        conn.close()
        
        # Call the database function to handle the actual database operations
        success, message, action = db_check_in_person(
            session_instance_id,
            person_id,
            attendance,
            comment,
            user_id=current_user_id,
        )
        
        if not success:
            return jsonify({"success": False, "message": message}), 500
        
        # Get full attendee information for response (as per test contract)
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Get person details and instruments
            cur.execute("""
                SELECT p.person_id, p.first_name, p.last_name, p.email,
                       COALESCE(sp.relationship, 'visitor') as relationship,
                       COALESCE(
                           array_agg(pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                           '{}'::text[]
                       ) as instruments
                FROM person p
                LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
                LEFT JOIN person_instrument pi ON p.person_id = pi.person_id
                WHERE p.person_id = %s
                GROUP BY p.person_id, p.first_name, p.last_name, p.email, sp.relationship
            """, (session_id, person_id))
            
            attendee_data = cur.fetchone()
            if not attendee_data:
                return jsonify({"success": False, "message": "Person not found"}), 404
            
            # Format display name
            first_name, last_name = attendee_data[1], attendee_data[2]
            display_name = f"{first_name} {last_name}".strip()
            
            return jsonify({
                "success": True,
                "message": f"Successfully {action} attendance for {display_name}",
                "data": {
                    "person_id": attendee_data[0],
                    "display_name": display_name,
                    "instruments": list(attendee_data[5]),
                    "attendance": attendance,
                    "relationship": attendee_data[4]
                }
            })
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def create_person_with_instruments():
    """
    Create a new person with associated instruments.
    
    Expected JSON payload:
    {
        "first_name": "string",
        "last_name": "string", 
        "email": "string (optional)",
        "instruments": ["instrument1", "instrument2", ...]
    }
    
    Returns JSON response with person data and display name.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No JSON data provided"}), 400
        
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip() or None
        instruments = data.get('instruments', [])
        
        # Validate required fields
        if not first_name or not last_name:
            return jsonify({"success": False, "message": "first_name and last_name are required"}), 400
        
        # Validate email format if provided
        if email:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return jsonify({"success": False, "message": "Invalid email format"}), 400
        
        # Validate instruments list
        if not isinstance(instruments, list):
            return jsonify({"success": False, "message": "instruments must be a list"}), 400
        
        # Canonicalize casing/aliases and de-dupe against one shared vocabulary
        normalized_instruments = normalize_instruments(
            [i for i in instruments if isinstance(i, str)]
        )

        # Check if user has admin permissions (system admin can create people anywhere)
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if current user is a system admin
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        if not user_row or not user_row[0]:
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403
        
        # Check if person with same name already exists (for display name disambiguation)
        cur.execute(
            """
            SELECT person_id, first_name, last_name, email 
            FROM person 
            WHERE LOWER(first_name) = LOWER(%s) AND LOWER(last_name) = LOWER(%s)
            """,
            (first_name, last_name)
        )
        
        existing_people = cur.fetchall()
        
        # Begin transaction
        cur.execute("BEGIN")
        
        try:
            # Insert person
            cur.execute(
                """
                INSERT INTO person (first_name, last_name, email, created_date, created_by_user_id)
                VALUES (%s, %s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
                RETURNING person_id
                """,
                (first_name, last_name, email, current_user.user_id)
            )

            person_id = cur.fetchone()[0]

            # Log person creation to history
            save_to_history(
                cur,
                'person',
                'INSERT',
                person_id,
                user_id=current_user.user_id
            )

            # Insert instruments
            for instrument in normalized_instruments:
                cur.execute(
                    """
                    INSERT INTO person_instrument (person_id, instrument, created_date, created_by_user_id)
                    VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
                    """,
                    (person_id, instrument, current_user.user_id)
                )

                # Log instrument creation to history
                save_to_history(
                    cur,
                    'person_instrument',
                    'INSERT',
                    (person_id, instrument),
                    user_id=current_user.user_id
                )
            
            # Commit transaction
            cur.execute("COMMIT")
            
            # Generate display name (with disambiguation if needed)
            base_name = f"{first_name} {last_name}"
            display_name = base_name
            
            # If there are existing people with same name, add email or ID for disambiguation
            if existing_people:
                if email:
                    display_name = f"{base_name} ({email})"
                else:
                    display_name = f"{base_name} (#{person_id})"
            
            cur.close()
            conn.close()
            
            return jsonify({
                "success": True,
                "message": f"Successfully created person: {display_name}",
                "data": {
                    "person_id": person_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "display_name": display_name,
                    "instruments": normalized_instruments
                }
            }), 201
            
        except Exception as e:
            cur.execute("ROLLBACK")
            raise e
            
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def get_person_instruments(person_id):
    """
    Get all instruments for a specific person.
    
    Returns JSON response with list of instruments.
    """
    try:
        # Get database connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if person exists
        cur.execute(
            "SELECT person_id, first_name, last_name FROM person WHERE person_id = %s",
            (person_id,)
        )
        
        person_result = cur.fetchone()
        if not person_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Person not found"}), 404
        
        # Permission check - can user view this person's instruments?
        current_user_id = current_user.user_id
        current_person_id = current_user.person_id
        is_system_admin = current_user.is_system_admin
        is_self_view = (person_id == current_person_id)
        
        # For viewing instruments, allow:
        # - System admins to view anyone's instruments
        # - Users to view their own instruments
        # Note: We're being restrictive here - only self or system admin can view instruments
        if not (is_system_admin or is_self_view):
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Insufficient permissions to view this person's instruments"}), 403
        
        # Get person's instruments (+ auto/manual flag + how much per-tune data would
        # be lost by removing each one). A removal loses data when it has override rows
        # that re-adding the instrument on Auto would NOT reproduce:
        #   - manual instrument: every override (its curated list) is lost;
        #   - auto instrument: any override whose status differs from the tune's
        #     learn_status (an auto instrument with no override just follows learn_status).
        cur.execute(
            """
            SELECT pi.instrument, pi.is_auto,
                   COUNT(*) FILTER (
                       WHERE pti.tune_id IS NOT NULL
                         AND (NOT pi.is_auto OR pti.status <> pt.learn_status)
                   ) AS removal_loss_count
            FROM person_instrument pi
            LEFT JOIN person_tune_instrument pti
                   ON pti.person_id = pi.person_id
                  AND pti.instrument = pi.instrument
            LEFT JOIN person_tune pt
                   ON pt.person_id = pti.person_id
                  AND pt.tune_id = pti.tune_id
            WHERE pi.person_id = %s
            GROUP BY pi.instrument, pi.is_auto
            ORDER BY pi.instrument
            """,
            (person_id,)
        )

        instrument_results = cur.fetchall()
        instruments = [row[0] for row in instrument_results]           # names (back-compat)
        instruments_detail = [
            {"instrument": row[0], "is_auto": row[1], "removal_loss_count": row[2]}
            for row in instrument_results
        ]

        cur.close()
        conn.close()

        # Get person's name for response
        person_name = f"{person_result[1]} {person_result[2]}"

        return jsonify({
            "success": True,
            "data": instruments,
            "instruments": instruments_detail,
            "meta": {
                "person_id": person_id,
                "person_name": person_name,
                "instrument_count": len(instruments)
            }
        })
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def update_person_instruments(person_id):
    """
    Update all instruments for a specific person.
    
    Expected JSON payload:
    {
        "instruments": ["instrument1", "instrument2", ...]
    }
    
    Returns JSON response with updated instrument list.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No JSON data provided"}), 400
        
        instruments = data.get('instruments', [])
        
        # Validate instruments list
        if not isinstance(instruments, list):
            return jsonify({"success": False, "message": "instruments must be a list"}), 400
        
        # Canonicalize casing/aliases and de-dupe against one shared vocabulary
        normalized_instruments = normalize_instruments(
            [i for i in instruments if isinstance(i, str)]
        )

        # Get database connection
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if person exists
        cur.execute(
            "SELECT person_id, first_name, last_name FROM person WHERE person_id = %s",
            (person_id,)
        )
        
        person_result = cur.fetchone()
        if not person_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Person not found"}), 404
        
        # Permission check - can user manage this person's instruments?
        current_user_id = current_user.user_id
        current_person_id = current_user.person_id
        is_system_admin = current_user.is_system_admin
        is_self_update = (person_id == current_person_id)
        
        # For instrument management, allow:
        # - System admins to manage anyone
        # - Users to manage their own instruments
        # - Session admins to manage anyone in their sessions (we'll be permissive here)
        if not (is_system_admin or is_self_update):
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Insufficient permissions to manage this person's instruments"}), 403
        
        # Get existing instruments for comparison
        cur.execute(
            "SELECT instrument FROM person_instrument WHERE person_id = %s",
            (person_id,)
        )
        
        existing_results = cur.fetchall()
        existing_instruments = set(row[0] for row in existing_results)
        new_instruments = set(normalized_instruments)
        
        # Begin transaction
        cur.execute("BEGIN")
        
        try:
            # Remove instruments no longer in the list
            instruments_to_remove = existing_instruments - new_instruments
            for instrument in instruments_to_remove:
                # Log removal to history (must be called before DELETE)
                save_to_history(
                    cur,
                    'person_instrument',
                    'DELETE',
                    (person_id, instrument),
                    user_id=current_user_id
                )

                cur.execute(
                    "DELETE FROM person_instrument WHERE person_id = %s AND instrument = %s",
                    (person_id, instrument)
                )

                # Removing an instrument also drops its per-tune override rows (nothing
                # else references them once the instrument is gone). Log each to history
                # before deleting so the removal is auditable and reversible.
                cur.execute(
                    "SELECT tune_id FROM person_tune_instrument WHERE person_id = %s AND instrument = %s",
                    (person_id, instrument)
                )
                for (override_tune_id,) in cur.fetchall():
                    save_to_history(
                        cur,
                        'person_tune_instrument',
                        'DELETE',
                        (person_id, override_tune_id, instrument),
                        user_id=current_user_id
                    )
                cur.execute(
                    "DELETE FROM person_tune_instrument WHERE person_id = %s AND instrument = %s",
                    (person_id, instrument)
                )

            # Add new instruments
            instruments_to_add = new_instruments - existing_instruments
            for instrument in instruments_to_add:
                cur.execute(
                    """
                    INSERT INTO person_instrument (person_id, instrument, created_date, created_by_user_id)
                    VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
                    """,
                    (person_id, instrument, current_user_id)
                )

                # Log addition to history
                save_to_history(
                    cur,
                    'person_instrument',
                    'INSERT',
                    (person_id, instrument),
                    user_id=current_user_id
                )
            
            # Commit transaction
            cur.execute("COMMIT")
            
            # Get person's name for response
            person_name = f"{person_result[1]} {person_result[2]}"
            
            cur.close()
            conn.close()
            
            return jsonify({
                "success": True,
                "message": f"Successfully updated instruments for {person_name}",
                "data": {
                    "person_id": person_id,
                    "person_name": person_name,
                    "instruments": sorted(normalized_instruments),
                    "changes": {
                        "added": sorted(list(instruments_to_add)),
                        "removed": sorted(list(instruments_to_remove)),
                        "total_changes": len(instruments_to_add) + len(instruments_to_remove)
                    }
                }
            })
            
        except Exception as e:
            cur.execute("ROLLBACK")
            raise e
            
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def set_person_instrument_auto(person_id):
    """
    PUT /api/person/<id>/instrument-auto

    Set whether one of this person's instruments is "auto" (linked — follows a tune's main
    status) or manual (a curated per-instrument list). Body: {"instrument": ..., "is_auto": bool}.
    Self or system admin only.
    """
    try:
        data = request.get_json(silent=True) or {}
        instrument = (data.get("instrument") or "").strip()
        is_auto = data.get("is_auto")
        if not instrument or not isinstance(is_auto, bool):
            return jsonify({"success": False, "message": "instrument and boolean is_auto are required"}), 400
        if not (current_user.is_system_admin or person_id == current_user.person_id):
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE person_instrument SET is_auto=%s WHERE person_id=%s AND LOWER(instrument)=LOWER(%s)",
                (is_auto, person_id, instrument),
            )
            if cur.rowcount == 0:
                return jsonify({"success": False, "message": "Instrument not found for this person"}), 404
            conn.commit()
        finally:
            cur.close()
            conn.close()
        return jsonify({"success": True, "instrument": instrument, "is_auto": is_auto})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def remove_person_attendance(session_instance_id, person_id):
    """
    Remove a person from a session instance attendance list.
    
    Returns JSON response with success status.
    """
    try:
        # Get database connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if session instance exists
        cur.execute(
            "SELECT session_id FROM session_instance WHERE session_instance_id = %s",
            (session_instance_id,)
        )
        
        result = cur.fetchone()
        if not result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"}), 404
        
        session_id = result[0]
        
        # Check if person exists
        cur.execute(
            "SELECT person_id, first_name, last_name FROM person WHERE person_id = %s",
            (person_id,)
        )
        
        person_result = cur.fetchone()
        if not person_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Person not found"}), 404
        
        # Check if attendance record exists
        cur.execute(
            """
            SELECT attendance, comment, created_date 
            FROM session_instance_person 
            WHERE session_instance_id = %s AND person_id = %s
            """,
            (session_instance_id, person_id)
        )
        
        existing_record = cur.fetchone()
        if not existing_record:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Person is not currently attending this session instance"}), 404
        
        # Permission check - need to verify user can manage this person's attendance
        current_user_id = current_user.user_id
        current_person_id = current_user.person_id
        
        # Get current user's admin status for this session
        cur.execute(
            """
            SELECT is_admin 
            FROM session_person 
            WHERE session_id = %s AND person_id = %s
            """,
            (session_id, current_person_id)
        )
        
        user_session_record = cur.fetchone()
        is_session_member = user_session_record is not None
        is_system_admin = current_user.is_system_admin
        is_self_removal = (person_id == current_person_id)

        # Permission rules:
        # - System admins can remove anyone
        # - Session members can remove anyone from their session
        # - Regular users can only remove themselves
        if not (is_system_admin or is_session_member or is_self_removal):
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Insufficient permissions to remove this person from attendance"}), 403
        
        # Close the connection since we'll use the database function that manages its own connection
        cur.close()
        conn.close()
        
        # Use the database function that handles session_person management
        from database import remove_person_attendance as db_remove_person_attendance
        success, message, previous_data = db_remove_person_attendance(session_instance_id, person_id, current_user_id)
        
        if success:
            # Get person's name for response
            person_name = f"{person_result[1]} {person_result[2]}"
            
            return jsonify({
                "success": True,
                "message": f"Successfully removed {person_name} from attendance",
                "data": {
                    "person_id": person_id,
                    "person_name": person_name,
                    "session_instance_id": session_instance_id,
                    "previous_attendance": previous_data['attendance'],
                    "previous_comment": previous_data['comment']
                }
            })
        else:
            return jsonify({"success": False, "message": message}), 500
            
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def search_session_people(session_id):
    """
    Search for people associated with a session.
    
    Query parameters:
    - q: Search query (name to search for)
    - limit: Maximum number of results (default 20, max 100)
    
    Returns JSON response with list of people matching the search.
    """
    try:
        search_query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 20)), 100)
        
        # Validate search query
        if not search_query:
            return jsonify({"success": False, "message": "Search query 'q' parameter is required"}), 400
        
        if len(search_query) < 2:
            return jsonify({"success": False, "message": "Search query must be at least 2 characters"}), 400
        
        # Get database connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if session exists
        cur.execute(
            "SELECT session_id, name FROM session WHERE session_id = %s",
            (session_id,)
        )
        
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404
        
        # Permission check - can user search people in this session?
        current_person_id = current_user.person_id
        is_system_admin = current_user.is_system_admin
        
        # For searching session people, allow:
        # - System admins to search any session
        # - Users who are associated with the session (regular, admin, or have attended)
        if not is_system_admin:
            # Check if user is associated with this session
            cur.execute("""
                SELECT 1 FROM (
                    -- Check if user is regular/admin for this session
                    SELECT 1 FROM session_person 
                    WHERE session_id = %s AND person_id = %s
                    
                    UNION
                    
                    -- Check if user has attended any instance of this session
                    SELECT 1 FROM session_instance_person sip
                    JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                    WHERE si.session_id = %s AND sip.person_id = %s
                ) AS user_associated
            """, (session_id, current_person_id, session_id, current_person_id))
            
            user_associated = cur.fetchone()
            if not user_associated:
                cur.close()
                conn.close()
                return jsonify({"success": False, "message": "Insufficient permissions to search people in this session"}), 403
        
        # People associated with THIS session (roster or past attendance). Never a global
        # person search -- see spec 034.
        # Spec 034: "regulars first" is computed from attendance now, not a stored flag.
        search_pattern = f"%{search_query.lower()}%"

        cur.execute(
            """
            WITH session_people AS (
                -- Get all people who have been associated with this session
                SELECT DISTINCT p.person_id, p.first_name, p.last_name, p.email,
                       COALESCE(sp.relationship, 'visitor') as relationship,
                       COALESCE(sp.archived, FALSE) as archived,
                       COALESCE(sp.is_admin, FALSE) as is_session_admin
                FROM person p
                LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
                LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id
                LEFT JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                WHERE (sp.session_id = %s OR si.session_id = %s)
                  AND p.active = TRUE
                  AND (LOWER(p.first_name) LIKE %s
                       OR LOWER(p.last_name) LIKE %s
                       OR LOWER(CONCAT(p.first_name, ' ', p.last_name)) LIKE %s)
            ),
            person_instruments AS (
                -- Get instruments for these people
                SELECT sp.person_id,
                       COALESCE(
                           array_agg(pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                           '{}'::text[]
                       ) as instruments
                FROM session_people sp
                LEFT JOIN person_instrument pi ON sp.person_id = pi.person_id
                GROUP BY sp.person_id
            ),
            attendance_rank AS (
                -- Computed regular-ness: how often they've actually turned up here lately.
                SELECT sip.person_id,
                       COUNT(DISTINCT sip.session_instance_id) FILTER (
                           WHERE sip.attendance = 'yes'
                             AND si.date >= (CURRENT_DATE - INTERVAL '6 months')
                       ) AS recent_count,
                       COUNT(DISTINCT sip.session_instance_id) FILTER (
                           WHERE sip.attendance = 'yes'
                       ) AS lifetime_count
                FROM session_instance_person sip
                JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                WHERE si.session_id = %s
                GROUP BY sip.person_id
            )
            SELECT sp.person_id, sp.first_name, sp.last_name, sp.email,
                   sp.relationship, sp.is_session_admin,
                   pi.instruments,
                   CASE
                       WHEN sp.first_name = sp.last_name THEN sp.first_name
                       ELSE CONCAT(sp.first_name, ' ', sp.last_name)
                   END as display_name
            FROM session_people sp
            JOIN person_instruments pi ON sp.person_id = pi.person_id
            LEFT JOIN attendance_rank ar ON sp.person_id = ar.person_id
            ORDER BY
                sp.archived,                              -- archived sink to the bottom
                COALESCE(ar.recent_count, 0) DESC,        -- then who actually comes here
                COALESCE(ar.lifetime_count, 0) DESC,
                display_name
            LIMIT %s
            """,
            (session_id, session_id, session_id, search_pattern, search_pattern, search_pattern,
             session_id, limit)
        )

        results = cur.fetchall()

        # Format results
        people = []
        for row in results:
            person_id, first_name, last_name, email, relationship, is_session_admin, instruments, display_name = row

            people.append({
                'person_id': person_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'display_name': display_name,
                'relationship': relationship,
                'is_session_admin': is_session_admin or False,
                'instruments': list(instruments) if instruments else []
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "data": people,
            "meta": {
                "session_id": session_id,
                "session_name": session_result[1],
                "search_query": search_query,
                "result_count": len(people),
                "limit": limit
            }
        })
        
    except ValueError:
        return jsonify({"success": False, "message": "Invalid limit parameter"}), 400
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def get_session_people(session_id):
    """
    Get all people associated with a session for preloading client-side search.

    Returns JSON response with list of all people who are associated with the session
    (both regulars and non-regulars).
    """
    try:
        # Get database connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if session exists
        cur.execute(
            "SELECT session_id, name FROM session WHERE session_id = %s",
            (session_id,)
        )
        
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404
        
        # Permission check - can user access this session?
        current_person_id = current_user.person_id
        is_system_admin = current_user.is_system_admin
        
        # For accessing session people, allow:
        # - System admins to access any session
        # - Users who are associated with the session (regular, admin, or have attended)
        if not is_system_admin:
            # Check if user is associated with this session
            cur.execute("""
                SELECT 1 FROM (
                    -- Check if user is regular/admin for this session
                    SELECT 1 FROM session_person 
                    WHERE session_id = %s AND person_id = %s
                    
                    UNION
                    
                    -- Check if user has attended any instance of this session
                    SELECT 1 FROM session_instance_person sip
                    JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                    WHERE si.session_id = %s AND sip.person_id = %s
                ) AS user_associated
            """, (session_id, current_person_id, session_id, current_person_id))
            
            user_associated = cur.fetchone()
            if not user_associated:
                cur.close()
                conn.close()
                return jsonify({"success": False, "message": "Insufficient permissions to access people in this session"}), 403
        
        # Get all people associated with this session
        cur.execute(
            """
            WITH session_all_people AS (
                -- Everyone associated with this session: on the roster, or has attended it
                SELECT DISTINCT p.person_id, p.first_name, p.last_name, p.email,
                       COALESCE(sp.relationship, 'visitor') as relationship,
                       COALESCE(sp.archived, FALSE) as archived,
                       COALESCE(sp.is_admin, FALSE) as is_session_admin
                FROM person p
                LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
                LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id
                LEFT JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                WHERE (sp.session_id = %s OR si.session_id = %s)
                  AND p.active = TRUE
            ),
            person_instruments AS (
                -- Get instruments for these people
                SELECT sap.person_id,
                       COALESCE(
                           array_agg(pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                           '{}'::text[]
                       ) as instruments
                FROM session_all_people sap
                LEFT JOIN person_instrument pi ON sap.person_id = pi.person_id
                GROUP BY sap.person_id
            ),
            attendance_rank AS (
                -- Computed regular-ness (spec 034): advisory sort order only.
                SELECT sip.person_id,
                       COUNT(DISTINCT sip.session_instance_id) FILTER (
                           WHERE sip.attendance = 'yes'
                             AND si.date >= (CURRENT_DATE - INTERVAL '6 months')
                       ) AS recent_count,
                       COUNT(DISTINCT sip.session_instance_id) FILTER (
                           WHERE sip.attendance = 'yes'
                       ) AS lifetime_count
                FROM session_instance_person sip
                JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                WHERE si.session_id = %s
                GROUP BY sip.person_id
            )
            SELECT sap.person_id, sap.first_name, sap.last_name, sap.email,
                   sap.relationship, sap.is_session_admin,
                   pi.instruments,
                   CASE
                       WHEN sap.first_name = sap.last_name THEN sap.first_name
                       ELSE CONCAT(sap.first_name, ' ', sap.last_name)
                   END as display_name
            FROM session_all_people sap
            JOIN person_instruments pi ON sap.person_id = pi.person_id
            LEFT JOIN attendance_rank ar ON sap.person_id = ar.person_id
            ORDER BY
                sap.archived,
                COALESCE(ar.recent_count, 0) DESC,
                COALESCE(ar.lifetime_count, 0) DESC,
                display_name
            """,
            (session_id, session_id, session_id, session_id)
        )

        results = cur.fetchall()

        # Format results
        people = []
        for row in results:
            person_id, first_name, last_name, email, relationship, is_session_admin, instruments, display_name = row

            people.append({
                'person_id': person_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'display_name': display_name,
                'relationship': relationship,
                'is_session_admin': is_session_admin or False,
                'instruments': list(instruments) if instruments else []
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "data": people,
            "meta": {
                "session_id": session_id,
                "session_name": session_result[1],
                "result_count": len(people)
            }
        })
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500



def parse_csv_data(csv_data, session_city=None, session_state=None, session_country=None):
    """
    Parse CSV data and return processed person records.
    
    Supports various CSV formats with optional headers.
    Auto-detects columns based on content.
    
    Args:
        csv_data: Raw CSV string
        session_city: Default city from session
        session_state: Default state from session
        session_country: Default country from session
        
    Returns:
        List of person dictionaries with detected fields
    """
    import csv
    import io
    import re
    
    if not csv_data or not csv_data.strip():
        raise ValueError("CSV data is empty")
    
    lines = csv_data.strip().split('\n')
    if not lines:
        raise ValueError("CSV data is empty")
    
    reader = csv.reader(lines)
    rows = list(reader)
    
    if not rows:
        raise ValueError("CSV data is empty")
    
    # Detect if first row is header by checking for typical header words
    header_words = {'first', 'last', 'name', 'email', 'phone', 'sms', 'city', 'state', 'country', 'regular', 'instrument'}
    first_row_lower = [col.lower().replace(' ', '').replace('_', '') for col in rows[0]]
    has_header = any(word in ' '.join(first_row_lower) for word in header_words)
    
    processed_people = []
    data_rows = rows[1:] if has_header else rows
    headers = rows[0] if has_header else None
    
    if not data_rows:
        raise ValueError("No data rows found after header")
    
    for row_idx, row in enumerate(data_rows):
        if not row or all(not cell.strip() for cell in row):
            continue  # Skip empty rows
        
        try:
            person = parse_csv_row(row, headers, session_city, session_state, session_country)
            if person:
                processed_people.append(person)
        except Exception as e:
            raise ValueError(f"Error parsing row {row_idx + (2 if has_header else 1)}: {str(e)}")
    
    if not processed_people:
        raise ValueError("No valid person records found in CSV data")
    
    return processed_people


def parse_csv_row(row, headers, session_city=None, session_state=None, session_country=None):
    """Parse a single CSV row into a person dictionary."""
    import re
    
    if not row:
        return None
    
    person = {
        'first_name': '',
        'last_name': '',
        'email': None,
        'sms_number': None,
        'city': session_city,
        'state': session_state,
        'country': session_country,
        'instruments': [],
    }
    
    if headers:
        # Parse with headers
        for i, value in enumerate(row):
            if i >= len(headers):
                break
                
            header = headers[i].lower().replace(' ', '').replace('_', '')
            value = value.strip()
            
            if not value:
                continue
                
            if 'firstname' in header or header == 'first':
                person['first_name'] = value
            elif 'lastname' in header or header == 'last':
                person['last_name'] = value
            elif header in ['name', 'fullname']:
                # Split full name at last space
                parts = value.strip().split()
                if parts:
                    person['last_name'] = parts[-1]
                    person['first_name'] = ' '.join(parts[:-1]) if len(parts) > 1 else parts[0]
            elif 'email' in header:
                if is_email(value):
                    person['email'] = value.lower()
            elif 'sms' in header or 'phone' in header:
                if is_phone_number(value):
                    person['sms_number'] = value
            elif 'city' in header:
                person['city'] = value
            elif 'state' in header:
                person['state'] = value
            elif 'country' in header:
                person['country'] = value
            elif 'instrument' in header:
                instruments = parse_instruments(value)
                person['instruments'] = instruments
    else:
        # Parse without headers - auto-detect based on content
        used_indices = set()
        
        # First, try to identify name (first 1-2 columns that don't look like email/phone)
        name_found = False
        for i, value in enumerate(row[:3]):  # Check first 3 columns for name
            value = value.strip()
            
            # If first column is empty, this indicates a malformed CSV
            if i == 0 and not value:
                raise ValueError("First column appears to be name but is empty")
            
            if not value or i in used_indices:
                continue
                
            if not is_email(value) and not is_phone_number(value):
                if not name_found:
                    # This looks like a name - split at last space
                    parts = value.split()
                    if parts:
                        person['last_name'] = parts[-1]
                        person['first_name'] = ' '.join(parts[:-1]) if len(parts) > 1 else parts[0]
                        used_indices.add(i)
                        name_found = True
                        break
        
        # Look for email
        for i, value in enumerate(row):
            if i in used_indices:
                continue
            if is_email(value.strip()):
                person['email'] = value.strip().lower()
                used_indices.add(i)
                break
        
        # Look for phone number
        for i, value in enumerate(row):
            if i in used_indices:
                continue
            if is_phone_number(value.strip()):
                person['sms_number'] = value.strip()
                used_indices.add(i)
                break
        
        # Remaining columns are likely instruments
        instruments = []
        for i, value in enumerate(row):
            if i in used_indices:
                continue
            value = value.strip()
            if value:
                instruments.extend(parse_instruments(value))
        
        person['instruments'] = instruments
    
    # Validate required fields
    if not person['first_name'] or not person['last_name']:
        raise ValueError("Name is required (either separate first/last name fields or full name)")
    
    # Clean and canonicalize instruments against one shared vocabulary
    person['instruments'] = normalize_instruments(person['instruments'])

    return person


def is_email(value):
    """Check if a value looks like an email address."""
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, value))


def is_phone_number(value):
    """Check if a value looks like a phone number."""
    import re
    # Match various phone number formats
    phone_pattern = r'^[\+]?[\d\s\-\(\)\.]{10,}$'
    return bool(re.match(phone_pattern, value)) and len(re.sub(r'[\s\-\(\)\.]', '', value)) >= 10


def parse_instruments(value):
    """Parse instrument string into list of instruments."""
    if not value:
        return []
    
    # Handle quoted comma-separated lists
    import re
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    
    # Split on commas and clean up
    instruments = [inst.strip() for inst in value.split(',') if inst.strip()]
    return instruments


def find_duplicate_person(person_data, session_id):
    """
    Find if person already exists based on email, phone, or name within session.
    
    Returns: (is_duplicate, existing_person_id, duplicate_reason)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # First check by email (exact match) — against person.email (accountless)
        # or the account email, since person.email is nulled once connected.
        if person_data.get('email'):
            cur.execute(
                """
                SELECT p.person_id
                FROM person p
                LEFT JOIN user_account ua ON ua.person_id = p.person_id
                WHERE p.email = %s OR LOWER(ua.user_email) = LOWER(%s)
                LIMIT 1
                """,
                (person_data['email'], person_data['email'])
            )
            result = cur.fetchone()
            if result:
                cur.close()
                conn.close()
                return True, result[0], "email"
        
        # Then check by SMS number (exact match)
        if person_data.get('sms_number'):
            cur.execute(
                "SELECT person_id FROM person WHERE sms_number = %s",
                (person_data['sms_number'],)
            )
            result = cur.fetchone()
            if result:
                cur.close()
                conn.close()
                return True, result[0], "phone"
        
        # Finally check by name within this session
        cur.execute(
            """
            SELECT p.person_id 
            FROM person p
            JOIN session_person sp ON p.person_id = sp.person_id
            WHERE sp.session_id = %s 
            AND LOWER(p.first_name) = LOWER(%s) 
            AND LOWER(p.last_name) = LOWER(%s)
            """,
            (session_id, person_data['first_name'], person_data['last_name'])
        )
        result = cur.fetchone()
        if result:
            cur.close()
            conn.close()
            return True, result[0], "name"
        
        cur.close()
        conn.close()
        return False, None, None
        
    except Exception:
        cur.close()
        conn.close()
        return False, None, None


@api_login_required  
def bulk_import_preprocess_session(session_id):
    """
    First stage of bulk import: preprocess CSV data and return preview.
    
    POST /api/session/{session_id}/bulk-import/preprocess
    
    Expected JSON payload:
    {
        "csv_data": "CSV string with person data"
    }
    
    Returns processed people with duplicate detection.
    """
    if request.method != 'POST':
        return jsonify({"success": False, "message": "Only POST method allowed"}), 405
    
    try:
        # Check permissions - must be system admin 
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        if not user_row or not user_row[0]:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403
        
        # Check if session exists and get location data
        cur.execute(
            "SELECT session_id, name, city, state, country FROM session WHERE session_id = %s",
            (session_id,)
        )
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404
        
        session_city = session_result[2]
        session_state = session_result[3] 
        session_country = session_result[4]
        
        cur.close()
        conn.close()
        
        # Get CSV data from request
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "message": "No JSON data provided"}), 400
        
        csv_data = data.get('csv_data', '').strip()
        if not csv_data:
            return jsonify({"success": False, "message": "csv_data field is required"}), 400
        
        # Parse CSV data
        try:
            processed_people = parse_csv_data(csv_data, session_city, session_state, session_country)
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400
        
        # Check for duplicates
        for person in processed_people:
            is_duplicate, existing_id, reason = find_duplicate_person(person, session_id)
            person['is_duplicate'] = is_duplicate
            if is_duplicate:
                person['existing_person_id'] = existing_id
                person['duplicate_reason'] = reason
        
        return jsonify({
            "success": True,
            "processed_people": processed_people,
            "session_info": {
                "session_id": session_id,
                "name": session_result[1],
                "city": session_city,
                "state": session_state,
                "country": session_country
            }
        })
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def bulk_import_save_session(session_id):
    """
    Second stage of bulk import: save processed people to database.
    
    POST /api/session/{session_id}/bulk-import/save
    
    Expected JSON payload:
    {
        "processed_people": [array of processed person objects]
    }
    
    Creates new people and associated session_person records.
    """
    if request.method != 'POST':
        return jsonify({"success": False, "message": "Only POST method allowed"}), 405
    
    try:
        # Check permissions - must be system admin
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        if not user_row or not user_row[0]:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403
        
        # Check if session exists
        cur.execute(
            "SELECT session_id FROM session WHERE session_id = %s",
            (session_id,)
        )
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404
        
        # Get processed people from request
        data = request.get_json()
        if data is None:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "No JSON data provided"}), 400
        
        processed_people = data.get('processed_people', [])
        if not processed_people:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "processed_people field is required"}), 400
        
        if not isinstance(processed_people, list):
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "processed_people must be an array"}), 400
        
        created_count = 0
        skipped_count = 0
        created_people = []
        
        # Begin transaction
        cur.execute("BEGIN")
        
        try:
            for person_data in processed_people:
                # Skip duplicates
                if person_data.get('is_duplicate', False):
                    skipped_count += 1
                    continue

                # Create person record
                cur.execute(
                    """
                    INSERT INTO person (first_name, last_name, email, sms_number, city, state, country, created_date, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
                    RETURNING person_id
                    """,
                    (
                        person_data.get('first_name', '').strip(),
                        person_data.get('last_name', '').strip(),
                        person_data.get('email'),
                        person_data.get('sms_number'),
                        person_data.get('city'),
                        person_data.get('state'),
                        person_data.get('country'),
                        current_user.user_id
                    )
                )

                person_id = cur.fetchone()[0]

                # Log person creation
                save_to_history(cur, 'person', 'INSERT', person_id, user_id=current_user.user_id)

                # Create instruments (canonicalized against one shared vocabulary)
                instruments = normalize_instruments(person_data.get('instruments', []))
                for instrument in instruments:
                    cur.execute(
                        """
                        INSERT INTO person_instrument (person_id, instrument, created_date, created_by_user_id)
                        VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'), %s)
                        """,
                        (person_id, instrument, current_user.user_id)
                    )

                    # Log instrument creation
                    save_to_history(cur, 'person_instrument', 'INSERT',
                                  (person_id, instrument), user_id=current_user.user_id)

                # Create session_person record. A bulk import is an admin populating their
                # own roster -- a deliberate vouch -- so these land confirmed (spec 034).
                cur.execute(
                    """
                    INSERT INTO session_person
                        (session_id, person_id, relationship, confirmed, archived, created_date, created_by_user_id)
                    VALUES (%s, %s, 'member', TRUE, FALSE, (NOW() AT TIME ZONE 'UTC'), %s)
                    """,
                    (session_id, person_id, current_user.user_id)
                )

                # Log session_person creation
                save_to_history(cur, 'session_person', 'INSERT',
                              (session_id, person_id), user_id=current_user.user_id)
                
                created_count += 1
                created_people.append({
                    "person_id": person_id,
                    "first_name": person_data.get('first_name', ''),
                    "last_name": person_data.get('last_name', ''),
                    "email": person_data.get('email'),
                    "instruments": instruments,
                    "relationship": "member"
                })
            
            # Commit transaction
            cur.execute("COMMIT")
            
            cur.close()
            conn.close()
            
            return jsonify({
                "success": True,
                "message": f"Successfully imported {created_count} people ({skipped_count} skipped as duplicates)",
                "created_count": created_count,
                "skipped_count": skipped_count,
                "created_people": created_people
            })

        except Exception as e:
            cur.execute("ROLLBACK")
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": f"Error saving people: {str(e)}"}), 500

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@public_api  # backs the logged-out /sessions directory (frontend/src/sessionsdir/App.svelte); current_user use below is personalization only
def get_sessions_with_today_status():
    """
    Get all sessions with indicators for today's status (active instances,
    membership, recurrence for client-side parsing).

    NOTE: "Today" is in the user's timezone; per-session "today" derives from
    each session's recurrence client-side.
    """
    try:
        from serializers import build_sessions_directory_payload

        user_person_id = None
        user_timezone = "UTC"
        if current_user.is_authenticated:
            user_person_id = getattr(current_user, 'person_id', None)
            user_timezone = getattr(current_user, 'timezone', None) or "UTC"

        # The whole response body comes from the shared serializer; the /sessions
        # page shell embeds the same function's output, so they can't drift.
        conn = get_db_connection()
        try:
            payload = build_sessions_directory_payload(conn, user_person_id, user_timezone)
        finally:
            conn.close()

        return jsonify(payload)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_login_required  # creates data; only reference is the orphaned templates/session_select_action.html (rendered by nothing)
def create_or_get_today_session_instance(session_path):
    """
    Create a new session instance for today, or return existing one if it already exists.
    This is idempotent - safe to call multiple times.

    NOTE: "Today" is determined based on the session's timezone, not server time.

    Returns:
    - session_instance_id: The ID of the instance (new or existing)
    - created: Boolean indicating if a new instance was created
    - date: The date of the instance (today in session's timezone)
    """
    try:
        from timezone_utils import get_today_in_timezone

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id, name, and timezone for this session_path
        cur.execute(
            "SELECT session_id, name, timezone FROM session WHERE path = %s",
            (session_path,),
        )
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id, session_name, session_timezone = session_result

        # Get "today" in the session's timezone
        today = get_today_in_timezone(session_timezone or "UTC")

        # Check if session instance already exists for today (race condition check)
        cur.execute(
            """
            SELECT session_instance_id FROM session_instance
            WHERE session_id = %s AND date = %s
            """,
            (session_id, today),
        )
        existing_instance = cur.fetchone()

        if existing_instance:
            cur.close()
            conn.close()
            return jsonify({
                "success": True,
                "session_instance_id": existing_instance[0],
                "created": False,
                "date": today.isoformat(),
                "session_name": session_name,
                "session_path": session_path
            })

        # Create new session instance for today
        cur.execute(
            """
            INSERT INTO session_instance (session_id, date, comments, created_by_user_id)
            VALUES (%s, %s, %s, %s)
            RETURNING session_instance_id
            """,
            (session_id, today, None, get_current_user_id()),
        )
        new_instance = cur.fetchone()

        if not new_instance:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Failed to create session instance"}), 500

        session_instance_id = new_instance[0]

        # Save to history
        save_to_history(cur, "session_instance", "INSERT", session_instance_id, user_id=get_current_user_id())

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "session_instance_id": session_instance_id,
            "created": True,
            "date": today.isoformat(),
            "session_name": session_name,
            "session_path": session_path
        })

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@public_api  # backs the /share page QR image (templates/share.html, no @login_required); serves only a QR PNG of a URL
def generate_qr_code(session_id=None):
    """
    Generate a QR code for sharing pages with optional referral tracking.
    Returns a PNG image that when scanned directs to the specified URL.

    Query parameters:
    - url: The target URL to encode (if not provided, uses session_id logic for backwards compatibility)
    - referrer: Person ID of the user sharing the link
    - session_id: (Deprecated but still supported) Session ID for registration URLs
    """
    try:
        # Check if URL parameter is provided (new behavior)
        target_url = request.args.get('url')
        referrer = request.args.get('referrer')

        if target_url:
            # New behavior: use provided URL with optional referrer
            qr_url = target_url
            if referrer:
                # Add referrer parameter to URL
                separator = '&' if '?' in qr_url else '?'
                qr_url = f"{qr_url}{separator}referrer={referrer}"
        else:
            # Backwards compatibility: use session_id logic
            base_url = request.host_url.rstrip('/')
            if session_id and session_id != 0:
                qr_url = f"{base_url}/register?session_id={session_id}"
            else:
                qr_url = f"{base_url}/register"

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,  # Size of QR code (1 is smallest, auto-sizes if data too large)
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Save to BytesIO buffer
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)

        return send_file(img_io, mimetype='image/png', as_attachment=False)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@public_api  # backs the logged-out session Logs tab's "happening now" banner (frontend/src/sessionpage/LogsTab.svelte)
def get_session_active_instance(session_id):
    """
    Get all currently active instances for a session.

    GET /api/session/<int:session_id>/active_instance

    Returns:
    {
        "success": true,
        "active_instance_ids": [int, ...],
        "session_id": int
    }
    """
    try:
        from active_session_manager import get_session_active_instances

        active_instance_ids = get_session_active_instances(session_id)

        return jsonify({
            "success": True,
            "active_instance_ids": active_instance_ids,
            "session_id": session_id
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_admin_or_self_required
def get_person_active_session(person_id):
    """
    Get the session instance a person is currently at.

    GET /api/person/<int:person_id>/active_session

    Returns:
    {
        "success": true,
        "active_session": {
            "session_instance_id": int,
            "session_id": int,
            "date": "YYYY-MM-DD",
            "start_time": "HH:MM:SS",
            "end_time": "HH:MM:SS",
            "session_name": string,
            "session_path": string
        } or null
    }
    """
    try:
        from active_session_manager import get_person_active_session as get_active

        active_session = get_active(person_id)

        # Convert date/time objects to strings for JSON serialization
        if active_session:
            active_session['date'] = active_session['date'].isoformat() if active_session['date'] else None
            active_session['start_time'] = active_session['start_time'].isoformat() if active_session['start_time'] else None
            active_session['end_time'] = active_session['end_time'].isoformat() if active_session['end_time'] else None

        return jsonify({
            "success": True,
            "active_session": active_session
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def get_admin_tunes():
    """
    Get all tunes with counts for admin dashboard.

    GET /api/admin/tunes

    Returns:
    {
        "success": true,
        "tunes": [
            {
                "tune_id": int,
                "name": string,
                "tune_type": string,
                "session_count": int (count of distinct sessions),
                "tunelist_count": int (count of person tune lists),
                "tunebook_count_cached": int
            },
            ...
        ]
    }
    """
    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Get all tunes with counts
        cur.execute("""
            SELECT
                t.tune_id,
                t.name,
                t.tune_type,
                COALESCE(session_counts.session_count, 0) as session_count,
                COALESCE(tunelist_counts.tunelist_count, 0) as tunelist_count,
                t.tunebook_count_cached,
                t.redirect_to_tune_id
            FROM tune t
            LEFT JOIN (
                -- Count distinct sessions where tune has been played
                SELECT DISTINCT st.tune_id, COUNT(DISTINCT st.session_id) as session_count
                FROM session_tune st
                GROUP BY st.tune_id
            ) session_counts ON t.tune_id = session_counts.tune_id
            LEFT JOIN (
                -- Count person tune lists containing this tune
                SELECT tune_id, COUNT(DISTINCT person_id) as tunelist_count
                FROM person_tune
                GROUP BY tune_id
            ) tunelist_counts ON t.tune_id = tunelist_counts.tune_id
            ORDER BY t.name
        """)

        tunes = []
        for row in cur.fetchall():
            tunes.append({
                "tune_id": row[0],
                "name": row[1],
                "tune_type": row[2],
                "session_count": row[3],
                "tunelist_count": row[4],
                "tunebook_count_cached": row[5] or 0,
                "redirect_to_tune_id": row[6]
            })

        return jsonify({
            "success": True,
            "tunes": tunes
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def update_admin_tune(tune_id):
    """
    Update a tune's name.

    PUT /api/admin/tunes/<int:tune_id>

    Request body:
    {
        "name": string (required)
    }

    Returns:
    {
        "success": true,
        "message": string
    }
    """
    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"success": False, "error": "Missing name field"}), 400

    name = data["name"].strip()
    if not name:
        return jsonify({"success": False, "error": "Name cannot be empty"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Check if tune exists
        cur.execute("SELECT name FROM tune WHERE tune_id = %s", (tune_id,))
        tune_row = cur.fetchone()
        if not tune_row:
            return jsonify({"success": False, "error": "Tune not found"}), 404

        old_name = tune_row[0]

        # Save to history before update
        save_to_history(
            cur,
            "tune",
            "UPDATE",
            tune_id,
            user_id=get_current_user_id()
        )

        # Update the tune name
        cur.execute(
            "UPDATE tune SET name = %s, last_modified_date = CURRENT_TIMESTAMP, last_modified_user_id = %s WHERE tune_id = %s",
            (name, get_current_user_id(), tune_id)
        )
        conn.commit()

        return jsonify({
            "success": True,
            "message": f"Updated tune name to '{name}'"
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def refresh_admin_tune_tunebook_count(tune_id):
    """
    Refresh the tunebook count for a tune from TheSession.org.

    POST /api/admin/tunes/<int:tune_id>/refresh_tunebook_count

    Returns:
    {
        "success": true,
        "old_count": int,
        "new_count": int,
        "cached_date": string (YYYY-MM-DD)
    }
    """
    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Check if tune exists and get current count
        cur.execute(
            "SELECT tunebook_count_cached FROM tune WHERE tune_id = %s",
            (tune_id,)
        )
        tune_row = cur.fetchone()
        if not tune_row:
            return jsonify({"success": False, "error": "Tune not found"}), 404

        old_count = tune_row[0] or 0

        # Fetch fresh tunebook count from TheSession.org
        try:
            api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
            response = requests.get(api_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                new_count = data.get("tunebooks", 0)

                # Update the cached count and date
                cur.execute(
                    """
                    UPDATE tune
                    SET tunebook_count_cached = %s,
                        tunebook_count_cached_date = CURRENT_DATE,
                        last_modified_date = CURRENT_TIMESTAMP
                    WHERE tune_id = %s
                    """,
                    (new_count, tune_id)
                )
                conn.commit()

                # Get the cached date for response
                cur.execute(
                    "SELECT tunebook_count_cached_date FROM tune WHERE tune_id = %s",
                    (tune_id,)
                )
                cached_date = cur.fetchone()[0].isoformat()

                return jsonify({
                    "success": True,
                    "old_count": old_count,
                    "new_count": new_count,
                    "cached_date": cached_date
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"TheSession.org returned status {response.status_code}"
                }), 500

        except requests.RequestException as e:
            return jsonify({
                "success": False,
                "error": f"Failed to fetch from TheSession.org: {str(e)}"
            }), 500

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# Admin Tune Merge API Endpoints
# ============================================================================


# The redirect verification + merge-apply sequence is shared with the weekly
# sync job (spec 031), which auto-applies upstream merges through the same code.
from services.tune_merge_scan_service import (  # noqa: E402
    verify_thesession_redirect as _verify_thesession_redirect,
    apply_merge as _apply_tune_merge,
)


@api_login_required
def merge_tune():
    """
    Merge references from one tune ID to another (for thesession.org merges).

    POST /api/admin/tunes/merge

    Request body:
    {
        "old_tune_id": int (required),
        "new_tune_id": int (required),
        "confirm": boolean (optional, default false)
    }

    If confirm is false or not provided, returns a preview of affected records.
    If confirm is true, executes the migration.

    Returns preview:
    {
        "success": true,
        "preview": true,
        "old_tune": { "tune_id": int, "name": string, "type": string },
        "new_tune": { "tune_id": int, "name": string, "type": string },
        "affected_records": {
            "tune_settings": int,
            "session_tunes": int,
            "session_tune_aliases": int,
            "session_instance_tunes": int,
            "person_tunes": int
        },
        "warnings": [string, ...]
    }

    Returns execution result:
    {
        "success": true,
        "message": "Migrated tune X → Y",
        "migrated_records": { ... }
    }
    """
    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Request body required"}), 400

    old_tune_id = data.get("old_tune_id")
    new_tune_id = data.get("new_tune_id")
    confirm = data.get("confirm", False)

    if not old_tune_id or not new_tune_id:
        return jsonify({"success": False, "error": "Both old_tune_id and new_tune_id are required"}), 400

    if old_tune_id == new_tune_id:
        return jsonify({"success": False, "error": "old_tune_id and new_tune_id cannot be the same"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Fetch old tune info
        cur.execute(
            "SELECT tune_id, name, tune_type, redirect_to_tune_id FROM tune WHERE tune_id = %s",
            (old_tune_id,)
        )
        old_tune_row = cur.fetchone()
        if not old_tune_row:
            return jsonify({"success": False, "error": f"Tune {old_tune_id} not found"}), 404

        if old_tune_row[3] is not None:
            return jsonify({
                "success": False,
                "error": f"Tune {old_tune_id} is already a redirect to tune {old_tune_row[3]}"
            }), 400

        old_tune = {
            "tune_id": old_tune_row[0],
            "name": old_tune_row[1],
            "type": old_tune_row[2]
        }

        # Fetch new tune info
        cur.execute(
            "SELECT tune_id, name, tune_type, redirect_to_tune_id FROM tune WHERE tune_id = %s",
            (new_tune_id,)
        )
        new_tune_row = cur.fetchone()

        # Missing target: auto-import from thesession.org (spec 031 #10). Preview
        # only announces it; confirm imports in THIS transaction (the live logger's
        # in-transaction importer) so a failure mid-import rolls back the merge too.
        will_import = False
        if not new_tune_row:
            if not confirm:
                try:
                    ts_data = _fetch_thesession_tune(new_tune_id)
                except TuneImportError as e:
                    return jsonify({
                        "success": False,
                        "error": f"Tune {new_tune_id} is not in the local database and could not be fetched from thesession.org: {e.message}"
                    }), e.status
                new_tune = {"tune_id": new_tune_id, "name": ts_data["name"], "type": ts_data["type"].title()}
            else:
                from live_logging_routes import _import_tune_for_live
                try:
                    imported_name, imported_type = _import_tune_for_live(cur, new_tune_id, current_user.user_id)
                except TuneImportError as e:
                    conn.rollback()
                    return jsonify({
                        "success": False,
                        "error": f"Could not import tune {new_tune_id} from thesession.org: {e.message}"
                    }), e.status
                new_tune = {"tune_id": new_tune_id, "name": imported_name, "type": imported_type}
            will_import = True
        else:
            if new_tune_row[3] is not None:
                return jsonify({
                    "success": False,
                    "error": f"Tune {new_tune_id} is a redirect to tune {new_tune_row[3]} - cannot redirect to a redirect"
                }), 400

            new_tune = {
                "tune_id": new_tune_row[0],
                "name": new_tune_row[1],
                "type": new_tune_row[2]
            }

        # Count affected records
        cur.execute("SELECT COUNT(*) FROM tune_setting WHERE tune_id = %s", (old_tune_id,))
        tune_settings_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM session_tune WHERE tune_id = %s", (old_tune_id,))
        session_tunes_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM session_tune_alias WHERE tune_id = %s", (old_tune_id,))
        session_tune_aliases_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM session_instance_tune WHERE tune_id = %s", (old_tune_id,))
        session_instance_tunes_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM person_tune WHERE tune_id = %s", (old_tune_id,))
        person_tunes_count = cur.fetchone()[0]

        # Per-instrument overrides split by fate (spec 030): clean-move parents carry
        # theirs along (FK ON UPDATE CASCADE); conflict-deleted parents drop theirs.
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE NOT EXISTS (
                       SELECT 1 FROM person_tune pt2
                       WHERE pt2.person_id = pti.person_id AND pt2.tune_id = %s)),
                   COUNT(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM person_tune pt2
                       WHERE pt2.person_id = pti.person_id AND pt2.tune_id = %s))
            FROM person_tune_instrument pti
            WHERE pti.tune_id = %s
        """, (new_tune_id, new_tune_id, old_tune_id))
        instrument_moved_count, instrument_dropped_count = cur.fetchone()

        cur.execute("SELECT COUNT(*) FROM recording_tune_segment WHERE tune_id = %s", (old_tune_id,))
        recording_segments_count = cur.fetchone()[0]

        # Name preservation (spec 030): rows that were displaying the old canonical
        # name get it frozen into their override slot so the merge doesn't rename
        # tunes out from under people.
        names_differ = (old_tune["name"] or "") != (new_tune["name"] or "")
        alias_fills = {
            "person_tune_name_alias": 0,
            "session_tune_alias": 0,
            "session_instance_tune_name": 0,
            "session_tune_alias_rows": 0,
        }
        if names_differ:
            cur.execute("""
                SELECT COUNT(*) FROM person_tune pt
                WHERE pt.tune_id = %s AND pt.name_alias IS NULL
                  AND NOT EXISTS (SELECT 1 FROM person_tune pt2
                                  WHERE pt2.person_id = pt.person_id AND pt2.tune_id = %s)
            """, (old_tune_id, new_tune_id))
            alias_fills["person_tune_name_alias"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM session_tune st
                WHERE st.tune_id = %s AND st.alias IS NULL
                  AND NOT EXISTS (SELECT 1 FROM session_tune st2
                                  WHERE st2.session_id = st.session_id AND st2.tune_id = %s)
            """, (old_tune_id, new_tune_id))
            alias_fills["session_tune_alias"] = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM session_instance_tune WHERE tune_id = %s AND name IS NULL",
                (old_tune_id,),
            )
            alias_fills["session_instance_tune_name"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(DISTINCT session_id) FROM (
                    SELECT session_id FROM session_tune WHERE tune_id = %s
                    UNION
                    SELECT session_id FROM session_tune_alias WHERE tune_id = %s
                ) s
            """, (old_tune_id, old_tune_id))
            alias_fills["session_tune_alias_rows"] = cur.fetchone()[0]

        # Check for conflicts (records that will be merged/deleted)
        warnings = []

        cur.execute("""
            SELECT COUNT(*) FROM session_tune st1
            WHERE st1.tune_id = %s
            AND EXISTS (
                SELECT 1 FROM session_tune st2
                WHERE st2.session_id = st1.session_id AND st2.tune_id = %s
            )
        """, (old_tune_id, new_tune_id))
        session_tune_conflicts = cur.fetchone()[0]
        if session_tune_conflicts > 0:
            warnings.append(f"{session_tune_conflicts} session_tune record(s) will be merged (session already has new tune)")

        cur.execute("""
            SELECT COUNT(*) FROM person_tune pt1
            WHERE pt1.tune_id = %s
            AND EXISTS (
                SELECT 1 FROM person_tune pt2
                WHERE pt2.person_id = pt1.person_id AND pt2.tune_id = %s
            )
        """, (old_tune_id, new_tune_id))
        person_tune_conflicts = cur.fetchone()[0]
        if person_tune_conflicts > 0:
            warnings.append(f"{person_tune_conflicts} person_tune record(s) will be merged (person already has new tune)")

        if not confirm:
            # Verify the redirect against thesession.org (spec 030 #8): the merge we
            # mirror usually originates there, so a mismatch is probably a typo.
            # Non-blocking — local-only duplicates and merging ahead of thesession
            # are legitimate, so failures warn rather than stop.
            thesession_check = _verify_thesession_redirect(old_tune_id, new_tune_id)
            if thesession_check["status"] != "confirmed":
                warnings.append(thesession_check["message"])

            if will_import:
                warnings.append(
                    f'Tune {new_tune_id} is not in the local database - it will be imported '
                    f'from thesession.org as "{new_tune["name"]}" when the merge is confirmed.'
                )

            return jsonify({
                "success": True,
                "preview": True,
                "old_tune": old_tune,
                "new_tune": new_tune,
                "will_import": will_import,
                "names_differ": names_differ,
                "affected_records": {
                    "tune_settings": tune_settings_count,
                    "session_tunes": session_tunes_count,
                    "session_tune_aliases": session_tune_aliases_count,
                    "session_instance_tunes": session_instance_tunes_count,
                    "person_tunes": person_tunes_count,
                    "person_tune_instruments_moved": instrument_moved_count,
                    "person_tune_instruments_dropped": instrument_dropped_count,
                    "recording_tune_segments": recording_segments_count
                },
                "alias_fills": alias_fills,
                "thesession_check": thesession_check,
                "warnings": warnings
            })

        # Shared apply sequence (also used by the weekly sync): capture the log
        # rows live-logger clients may have open, run merge_tune_ids, then emit
        # change_tune events so connected screens relink in place (spec 030 #6).
        result, events_emitted = _apply_tune_merge(cur, old_tune_id, new_tune_id, current_user.user_id)

        conn.commit()

        return jsonify({
            "success": True,
            "message": f"Migrated tune {old_tune_id} → {new_tune_id}",
            "old_tune": old_tune,
            "new_tune": new_tune,
            "imported_target": will_import,
            "migrated_records": result.get("tables_updated", {}),
            "total_records_affected": result.get("total_records_affected", 0),
            "live_events_emitted": events_emitted
        })

    except psycopg2.Error as e:
        conn.rollback()
        error_msg = str(e)
        # Extract the actual error message from PostgreSQL
        if hasattr(e, 'pgerror') and e.pgerror:
            error_msg = e.pgerror
        return jsonify({"success": False, "error": error_msg}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# Admin Merged-Tune Scan API Endpoints (spec 031)
# ============================================================================


@api_login_required
def start_merge_scan():
    """
    POST /api/admin/tunes/merge-scan

    Run the thesession.org merge sync now (spec 031) — same run the weekly
    cron performs. 409 if a run is already going with a fresh heartbeat.
    """
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    from services.tune_merge_scan_service import create_run, start_scan_thread

    try:
        scan_id = create_run(started_by_user_id=current_user.user_id)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    if scan_id is None:
        return jsonify({"success": False, "error": "A sync run is already in progress."}), 409
    start_scan_thread(scan_id)
    return jsonify({"success": True, "scan_id": scan_id})


@api_login_required
def get_merge_scan():
    """
    GET /api/admin/tunes/merge-scan

    The sync record: recent runs (newest first) with each run's result rows —
    merges applied (or attempted), tunes deleted upstream, errors. Result rows
    persist across runs, so this is the durable history the admin page shows.
    """
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    from services.tune_merge_scan_service import HEARTBEAT_STALE_SECONDS

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT scan_id, status, total_count, checked_count, merged_count,
                   applied_count, deleted_count, error_count, started_by_user_id,
                   started_at, finished_at,
                   (status = 'running'
                    AND heartbeat_at < (NOW() AT TIME ZONE 'UTC') - make_interval(secs => %s)) AS stale
            FROM tune_merge_scan
            ORDER BY scan_id DESC
            LIMIT 26
            """,
            (HEARTBEAT_STALE_SECONDS,),
        )
        runs = {}
        run_order = []
        for row in cur.fetchall():
            run = {
                "scan_id": row[0],
                "status": row[1],
                "total_count": row[2],
                "checked_count": row[3],
                "merged_count": row[4],
                "applied_count": row[5],
                "deleted_count": row[6],
                "error_count": row[7],
                "triggered_by": "admin" if row[8] is not None else "weekly job",
                "started_at": row[9].isoformat() if row[9] else None,
                "finished_at": row[10].isoformat() if row[10] else None,
                "stale": row[11],
                "results": [],
            }
            runs[row[0]] = run
            run_order.append(run)

        if runs:
            cur.execute(
                """
                SELECT r.scan_id, r.tune_id,
                       COALESCE(ot.name, '(tune #' || r.tune_id || ')') AS tune_name,
                       r.result_type, r.target_tune_id,
                       COALESCE(r.target_name, tt.name) AS target_name,
                       r.target_aliases, r.detail,
                       r.applied_at, r.checked_at
                FROM tune_merge_scan_result r
                LEFT JOIN tune ot ON ot.tune_id = r.tune_id
                LEFT JOIN tune tt ON tt.tune_id = r.target_tune_id
                WHERE r.scan_id = ANY(%s)
                ORDER BY r.scan_id DESC, r.result_type, r.tune_id
                """,
                (list(runs.keys()),),
            )
            for (scan_id, tune_id, tune_name, result_type, target_tune_id,
                 target_name, target_aliases, detail, applied_at, checked_at) in cur.fetchall():
                runs[scan_id]["results"].append({
                    "tune_id": tune_id,
                    "tune_name": tune_name,
                    "result_type": result_type,
                    "target_tune_id": target_tune_id,
                    "target_name": target_name,
                    "target_aliases": target_aliases or [],
                    "detail": detail,
                    "applied": applied_at is not None,
                    "applied_at": applied_at.isoformat() if applied_at else None,
                    "imported": bool(detail and "target imported" in detail),
                    "checked_at": checked_at.isoformat() if checked_at else None,
                })

        return jsonify({"success": True, "runs": run_order})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def cancel_merge_scan():
    """
    DELETE /api/admin/tunes/merge-scan

    Cancel the running scan. The worker thread notices the status flip on its
    next iteration and exits; results collected so far stay visible.
    """
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tune_merge_scan
            SET status = 'cancelled', finished_at = (NOW() AT TIME ZONE 'UTC')
            WHERE status = 'running'
            RETURNING scan_id
            """
        )
        cancelled = cur.fetchone()
        conn.commit()
        if not cancelled:
            return jsonify({"success": False, "error": "No running scan to cancel."}), 404
        return jsonify({"success": True, "scan_id": cancelled[0]})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# Session Instance Tune Detail Endpoints
# ============================================================================

@public_api  # backs the tune-detail modal on logged-out session-instance pages; current_user use is personalization only
def get_session_instance_tune_detail(session_path, date_or_id, tune_id):
    """Instance-scoped tune detail — the same drawer payload as
    /api/tunes/<id>/detail?session=<path>&instance=<date-or-id> (one builder);
    kept routed for legacy callers (the quarantined pill logger)."""
    from serializers import (
        build_tune_detail_payload,
        SessionNotFound,
        SessionInstanceNotFound,
    )

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Greedy-path fallback: "<path>/<segment>" may itself be the session path
        # (e.g. oflahertys/2025), in which case this is a session-level request.
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        if not cur.fetchone():
            combined_path = f"{session_path}/{date_or_id}"
            cur.execute("SELECT session_id FROM session WHERE path = %s", (combined_path,))
            if cur.fetchone():
                return get_session_tune_detail(combined_path, tune_id)
            return jsonify({"success": False, "message": "Session not found"}), 404

        tune_id, redirected_from = follow_tune_redirect(cur, tune_id)
        person_id = current_user.person_id if current_user.is_authenticated else None
        try:
            payload = build_tune_detail_payload(
                conn,
                tune_id,
                person_id=person_id,
                logged_in=current_user.is_authenticated,
                is_admin=bool(current_user.is_authenticated and current_user.is_system_admin),
                session_path=session_path,
                date_or_id=date_or_id,
                redirected_from=redirected_from,
            )
        except SessionNotFound:
            return jsonify({"success": False, "message": "Session not found"}), 404
        except SessionInstanceNotFound:
            return jsonify({"success": False, "message": "Session instance not found"}), 404
        if payload is None:
            return jsonify({"success": False, "message": "Tune not found"}), 404
        return jsonify(payload)
    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error retrieving tune details: {str(e)}"}
        ), 500
    finally:
        conn.close()


@api_login_required
def update_session_instance_tune_details(session_path, date_or_id, tune_id):
    """
    Update session_instance_tune details (name, key_override, setting_override).

    PUT /api/sessions/<session_path>/<date_or_id>/tunes/<tune_id>

    Request body:
    {
        "name": string or null,
        "key_override": string or null,
        "setting_override": int or null
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id = session_result[0]

        # Get session_instance_id
        session_instance_id = get_session_instance_id(cur, session_id, date_or_id)
        if not session_instance_id:
            return jsonify({"success": False, "message": "Session instance not found"}), 404

        # Any session member may edit all three fields on a specific instance (spec
        # 037). This is a record of what happened in a room they were in — not the
        # session speaking about its repertoire, which stays admin-only over in
        # update_session_tune_details. Before 037 a non-admin member could set only
        # setting_override.
        if not is_session_member_for(cur, session_id, current_user.person_id):
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Check if this tune exists in this session instance
        cur.execute(
            """
            SELECT session_instance_tune_id
            FROM session_instance_tune
            WHERE session_instance_id = %s AND tune_id = %s
        """,
            (session_instance_id, tune_id),
        )
        if not cur.fetchone():
            return jsonify({"success": False, "message": "Tune not found in this session instance"}), 404

        # Build dynamic update - only update fields that are explicitly present in request
        update_fields = []
        update_values = []
        updated_records = []  # returned to the caller so a live logger can patch its rows

        # Handle name if present in request
        if "name" in data:
            name_raw = data.get("name")
            if name_raw is None or name_raw == "":
                update_fields.append("name = %s")
                update_values.append(None)
            else:
                name_str = str(name_raw).strip()
                # Override-only: this endpoint targets linked rows (WHERE tune_id
                # below), so saving back the display name unchanged must not create
                # a spurious per-night override.
                name_str = normalize_override_name(cur, session_id, tune_id, name_str)
                update_fields.append("name = %s")
                update_values.append(name_str if name_str else None)

        # Handle key_override if present in request
        if "key_override" in data:
            key_raw = data.get("key_override")
            if key_raw is None or key_raw == "":
                update_fields.append("key_override = %s")
                update_values.append(None)
            else:
                key_str = str(key_raw).strip()
                update_fields.append("key_override = %s")
                update_values.append(key_str if key_str else None)

        # Handle setting_override if present in request
        if "setting_override" in data:
            setting_raw = data.get("setting_override")
            if setting_raw is None or setting_raw == "" or setting_raw == "null":
                update_fields.append("setting_override = %s")
                update_values.append(None)
            else:
                try:
                    update_fields.append("setting_override = %s")
                    update_values.append(int(setting_raw))
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "Invalid setting_override value"}), 400

        # Update the session_instance_tune record - only update fields that were in the request
        if update_fields:
            # Always update last_modified_user_id
            update_fields.append("last_modified_user_id = %s")
            update_values.append(get_current_user_id())
            update_values.extend([session_instance_id, tune_id])

            cur.execute(
                f"""
                UPDATE session_instance_tune
                SET {', '.join(update_fields)}
                WHERE session_instance_id = %s AND tune_id = %s
            """,
                tuple(update_values),
            )

            # Broadcast the edit to any live-logging clients watching this instance
            # (spec 024): emit a change_tune feed event per affected record + NOTIFY,
            # in the same transaction, so they update in real time. Best-effort — a
            # failure here must not block the edit itself.
            #
            # The same records go back in the response: the editor's own screen must
            # not have to wait for its edit to make the round trip through the feed.
            try:
                from live_logging_routes import emit_change_tune, _reselect
                cur.execute(
                    "SELECT session_instance_tune_id FROM session_instance_tune "
                    "WHERE session_instance_id = %s AND tune_id = %s AND record_type = 'tune' AND deleted = FALSE",
                    (session_instance_id, tune_id),
                )
                for (rid,) in cur.fetchall():
                    emit_change_tune(cur, session_instance_id, rid, get_current_user_id())
                    updated_records.append(_reselect(cur, rid))
            except Exception as e:
                print(f"live broadcast (change_tune) failed: {e}")

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Tune details updated successfully",
            "records": updated_records,
        })

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify(
            {"success": False, "message": f"Error updating tune details: {str(e)}"}
        ), 500


@api_login_required
def update_set_started_by(session_instance_id, set_index):
    """
    Update the started_by_person_id for all tunes in a set.

    PUT /api/session_instance/<session_instance_id>/sets/<set_index>/started_by

    Request body:
    {
        "person_id": int or null
    }
    """
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"success": False, "message": "No data provided"}), 400

        person_id = data.get("person_id")
        # Allow null/None to clear the value
        if person_id == "":
            person_id = None

        conn = get_db_connection()
        cur = conn.cursor()

        # Verify session instance exists and get session_id
        cur.execute(
            "SELECT session_id FROM session_instance WHERE session_instance_id = %s",
            (session_instance_id,)
        )
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "message": "Session instance not found"}), 404

        session_id = session_result[0]

        # If setting a person_id (not clearing), verify the person exists and is active
        if person_id is not None:
            cur.execute(
                "SELECT first_name, last_name, active FROM person WHERE person_id = %s",
                (person_id,)
            )
            person_result = cur.fetchone()
            if not person_result:
                cur.close()
                conn.close()
                return jsonify({"success": False, "message": "Person not found"}), 404
            if not person_result[2]:  # active is False
                person_name = f"{person_result[0]} {person_result[1]}"
                cur.close()
                conn.close()
                return jsonify({"success": False, "message": f"{person_name} is deactivated and cannot be set as 'Started By'"}), 400

        # Check if user has permission to edit this session (must be a session member)
        if not current_user.is_system_admin:
            cur.execute(
                """
                SELECT 1 FROM session_person
                WHERE session_id = %s AND person_id = %s
            """,
                (session_id, current_user.person_id),
            )
            is_session_member = cur.fetchone()
            if not is_session_member:
                return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Get all tunes for this session instance ordered by order_position
        cur.execute(
            """
            SELECT session_instance_tune_id, record_type
            FROM session_instance_tune
            WHERE session_instance_id = %s
            ORDER BY order_position
        """,
            (session_instance_id,),
        )
        tunes = cur.fetchall()

        if not tunes:
            return jsonify({"success": False, "message": "No tunes found"}), 404

        # Group tunes into sets by break records
        sets = segment_records_into_sets(tunes, type_index=1)

        # Validate set_index
        if set_index < 0 or set_index >= len(sets):
            return jsonify({"success": False, "message": f"Invalid set index: {set_index}"}), 400

        # Get the tune IDs in the specified set
        target_set = sets[set_index]
        tune_ids = [tune[0] for tune in target_set]  # session_instance_tune_id

        # Update all tunes in the set
        cur.execute(
            """
            UPDATE session_instance_tune
            SET started_by_person_id = %s, last_modified_date = NOW(), last_modified_user_id = %s
            WHERE session_instance_tune_id = ANY(%s)
        """,
            (person_id, get_current_user_id(), tune_ids),
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"Updated {len(tune_ids)} tunes in set {set_index}",
            "updated_count": len(tune_ids)
        })

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify(
            {"success": False, "message": f"Error updating set started_by: {str(e)}"}
        ), 500


@api_login_required
def get_admin_tune_detail(tune_id):
    """
    Get detailed information about a tune for admin view.

    GET /api/admin/tunes/<tune_id>

    Returns tune details with global play history across all sessions.
    """
    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        tune_id, redirected_from = follow_tune_redirect(cur, tune_id)

        # Get tune basic info
        cur.execute(
            """
            SELECT name, tune_type, tunebook_count_cached, tunebook_count_cached_date
            FROM tune
            WHERE tune_id = %s
        """,
            (tune_id,),
        )
        tune_info = cur.fetchone()

        if not tune_info:
            return jsonify({"success": False, "message": "Tune not found"}), 404

        tune_name, tune_type, tunebook_count, tunebook_count_cached_date = tune_info

        # Get ABC notation from the first setting (ordered by setting_id ASC)
        abc_notation = None
        incipit_abc = None
        abc_image = None
        incipit_image = None
        first_setting_id = None
        setting_key = None
        cur.execute(
            """
            SELECT setting_id, abc, incipit_abc, image, incipit_image, key
            FROM tune_setting
            WHERE tune_id = %s
            ORDER BY setting_id ASC
            LIMIT 1
        """,
            (tune_id,),
        )
        setting_result = cur.fetchone()
        if setting_result:
            first_setting_id = setting_result[0]
            abc_notation = setting_result[1]
            incipit_abc = setting_result[2]
            abc_image = setting_result[3]
            incipit_image = setting_result[4]
            setting_key = setting_result[5]

        # Get count of distinct sessions playing this tune
        cur.execute(
            """
            SELECT COUNT(DISTINCT session_id)
            FROM session_tune
            WHERE tune_id = %s
        """,
            (tune_id,),
        )
        session_count_result = cur.fetchone()
        session_count = session_count_result[0] if session_count_result else 0

        # Get global play count
        cur.execute(
            """
            SELECT COUNT(DISTINCT session_instance_id)
            FROM session_instance_tune
            WHERE tune_id = %s
        """,
            (tune_id,),
        )
        play_count_result = cur.fetchone()
        global_play_count = play_count_result[0] if play_count_result else 0

        # How many people have this tune on their Ceol.io tune list
        cur.execute(
            "SELECT COUNT(*) FROM person_tune WHERE tune_id = %s", (tune_id,)
        )
        person_list_result = cur.fetchone()
        person_list_count = person_list_result[0] if person_list_result else 0

        # Play history is NOT fetched here — the modal lazily loads it from
        # /api/tunes/<id>/history when the History tab is first viewed.

        conn.close()

        # Build response
        return jsonify(
            {
                "success": True,
                "redirected_from": redirected_from,
                "tune": {
                    "tune_id": tune_id,
                    "name": tune_name,
                    "tune_name": tune_name,
                    "tune_type": tune_type,
                    "setting_id": first_setting_id,
                    "setting_key": setting_key,
                    "abc": abc_notation,
                    "incipit_abc": incipit_abc,
                    "image": bytea_to_base64(abc_image),
                    "incipit_image": bytea_to_base64(incipit_image),
                    "tunebook_count": tunebook_count,
                    "tunebook_count_cached": tunebook_count,
                    "tunebook_count_cached_date": (
                        tunebook_count_cached_date.isoformat()
                        if tunebook_count_cached_date
                        else None
                    ),
                    "session_count": session_count,
                    "global_play_count": global_play_count,
                    "person_list_count": person_list_count,
                },
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error retrieving tune details: {str(e)}"}
        ), 500

# ========================================
# Admin Cache Settings
# ========================================


@api_login_required
def run_cache_settings():
    """Run the cache missing settings script"""
    import subprocess
    import os
    import time
    import re

    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        # Get the project root directory
        project_root = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(project_root, "scripts", "cache_missing_settings.py")

        # Run the script and capture output
        start_time = time.time()

        # Prepare environment - force production ABC renderer
        env = os.environ.copy()
        # Always use production ABC renderer (don't inherit old localhost value)
        env['ABC_RENDERER_URL'] = 'https://abc-renderer.onrender.com'

        result = subprocess.run(
            ["python3", script_path, "--skip-defaults"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            env=env
        )

        elapsed_time = time.time() - start_time

        output = result.stdout + result.stderr

        # Parse the output to extract statistics
        stats = {
            "total": 0,
            "cached": 0,
            "abc_updated": 0,
            "images_rendered": 0,
            "already_cached": 0,
            "failed": 0,
            "api_calls": 0,
            "time_minutes": elapsed_time / 60,
            "errors": []
        }

        # Extract stats from output using regex
        if "Total settings processed:" in output:
            match = re.search(r"Total settings processed:\s*(\d+)", output)
            if match:
                stats["total"] = int(match.group(1))

        if "Newly cached:" in output:
            match = re.search(r"Newly cached:\s*(\d+)", output)
            if match:
                stats["cached"] = int(match.group(1))

        if "ABC updated:" in output:
            match = re.search(r"ABC updated:\s*(\d+)", output)
            if match:
                stats["abc_updated"] = int(match.group(1))

        if "Images rendered:" in output:
            match = re.search(r"Images rendered:\s*(\d+)", output)
            if match:
                stats["images_rendered"] = int(match.group(1))

        if "Already cached:" in output:
            match = re.search(r"Already cached:\s*(\d+)", output)
            if match:
                stats["already_cached"] = int(match.group(1))

        if "Failed:" in output:
            match = re.search(r"Failed:\s*(\d+)", output)
            if match:
                stats["failed"] = int(match.group(1))

        if "thesession.org API calls:" in output:
            match = re.search(r"thesession\.org API calls:\s*(\d+)", output)
            if match:
                stats["api_calls"] = int(match.group(1))

        # Extract errors
        errors_section = re.search(r"Errors \((\d+)\):(.*?)(?=\n\n|\Z)", output, re.DOTALL)
        if errors_section:
            error_lines = errors_section.group(2).strip().split("\n")
            stats["errors"] = [line.strip().lstrip("- ") for line in error_lines if line.strip().startswith("-")]

        if result.returncode == 0:
            return jsonify({
                "success": True,
                "output": output,
                "results": stats
            })
        else:
            return jsonify({
                "success": False,
                "error": "Script failed",
                "output": output,
                "results": stats
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "error": "Script timed out after 5 minutes"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@api_login_required
def get_cache_settings_stats():
    """Get statistics about cached tune settings"""
    # Check if user is system admin
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get statistics about cached settings
        cur.execute("""
            SELECT 
                COUNT(*) as total_settings,
                COUNT(CASE WHEN abc IS NOT NULL AND abc != '' THEN 1 END) as has_abc,
                COUNT(CASE WHEN image IS NOT NULL THEN 1 END) as has_image,
                COUNT(CASE WHEN incipit_image IS NOT NULL THEN 1 END) as has_incipit_image,
                COUNT(CASE WHEN abc IS NOT NULL AND abc != '' AND image IS NOT NULL AND incipit_image IS NOT NULL THEN 1 END) as fully_cached,
                COUNT(CASE WHEN abc IS NULL OR abc = '' THEN 1 END) as missing_abc,
                COUNT(CASE WHEN (abc IS NOT NULL AND abc != '') AND (image IS NULL OR incipit_image IS NULL) THEN 1 END) as missing_images
            FROM tune_setting
        """)
        
        result = cur.fetchone()
        
        # Get count of referenced settings (from person_tune, session_tune, session_instance_tune)
        cur.execute("""
            SELECT COUNT(DISTINCT setting_id) as referenced_settings
            FROM (
                SELECT setting_id FROM person_tune WHERE setting_id IS NOT NULL
                UNION
                SELECT setting_id FROM session_tune WHERE setting_id IS NOT NULL
                UNION
                SELECT setting_override as setting_id FROM session_instance_tune WHERE setting_override IS NOT NULL
            ) as all_settings
        """)
        referenced_result = cur.fetchone()

        # Get count of referenced settings that don't exist in tune_setting yet
        cur.execute("""
            SELECT COUNT(DISTINCT all_refs.setting_id) as missing_records
            FROM (
                SELECT setting_id FROM person_tune WHERE setting_id IS NOT NULL
                UNION
                SELECT setting_id FROM session_tune WHERE setting_id IS NOT NULL
                UNION
                SELECT setting_override as setting_id FROM session_instance_tune WHERE setting_override IS NOT NULL
            ) as all_refs
            LEFT JOIN tune_setting ts ON all_refs.setting_id = ts.setting_id
            WHERE ts.setting_id IS NULL
        """)
        missing_records_result = cur.fetchone()

        # Get count of tunes
        cur.execute("SELECT COUNT(*) FROM tune")
        tune_count = cur.fetchone()[0]

        cur.close()
        conn.close()

        stats = {
            "total_settings": result[0],
            "has_abc": result[1],
            "has_image": result[2],
            "has_incipit_image": result[3],
            "fully_cached": result[4],
            "missing_abc": result[5],
            "missing_images": result[6],
            "referenced_settings": referenced_result[0],
            "missing_records": missing_records_result[0],
            "total_tunes": tune_count
        }

        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@public_api  # backs the logged-out session Logs tab (frontend/src/sessionpage/LogsTab.svelte, warmed by static/js/prefetch.js)
def get_session_logs(session_path):
    """
    Get all session instances (logs) for a session.
    No authentication required - public endpoint.

    Returns:
    {
        "success": true,
        "instances_by_year": {...},
        "sorted_years": [...],
        "instances_by_day": {...},
        "sorted_days": [...],
        "session_type": "regular" | "festival"
    }
    """
    try:
        from datetime import datetime, time as datetime_time

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID and type
        cur.execute(
            "SELECT session_id, session_type FROM session WHERE path = %s",
            (session_path,)
        )
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id = session_result[0]
        session_type = session_result[1] or "regular"

        # Fetch past session instances with instance counts per date
        cur.execute(
            """
            SELECT si.date, si.location_override, si.start_time, si.end_time,
                   si.session_instance_id,
                   COUNT(*) OVER (PARTITION BY si.date) as instances_on_date,
                   (SELECT COUNT(*) FROM session_instance_tune sit
                    WHERE sit.session_instance_id = si.session_instance_id
                      AND sit.record_type = 'tune'
                      AND sit.deleted = FALSE) as tune_count
            FROM session_instance si
            WHERE si.session_id = %s
            ORDER BY si.date DESC, si.session_instance_id ASC
        """,
            (session_id,),
        )
        past_instances = cur.fetchall()
        cur.close()
        conn.close()

        # Group past instances by year or by day depending on session type
        instances_by_year = {}
        instances_by_day = {}

        if session_type == "festival":
            # For festivals, group by day and include time/location info
            for instance in past_instances:
                date = instance[0]
                day_key = date.isoformat()  # Convert to ISO string for JSON
                if day_key not in instances_by_day:
                    instances_by_day[day_key] = []
                instances_by_day[day_key].append({
                    'date': date.isoformat(),
                    'location_override': instance[1],
                    'start_time': instance[2].isoformat() if instance[2] else None,
                    'end_time': instance[3].isoformat() if instance[3] else None,
                    'session_instance_id': instance[4],
                    'multiple_on_date': instance[5] > 1,
                    'tune_count': instance[6]
                })
        else:
            # For regular sessions, group by year and include time info
            for instance in past_instances:
                date = instance[0]
                year = date.year
                if year not in instances_by_year:
                    instances_by_year[year] = []
                instances_by_year[year].append({
                    'date': date.isoformat(),
                    'location_override': instance[1],
                    'start_time': instance[2].isoformat() if instance[2] else None,
                    'end_time': instance[3].isoformat() if instance[3] else None,
                    'session_instance_id': instance[4],
                    'multiple_on_date': instance[5] > 1,
                    'tune_count': instance[6]
                })

        # Sort instances within each group by start_time
        for day_key in instances_by_day:
            instances_by_day[day_key].sort(
                key=lambda x: x['start_time'] if x['start_time'] else ''
            )

        for year in instances_by_year:
            instances_by_year[year].sort(
                key=lambda x: (x['date'], x['start_time'] if x['start_time'] else ''),
                reverse=True
            )

        # Sort years in descending order (for regular sessions)
        sorted_years = sorted(instances_by_year.keys(), reverse=True) if instances_by_year else []

        # Sort days in ascending order for festivals (chronological)
        sorted_days = sorted(instances_by_day.keys(), reverse=False) if instances_by_day else []

        return jsonify({
            "success": True,
            "instances_by_year": instances_by_year,
            "sorted_years": sorted_years,
            "instances_by_day": instances_by_day,
            "sorted_days": sorted_days,
            "session_type": session_type
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@public_api  # backs the logged-out /sessions/<path> page (the shell embeds the same serializer output; flags reflect the anonymous user)
def get_session_detail(session_path):
    """
    GET /api/sessions/<path>/detail — the aggregate session-detail payload
    (spec 035 Step 4b): session row + recurrence_readable, permission flags,
    today in the session's timezone, default tab, first page of the repertoire,
    and the popular list. The /sessions/<path> page shell embeds the SAME
    serializer output, so the two cannot drift. Public endpoint (flags reflect
    the current user, anonymous included).
    """
    try:
        from serializers import build_session_detail_payload
        from flask import session as flask_session

        person_id = getattr(current_user, 'person_id', None) if current_user.is_authenticated else None

        conn = get_db_connection()
        try:
            payload = build_session_detail_payload(
                conn,
                session_path,
                person_id=person_id,
                is_system_admin=flask_session.get("is_system_admin", False),
                is_logged_in=current_user.is_authenticated,
            )
        finally:
            conn.close()

        if payload is None:
            return jsonify({"success": False, "message": "Session not found"}), 404
        return jsonify(payload)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@public_api  # backs the logged-out session Tunes tab pagination (frontend/src/sessionpage/TunesTab.svelte, warmed by static/js/prefetch.js)
def get_session_tunes_remaining(session_path):
    """
    Get remaining session tunes (after the first 20) for a session.
    No authentication required - public endpoint. Rows come from the same
    serializer the page embed uses (serializers.load_session_tunes).
    """
    try:
        from serializers import load_session_tunes

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
            session_result = cur.fetchone()
            if not session_result:
                return jsonify({"success": False, "message": "Session not found"}), 404

            # Same shape as the embedded first page: logged-in viewers also get
            # the per-tune attended_play_count (spec 033 R4) their filter needs.
            person_id = None
            if current_user.is_authenticated:
                cur.execute(
                    "SELECT person_id FROM user_account WHERE user_id = %s",
                    (current_user.user_id,),
                )
                pr = cur.fetchone()
                person_id = pr[0] if pr else None

            tunes_list = load_session_tunes(conn, session_result[0], offset=20, person_id=person_id)
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "tunes": tunes_list
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_login_required
def join_session(session_path):
    """Join a session yourself (spec 034).

    POST /api/sessions/<session_path>/join   Body: {relationship: 'member'|'visitor'}

    The UI asks one question -- "Are you a local, or just visiting?" -- and that is all this
    endpoint decides. It lands `confirmed = FALSE`, always: this is the self-serve path, and
    the whole point of `confirmed` is that people-visibility is granted by the session, never
    claimed by joining it. Otherwise anyone with an account could join any session and read
    every member's name off the People tab.
    """
    try:
        data = request.get_json(silent=True) or {}
        relationship = data.get("relationship", "member")
        if relationship not in ("member", "visitor"):
            return (
                jsonify({"success": False, "message": "relationship must be 'member' or 'visitor'"}),
                400,
            )

        # Get user's person_id
        user_person_id = getattr(current_user, 'person_id', None)
        if not user_person_id:
            return jsonify({"success": False, "message": "User not linked to person"}), 403

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id from path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id = session_result[0]

        # Check if already a member
        cur.execute(
            "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, user_person_id)
        )
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Already a member of this session"}), 400

        # Unconfirmed, always. See the docstring.
        cur.execute(
            """
            INSERT INTO session_person
                (session_id, person_id, relationship, confirmed, archived, is_admin, created_by_user_id)
            VALUES (%s, %s, %s, FALSE, FALSE, FALSE, %s)
            """,
            (session_id, user_person_id, relationship, get_current_user_id())
        )
        save_to_history(
            cur,
            "session_person",
            "INSERT",
            (session_id, user_person_id),
            user_id=get_current_user_id(),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": "Successfully joined session",
                "relationship": relationship,
                "confirmed": False,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to join session: {str(e)}"}), 500


# History table mapping for drill-down
HISTORY_TABLE_MAP = {
    'session': ('session_history', 'session_id', ['name', 'path', 'city', 'state']),
    'session_instance': ('session_instance_history', 'session_instance_id', ['date', 'comments', 'is_cancelled']),
    'tune': ('tune_history', 'tune_id', ['name', 'tune_type']),
    'tune_setting': ('tune_setting_history', 'setting_id', ['key', 'abc']),
    'session_tune': ('session_tune_history', 'session_id', ['alias', 'key']),  # composite key
    'session_tune_alias': ('session_tune_alias_history', 'session_tune_alias_id', ['alias']),
    'session_instance_tune': ('session_instance_tune_history', 'session_instance_tune_id', ['name']),
    'person': ('person_history', 'person_id', ['first_name', 'last_name', 'email']),
    'user_account': ('user_account_history', 'user_id', ['username', 'is_active']),
    'person_instrument': ('person_instrument_history', 'person_id', ['instrument']),  # composite key
    'person_tune': ('person_tune_history', 'person_id', ['status']),  # composite key
    'session_person': ('session_person_history', 'session_id',
                       ['relationship', 'confirmed', 'archived', 'is_admin']),  # composite key
    'session_instance_person': ('session_instance_person_history', 'session_instance_id', ['attendance', 'comment']),  # composite key
}


def api_admin_history(entity_type, entity_id):
    """Get change history for a specific record - admin only"""
    from flask_login import current_user

    if not current_user.is_authenticated or not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    if entity_type not in HISTORY_TABLE_MAP:
        return jsonify({"success": False, "error": f"Unknown entity type: {entity_type}"}), 400

    history_table, id_column, _ = HISTORY_TABLE_MAP[entity_type]

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Handle composite keys (contain /)
        if '/' in entity_id:
            parts = entity_id.split('/')
            if entity_type == 'session_tune':
                where_clause = "session_id = %s AND tune_id = %s"
                params = [int(parts[0]), int(parts[1])]
            elif entity_type == 'person_instrument':
                where_clause = "person_id = %s AND instrument = %s"
                params = [int(parts[0]), parts[1]]
            elif entity_type == 'person_tune':
                where_clause = "person_id = %s AND tune_id = %s"
                params = [int(parts[0]), int(parts[1])]
            elif entity_type == 'session_person':
                where_clause = "session_id = %s AND person_id = %s"
                params = [int(parts[0]), int(parts[1])]
            elif entity_type == 'session_instance_person':
                where_clause = "session_instance_id = %s AND person_id = %s"
                params = [int(parts[0]), int(parts[1])]
            else:
                where_clause = f"{id_column} = %s"
                params = [entity_id]
        else:
            where_clause = f"{id_column} = %s"
            params = [int(entity_id)]

        query = f"""
            SELECT
                h.changed_at,
                h.operation,
                h.changed_by_user_id,
                u.username
            FROM {history_table} h
            LEFT JOIN user_account u ON h.changed_by_user_id = u.user_id
            WHERE {where_clause}
            ORDER BY h.changed_at DESC
            LIMIT 100
        """
        cur.execute(query, params)

        history = []
        for row in cur.fetchall():
            changed_at, operation, changed_by_user_id, username = row
            history.append({
                'changed_at': changed_at.strftime('%Y-%m-%d %H:%M:%S') if changed_at else None,
                'operation': operation,
                'changed_by_user_id': changed_by_user_id,
                'changed_by': username or 'System',
            })

        return jsonify({"success": True, "history": history})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# Tune Copy/Bulk Operations
# ============================================================================

@api_login_required
def get_user_admin_sessions():
    """
    Get list of sessions the current user is admin of.

    GET /api/user/admin-sessions

    Returns:
    {
        "success": true,
        "sessions": [
            {"session_id": int, "name": str, "path": str},
            ...
        ]
    }
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Get person_id from current user
        cur.execute(
            "SELECT person_id FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        person_row = cur.fetchone()
        if not person_row:
            return jsonify({"success": False, "error": "User's person record not found"}), 404

        person_id = person_row[0]

        # Get sessions where user is admin
        cur.execute(
            """
            SELECT s.session_id, s.name, s.path
            FROM session s
            JOIN session_person sp ON s.session_id = sp.session_id
            WHERE sp.person_id = %s AND sp.is_admin = TRUE
            ORDER BY s.name
            """,
            (person_id,)
        )

        sessions = []
        for row in cur.fetchall():
            sessions.append({
                "session_id": row[0],
                "name": row[1],
                "path": row[2]
            })

        return jsonify({"success": True, "sessions": sessions})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def copy_tunes_to_destination():
    """
    Copy multiple tunes to a destination (My Tunes or a session).

    POST /api/tunes/copy

    Request body:
    {
        "tune_ids": [int, ...],
        "destination_type": "my_tunes" | "session",
        "destination_session_path": str (required if destination_type is "session"),
        "learn_status": "want to learn" | "learning" | "learned" (required if destination_type is "my_tunes")
    }

    Returns:
    {
        "success": true,
        "copied_count": int,
        "skipped_count": int,
        "message": str,
        "redirect_url": str
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    tune_ids = data.get("tune_ids", [])
    destination_type = data.get("destination_type")
    destination_session_path = data.get("destination_session_path")
    learn_status = data.get("learn_status", "want to learn")

    if not tune_ids:
        return jsonify({"success": False, "error": "No tunes selected"}), 400

    if destination_type not in ["my_tunes", "session"]:
        return jsonify({"success": False, "error": "Invalid destination type"}), 400

    if destination_type == "session" and not destination_session_path:
        return jsonify({"success": False, "error": "Session path is required for session destination"}), 400

    # Validate learn_status for my_tunes
    if destination_type == "my_tunes":
        valid_statuses = ["want to learn", "learning", "learned"]
        if learn_status not in valid_statuses:
            return jsonify({"success": False, "error": f"learn_status must be one of: {', '.join(valid_statuses)}"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Get person_id from current user
        cur.execute(
            "SELECT person_id FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        person_row = cur.fetchone()
        if not person_row:
            return jsonify({"success": False, "error": "User's person record not found"}), 404

        person_id = person_row[0]

        copied_count = 0
        skipped_count = 0
        destination_name = ""
        redirect_url = ""

        if destination_type == "my_tunes":
            destination_name = "My Tunes"
            redirect_url = "/my-tunes"

            for tune_id in tune_ids:
                # Check if tune already exists in person_tune
                cur.execute(
                    "SELECT person_tune_id FROM person_tune WHERE person_id = %s AND tune_id = %s",
                    (person_id, tune_id)
                )
                if cur.fetchone():
                    skipped_count += 1
                    continue

                # Insert into person_tune
                cur.execute(
                    """
                    INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count, created_by_user_id)
                    VALUES (%s, %s, %s, 1, %s)
                    """,
                    (person_id, tune_id, learn_status, get_current_user_id())
                )
                copied_count += 1

        else:  # destination_type == "session"
            # Get session_id and verify user is admin
            cur.execute("SELECT session_id, name FROM session WHERE path = %s", (destination_session_path,))
            session_result = cur.fetchone()
            if not session_result:
                return jsonify({"success": False, "error": "Destination session not found"}), 404

            session_id, session_name = session_result
            destination_name = session_name
            redirect_url = f"/sessions/{destination_session_path}/tunes"

            # Check if user is admin of this session (or system admin)
            if not current_user.is_system_admin:
                cur.execute(
                    "SELECT is_admin FROM session_person WHERE session_id = %s AND person_id = %s",
                    (session_id, person_id)
                )
                admin_row = cur.fetchone()
                if not admin_row or not admin_row[0]:
                    return jsonify({"success": False, "error": "You must be an admin of the destination session"}), 403

            for tune_id in tune_ids:
                # Check if tune already exists in session_tune
                cur.execute(
                    "SELECT tune_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
                    (session_id, tune_id)
                )
                if cur.fetchone():
                    skipped_count += 1
                    continue

                # Insert into session_tune
                cur.execute(
                    """
                    INSERT INTO session_tune (session_id, tune_id, created_by_user_id)
                    VALUES (%s, %s, %s)
                    """,
                    (session_id, tune_id, get_current_user_id())
                )

                # Save to history
                save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id), user_id=get_current_user_id())

                copied_count += 1

        conn.commit()

        # Build message
        message = f"Copied {copied_count} tune{'s' if copied_count != 1 else ''} to {destination_name}."
        if skipped_count > 0:
            message += f" ({skipped_count} tune{'s' if skipped_count != 1 else ''} skipped because it was already there.)"

        return jsonify({
            "success": True,
            "copied_count": copied_count,
            "skipped_count": skipped_count,
            "message": message,
            "redirect_url": redirect_url
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


# =============================================================================
# Recording endpoints (admin only)
# =============================================================================

def _require_system_admin():
    """Check if current user is a system admin. Returns error response or None."""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Admin access required"}), 403
    return None


def start_recording(session_instance_id):
    """POST /api/session_instance/<id>/recordings — Start a new recording."""
    admin_check = _require_system_admin()
    if admin_check:
        return admin_check

    conn = get_db_connection()
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        cur = conn.cursor()

        # Verify session instance exists
        cur.execute("SELECT session_instance_id FROM session_instance WHERE session_instance_id = %s",
                     (session_instance_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        person_id = current_user.person_id
        user_id = get_current_user_id()

        cur.execute(
            """
            INSERT INTO recording (session_instance_id, person_id, source, status, device_info,
                format, sample_rate, channels, bitrate, client_started_at,
                created_by_user_id, last_modified_user_id)
            VALUES (%s, %s, 'live', 'started', %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING recording_id
            """,
            (
                session_instance_id,
                person_id,
                json.dumps(data.get("device_info")) if data.get("device_info") else None,
                data.get("format"),
                data.get("sample_rate"),
                data.get("channels"),
                data.get("bitrate"),
                data.get("client_started_at"),
                user_id,
                user_id,
            ),
        )
        recording_id = cur.fetchone()[0]

        # Set the s3_prefix
        s3_prefix = f"recordings/{recording_id}/"
        cur.execute("UPDATE recording SET s3_prefix = %s WHERE recording_id = %s",
                     (s3_prefix, recording_id))

        # Log start event
        cur.execute(
            """
            INSERT INTO recording_event (recording_id, event_type, client_timestamp)
            VALUES (%s, 'start', %s)
            """,
            (recording_id, data.get("client_started_at")),
        )

        # Save to history
        save_to_history(cur, "recording", "INSERT", recording_id, user_id=user_id)

        conn.commit()
        return jsonify({
            "success": True,
            "recording_id": recording_id,
            "s3_prefix": s3_prefix,
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


def upload_chunk(recording_id):
    """POST /api/recordings/<id>/chunks — Upload an audio chunk."""
    admin_check = _require_system_admin()
    if admin_check:
        return admin_check

    conn = get_db_connection()
    try:
        audio_file = request.files.get("audio")
        if not audio_file:
            return jsonify({"success": False, "error": "No audio file provided"}), 400

        sequence_number = request.form.get("sequence_number", type=int)
        start_timestamp_ms = request.form.get("start_timestamp_ms", type=int)
        end_timestamp_ms = request.form.get("end_timestamp_ms", type=int)
        client_checksum = request.form.get("checksum")

        if sequence_number is None or start_timestamp_ms is None or end_timestamp_ms is None:
            return jsonify({"success": False, "error": "sequence_number, start_timestamp_ms, and end_timestamp_ms are required"}), 400

        cur = conn.cursor()

        # Verify recording exists
        cur.execute("SELECT person_id, status FROM recording WHERE recording_id = %s", (recording_id,))
        rec = cur.fetchone()
        if not rec:
            return jsonify({"success": False, "error": "Recording not found"}), 404

        audio_data = audio_file.read()
        file_size = len(audio_data)
        checksum = compute_checksum(audio_data)

        # Verify checksum if provided
        if client_checksum and client_checksum != checksum:
            return jsonify({"success": False, "error": "Checksum mismatch"}), 400

        # Upload to S3
        s3_key = upload_chunk_to_s3(recording_id, sequence_number, audio_data)

        user_id = get_current_user_id()

        # Insert chunk record (upsert in case of retry)
        cur.execute(
            """
            INSERT INTO recording_chunk (recording_id, sequence_number, start_timestamp_ms, end_timestamp_ms,
                s3_key, file_size_bytes, upload_status, checksum)
            VALUES (%s, %s, %s, %s, %s, %s, 'uploaded', %s)
            ON CONFLICT (recording_id, sequence_number)
            DO UPDATE SET s3_key = EXCLUDED.s3_key, file_size_bytes = EXCLUDED.file_size_bytes,
                upload_status = 'uploaded', checksum = EXCLUDED.checksum
            RETURNING recording_chunk_id
            """,
            (recording_id, sequence_number, start_timestamp_ms, end_timestamp_ms,
             s3_key, file_size, checksum),
        )
        chunk_id = cur.fetchone()[0]

        # Update recording aggregates
        cur.execute(
            """
            UPDATE recording SET
                status = CASE WHEN status = 'started' THEN 'recording' ELSE status END,
                total_chunks = (SELECT COUNT(*) FROM recording_chunk WHERE recording_id = %s AND upload_status = 'uploaded'),
                total_duration_ms = COALESCE((SELECT MAX(end_timestamp_ms) FROM recording_chunk WHERE recording_id = %s AND upload_status = 'uploaded'), 0),
                total_size_bytes = COALESCE((SELECT SUM(file_size_bytes) FROM recording_chunk WHERE recording_id = %s AND upload_status = 'uploaded'), 0),
                last_modified_user_id = %s
            WHERE recording_id = %s
            """,
            (recording_id, recording_id, recording_id, user_id, recording_id),
        )

        conn.commit()
        return jsonify({
            "success": True,
            "recording_chunk_id": chunk_id,
            "s3_key": s3_key,
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


def update_recording_status(recording_id):
    """PUT /api/recordings/<id>/status — Pause/resume/stop a recording."""
    admin_check = _require_system_admin()
    if admin_check:
        return admin_check

    conn = get_db_connection()
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        new_status = data.get("status")
        if new_status not in ("recording", "paused", "stopped", "failed"):
            return jsonify({"success": False, "error": "Invalid status. Must be: recording, paused, stopped, failed"}), 400

        cur = conn.cursor()
        user_id = get_current_user_id()

        # Verify recording exists
        cur.execute("SELECT status FROM recording WHERE recording_id = %s", (recording_id,))
        rec = cur.fetchone()
        if not rec:
            return jsonify({"success": False, "error": "Recording not found"}), 404

        old_status = rec[0]

        # Save to history before update
        save_to_history(cur, "recording", "UPDATE", recording_id, user_id=user_id)

        cur.execute(
            "UPDATE recording SET status = %s, last_modified_user_id = %s WHERE recording_id = %s",
            (new_status, user_id, recording_id),
        )

        # Map status changes to event types
        event_type_map = {
            "paused": "pause",
            "recording": "resume",
            "stopped": "stop",
            "failed": "error",
        }
        event_type = event_type_map.get(new_status, new_status)

        cur.execute(
            """
            INSERT INTO recording_event (recording_id, event_type, event_data, client_timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (
                recording_id,
                event_type,
                json.dumps(data.get("event_data")) if data.get("event_data") else None,
                data.get("client_timestamp"),
            ),
        )

        conn.commit()

        return jsonify({
            "success": True,
            "recording_id": recording_id,
            "old_status": old_status,
            "new_status": new_status,
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


def list_recordings(session_instance_id):
    """GET /api/session_instance/<id>/recordings — List recordings for a session instance."""
    admin_check = _require_system_admin()
    if admin_check:
        return admin_check

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Verify session instance exists
        cur.execute("SELECT session_instance_id FROM session_instance WHERE session_instance_id = %s",
                     (session_instance_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        cur.execute(
            """
            SELECT r.recording_id, r.person_id, p.first_name, p.last_name, r.source, r.status,
                   r.total_chunks, r.total_duration_ms, r.total_size_bytes, r.client_started_at,
                   r.created_date, r.format
            FROM recording r
            JOIN person p ON p.person_id = r.person_id
            WHERE r.session_instance_id = %s
            ORDER BY r.created_date
            """,
            (session_instance_id,),
        )

        recordings = []
        for row in cur.fetchall():
            recordings.append({
                "recording_id": row[0],
                "person_id": row[1],
                "person_name": f"{row[2] or ''} {row[3] or ''}".strip(),
                "source": row[4],
                "status": row[5],
                "total_chunks": row[6],
                "total_duration_ms": row[7],
                "total_size_bytes": row[8],
                "client_started_at": row[9].isoformat() if row[9] else None,
                "created_date": row[10].isoformat() if row[10] else None,
                "format": row[11],
            })

        return jsonify({"success": True, "recordings": recordings})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


def get_recording_playback(recording_id):
    """GET /api/recordings/<id>/playback — Get presigned URLs for playback."""
    admin_check = _require_system_admin()
    if admin_check:
        return admin_check

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Verify recording exists
        cur.execute("SELECT recording_id, total_duration_ms FROM recording WHERE recording_id = %s",
                     (recording_id,))
        rec = cur.fetchone()
        if not rec:
            return jsonify({"success": False, "error": "Recording not found"}), 404

        chunks = get_recording_timeline(cur, recording_id)

        return jsonify({
            "success": True,
            "recording_id": recording_id,
            "total_duration_ms": rec[1],
            "chunks": chunks,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


def upload_recording_file(session_instance_id):
    """POST /api/session_instance/<id>/recordings/upload — Upload a complete audio file."""
    admin_check = _require_system_admin()
    if admin_check:
        return admin_check

    conn = get_db_connection()
    tmp_path = None
    try:
        audio_file = request.files.get("audio")
        if not audio_file:
            return jsonify({"success": False, "error": "No audio file provided"}), 400

        client_started_at = request.form.get("client_started_at")

        cur = conn.cursor()

        # Verify session instance exists
        cur.execute("SELECT session_instance_id FROM session_instance WHERE session_instance_id = %s",
                     (session_instance_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "error": "Session instance not found"}), 404

        person_id = current_user.person_id
        user_id = get_current_user_id()

        # Save uploaded file to temp location
        ext = os.path.splitext(audio_file.filename)[1] if audio_file.filename else ".mp3"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
            audio_file.save(tmp)

        # Create recording row
        cur.execute(
            """
            INSERT INTO recording (session_instance_id, person_id, source, status,
                format, channels, sample_rate, bitrate, client_started_at,
                created_by_user_id, last_modified_user_id)
            VALUES (%s, %s, 'upload', 'started', %s, 1, 48000, 64000, %s, %s, %s)
            RETURNING recording_id
            """,
            (session_instance_id, person_id, "audio/webm;codecs=opus",
             client_started_at, user_id, user_id),
        )
        recording_id = cur.fetchone()[0]

        s3_prefix = f"recordings/{recording_id}/"
        cur.execute("UPDATE recording SET s3_prefix = %s WHERE recording_id = %s",
                     (s3_prefix, recording_id))

        # Chunk the file
        chunks = chunk_audio_file(tmp_path)

        total_size = 0
        total_duration = 0

        for chunk in chunks:
            s3_key = upload_chunk_to_s3(recording_id, chunk["sequence_number"], chunk["data"])
            checksum = compute_checksum(chunk["data"])
            file_size = len(chunk["data"])
            total_size += file_size
            total_duration = max(total_duration, chunk["end_ms"])

            cur.execute(
                """
                INSERT INTO recording_chunk (recording_id, sequence_number, start_timestamp_ms, end_timestamp_ms,
                    s3_key, file_size_bytes, upload_status, checksum)
                VALUES (%s, %s, %s, %s, %s, %s, 'uploaded', %s)
                """,
                (recording_id, chunk["sequence_number"], chunk["start_ms"], chunk["end_ms"],
                 s3_key, file_size, checksum),
            )

        # Update recording with final stats
        cur.execute(
            """
            UPDATE recording SET status = 'stopped', total_chunks = %s,
                total_duration_ms = %s, total_size_bytes = %s, last_modified_user_id = %s
            WHERE recording_id = %s
            """,
            (len(chunks), total_duration, total_size, user_id, recording_id),
        )

        # Log events
        cur.execute(
            "INSERT INTO recording_event (recording_id, event_type) VALUES (%s, 'start')",
            (recording_id,),
        )
        cur.execute(
            "INSERT INTO recording_event (recording_id, event_type) VALUES (%s, 'stop')",
            (recording_id,),
        )

        save_to_history(cur, "recording", "INSERT", recording_id, user_id=user_id)

        conn.commit()

        return jsonify({
            "success": True,
            "recording_id": recording_id,
            "total_chunks": len(chunks),
            "total_duration_ms": total_duration,
            "total_size_bytes": total_size,
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Page-payload endpoints (spec 035 Step 5): each returns exactly the serializer
# output its page shell embeds, so the API and the embed cannot drift.
# ---------------------------------------------------------------------------


@api_login_required
def get_person_details_api(person_id=None):
    """
    GET /api/me/details (the current user's profile) and
    GET /api/admin/people/<person_id>/details (system-admin only) — the aggregate
    person-details payload (spec 035 Step 5a): person + instruments, linked user
    account, sessions with derived roles, timezone options. The /me and
    /admin/people/<id> page shells embed the SAME serializer output.
    """
    try:
        from serializers import build_person_details_payload

        is_user_profile = person_id is None
        if is_user_profile:
            person_id = current_user.person_id
        elif not current_user.is_system_admin:
            return jsonify({"success": False, "error": "Admin access required"}), 403

        conn = get_db_connection()
        try:
            payload = build_person_details_payload(
                conn,
                person_id,
                is_user_profile=is_user_profile,
                is_system_admin=current_user.is_authenticated and current_user.is_system_admin,
            )
        finally:
            conn.close()

        if payload is None:
            return jsonify({"success": False, "message": "Person not found"}), 404
        return jsonify(payload)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_login_required
def get_session_admin_detail(session_path):
    """
    GET /api/admin/sessions/<path>/admin-detail — the session-admin page payload
    (spec 035 Step 5b): session row + timezone_display + recurrence_readable +
    auto-create / live-cache settings, plus timezone options. Gated by the same
    session-admin check the web route uses (system admin OR session-level admin).
    The /admin/sessions/<path> page shell embeds the SAME serializer output.
    """
    try:
        # Lazy import: web_routes imports from api_routes at module level.
        from serializers import build_session_admin_payload
        from web_routes import _check_session_admin_access

        if not _check_session_admin_access(session_path):
            return jsonify({"success": False, "error": "Admin access required"}), 403

        conn = get_db_connection()
        try:
            payload = build_session_admin_payload(conn, session_path)
        finally:
            conn.close()

        if payload is None:
            return jsonify({"success": False, "message": "Session not found"}), 404
        return jsonify(payload)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@public_api  # backs the public /add-session page shell (no @login_required there; only POST /api/add-session is gated)
def get_add_session_payload():
    """
    GET /api/add-session — the add-session wizard payload (timezone options +
    viewer flag). The /add-session page shell embeds the SAME serializer output
    (serializers.build_add_session_payload). Same rule as POST /api/add-session,
    different method/endpoint.
    """
    from serializers import build_add_session_payload

    return jsonify(build_add_session_payload(current_user.is_authenticated))


@api_login_required
def merge_people():
    """
    Merge two people that are the same human (system-admin only).

    POST /api/admin/people/merge

    Request body:
    {
        "loser_person_id": int (required)  — the person being absorbed/deleted,
        "winner_person_id": int (required) — the surviving person,
        "confirm": boolean (default false),
        "surviving_user_id": int — required iff BOTH people have login accounts
    }

    confirm=false returns a detailed preview: per-table move counts, every
    colliding row with the exact field-merge outcome, profile fills/discards,
    the account situation, and warnings (checked-in, active-flag mismatch).
    confirm=true executes the merge in one transaction. Hard merge: the loser
    row is deleted; history tables keep the old person_id as the audit trail.
    """
    from services.person_merge_service import (
        MergeValidationError,
        build_merge_preview,
        execute_merge,
    )

    if not current_user.is_system_admin:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Request body required"}), 400

    loser_id = data.get("loser_person_id")
    winner_id = data.get("winner_person_id")
    confirm = data.get("confirm", False)
    surviving_user_id = data.get("surviving_user_id")

    if not loser_id or not winner_id:
        return jsonify(
            {"success": False, "error": "Both loser_person_id and winner_person_id are required"}
        ), 400

    conn = get_db_connection()
    try:
        if not confirm:
            preview = build_merge_preview(conn, loser_id, winner_id)
            return jsonify(preview)

        result = execute_merge(
            conn, loser_id, winner_id, current_user.user_id, surviving_user_id=surviving_user_id
        )
        conn.commit()
        return jsonify(result)
    except MergeValidationError as e:
        conn.rollback()
        return jsonify({"success": False, "error": e.message}), e.status
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def get_admin_people_api():
    """
    GET /api/admin/people — the admin people-table payload (system-admin only):
    every person with account/login info and activity roll-ups. The
    /admin/people page shell embeds the SAME serializer output
    (serializers.build_admin_people_payload).
    """
    try:
        from serializers import build_admin_people_payload

        if not current_user.is_system_admin:
            return jsonify({"success": False, "error": "Admin access required"}), 403

        conn = get_db_connection()
        try:
            payload = build_admin_people_payload(conn)
        finally:
            conn.close()

        return jsonify(payload)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
