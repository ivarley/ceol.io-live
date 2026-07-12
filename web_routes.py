from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    make_response,
)
import random
import bcrypt
from flask_login import login_user, logout_user, login_required, current_user
import datetime
from datetime import timedelta
import re

# Import from local modules
from database import get_db_connection, save_to_history, get_current_user_id
from instruments import CANONICAL_INSTRUMENTS, normalize_instruments
from api_routes import segment_records_into_sets
from timezone_utils import (
    now_utc,
    get_timezone_display_name,
    get_timezone_display_with_offset,
)
from auth import (
    User,
    create_session,
    cleanup_expired_sessions,
    generate_password_reset_token,
    generate_verification_token,
    generate_login_token,
    log_login_event,
)
from email_utils import (
    send_password_reset_email,
    send_verification_email,
    send_login_link_email,
    verify_unsubscribe_token,
)
from recurrence_utils import to_human_readable


def home():
    try:
        if current_user.is_authenticated:
            from timezone_utils import get_today_in_timezone

            conn = get_db_connection()
            cur = conn.cursor()
            person_id = current_user.person_id

            # Learning counts
            cur.execute(
                """
                SELECT learn_status, COUNT(*)
                FROM person_tune
                WHERE person_id = %s AND learn_status IN ('learning', 'want to learn')
                GROUP BY learn_status
                """,
                (person_id,),
            )
            learning_counts = dict(cur.fetchall())
            learning_count = learning_counts.get("learning", 0)
            want_to_learn_count = learning_counts.get("want to learn", 0)

            # Suggested tune: most played at user's sessions, not already in their list
            cur.execute(
                """
                SELECT t.tune_id, t.name, t.tune_type, COUNT(sit.session_instance_tune_id) AS play_count
                FROM session_instance_tune sit
                JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                JOIN session_person sp ON si.session_id = sp.session_id AND sp.person_id = %s
                JOIN tune t ON sit.tune_id = t.tune_id
                WHERE sit.tune_id IS NOT NULL
                  AND t.redirect_to_tune_id IS NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM person_tune pt WHERE pt.person_id = %s AND pt.tune_id = sit.tune_id
                  )
                GROUP BY t.tune_id, t.name, t.tune_type, t.tunebook_count_cached
                ORDER BY play_count DESC, t.tunebook_count_cached DESC
                LIMIT 1
                """,
                (person_id, person_id),
            )
            suggested_tune_row = cur.fetchone()
            suggested_tune = None
            if suggested_tune_row:
                suggested_tune = {
                    "tune_id": suggested_tune_row[0],
                    "name": suggested_tune_row[1],
                    "tune_type": suggested_tune_row[2],
                }

            # Upcoming sessions this week (Monday-Sunday in user's timezone)
            today = get_today_in_timezone(current_user.timezone or "UTC")
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)

            cur.execute(
                """
                SELECT s.name, s.path, si.session_instance_id, si.date, si.start_time,
                       si.log_complete_date
                FROM session_person sp
                JOIN session s ON sp.session_id = s.session_id
                JOIN session_instance si ON s.session_id = si.session_id
                WHERE sp.person_id = %s
                  AND si.date BETWEEN %s AND %s
                  AND si.is_cancelled = FALSE
                ORDER BY si.date, si.start_time
                """,
                (person_id, monday, sunday),
            )
            upcoming_rows = cur.fetchall()
            upcoming_sessions = [
                {
                    "name": row[0],
                    "path": row[1],
                    "session_instance_id": row[2],
                    "date": row[3],
                    "start_time": row[4],
                    "log_complete_date": row[5],
                }
                for row in upcoming_rows
            ]

            # In-progress logs: instances the user edited in the last 30 days
            # that aren't marked complete
            cur.execute(
                """
                SELECT s.name, s.path, si.session_instance_id, si.date,
                       MAX(sit.last_modified_date) AS last_edit
                FROM session_instance_tune sit
                JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                JOIN session s ON si.session_id = s.session_id
                WHERE sit.last_modified_user_id = %s
                  AND sit.last_modified_date >= (NOW() AT TIME ZONE 'UTC') - INTERVAL '30 days'
                  AND si.log_complete_date IS NULL
                  AND si.is_cancelled = FALSE
                GROUP BY s.name, s.path, si.session_instance_id, si.date
                ORDER BY last_edit DESC
                LIMIT 3
                """,
                (current_user.user_id,),
            )
            in_progress_logs = [
                {
                    "name": row[0],
                    "path": row[1],
                    "session_instance_id": row[2],
                    "date": row[3],
                    "last_edit": row[4],
                }
                for row in cur.fetchall()
            ]

            cur.close()
            conn.close()

            return render_template(
                "home.html",
                learning_count=learning_count,
                want_to_learn_count=want_to_learn_count,
                suggested_tune=suggested_tune,
                upcoming_sessions=upcoming_sessions,
                in_progress_logs=in_progress_logs,
                current_year=today.year,
            )
        else:
            return render_template("home.html")

    except Exception as e:
        return f"Database connection failed: {str(e)}"


def magic():
    tune_type = request.args.get("type", "reel")
    # Convert URL parameter back to database format
    db_tune_type = tune_type.replace("+", " ")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.tune_id, t.name, t.tune_type, COUNT(sit.session_instance_tune_id) AS instance_count
            FROM tune t
            JOIN session_tune st ON t.tune_id = st.tune_id
            LEFT JOIN session_instance_tune sit ON st.session_id = (
                SELECT si.session_id
                FROM session_instance si
                WHERE si.session_instance_id = sit.session_instance_id
            ) AND st.tune_id = sit.tune_id
            WHERE st.session_id = 1 AND lower(t.tune_type) = lower(%s)
            GROUP BY t.tune_id, t.name, t.tune_type
            HAVING COUNT(sit.session_instance_tune_id) > 1
        """,
            (db_tune_type,),
        )

        all_tunes = cur.fetchall()
        cur.close()
        conn.close()

        if len(all_tunes) >= 3:
            # Randomly select 3 tunes
            selected_tunes = random.sample(all_tunes, 3)

            # Sort by instance_count to get low, middle, high
            sorted_tunes = sorted(selected_tunes, key=lambda x: x[3])

            # Reorder as middle, low, high
            if len(sorted_tunes) == 3:
                ordered_tunes = [
                    sorted_tunes[1],
                    sorted_tunes[0],
                    sorted_tunes[2],
                ]  # middle, low, high
            else:
                ordered_tunes = sorted_tunes
        else:
            ordered_tunes = all_tunes

        tune_types = ["reel", "jig", "slip+jig", "slide", "polka"]

        return render_template(
            "magic.html",
            tunes=ordered_tunes,
            tune_types=tune_types,
            current_type=tune_type,
        )

    except Exception as e:
        return f"Database connection failed: {str(e)}"


def db_test():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM test_table ORDER BY id;")
        records = cur.fetchall()
        cur.close()
        conn.close()
        return render_template("db_test.html", records=records)
    except Exception as e:
        return f"Database connection failed: {str(e)}"


def sessions():
    """Sessions directory (spec 035 Step 4a): a thin shell that embeds the SAME
    payload GET /api/sessions/with-today-status returns (one serializer — they
    can't drift) and mounts the Svelte view."""
    try:
        from serializers import build_sessions_directory_payload

        user_person_id = None
        user_timezone = "UTC"
        if current_user.is_authenticated:
            user_person_id = getattr(current_user, 'person_id', None)
            user_timezone = getattr(current_user, 'timezone', None) or "UTC"

        conn = get_db_connection()
        try:
            payload = build_sessions_directory_payload(conn, user_person_id, user_timezone)
        finally:
            conn.close()

        return render_template("sessions.html", payload=payload, is_logged_in=current_user.is_authenticated)
    except Exception as e:
        return f"Database connection failed: {str(e)}"


def session_tunes(session_path):
    """Show session detail page with tunes tab active."""
    return session_handler(session_path, active_tab='tunes')


def _resolve_tune_redirect(tune_id):
    """If tune_id has been merged away (tune.redirect_to_tune_id set), return the
    canonical id it now points to, else None. Permalinks to merged tunes 301 to
    the new id so old bookmarks keep working (spec 030)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT redirect_to_tune_id FROM tune WHERE tune_id = %s", (tune_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def session_tune_info(session_path, tune_id):
    """Show session detail page with tunes tab active and tune modal open."""
    redirect_to = _resolve_tune_redirect(tune_id)
    if redirect_to:
        return redirect(f"/sessions/{session_path}/tunes/{redirect_to}", code=301)
    return session_handler(session_path, active_tab='tunes', tune_id=tune_id)


def session_people(session_path):
    """Show session detail page with people tab active."""
    return session_handler(session_path, active_tab='people')


def session_person_detail(session_path, person_id):
    """Show session detail page with people tab active and person modal open."""
    return session_handler(session_path, active_tab='people', person_id=person_id)


def session_logs(session_path):
    """Show session detail page with logs tab active."""
    return session_handler(session_path, active_tab='logs')


def session_handler(full_path, active_tab=None, tune_id=None, person_id=None):
    # Strip trailing slash to normalize the path
    full_path = full_path.rstrip("/")

    # Check if the last part of the path looks like a date (yyyy-mm-dd) or a numeric ID
    path_parts = full_path.split("/")
    last_part = path_parts[-1]
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    id_pattern = r"^\d+$"

    # CRITICAL: Eagerly match full paths first (e.g., "oflahertys/2025" should be a session path, not "oflahertys" + year 2025)
    # Determine if this looks like a session instance request
    looks_like_instance = re.match(date_pattern, last_part) or re.match(id_pattern, last_part)

    # If it looks like an instance, check if the FULL path is actually a session first
    is_session_overview = False
    if looks_like_instance:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT session_id FROM session WHERE path = %s", (full_path,))
            full_path_session = cur.fetchone()
            cur.close()
            conn.close()

            if full_path_session:
                # The full path IS a session (e.g., "oflahertys/2025")
                # Treat as session overview, not instance
                is_session_overview = True
        except Exception as e:
            return f"Database connection failed: {str(e)}"

    # Check if this is a session instance request (by date or ID)
    if looks_like_instance and not is_session_overview:
        is_date_based = re.match(date_pattern, last_part)

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            if is_date_based:
                # Date-based URL: /sessions/<path>/<date>
                session_path = "/".join(path_parts[:-1])
                date = last_part
                cur.execute(
                    """
                    SELECT s.name, si.date, si.comments, si.session_instance_id, si.is_cancelled,
                           si.location_override, s.location_name, si.log_complete_date, s.session_id,
                           si.start_time, si.end_time, s.path, si.is_active, si.logging_mode
                    FROM session_instance si
                    JOIN session s ON si.session_id = s.session_id
                    WHERE s.path = %s AND si.date = %s
                    ORDER BY si.session_instance_id ASC
                    LIMIT 1
                """,
                    (session_path, date),
                )
            else:
                # ID-based URL: /sessions/<path>/<id>
                session_instance_id = int(last_part)
                session_path = "/".join(path_parts[:-1])
                cur.execute(
                    """
                    SELECT s.name, si.date, si.comments, si.session_instance_id, si.is_cancelled,
                           si.location_override, s.location_name, si.log_complete_date, s.session_id,
                           si.start_time, si.end_time, s.path, si.is_active, si.logging_mode
                    FROM session_instance si
                    JOIN session s ON si.session_id = s.session_id
                    WHERE si.session_instance_id = %s AND s.path = %s
                """,
                    (session_instance_id, session_path),
                )

            session_instance = cur.fetchone()

            if session_instance:
                # Beta rollout (spec 024): users opted into the new live editor go straight
                # to it for any session instance. Everyone else stays on the classic editor.
                if current_user.is_authenticated and getattr(current_user, "beta_live_logging", False):
                    cur.close(); conn.close()
                    # Forward a play-history deep-link (?highlight=<record>) so the live
                    # screen can scroll to it. Deliberately NOT ?tune= — on the live
                    # screen that means "append this tune".
                    live_kwargs = {"session_instance_id": session_instance[3]}
                    if request.args.get("highlight"):
                        live_kwargs["highlight"] = request.args["highlight"]
                    return redirect(url_for("live_logging_screen", **live_kwargs))
                logging_mode = session_instance[13]
                # Use s.path from database (index 11) for consistency
                session_path_from_db = session_instance[11]
                session_instance_dict = {
                    "session_name": session_instance[0],
                    "date": session_instance[1],
                    "comments": session_instance[2],
                    "session_instance_id": session_instance[3],
                    "is_cancelled": session_instance[4],
                    "location_override": session_instance[5],
                    "default_location": session_instance[6],
                    "log_complete_date": session_instance[7],
                    "session_path": session_path_from_db,
                    "session_id": session_instance[8],
                    "start_time": session_instance[9],
                    "end_time": session_instance[10],
                    "is_active": session_instance[12],
                }

                # Get tunes played in this session instance
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
                    LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                        SELECT si2.session_id
                        FROM session_instance si2
                        WHERE si2.session_instance_id = %s
                    )
                    LEFT JOIN user_account created_by_user ON sit.created_by_user_id = created_by_user.user_id
                    LEFT JOIN person created_by_person ON created_by_user.person_id = created_by_person.person_id
                    WHERE sit.session_instance_id = %s
                    ORDER BY sit.order_position
                """,
                    (session_instance[3], session_instance[3]),
                )

                tunes = cur.fetchall()

                # Get attendees for the started-by dropdown
                session_id = session_instance[8]
                session_instance_id = session_instance[3]
                cur.execute("""
                    SELECT DISTINCT
                        p.person_id,
                        p.first_name,
                        p.last_name
                    FROM person p
                    JOIN session_instance_person sip ON p.person_id = sip.person_id
                    WHERE sip.session_instance_id = %s
                    ORDER BY p.first_name, p.last_name
                """, (session_instance_id,))

                attendees_data = cur.fetchall()
                attendees_list = []
                for row in attendees_data:
                    person_id, first_name, last_name = row
                    display_name = f"{first_name} {last_name[0]}" if last_name else first_name
                    attendees_list.append({
                        'person_id': person_id,
                        'display_name': display_name
                    })

                # Handle display name disambiguation
                display_name_counts = {}
                for attendee in attendees_list:
                    dn = attendee['display_name']
                    if dn in display_name_counts:
                        display_name_counts[dn].append(attendee)
                    else:
                        display_name_counts[dn] = [attendee]

                for dn, attendees_with_name in display_name_counts.items():
                    if len(attendees_with_name) > 1:
                        attendees_with_name.sort(key=lambda x: x['person_id'])
                        for attendee in attendees_with_name:
                            attendee['display_name'] = f"{dn} (#{attendee['person_id']})"

                cur.close()
                conn.close()

                # Group tunes into sets by break records, then rebuild each tune row with a
                # synthesized continues_set at index 0 (False for the first tune of a set) to
                # preserve the structure the template/JS expects.
                sets = []
                for tune_set in segment_records_into_sets(tunes, type_index=0):
                    sets.append(
                        [
                            [tune_idx > 0] + list(row[1:])
                            for tune_idx, row in enumerate(tune_set)
                        ]
                    )

                # Check if current user is an admin of this session
                is_session_admin = False
                is_regular = False
                if current_user.is_authenticated:
                    # session_instance[8] is the session_id from our updated query
                    # Use request.session to access Flask session data
                    from flask import session as flask_session
                    from auth import is_session_regular

                    is_session_admin = flask_session.get(
                        "is_system_admin", False
                    ) or session_instance[8] in flask_session.get(
                        "admin_session_ids", []
                    )

                    # Check if user is a regular for this session
                    user_person_id = getattr(current_user, 'person_id', None)
                    if user_person_id:
                        is_regular = is_session_regular(user_person_id, session_instance[8])

                resp = make_response(
                    render_template(
                        "session_instance_detail.html",
                        session_instance=session_instance_dict,
                        tune_sets=sets,
                        is_session_admin=is_session_admin,
                        is_session_regular=is_regular,
                        attendees=attendees_list,
                        logging_mode=logging_mode,
                    )
                )
                # Legacy word-processor editor (being deprecated): the service worker
                # must never cache it for offline use.
                resp.headers["X-Offline-Exclude"] = "1"
                return resp
            else:
                cur.close()
                conn.close()
                from app import render_error_page

                if is_date_based:
                    error_msg = f"Session instance not found: {session_path} on {last_part}"
                else:
                    error_msg = f"Session instance not found: ID {last_part} for session {session_path}"
                return render_error_page(error_msg, 404)
        except Exception as e:
            return f"Database connection failed: {str(e)}"

    else:
        # This is a session detail request (spec 035 Step 4b): a thin shell around
        # serializers.build_session_detail_payload — the SAME function that backs
        # GET /api/sessions/<path>/detail, so the page embed and the API cannot
        # drift. The tabbed interface (tunes/logs/people) is rendered client-side
        # by the Svelte bundle (/static/sessionpage/page.js).
        session_path = full_path

        try:
            from flask import session as flask_session
            from serializers import build_session_detail_payload

            user_person_id = (
                getattr(current_user, "person_id", None) if current_user.is_authenticated else None
            )

            conn = get_db_connection()
            try:
                payload = build_session_detail_payload(
                    conn,
                    session_path,
                    person_id=user_person_id,
                    is_system_admin=flask_session.get("is_system_admin", False),
                    is_logged_in=current_user.is_authenticated,
                )
            finally:
                conn.close()

            if payload is None:
                from app import render_error_page

                return render_error_page(f"Session not found: {session_path}", 404)

            return render_template(
                "session_detail.html",
                payload=payload,
                session=payload["session"],
                is_logged_in=payload["permissions"]["is_logged_in"],
                is_session_admin=payload["permissions"]["is_session_admin"],
                is_session_member=payload["permissions"]["is_session_member"],
                active_tab=active_tab,
                tune_id=tune_id,
                person_id=person_id,
            )
        except Exception as e:
            return f"Database connection failed: {str(e)}"


def session_instance_players(full_path):
    """Handle the Players tab for a session instance as a separate page"""
    # Strip trailing slash and remove /players suffix
    full_path = full_path.rstrip("/")
    if full_path.endswith("/players"):
        full_path = full_path[:-8]  # Remove "/players"

    # Check if the last part of the path looks like a date (yyyy-mm-dd) or a numeric ID
    path_parts = full_path.split("/")
    last_part = path_parts[-1]
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    id_pattern = r"^\d+$"

    is_date_based = re.match(date_pattern, last_part)
    is_id_based = re.match(id_pattern, last_part) and not is_date_based

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # CRITICAL: Eagerly match full paths first (e.g., "oflahertys/2025" should be a session path, not "oflahertys" + year 2025)
        # Only check this if last part could be ambiguous (date or ID pattern)
        if is_date_based or is_id_based:
            cur.execute(
                "SELECT session_id FROM session WHERE path = %s",
                (full_path,),
            )
            full_path_session = cur.fetchone()

            if full_path_session:
                # The full path is a session, not a session instance!
                # This shouldn't happen for /players route, but return error
                cur.close()
                conn.close()
                from app import render_error_page
                return render_error_page(
                    f"Players tab requires a specific session instance. Please select a date from the session page.",
                    400
                )

        if is_date_based:
            # Date-based URL: /sessions/<path>/<date>/players
            session_path = "/".join(path_parts[:-1])
            date = last_part
            cur.execute(
                """
                SELECT s.name, si.date, si.comments, si.session_instance_id, si.is_cancelled,
                       si.location_override, s.location_name, si.log_complete_date, s.session_id, s.path
                FROM session_instance si
                JOIN session s ON si.session_id = s.session_id
                WHERE s.path = %s AND si.date = %s
                ORDER BY si.session_instance_id ASC
                LIMIT 1
            """,
                (session_path, date),
            )
        else:
            # ID-based URL: /sessions/<path>/<id>/players
            session_instance_id = int(last_part)
            session_path = "/".join(path_parts[:-1])
            cur.execute(
                """
                SELECT s.name, si.date, si.comments, si.session_instance_id, si.is_cancelled,
                       si.location_override, s.location_name, si.log_complete_date, s.session_id, s.path
                FROM session_instance si
                JOIN session s ON si.session_id = s.session_id
                WHERE si.session_instance_id = %s AND s.path = %s
            """,
                (session_instance_id, session_path),
            )

        session_instance = cur.fetchone()

        if session_instance:
            # Use s.path from database (index 9) for consistency
            session_path_from_db = session_instance[9]
            session_instance_dict = {
                "session_name": session_instance[0],
                "date": session_instance[1],
                "comments": session_instance[2],
                "session_instance_id": session_instance[3],
                "is_cancelled": session_instance[4],
                "location_override": session_instance[5],
                "default_location": session_instance[6],
                "log_complete_date": session_instance[7],
                "session_path": session_path_from_db,
                "session_id": session_instance[8],
            }

            # Check if current user is an admin or regular of this session
            is_session_admin = False
            is_regular = False
            if current_user.is_authenticated:
                from flask import session as flask_session
                from auth import is_session_regular

                is_session_admin = flask_session.get(
                    "is_system_admin", False
                ) or session_instance[8] in flask_session.get(
                    "admin_session_ids", []
                )

                # Check if user is a regular for this session
                user_person_id = getattr(current_user, 'person_id', None)
                if user_person_id:
                    is_regular = is_session_regular(user_person_id, session_instance[8])

            cur.close()
            conn.close()

            return render_template(
                "session_instance_players.html",
                session_instance=session_instance_dict,
                is_session_admin=is_session_admin,
                is_session_regular=is_regular,
            )
        else:
            cur.close()
            conn.close()
            from app import render_error_page

            if is_date_based:
                error_msg = f"Session instance not found: {session_path} on {last_part}"
            else:
                error_msg = f"Session instance not found: ID {last_part} for session {session_path}"
            return render_error_page(error_msg, 404)
    except Exception as e:
        return f"Database connection failed: {str(e)}"


def add_session():
    """Add-session wizard (spec 035 final migration): a thin shell embedding the
    SAME payload GET /api/add-session returns (one serializer — they can't
    drift). Deliberately public — anyone can browse the wizard; only the final
    POST /api/add-session requires login."""
    from serializers import build_add_session_payload

    payload = build_add_session_payload(current_user.is_authenticated)
    return render_template("add_session.html", payload=payload)


def help_page():
    return render_template("help.html")


def share_page():
    # Get the target URL from query parameter (the page to share)
    target_url = request.args.get("url", request.host_url.rstrip('/'))

    # Get current user's person_id if authenticated
    person_id = None
    if current_user.is_authenticated:
        person_id = current_user.person_id

    return render_template("share.html", target_url=target_url, person_id=person_id)


def help_my_tunes():
    return render_template("help_my_tunes.html")


def help_sessions():
    return render_template("help_sessions.html")


def help_offline():
    return render_template("help_offline.html")


def help_session_tunes():
    return render_template("help_session_tunes.html")


def help_session_logs():
    return render_template("help_session_logs.html")


def help_session_members():
    return render_template("help_session_members.html")


def help_release_notes(month):
    # Map month to display name
    month_names = {
        '2025-12': 'December 2025',
        '2025-11': 'November 2025',
        '2025-10': 'October 2025',
        '2025-09': 'September 2025',
        '2025-08': 'August 2025',
        '2025-07': 'July 2025',
    }
    month_name = month_names.get(month, month)
    return render_template("help_release_notes.html", month=month, month_name=month_name)


def register():
    # Get session_id from query parameter if present
    session_id_param = request.args.get("session_id")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        timezone = request.form.get("time_zone", "UTC")
        # Migrate legacy timezone values to IANA identifiers
        from timezone_utils import migrate_legacy_timezone

        timezone = migrate_legacy_timezone(timezone)

        # Validation
        if not username or not password or not first_name or not last_name or not email:
            flash(
                "Username, password, first name, last name, and email are required.",
                "error",
            )
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("auth/register.html")

        # Check if username already exists
        existing_user = User.get_by_username(username)
        if existing_user:
            flash("Username already exists. Please choose a different one.", "error")
            return render_template("auth/register.html")

        # Check if email already exists and whether it has a user account
        existing_person_id = None
        existing_person = None
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Get person details if email exists
            cur.execute(
                "SELECT person_id, first_name, last_name FROM person WHERE email = %s",
                (email,)
            )
            person_result = cur.fetchone()

            if person_result:
                existing_person_id, existing_first_name, existing_last_name = person_result
                existing_person = {
                    'person_id': existing_person_id,
                    'first_name': existing_first_name,
                    'last_name': existing_last_name
                }

                # Check if this person already has a user account
                cur.execute(
                    "SELECT user_id FROM user_account WHERE person_id = %s",
                    (existing_person_id,)
                )
                if cur.fetchone():
                    flash(
                        "Email address already registered with a user account. Please try logging in or use password reset if needed.",
                        "error",
                    )
                    return render_template("auth/register.html")
                # If we get here, person exists but has no user account - we'll link to it
        finally:
            conn.close()

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Create or update person record
            if existing_person_id:
                # Use existing person and update their name if different
                person_id = existing_person_id
                if (first_name != existing_person['first_name'] or
                    last_name != existing_person['last_name']):
                    # Update person's name to match registration (no user logged in yet)
                    save_to_history(
                        cur,
                        "person",
                        "UPDATE",
                        person_id,
                        user_id=None,
                    )
                    cur.execute(
                        """
                        UPDATE person
                        SET first_name = %s, last_name = %s, last_modified_date = %s, last_modified_user_id = NULL
                        WHERE person_id = %s
                        """,
                        (first_name, last_name, now_utc(), person_id)
                    )
            else:
                # Create new person record (no user yet during registration)
                cur.execute(
                    """
                    INSERT INTO person (first_name, last_name, email, created_by_user_id)
                    VALUES (%s, %s, %s, NULL)
                    RETURNING person_id
                """,
                    (first_name, last_name, email),
                )
                result = cur.fetchone()
                if not result:
                    flash("Failed to create person record", "error")
                    return redirect(url_for("register"))
                person_id = result[0]

            # Create user record (unverified, no user yet during registration)
            hashed_password = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            verification_token = generate_verification_token()
            verification_expires = now_utc() + timedelta(hours=24)

            # Get referrer from session if present
            referred_by_person_id = session.get('referred_by_person_id')

            cur.execute(
                """
                INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone,
                                        email_verified, verification_token, verification_token_expires, referred_by_person_id, created_by_user_id)
                VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s, %s, NULL)
                RETURNING user_id
            """,
                (
                    person_id,
                    username,
                    email,
                    hashed_password,
                    timezone,
                    verification_token,
                    verification_expires,
                    referred_by_person_id,
                ),
            )
            result = cur.fetchone()
            if not result:
                flash("Failed to create user account", "error")
                return redirect(url_for("register"))
            user_id = result[0]

            # Log history entry for linking existing person to new user account
            if existing_person_id:
                save_to_history(
                    cur,
                    "user_account",
                    "INSERT",
                    user_id,
                    user_id=get_current_user_id(),
                )

            conn.commit()

            # Send verification email
            user = User(
                user_id,
                person_id,
                username,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            if send_verification_email(user, verification_token):
                flash(
                    "Registration successful! Please check your email to verify your account before logging in.",
                    "success",
                )
            else:
                flash(
                    "Registration successful, but failed to send verification email. Please contact support.",
                    "warning",
                )

            return redirect(url_for("login"))

        except Exception as e:
            conn.rollback()
            print(f"Registration error: {str(e)}")
            flash("Registration failed. Please try again.", "error")
            return render_template("auth/register.html")
        finally:
            conn.close()

    return render_template("auth/register.html", session_id=session_id_param)


def login():
    # Capture referrer URL for redirect after login
    if request.method == "GET" and request.referrer and "login" not in request.referrer:
        session["login_redirect_url"] = request.referrer

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Get client info for logging
        ip_address = request.environ.get(
            "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR")
        )
        # Handle comma-separated IPs from X-Forwarded-For header (take the first one)
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()
        user_agent = request.headers.get("User-Agent")

        if not username or not password:
            log_login_event(
                None,
                username,
                "LOGIN_FAILURE",
                ip_address,
                user_agent,
                failure_reason="MISSING_CREDENTIALS",
            )
            flash("Username and password are required.", "error")
            return render_template("auth/login.html")

        user = User.get_by_username(username)
        if user and user.is_active and user.check_password(password):
            if not user.email_verified:
                log_login_event(
                    user.user_id,
                    username,
                    "LOGIN_FAILURE",
                    ip_address,
                    user_agent,
                    failure_reason="EMAIL_NOT_VERIFIED",
                )
                flash(
                    "Please verify your email address before logging in. Check your email for a verification link.",
                    "warning",
                )
                return render_template("auth/login.html")

            login_user(user, remember=True)

            # Create session record
            session_id = create_session(user.user_id, ip_address, user_agent)

            # Log successful login
            log_login_event(
                user.user_id,
                username,
                "LOGIN_SUCCESS",
                ip_address,
                user_agent,
                session_id=session_id,
            )

            # Mark Flask session as permanent so it persists across browser/PWA restarts
            # This ensures the session cookie doesn't expire when the browser/PWA closes
            session.permanent = True

            # Store session_id in Flask session to identify this specific session
            session["db_session_id"] = session_id

            # Cache list of sessions this user is an admin of
            conn_admin = get_db_connection()
            try:
                cur_admin = conn_admin.cursor()
                cur_admin.execute(
                    """
                    SELECT s.session_id
                    FROM session_person sp
                    JOIN session s ON sp.session_id = s.session_id
                    WHERE sp.person_id = %s AND sp.is_admin = TRUE
                """,
                    (user.person_id,),
                )
                admin_session_ids = [row[0] for row in cur_admin.fetchall()]
                session["admin_session_ids"] = admin_session_ids
            finally:
                conn_admin.close()

            # Clean up expired sessions
            cleanup_expired_sessions()

            # Check for stored redirect URL first, then next parameter, then default to home
            redirect_url = session.pop("login_redirect_url", None)
            next_page = request.args.get("next")

            if redirect_url:
                return redirect(redirect_url)
            elif next_page:
                return redirect(next_page)
            return redirect(url_for("home"))
        else:
            # Determine failure reason
            if user and not user.is_active:
                failure_reason = "ACCOUNT_INACTIVE"
            elif user:
                failure_reason = "INVALID_PASSWORD"
            else:
                failure_reason = "USER_NOT_FOUND"

            log_login_event(
                user.user_id if user else None,
                username,
                "LOGIN_FAILURE",
                ip_address,
                user_agent,
                failure_reason=failure_reason,
            )
            flash("Invalid username or password.", "error")

    return render_template("auth/login.html")


@login_required
def logout():
    user_id = None
    username = None
    db_session_id = None

    if current_user.is_authenticated:
        user_id = current_user.user_id
        username = current_user.username

        # Get client info for logging
        ip_address = request.environ.get(
            "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR")
        )
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()
        user_agent = request.headers.get("User-Agent")

        # Remove only the current session from database
        db_session_id = session.get("db_session_id")
        if db_session_id:
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM user_session WHERE session_id = %s", (db_session_id,)
                )
                conn.commit()
            finally:
                conn.close()

        # Log logout event
        log_login_event(
            user_id,
            username,
            "LOGOUT",
            ip_address,
            user_agent,
            session_id=db_session_id,
        )

    # Clear all session data first
    session.clear()

    # Then clear Flask-Login session
    logout_user()

    # Set flash message after clearing the session
    flash("You have been logged out.", "info")

    # Create response with cache control headers and explicitly clear cookies
    response = redirect(url_for("home"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    # Clear all possible session-related cookies
    response.set_cookie("session", "", expires=0, path="/")
    response.set_cookie("remember_token", "", expires=0, path="/")
    response.set_cookie("user_id", "", expires=0, path="/")

    return response


def check_email_api():
    """
    API endpoint for the unified login flow.
    Check if email exists and return appropriate action:
    - password_login: User exists with password, show password field
    - magic_link_sent: User exists without password, magic link emailed
    - registration_started: New user created, verification email sent
    """
    if not request.is_json:
        return jsonify({"error": "JSON request required"}), 400

    data = request.get_json()
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email address is required"}), 400

    # Basic email validation
    if "@" not in email or "." not in email:
        return jsonify({"error": "Please enter a valid email address"}), 400

    # Get client info for logging
    ip_address = request.environ.get(
        "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR")
    )
    if ip_address and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent")

    # Check if user exists with this email
    user = User.get_by_email(email)

    if user:
        # User exists
        if not user.is_active:
            return jsonify({"error": "This account has been deactivated. Please contact support."}), 403

        if user.has_password():
            # User has password - prompt for password login
            return jsonify({
                "action": "password_login",
                "email": email,
                "message": "Enter your password to log in"
            })
        else:
            # User has no password - send magic link
            token = generate_login_token()
            expires = now_utc() + timedelta(minutes=15)

            conn = get_db_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE user_account
                    SET login_token = %s, login_token_expires = %s, last_modified_date = %s
                    WHERE user_id = %s
                """,
                    (token, expires, now_utc(), user.user_id),
                )
                conn.commit()
            finally:
                conn.close()

            send_login_link_email(user, token)

            log_login_event(
                user.user_id,
                email,
                "MAGIC_LINK_SENT",
                ip_address,
                user_agent,
            )

            return jsonify({
                "action": "magic_link_sent",
                "email": email,
                "message": "Check your email for a login link"
            })
    else:
        # New user - create account and send verification email
        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Check if person exists with this email
            cur.execute(
                "SELECT person_id FROM person WHERE LOWER(email) = LOWER(%s)",
                (email,)
            )
            person_row = cur.fetchone()

            if person_row:
                person_id = person_row[0]
            else:
                # Create minimal person record (name will be collected in profile setup)
                cur.execute(
                    """
                    INSERT INTO person (first_name, last_name, email, created_date, last_modified_date)
                    VALUES ('', '', %s, %s, %s)
                    RETURNING person_id
                """,
                    (email, now_utc(), now_utc()),
                )
                person_id = cur.fetchone()[0]

            conn.commit()
        finally:
            conn.close()

        # Create passwordless user
        user_id = User.create_user_passwordless(email, person_id)

        if not user_id:
            return jsonify({"error": "Failed to create account. Please try again."}), 500

        # Generate verification token
        token = generate_verification_token()
        expires = now_utc() + timedelta(hours=24)

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_account
                SET verification_token = %s, verification_token_expires = %s
                WHERE user_id = %s
            """,
                (token, expires, user_id),
            )
            conn.commit()
        finally:
            conn.close()

        # Get user object for email
        user = User.get_by_id(user_id)
        send_verification_email(user, token)

        log_login_event(
            user_id,
            email,
            "REGISTRATION",
            ip_address,
            user_agent,
        )

        return jsonify({
            "action": "registration_started",
            "email": email,
            "message": "Check your email to verify your account"
        })


def login_password_api():
    """API endpoint for email + password login"""
    if not request.is_json:
        return jsonify({"error": "JSON request required"}), 400

    data = request.get_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Get client info for logging
    ip_address = request.environ.get(
        "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR")
    )
    if ip_address and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent")

    user = User.get_by_email(email)

    if not user:
        log_login_event(
            None,
            email,
            "LOGIN_FAILURE",
            ip_address,
            user_agent,
            failure_reason="USER_NOT_FOUND",
        )
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.is_active:
        log_login_event(
            user.user_id,
            email,
            "LOGIN_FAILURE",
            ip_address,
            user_agent,
            failure_reason="ACCOUNT_INACTIVE",
        )
        return jsonify({"error": "This account has been deactivated"}), 403

    if not user.check_password(password):
        log_login_event(
            user.user_id,
            email,
            "LOGIN_FAILURE",
            ip_address,
            user_agent,
            failure_reason="INVALID_PASSWORD",
        )
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.email_verified:
        log_login_event(
            user.user_id,
            email,
            "LOGIN_FAILURE",
            ip_address,
            user_agent,
            failure_reason="EMAIL_NOT_VERIFIED",
        )
        return jsonify({
            "error": "Please verify your email address first",
            "action": "resend_verification"
        }), 403

    # Successful login
    login_user(user, remember=True)

    # Create session record
    session_id = create_session(user.user_id, ip_address, user_agent)

    log_login_event(
        user.user_id,
        email,
        "LOGIN_SUCCESS",
        ip_address,
        user_agent,
        session_id=session_id,
    )

    session.permanent = True
    session["db_session_id"] = session_id

    # Cache admin session IDs
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.session_id
            FROM session_person sp
            JOIN session s ON sp.session_id = s.session_id
            WHERE sp.person_id = %s AND sp.is_admin = TRUE
        """,
            (user.person_id,),
        )
        admin_session_ids = [row[0] for row in cur.fetchall()]
        session["admin_session_ids"] = admin_session_ids
    finally:
        conn.close()

    cleanup_expired_sessions()

    return jsonify({
        "success": True,
        "redirect": url_for("home")
    })


def login_with_token(token):
    """Login via magic link token"""
    user = User.get_by_login_token(token)

    # Get client info for logging
    ip_address = request.environ.get(
        "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR")
    )
    if ip_address and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent")

    if not user:
        log_login_event(
            None,
            None,
            "LOGIN_FAILURE",
            ip_address,
            user_agent,
            failure_reason="INVALID_LOGIN_TOKEN",
        )
        flash("Invalid or expired login link. Please request a new one.", "error")
        return redirect(url_for("login"))

    if not user.is_active:
        flash("This account has been deactivated.", "error")
        return redirect(url_for("login"))

    # Clear the login token
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_account
            SET login_token = NULL, login_token_expires = NULL, last_modified_date = %s
            WHERE user_id = %s
        """,
            (now_utc(), user.user_id),
        )
        conn.commit()
    finally:
        conn.close()

    # Log user in
    login_user(user, remember=True)

    session_id = create_session(user.user_id, ip_address, user_agent)

    log_login_event(
        user.user_id,
        user.email,
        "LOGIN_SUCCESS",
        ip_address,
        user_agent,
        session_id=session_id,
        additional_data={"method": "magic_link"},
    )

    session.permanent = True
    session["db_session_id"] = session_id

    # Cache admin session IDs
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.session_id
            FROM session_person sp
            JOIN session s ON sp.session_id = s.session_id
            WHERE sp.person_id = %s AND sp.is_admin = TRUE
        """,
            (user.person_id,),
        )
        admin_session_ids = [row[0] for row in cur.fetchall()]
        session["admin_session_ids"] = admin_session_ids
    finally:
        conn.close()

    cleanup_expired_sessions()

    # Redirect to password setup (optional) for users without password
    if not user.has_password():
        return redirect(url_for("set_password_optional"))

    flash("You have been logged in.", "success")
    return redirect(url_for("home"))


def _needs_profile_setup(person_id):
    """Check if a person needs to complete their profile (missing name or location)"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT first_name, last_name, city, state, country
            FROM person WHERE person_id = %s
        """,
            (person_id,),
        )
        row = cur.fetchone()
        if not row:
            return True

        first_name, last_name, city, state, country = row

        # Need setup if first name or last name is missing/empty
        if not first_name or not first_name.strip():
            return True
        if not last_name or not last_name.strip():
            return True

        # Need setup if all location fields are empty
        has_location = (city and city.strip()) or (state and state.strip()) or (country and country.strip())
        if not has_location:
            return True

        return False
    finally:
        conn.close()


@login_required
def set_password_optional():
    """Optional password setup for passwordless users"""
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password:
            if len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
                return render_template("auth/set_password.html")

            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return render_template("auth/set_password.html")

            # Hash and save password
            hashed_password = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            conn = get_db_connection()
            try:
                cur = conn.cursor()
                save_to_history(
                    cur, "user_account", "UPDATE", current_user.user_id, user_id=current_user.user_id
                )
                cur.execute(
                    """
                    UPDATE user_account
                    SET hashed_password = %s, last_modified_date = %s, last_modified_user_id = %s
                    WHERE user_id = %s
                """,
                    (hashed_password, now_utc(), current_user.user_id, current_user.user_id),
                )
                conn.commit()
            finally:
                conn.close()

            flash("Password set successfully! You can use it to log in next time.", "success")

        # Check if profile setup is needed
        if _needs_profile_setup(current_user.person_id):
            return redirect(url_for("setup_profile"))
        return redirect(url_for("home"))

    return render_template("auth/set_password.html")


# Common instruments for Irish/folk music
# The canonical instrument list is defined once in instruments.py. Kept under the
# old name here for the setup_profile template context.
COMMON_INSTRUMENTS = CANONICAL_INSTRUMENTS


@login_required
def setup_profile():
    """Profile setup for new users - collect name, location, timezone, instruments"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Get current person data
        cur.execute(
            """
            SELECT person_id, first_name, last_name, city, state, country
            FROM person WHERE person_id = %s
        """,
            (current_user.person_id,),
        )
        person_row = cur.fetchone()
        person = {
            "person_id": person_row[0],
            "first_name": person_row[1],
            "last_name": person_row[2],
            "city": person_row[3],
            "state": person_row[4],
            "country": person_row[5],
        } if person_row else {}

        # Get user's current instruments
        cur.execute(
            "SELECT instrument FROM person_instrument WHERE person_id = %s",
            (current_user.person_id,),
        )
        user_instruments = [row[0] for row in cur.fetchall()]

        # Separate common instruments from other instruments (case-insensitive)
        common_instruments_lower = [i.lower() for i in COMMON_INSTRUMENTS]
        other_instruments = [i for i in user_instruments if i.lower() not in common_instruments_lower]

        if request.method == "POST":
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            city = request.form.get("city", "").strip()
            state = request.form.get("state", "").strip()
            country = request.form.get("country", "").strip()
            timezone = request.form.get("timezone", "UTC")
            instruments = request.form.getlist("instruments")
            other_instrument = request.form.get("other_instrument", "").strip()

            # Add other instrument if specified
            if other_instrument:
                instruments.extend(other_instrument.split(","))

            # Canonicalize casing/aliases and de-dupe against one shared vocabulary
            instruments = normalize_instruments(instruments)

            # Update person record
            save_to_history(
                cur, "person", "UPDATE", current_user.person_id, user_id=current_user.user_id
            )
            cur.execute(
                """
                UPDATE person
                SET first_name = COALESCE(NULLIF(%s, ''), first_name),
                    last_name = COALESCE(NULLIF(%s, ''), last_name),
                    city = NULLIF(%s, ''),
                    state = NULLIF(%s, ''),
                    country = NULLIF(%s, ''),
                    last_modified_date = %s,
                    last_modified_user_id = %s
                WHERE person_id = %s
            """,
                (first_name, last_name, city, state, country, now_utc(), current_user.user_id, current_user.person_id),
            )

            # Update user timezone
            save_to_history(
                cur, "user_account", "UPDATE", current_user.user_id, user_id=current_user.user_id
            )
            cur.execute(
                """
                UPDATE user_account
                SET timezone = %s, last_modified_date = %s, last_modified_user_id = %s
                WHERE user_id = %s
            """,
                (timezone, now_utc(), current_user.user_id, current_user.user_id),
            )

            # Update instruments - delete existing and insert new
            cur.execute(
                "DELETE FROM person_instrument WHERE person_id = %s",
                (current_user.person_id,),
            )
            for instrument in instruments:
                if instrument:
                    cur.execute(
                        """
                        INSERT INTO person_instrument (person_id, instrument)
                        VALUES (%s, %s)
                        ON CONFLICT (person_id, instrument) DO NOTHING
                    """,
                        (current_user.person_id, instrument),
                    )

            conn.commit()
            flash("Profile updated!", "success")
            return redirect(url_for("home"))

        # Build timezone options
        timezone_options = [
            {"value": "UTC", "display": get_timezone_display_with_offset("UTC")},
            {"value": "America/New_York", "display": get_timezone_display_with_offset("America/New_York")},
            {"value": "America/Chicago", "display": get_timezone_display_with_offset("America/Chicago")},
            {"value": "America/Denver", "display": get_timezone_display_with_offset("America/Denver")},
            {"value": "America/Los_Angeles", "display": get_timezone_display_with_offset("America/Los_Angeles")},
            {"value": "America/Anchorage", "display": get_timezone_display_with_offset("America/Anchorage")},
            {"value": "Pacific/Honolulu", "display": get_timezone_display_with_offset("Pacific/Honolulu")},
            {"value": "America/Toronto", "display": get_timezone_display_with_offset("America/Toronto")},
            {"value": "America/Vancouver", "display": get_timezone_display_with_offset("America/Vancouver")},
            {"value": "America/Phoenix", "display": get_timezone_display_with_offset("America/Phoenix")},
            {"value": "Europe/London", "display": get_timezone_display_with_offset("Europe/London")},
            {"value": "Europe/Dublin", "display": get_timezone_display_with_offset("Europe/Dublin")},
            {"value": "Europe/Paris", "display": get_timezone_display_with_offset("Europe/Paris")},
            {"value": "Europe/Berlin", "display": get_timezone_display_with_offset("Europe/Berlin")},
            {"value": "Europe/Rome", "display": get_timezone_display_with_offset("Europe/Rome")},
            {"value": "Europe/Madrid", "display": get_timezone_display_with_offset("Europe/Madrid")},
            {"value": "Europe/Amsterdam", "display": get_timezone_display_with_offset("Europe/Amsterdam")},
            {"value": "Australia/Sydney", "display": get_timezone_display_with_offset("Australia/Sydney")},
            {"value": "Australia/Melbourne", "display": get_timezone_display_with_offset("Australia/Melbourne")},
            {"value": "Australia/Perth", "display": get_timezone_display_with_offset("Australia/Perth")},
            {"value": "Pacific/Auckland", "display": get_timezone_display_with_offset("Pacific/Auckland")},
            {"value": "Asia/Tokyo", "display": get_timezone_display_with_offset("Asia/Tokyo")},
            {"value": "Asia/Singapore", "display": get_timezone_display_with_offset("Asia/Singapore")},
        ]

        return render_template(
            "auth/setup_profile.html",
            person=person,
            timezones=timezone_options,
            common_instruments=COMMON_INSTRUMENTS,
            user_instruments=user_instruments,
            other_instruments=other_instruments,
        )

    finally:
        conn.close()


def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()

        if not email:
            flash("Email address is required.", "error")
            return render_template("auth/forgot_password.html")

        # Find user by email
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT ua.user_id, ua.username, ua.user_email, p.first_name
                FROM user_account ua
                JOIN person p ON ua.person_id = p.person_id
                WHERE ua.user_email = %s AND ua.is_active = TRUE
            """,
                (email,),
            )
            user_data = cur.fetchone()

            if user_data:
                # Generate reset token
                token = generate_password_reset_token()
                expires = now_utc() + timedelta(hours=1)

                # Save token to database (no user logged in during password reset request)
                save_to_history(
                    cur,
                    "user_account",
                    "UPDATE",
                    user_data[0],
                    user_id=None,
                )
                cur.execute(
                    """
                    UPDATE user_account
                    SET password_reset_token = %s, password_reset_expires = %s, last_modified_user_id = NULL
                    WHERE user_id = %s
                """,
                    (token, expires, user_data[0]),
                )
                conn.commit()

                # Create user object for email sending
                user = User(
                    user_data[0],
                    None,
                    user_data[1],
                    email=user_data[2],
                    first_name=user_data[3],
                )

                # Send reset email
                if send_password_reset_email(user, token):
                    flash(
                        "Password reset instructions have been sent to your email.",
                        "info",
                    )
                else:
                    flash(
                        "Failed to send reset email. Please try again later.", "error"
                    )
            else:
                # Don't reveal whether email exists
                flash(
                    "If an account with that email exists, password reset instructions have been sent.",
                    "info",
                )

        finally:
            conn.close()

        return redirect(url_for("login"))

    return render_template("auth/forgot_password.html")


def reset_password(token):
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password or not confirm_password:
            flash("Both password fields are required.", "error")
            return render_template("auth/reset_password.html", token=token)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/reset_password.html", token=token)

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("auth/reset_password.html", token=token)

        # Verify token and update password
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT user_id FROM user_account
                WHERE password_reset_token = %s
                AND password_reset_expires > %s
                AND is_active = TRUE
            """,
                (token, now_utc()),
            )
            user_data = cur.fetchone()

            if user_data:
                # Get username for logging
                cur.execute(
                    "SELECT username FROM user_account WHERE user_id = %s",
                    (user_data[0],),
                )
                username_row = cur.fetchone()
                username = username_row[0] if username_row else "unknown"

                # Update password and clear reset token (no user logged in during password reset)
                save_to_history(
                    cur,
                    "user_account",
                    "UPDATE",
                    user_data[0],
                    user_id=None,
                )
                hashed_password = bcrypt.hashpw(
                    password.encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")
                cur.execute(
                    """
                    UPDATE user_account
                    SET hashed_password = %s, password_reset_token = NULL, password_reset_expires = NULL, last_modified_user_id = NULL
                    WHERE user_id = %s
                """,
                    (hashed_password, user_data[0]),
                )
                conn.commit()

                # Log password reset event
                ip_address = request.environ.get(
                    "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR")
                )
                if ip_address and "," in ip_address:
                    ip_address = ip_address.split(",")[0].strip()
                user_agent = request.headers.get("User-Agent")
                log_login_event(
                    user_data[0], username, "PASSWORD_RESET", ip_address, user_agent
                )

                flash("Password has been reset successfully. Please log in.", "success")
                return redirect(url_for("login"))
            else:
                flash("Invalid or expired reset token.", "error")
                return redirect(url_for("forgot_password"))

        finally:
            conn.close()

    # Verify token is valid for GET request
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id FROM user_account
            WHERE password_reset_token = %s
            AND password_reset_expires > %s
            AND is_active = TRUE
        """,
            (token, now_utc()),
        )
        if not cur.fetchone():
            flash("Invalid or expired reset token.", "error")
            return redirect(url_for("forgot_password"))
    finally:
        conn.close()

    return render_template("auth/reset_password.html", token=token)


@login_required
def change_password():
    # Get current user with hashed password to check if they have one
    user = User.get_by_username(current_user.username)
    user_has_password = user.has_password() if user else False

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Only require current password if user has one
        if user_has_password:
            if not current_password or not new_password or not confirm_password:
                flash("All password fields are required.", "error")
                return render_template("auth/change_password.html", has_password=user_has_password)
        else:
            if not new_password or not confirm_password:
                flash("Password fields are required.", "error")
                return render_template("auth/change_password.html", has_password=user_has_password)

        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return render_template("auth/change_password.html", has_password=user_has_password)

        if len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("auth/change_password.html", has_password=user_has_password)

        # Verify current password only if user has one
        if user_has_password:
            if not user or not user.check_password(current_password):
                flash("Current password is incorrect.", "error")
                return render_template("auth/change_password.html", has_password=user_has_password)

        # Update password
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            save_to_history(
                cur,
                "user_account",
                "UPDATE",
                current_user.user_id,
                user_id=current_user.user_id,
            )
            hashed_password = bcrypt.hashpw(
                new_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            cur.execute(
                """
                UPDATE user_account
                SET hashed_password = %s, last_modified_date = %s, last_modified_user_id = %s
                WHERE user_id = %s
            """,
                (hashed_password, now_utc(), current_user.user_id, current_user.user_id),
            )
            conn.commit()

            if user_has_password:
                flash("Password changed successfully.", "success")
            else:
                flash("Password created successfully.", "success")
            return redirect(url_for("home"))

        finally:
            conn.close()

    return render_template("auth/change_password.html", has_password=user_has_password)


def verify_email(token):
    """Verify email and auto-login the user"""
    # Get client info for logging
    ip_address = request.environ.get(
        "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR")
    )
    if ip_address and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Find user with valid verification token
        cur.execute(
            """
            SELECT user_id, username FROM user_account
            WHERE verification_token = %s
            AND verification_token_expires > %s
            AND email_verified = FALSE
        """,
            (token, now_utc()),
        )
        user_data = cur.fetchone()

        if user_data:
            user_id = user_data[0]

            # Mark email as verified and clear token
            save_to_history(
                cur, "user_account", "UPDATE", user_id, user_id=None
            )
            cur.execute(
                """
                UPDATE user_account
                SET email_verified = TRUE,
                    verification_token = NULL,
                    verification_token_expires = NULL,
                    last_modified_date = %s,
                    last_modified_user_id = NULL
                WHERE user_id = %s
            """,
                (now_utc(), user_id),
            )
            conn.commit()

            # Auto-login the user
            user = User.get_by_id(user_id)
            if user and user.is_active:
                login_user(user, remember=True)

                session_id = create_session(user.user_id, ip_address, user_agent)

                log_login_event(
                    user.user_id,
                    user.email,
                    "LOGIN_SUCCESS",
                    ip_address,
                    user_agent,
                    session_id=session_id,
                    additional_data={"method": "email_verification"},
                )

                session.permanent = True
                session["db_session_id"] = session_id

                # Cache admin session IDs
                cur.execute(
                    """
                    SELECT s.session_id
                    FROM session_person sp
                    JOIN session s ON sp.session_id = s.session_id
                    WHERE sp.person_id = %s AND sp.is_admin = TRUE
                """,
                    (user.person_id,),
                )
                admin_session_ids = [row[0] for row in cur.fetchall()]
                session["admin_session_ids"] = admin_session_ids

                cleanup_expired_sessions()

                flash("Email verified! Welcome to Irish Music Sessions.", "success")

                # Redirect to password setup if user has no password
                if not user.has_password():
                    return redirect(url_for("set_password_optional"))

                return redirect(url_for("home"))

            flash("Email verified successfully! You can now log in.", "success")
            return redirect(url_for("login"))
        else:
            flash(
                "Invalid or expired verification link. Please request a new verification email.",
                "error",
            )
            return redirect(url_for("resend_verification"))

    finally:
        conn.close()


def resend_verification():
    if request.method == "POST":
        email = request.form.get("email", "").strip()

        if not email:
            flash("Email address is required.", "error")
            return render_template("auth/resend_verification.html")

        conn = get_db_connection()
        try:
            cur = conn.cursor()

            # Find unverified user by email
            cur.execute(
                """
                SELECT ua.user_id, ua.username, p.first_name, p.last_name, p.email
                FROM user_account ua
                JOIN person p ON ua.person_id = p.person_id
                WHERE p.email = %s AND ua.email_verified = FALSE AND ua.is_active = TRUE
            """,
                (email,),
            )
            user_data = cur.fetchone()

            if user_data:
                # Generate new verification token
                verification_token = generate_verification_token()
                verification_expires = now_utc() + timedelta(hours=24)

                # Update token in database (no user logged in during resend verification)
                save_to_history(
                    cur,
                    "user_account",
                    "UPDATE",
                    user_data[0],
                    user_id=None,
                )
                cur.execute(
                    """
                    UPDATE user_account
                    SET verification_token = %s, verification_token_expires = %s, last_modified_user_id = NULL
                    WHERE user_id = %s
                """,
                    (verification_token, verification_expires, user_data[0]),
                )
                conn.commit()

                # Send verification email
                user = User(
                    user_data[0],
                    None,
                    user_data[1],
                    email=user_data[4],
                    first_name=user_data[2],
                    last_name=user_data[3],
                )
                if send_verification_email(user, verification_token):
                    flash(
                        "Verification email sent! Please check your email.", "success"
                    )
                else:
                    flash(
                        "Failed to send verification email. Please try again later.",
                        "error",
                    )
            else:
                # Don't reveal whether email exists or is already verified
                flash(
                    "If an unverified account with that email exists, a verification email has been sent.",
                    "info",
                )

        finally:
            conn.close()

        return redirect(url_for("login"))

    return render_template("auth/resend_verification.html")


def unsubscribe_updates(token):
    """One-click unsubscribe from app update emails (spec 027). No login required:
    the signed token identifies the user. GET shows a confirmation page; POST is
    the RFC 8058 one-click target (mail clients POST List-Unsubscribe=One-Click)."""
    user_id = verify_unsubscribe_token(token)
    if user_id is None:
        from app import render_error_page

        return render_error_page("This unsubscribe link is not valid.", 404)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        save_to_history(cur, "user_account", "UPDATE", user_id, user_id=user_id)
        cur.execute(
            """
            UPDATE user_account
            SET receive_update_emails = FALSE, last_modified_date = %s
            WHERE user_id = %s
            """,
            (now_utc(), user_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            from app import render_error_page

            return render_error_page("This unsubscribe link is not valid.", 404)
        conn.commit()
    finally:
        conn.close()

    if request.method == "POST":
        return "", 200
    return render_template("unsubscribe.html")


@login_required
def admin():
    # Check if user is system admin
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    return render_template("admin_home.html")


@login_required
def admin_sessions_list():
    # Check if user is system admin or a session admin for at least one session
    is_system_admin = current_user.is_system_admin
    admin_session_ids = session.get("admin_session_ids", [])

    if not is_system_admin and not admin_session_ids:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Build the query - system admins see all, session admins see only their sessions
        base_query = """
            SELECT
                s.session_id,
                s.thesession_id,
                s.name,
                s.path,
                s.location_name,
                s.location_street,
                s.city,
                s.state,
                s.country,
                s.timezone,
                s.comments,
                s.unlisted_address,
                s.initiation_date,
                s.termination_date,
                s.recurrence,
                s.created_date,
                s.last_modified_date,
                COALESCE(si_counts.instance_count, 0) as instance_count,
                COALESCE(player_counts.total_players, 0) as total_players,
                COALESCE(player_counts.regular_players, 0) as regular_players,
                latest_si.latest_instance_date
            FROM session s
            LEFT JOIN (
                SELECT
                    session_id,
                    COUNT(*) as instance_count
                FROM session_instance
                GROUP BY session_id
            ) si_counts ON s.session_id = si_counts.session_id
            LEFT JOIN (
                SELECT
                    sp.session_id,
                    COUNT(*) as total_players,
                    COUNT(CASE WHEN sp.is_regular = TRUE THEN 1 END) as regular_players
                FROM session_person sp
                GROUP BY sp.session_id
            ) player_counts ON s.session_id = player_counts.session_id
            LEFT JOIN (
                SELECT DISTINCT ON (si.session_id)
                    si.session_id,
                    si.date as latest_instance_date
                FROM session_instance si
                ORDER BY si.session_id, si.date DESC
            ) latest_si ON s.session_id = latest_si.session_id
        """

        if is_system_admin:
            # System admins see all sessions
            cur.execute(base_query + " ORDER BY s.name")
        else:
            # Session admins only see sessions they admin
            cur.execute(
                base_query + " WHERE s.session_id = ANY(%s) ORDER BY s.name",
                (admin_session_ids,)
            )

        sessions = []
        for row in cur.fetchall():
            (
                session_id,
                thesession_id,
                name,
                path,
                location_name,
                location_street,
                city,
                state,
                country,
                timezone,
                comments,
                unlisted_address,
                initiation_date,
                termination_date,
                recurrence,
                created_date,
                last_modified_date,
                instance_count,
                total_players,
                regular_players,
                latest_instance_date,
            ) = row

            # Format location for display (city/state/country only, not venue name)
            location_parts = []
            if city:
                location_parts.append(city)
            if state:
                location_parts.append(state)
            if country:
                location_parts.append(country)
            location_display = ", ".join(location_parts) if location_parts else "Unknown"

            # Format player count display like "65 (12 regulars)"
            player_count_display = f"{total_players}"
            if regular_players > 0:
                player_count_display += f" ({regular_players} regulars)"

            # Format latest instance date
            latest_instance_display = ""
            if latest_instance_date:
                latest_instance_display = latest_instance_date.strftime("%Y-%m-%d")

            sessions.append(
                {
                    "session_id": session_id,
                    "thesession_id": thesession_id,
                    "name": name,
                    "path": path,
                    "location_name": location_name,
                    "location_street": location_street,
                    "city": city,
                    "state": state,
                    "country": country,
                    "timezone": timezone,
                    "comments": comments,
                    "unlisted_address": unlisted_address,
                    "initiation_date": initiation_date,
                    "termination_date": termination_date,
                    "recurrence": recurrence,
                    "created_date": created_date,
                    "last_modified_date": last_modified_date,
                    "location_display": location_display,
                    "instance_count": instance_count,
                    "total_players": total_players,
                    "regular_players": regular_players,
                    "player_count_display": player_count_display,
                    "latest_instance_display": latest_instance_display,
                }
            )

        return render_template("admin_sessions_list.html", sessions=sessions, active_tab="sessions_list")

    finally:
        conn.close()


@login_required
def admin_login_sessions():
    """Redirect old active logins URL to Activity page with active sessions filter"""
    return redirect(url_for(
        "admin_activity",
        category="logins",
        activity_type="ACTIVE_SESSIONS"
    ))


@login_required
def admin_login_history():
    """Redirect old login history URL to Activity page with logins category"""
    # Preserve filter parameters where possible
    hours = request.args.get("hours", 24, type=int)
    event_type = request.args.get("event_type", "")
    username = request.args.get("username", "")

    return redirect(url_for(
        "admin_activity",
        category="logins",
        hours=hours,
        activity_type=event_type,
        user=username
    ))


@login_required
def admin_people():
    """Admin people table (spec 035 final migration): a thin shell embedding the
    SAME payload GET /api/admin/people returns (one serializer — they can't
    drift). Search/sort and the add-person wizard live in the Svelte bundle."""
    # Check if user is system admin
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    from serializers import build_admin_people_payload

    conn = get_db_connection()
    try:
        payload = build_admin_people_payload(conn)
    finally:
        conn.close()
    return render_template("admin_people.html", payload=payload, active_tab="people")


@login_required
def admin_tunes():
    """Admin tunes page - shows all tunes with counts"""
    # Check if user is system admin
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    return render_template("admin_tunes.html", active_tab="tunes")


@login_required
def admin_tune_detail(tune_id):
    """Admin tune detail page - shows tunes list with specific tune modal open"""
    # Check if user is system admin
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    redirect_to = _resolve_tune_redirect(tune_id)
    if redirect_to:
        return redirect(f"/admin/tunes/{redirect_to}", code=301)

    return render_template("admin_tunes.html", active_tab="tunes", tune_id=tune_id)


@login_required
def admin_tune_merge():
    """Admin tune merge page - merge tune references when thesession.org merges tunes"""
    # Check if user is system admin
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    return render_template("admin_tune_merge.html", active_tab="merge_tunes")


@login_required
def admin_test_links():
    """Admin test links page with sample URLs for testing"""
    # Check if user is system admin
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Get a sample session (try to find session_id=1 first, fallback to any session)
        cur.execute(
            """
            SELECT session_id, path, name
            FROM session
            WHERE session_id = 1
            LIMIT 1
        """
        )
        sample_session = cur.fetchone()

        if not sample_session:
            # Fallback to any session
            cur.execute(
                """
                SELECT session_id, path, name
                FROM session
                ORDER BY session_id
                LIMIT 1
            """
            )
            sample_session = cur.fetchone()

        # Get a random tune from that session
        sample_tune_id = None
        if sample_session:
            cur.execute(
                """
                SELECT tune_id
                FROM session_tune
                WHERE session_id = %s
                ORDER BY RANDOM()
                LIMIT 1
            """,
                (sample_session[0],),
            )
            tune_result = cur.fetchone()
            if tune_result:
                sample_tune_id = tune_result[0]

        # Get latest session instance for that session
        latest_instance_date = None
        if sample_session:
            cur.execute(
                """
                SELECT date
                FROM session_instance
                WHERE session_id = %s
                ORDER BY date DESC
                LIMIT 1
            """,
                (sample_session[0],),
            )
            instance_result = cur.fetchone()
            if instance_result:
                latest_instance_date = instance_result[0]

        # Get a random person
        cur.execute(
            """
            SELECT person_id
            FROM person
            ORDER BY RANDOM()
            LIMIT 1
        """
        )
        person_result = cur.fetchone()
        sample_person_id = person_result[0] if person_result else None

        return render_template(
            "admin_test_links.html",
            active_tab="test_links",
            sample_session=sample_session,
            sample_tune_id=sample_tune_id,
            latest_instance_date=latest_instance_date,
            sample_person_id=sample_person_id,
        )

    finally:
        conn.close()


@login_required
def admin_cache_settings():
    """Admin cache settings page - run cache process for missing tune settings"""
    # Check if user is system admin
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    return render_template("admin_cache_settings.html", active_tab="cache_settings")


@login_required
def admin_email_updates():
    """Admin screen to compose and send app update emails (spec 027)."""
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM user_account
            WHERE receive_update_emails = TRUE AND is_active = TRUE AND user_email IS NOT NULL
            """
        )
        recipient_count = cur.fetchone()[0]

        cur.execute(
            """
            SELECT em.email_message_id, em.subject, em.sent_date, ua.username,
                   em.recipient_count, em.success_count, em.failure_count
            FROM email_message em
            JOIN user_account ua ON em.sent_by_user_id = ua.user_id
            ORDER BY em.email_message_id DESC
            """
        )
        messages = [
            {
                "id": row[0],
                "subject": row[1],
                "sent_date": row[2],
                "sent_by": row[3],
                "recipient_count": row[4],
                "success_count": row[5],
                "failure_count": row[6],
                "failures": [],
            }
            for row in cur.fetchall()
        ]

        if messages:
            cur.execute(
                """
                SELECT email_message_id, email, error_message
                FROM email_message_recipient
                WHERE status = 'failed'
                """
            )
            failures_by_message = {}
            for msg_id, email, error_message in cur.fetchall():
                failures_by_message.setdefault(msg_id, []).append(
                    {"email": email, "error": error_message}
                )
            for message in messages:
                message["failures"] = failures_by_message.get(message["id"], [])
    finally:
        conn.close()

    return render_template(
        "admin_email_updates.html",
        active_tab="email_updates",
        recipient_count=recipient_count,
        messages=messages,
    )


@login_required
def person_details(person_id=None):
    """Person details page (spec 035 Step 5a): a thin shell that embeds the SAME
    payload GET /api/me/details / GET /api/admin/people/<id>/details returns
    (one serializer — they cannot drift) and mounts the Svelte view
    (/static/personpage/page.js)."""
    from serializers import build_person_details_payload

    # Determine if this is a user profile view or admin view
    is_user_profile = person_id is None

    if is_user_profile:
        # User profile view - use current user's person_id
        person_id = current_user.person_id
    else:
        # Admin view - check if user is system admin
        if not current_user.is_system_admin:
            flash("You must be authorized to view this page.", "error")
            return redirect(url_for("home"))

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
        from app import render_error_page

        return render_error_page("Person not found.", 404)

    return render_template(
        "person_details.html",
        payload=payload,
        person=payload["person"],
        is_user_profile=is_user_profile,
    )


def _get_session_data(session_path):
    """Helper function to get session data by path"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Get session details
        cur.execute(
            """
            SELECT session_id, name, path, location_name, location_website, location_phone,
                   location_street, city, state, country, comments, unlisted_address,
                   initiation_date, termination_date, recurrence, timezone,
                   COALESCE(auto_create_instances, FALSE) as auto_create_instances,
                   COALESCE(auto_create_hours_ahead, 24) as auto_create_hours_ahead,
                   COALESCE(live_cache_session_limit, 200) as live_cache_session_limit,
                   COALESCE(live_cache_global_limit, 25) as live_cache_global_limit
            FROM session
            WHERE path = %s
        """,
            (session_path,),
        )

        session_row = cur.fetchone()
        if not session_row:
            return None

        session_data = {
            "session_id": session_row[0],
            "name": session_row[1],
            "path": session_row[2],
            "location_name": session_row[3],
            "location_website": session_row[4],
            "location_phone": session_row[5],
            "location_street": session_row[6],
            "city": session_row[7],
            "state": session_row[8],
            "country": session_row[9],
            "comments": session_row[10],
            "unlisted_address": session_row[11],
            "initiation_date": session_row[12],
            "termination_date": session_row[13],
            "recurrence": session_row[14],
            "timezone": session_row[15],
            "timezone_display": get_timezone_display_name(session_row[15] or "UTC"),
            "auto_create_instances": session_row[16],
            "auto_create_hours_ahead": session_row[17],
            "live_cache_session_limit": session_row[18],
            "live_cache_global_limit": session_row[19],
        }

        from serializers import recurrence_readable
        session_data["recurrence_readable"] = recurrence_readable(session_row[14])

        return session_data

    finally:
        conn.close()


def _check_session_admin_access(session_path):
    """
    Check if the current user has admin access to a specific session.
    Returns True if user is a system admin or a session-level admin for this session.
    Returns False if not authorized.
    """
    if not current_user.is_authenticated:
        return False

    # System admins have access to all sessions
    if current_user.is_system_admin:
        return True

    # Check if user is an admin for this specific session
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return False

        session_id = session_result[0]
        cur.execute(
            """SELECT sp.is_admin FROM session_person sp
               WHERE sp.session_id = %s AND sp.person_id = %s""",
            (session_id, current_user.person_id)
        )
        admin_row = cur.fetchone()
        return admin_row and admin_row[0]
    finally:
        conn.close()


def _render_session_admin(session_path, active_tab):
    """Shared renderer for the session-admin tab wrapper routes (spec 035 Step
    5b): auth check, then a thin shell embedding the SAME payload GET
    /api/admin/sessions/<path>/admin-detail returns (one serializer — they
    cannot drift). The tab content and all page behavior live in the Svelte
    bundle (/static/sessionadminpage/page.js)."""
    from serializers import build_session_admin_payload

    # Check if user is system admin or session admin
    if not _check_session_admin_access(session_path):
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    conn = get_db_connection()
    try:
        payload = build_session_admin_payload(conn, session_path)
    finally:
        conn.close()

    if payload is None:
        from app import render_error_page

        return render_error_page("Session not found", 404)

    return render_template(
        "session_admin.html",
        payload=payload,
        session=payload["session"],
        session_path=session_path,
        active_tab=active_tab,
    )


@login_required
def session_admin(session_path):
    """Session admin details page"""
    return _render_session_admin(session_path, "details")


@login_required
def session_admin_players(session_path):
    """Session admin players page"""
    return _render_session_admin(session_path, "people")


@login_required
def session_admin_logs(session_path):
    """Session admin logs page"""
    return _render_session_admin(session_path, "logs")


@login_required
def session_admin_cache(session_path):
    """Session admin "Local Cache" page — view/tune the live-logging fast-match
    vocabulary (N most-played session tunes + M globally-popular tunes; spec 024)."""
    return _render_session_admin(session_path, "cache")


@login_required
def session_admin_tunes(session_path):
    """Session admin tunes page - grid view of all tunes played at this session"""
    return _render_session_admin(session_path, "tunes")


@login_required
def session_admin_person(session_path, person_id):
    """Session admin person details page"""
    # Check if user is system admin or session admin
    if not _check_session_admin_access(session_path):
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Get session details
        session_data = _get_session_data(session_path)
        if not session_data:
            from app import render_error_page

            return render_error_page("Session not found", 404)

        session_id = session_data["session_id"]

        # Get person details and their relationship to this session
        cur.execute(
            """
            SELECT
                p.person_id,
                p.first_name,
                p.last_name,
                p.email,
                p.sms_number,
                p.city,
                p.state,
                p.country,
                p.thesession_user_id,
                sp.is_regular,
                sp.is_admin,
                sp.gets_email_reminder,
                sp.gets_email_followup,
                u.username,
                u.is_system_admin
            FROM person p
            JOIN session_person sp ON p.person_id = sp.person_id
            LEFT JOIN user_account u ON p.person_id = u.person_id
            WHERE p.person_id = %s AND sp.session_id = %s
        """,
            (person_id, session_id),
        )

        person_row = cur.fetchone()
        if not person_row:
            from app import render_error_page

            return render_error_page("Person not found in this session", 404)

        person_data = {
            "person_id": person_row[0],
            "first_name": person_row[1],
            "last_name": person_row[2],
            "email": person_row[3],
            "sms_number": person_row[4],
            "city": person_row[5],
            "state": person_row[6],
            "country": person_row[7],
            "thesession_user_id": person_row[8],
            "is_regular": person_row[9],
            "is_admin": person_row[10],
            "gets_email_reminder": person_row[11],
            "gets_email_followup": person_row[12],
            "username": person_row[13],
            "is_system_admin": person_row[14],
        }

        # Get instruments for this person
        cur.execute(
            """
            SELECT instrument 
            FROM person_instrument 
            WHERE person_id = %s 
            ORDER BY instrument
            """,
            (person_id,)
        )
        person_data["instruments"] = [row[0] for row in cur.fetchall()]

        # Get attendance history for this person at this session
        cur.execute(
            """
            SELECT
                si.date,
                si.start_time,
                si.end_time,
                si.is_cancelled,
                si.comments,
                si.session_instance_id,
                COUNT(*) OVER (PARTITION BY si.date) as instances_on_date
            FROM session_instance si
            JOIN session_instance_person sip ON si.session_instance_id = sip.session_instance_id
            WHERE si.session_id = %s AND sip.person_id = %s
            ORDER BY si.date DESC, si.session_instance_id ASC
        """,
            (session_id, person_id),
        )

        attendance_history = []
        for row in cur.fetchall():
            attendance_history.append(
                {
                    "date": row[0],
                    "start_time": row[1],
                    "end_time": row[2],
                    "is_cancelled": row[3],
                    "comments": row[4],
                    "session_instance_id": row[5],
                    "multiple_on_date": row[6] > 1,
                }
            )

        # Check if coming from attendance tab
        from_attendance = request.args.get('from') == 'attendance'
        instance_id = request.args.get('instance_id')
        session_instance_date = None
        
        if from_attendance and instance_id:
            # Get the session instance date for the breadcrumb
            cur.execute(
                "SELECT date FROM session_instance WHERE session_instance_id = %s",
                (instance_id,)
            )
            instance_row = cur.fetchone()
            if instance_row:
                session_instance_date = instance_row[0]

        return render_template(
            "session_admin_person.html",
            session=session_data,
            session_path=session_path,
            person=person_data,
            attendance_history=attendance_history,
            from_attendance=from_attendance,
            session_instance_date=session_instance_date,
            session_instance_id=instance_id,
        )

    finally:
        conn.close()

@login_required
def session_admin_bulk_import(session_path):
    """Session admin bulk import page - supports both CSV input and preview steps"""
    # Check if user is system admin only (per API design)
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    session_data = _get_session_data(session_path)
    if not session_data:
        from app import render_error_page
        return render_error_page("Session not found", 404)

    # Get step from query parameter, default to 'input'
    step = request.args.get('step', 'input')
    if step not in ['input', 'preview']:
        step = 'input'

    return render_template(
        "session_bulk_import.html",
        session=session_data,
        session_path=session_path,
        step=step
    )


@login_required
def my_tunes():
    """Personal tune collection page (spec 035 Step 2): a thin shell that embeds
    the SAME payload GET /api/my-tunes returns (one serializer — they can't
    drift) and mounts the Svelte view. Filtering/sorting is client-side; the
    embed is always the default sort, and the client re-sorts from URL params."""
    from serializers import build_my_tunes_payload
    conn = get_db_connection()
    try:
        payload = build_my_tunes_payload(conn, current_user.person_id)
    finally:
        conn.close()
    return render_template("my_tunes.html", payload=payload)


@login_required
def add_my_tune_page():
    """Folded-away legacy add page: redirect to My Tunes with the modern add
    pane auto-opened (?add=1, optional ?q= prefilling the pane's search)."""
    args = {"add": 1}
    q = request.args.get("q", "").strip()
    if q:
        args["q"] = q
    return redirect(url_for("my_tunes", **args))


@login_required
def sync_my_tunes_page():
    """Sync tunes from thesession.org page"""
    # Get current user's thesession_user_id from person table
    thesession_user_id = None
    if hasattr(current_user, 'person_id'):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT thesession_user_id FROM person WHERE person_id = %s",
                (current_user.person_id,)
            )
            row = cur.fetchone()
            if row:
                thesession_user_id = row[0]
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error fetching thesession_user_id: {e}")

    return render_template("my_tunes_sync.html", thesession_user_id=thesession_user_id)


@login_required
def common_tunes(person_id):
    """Common tunes page - shows tunes that both users have learned/learning"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the other person's details
        cur.execute("""
            SELECT p.person_id, p.first_name, p.last_name,
                   EXISTS(SELECT 1 FROM user_account WHERE person_id = p.person_id) as has_account
            FROM person p
            WHERE p.person_id = %s
        """, (person_id,))

        other_person = cur.fetchone()

        if not other_person:
            cur.close()
            conn.close()
            from app import render_error_page
            return render_error_page("Person not found", 404)

        # Check if the other person has a user account
        if not other_person[3]:  # has_account
            cur.close()
            conn.close()
            from app import render_error_page
            return render_error_page("This person does not have a user account", 404)

        other_person_name = f"{other_person[1]} {other_person[2]}"

        # Get current user's name
        cur.execute("""
            SELECT first_name, last_name
            FROM person
            WHERE person_id = %s
        """, (current_user.person_id,))

        current_person = cur.fetchone()
        current_person_name = f"{current_person[0]} {current_person[1]}" if current_person else "You"

        cur.close()
        conn.close()

        return render_template(
            "common_tunes.html",
            current_person_name=current_person_name,
            other_person_name=other_person_name,
            other_person_id=person_id
        )

    except Exception as e:
        print(f"Error in common_tunes: {e}")
        from app import render_error_page
        return render_error_page("Error loading page", 500)


def add_session_tune_page(session_path):
    """Folded-away legacy add page: redirect to the session's Tunes tab with the
    modern add pane auto-opened (?add=1, optional ?q= prefilling the pane's
    search). A bad session_path 404s at the target, exactly as before."""
    args = {"session_path": session_path, "add": 1}
    q = request.args.get("q", "").strip()
    if q:
        args["q"] = q
    return redirect(url_for("session_tunes", **args))


# Category to entity type mapping for activity view
ACTIVITY_CATEGORIES = {
    'all': None,  # No filter
    'sessions': ['session', 'session_tune', 'session_tune_alias', 'session_person'],
    'people': ['person', 'user_account', 'person_instrument', 'person_tune',
               'person_tune_instrument', 'session_person', 'session_instance_person'],
    'tunes': ['tune', 'tune_setting', 'session_tune', 'session_tune_alias'],
    'logs': ['session_instance', 'session_instance_tune', 'session_instance_person'],
    'logins': ['login'],
}


@login_required
def admin_activity():
    """Admin activity view - unified feed of site activity"""
    if not current_user.is_system_admin:
        flash("You must be authorized to view this page.", "error")
        return redirect(url_for("home"))

    # Get filter parameters
    page = request.args.get("page", 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page

    category = request.args.get("category", "all")
    hours_filter = request.args.get("hours", 24, type=int)
    activity_type_filter = request.args.get("activity_type", "")
    session_filter = request.args.get("session_id", "", type=str)
    user_filter = request.args.get("user", "")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Special handling for Active Sessions view
        if activity_type_filter == 'ACTIVE_SESSIONS':
            # Query active sessions from user_session table
            where_conditions = ["us.expires_at > %s"]
            params = [now_utc()]

            if user_filter:
                where_conditions.append("(u.username ILIKE %s OR p.first_name ILIKE %s OR p.last_name ILIKE %s)")
                params.extend([f"%{user_filter}%", f"%{user_filter}%", f"%{user_filter}%"])

            where_clause = " AND ".join(where_conditions)

            # Get total count
            count_query = f"""
                SELECT COUNT(*)
                FROM user_session us
                JOIN user_account u ON us.user_id = u.user_id
                JOIN person p ON u.person_id = p.person_id
                WHERE {where_clause}
            """
            cur.execute(count_query, params)
            result = cur.fetchone()
            total_count = result[0] if result else 0

            # Get active sessions
            query = f"""
                SELECT
                    us.user_id,
                    u.username,
                    p.first_name,
                    p.last_name,
                    us.created_date,
                    us.last_accessed,
                    us.ip_address
                FROM user_session us
                JOIN user_account u ON us.user_id = u.user_id
                JOIN person p ON u.person_id = p.person_id
                WHERE {where_clause}
                ORDER BY us.last_accessed DESC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            cur.execute(query, params)

            activity_items = []
            for row in cur.fetchall():
                (user_id, username, first_name, last_name, created_date, last_accessed, ip_address) = row

                # Calculate duration
                login_duration = now_utc() - created_date
                days = login_duration.days
                hours, remainder = divmod(login_duration.seconds, 3600)
                minutes, _ = divmod(remainder, 60)

                if days > 0:
                    duration_str = f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    duration_str = f"{hours}h {minutes}m"
                else:
                    duration_str = f"{minutes}m"

                activity_items.append({
                    'activity_date': created_date,
                    'entity_type': 'active_session',
                    'entity_id': user_id,
                    'activity_type': 'ACTIVE',
                    'user_id': user_id,
                    'entity_name': f"{first_name} {last_name}",
                    'entity_path': None,
                    'username': username,
                    'duration': duration_str,
                    'ip_address': ip_address or 'Unknown',
                    'last_accessed': last_accessed,
                })
        else:
            # Standard activity query
            # Build WHERE conditions
            where_conditions = ["ra.activity_date > %s"]
            params = [now_utc() - timedelta(hours=hours_filter)]

            # Category filter
            if category in ACTIVITY_CATEGORIES and ACTIVITY_CATEGORIES[category]:
                entity_types = ACTIVITY_CATEGORIES[category]
                placeholders = ','.join(['%s'] * len(entity_types))
                where_conditions.append(f"ra.entity_type IN ({placeholders})")
                params.extend(entity_types)

            # Activity type filter
            if activity_type_filter:
                where_conditions.append("ra.activity_type = %s")
                params.append(activity_type_filter)

            # Session filter
            if session_filter:
                where_conditions.append("ra.session_id_ref = %s")
                params.append(int(session_filter))

            # User filter (search by username)
            if user_filter:
                where_conditions.append("u.username ILIKE %s")
                params.append(f"%{user_filter}%")

            where_clause = " AND ".join(where_conditions)

            # Get total count for pagination
            count_query = f"""
                SELECT COUNT(*)
                FROM recent_activity ra
                LEFT JOIN user_account u ON ra.user_id = u.user_id
                WHERE {where_clause}
            """
            cur.execute(count_query, params)
            result = cur.fetchone()
            total_count = result[0] if result else 0

            # Get activity records
            query = f"""
                SELECT
                    ra.activity_date,
                    ra.entity_type,
                    ra.entity_id,
                    ra.activity_type,
                    ra.user_id,
                    ra.entity_name,
                    ra.entity_path,
                    u.username
                FROM recent_activity ra
                LEFT JOIN user_account u ON ra.user_id = u.user_id
                WHERE {where_clause}
                ORDER BY ra.activity_date DESC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            cur.execute(query, params)

            activity_items = []
            for row in cur.fetchall():
                (
                    activity_date,
                    entity_type,
                    entity_id,
                    activity_type,
                    user_id,
                    entity_name,
                    entity_path,
                    username,
                ) = row

                activity_items.append({
                    'activity_date': activity_date,
                    'entity_type': entity_type,
                    'entity_id': entity_id,
                    'activity_type': activity_type,
                    'user_id': user_id,
                    'entity_name': entity_name,
                    'entity_path': entity_path,
                    'username': username or 'System',
                })

        # Get list of sessions for filter dropdown
        cur.execute("""
            SELECT session_id, name, path
            FROM session
            ORDER BY name
        """)
        sessions = [{'session_id': r[0], 'name': r[1], 'path': r[2]} for r in cur.fetchall()]

        # Pagination calculations
        total_pages = (total_count + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages

        return render_template(
            "admin_activity.html",
            activity_items=activity_items,
            active_tab="activity",
            page=page,
            total_pages=total_pages,
            has_prev=has_prev,
            has_next=has_next,
            total_count=total_count,
            category=category,
            hours_filter=hours_filter,
            activity_type_filter=activity_type_filter,
            session_filter=session_filter,
            user_filter=user_filter,
            sessions=sessions,
        )

    finally:
        conn.close()


@login_required
def live_logging_screen(session_instance_id):
    """
    Serve the clean-slate Svelte live-logging screen (spec 024 §H, Phase 0).

    A thin shell: it passes the instance id, current person, and the streaming
    service base URL to the bundle, which then fetches the bootstrap snapshot and
    opens the SSE stream. The bundle is a self-contained Vite build under
    /static/live, isolated to this screen (not the base layout).
    """
    import os

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.path FROM session_instance si
            JOIN session s ON s.session_id = si.session_id
            WHERE si.session_instance_id = %s
            """,
            (session_instance_id,),
        )
        row = cur.fetchone()
        if not row:
            return render_template("error.html", error_message="Session instance not found"), 404
        session_path = row[0]
    finally:
        conn.close()

    streaming_base_url = os.environ.get("STREAMING_BASE_URL", "http://localhost:8080")
    return render_template(
        "live_logging.html",
        session_instance_id=session_instance_id,
        session_path=session_path,
        streaming_base_url=streaming_base_url,
        current_person={
            "person_id": current_user.person_id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
        },
    )
