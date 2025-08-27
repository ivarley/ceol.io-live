from flask import request, jsonify, session
import requests
import re
from flask_login import login_required
from database import (
    get_db_connection,
    save_to_history,
    find_matching_tune,
    normalize_apostrophes,
)
from email_utils import send_email_via_sendgrid
from timezone_utils import now_utc, format_datetime_with_timezone, utc_to_local
from flask_login import current_user
from functools import wraps


def api_login_required(f):
    """
    Decorator for API endpoints that require authentication.
    Returns JSON error response instead of redirecting to login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


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


@login_required
def update_session_ajax(session_path):
    """Update session details from admin page"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})

        conn = get_db_connection()
        cur = conn.cursor()

        # Get current session details for history tracking
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Session not found"})

        session_id = session_result[0]

        # Save to history before making changes
        user_id = session.get("user_id")
        save_to_history(
            cur, "session", "UPDATE", session_id, str(user_id) if user_id else "system"
        )

        # Prepare the update query
        update_fields = []
        update_values = []

        # Map form fields to database columns
        field_mapping = {
            "name": "name",
            "path": "path",
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
        }

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
                elif form_field == "unlisted_address":
                    value = bool(value)

                update_fields.append(f"{db_field} = %s")
                update_values.append(value)

        if not update_fields:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "No valid fields to update"})

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


def sessions_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT name, path, city, state, country, termination_date FROM session ORDER BY name;"
        )
        sessions = cur.fetchall()
        cur.close()
        conn.close()

        # Convert to list format for JSON serialization, handling dates
        sessions_list = []
        for session_row in sessions:
            session_data = list(session_row)
            # Convert date to string if it exists
            if session_data[5]:  # termination_date
                session_data[5] = session_data[5].isoformat()
            sessions_list.append(session_data)

        return jsonify({"sessions": sessions_list})
    except Exception as e:
        return jsonify({"error": f"Database connection failed: {str(e)}"}), 500


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


def add_session_tune_alias(session_path, tune_id):
    """Add a new alias for a tune in a session"""
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    alias = request.json.get("alias", "").strip()
    if not alias:
        return jsonify({"success": False, "message": "Please enter an alias"})

    # Normalize the alias
    normalized_alias = normalize_apostrophes(alias)

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
            INSERT INTO session_tune_alias (session_id, tune_id, alias, created_date, last_modified_date)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING session_tune_alias_id, created_date
        """,
            (session_id, tune_id, normalized_alias),
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


def add_session_instance_ajax(session_path):
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    date = request.json.get("date", "").strip()
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

        # Check if session instance already exists for this date
        cur.execute(
            """
            SELECT session_instance_id FROM session_instance
            WHERE session_id = %s AND date = %s
        """,
            (session_id, date),
        )
        existing_instance = cur.fetchone()

        if existing_instance:
            cur.close()
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "message": f"Session instance for {date} already exists",
                }
            )

        # Determine location_override: only set if location is provided AND different from session's location_name
        location_override = None
        if location and location != session_location_name:
            location_override = location

        # Insert new session instance
        cur.execute(
            """
            INSERT INTO session_instance (session_id, date, location_override, is_cancelled, comments)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_instance_id
        """,
            (session_id, date, location_override, cancelled, comments),
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
        save_to_history(cur, "session_instance", "INSERT", session_instance_id)

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f"Session instance for {date} created successfully!",
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": f"Failed to create session instance: {str(e)}",
            }
        )


def update_session_instance_ajax(session_path, date):
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    new_date = request.json.get("date", "").strip()
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

        # Get the session instance ID
        cur.execute(
            """
            SELECT session_instance_id FROM session_instance
            WHERE session_id = %s AND date = %s
        """,
            (session_id, date),
        )
        instance_result = cur.fetchone()

        if not instance_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id = instance_result[0]

        # If date is changing, check if new date conflicts with existing instance
        if new_date != date:
            cur.execute(
                """
                SELECT session_instance_id FROM session_instance
                WHERE session_id = %s AND date = %s
            """,
                (session_id, new_date),
            )
            existing_instance = cur.fetchone()

            if existing_instance:
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "message": f"Session instance for {new_date} already exists",
                    }
                )

        # Determine location_override: only set if location is provided AND different from session's location_name
        location_override = None
        if location and location != session_location_name:
            location_override = location

        # Save current state to history before update
        save_to_history(cur, "session_instance", "UPDATE", session_instance_id)

        # Update the session instance
        cur.execute(
            """
            UPDATE session_instance
            SET date = %s, location_override = %s, is_cancelled = %s, comments = %s
            WHERE session_instance_id = %s
        """,
            (new_date, location_override, cancelled, comments, session_instance_id),
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


def get_session_tune_count_ajax(session_path, date):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get tune count for this session instance
        cur.execute(
            """
            SELECT COUNT(*)
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s
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


def delete_session_instance_ajax(session_path, date):
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
            (session_id, date),
        )
        instance_result = cur.fetchone()

        if not instance_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id = instance_result[0]

        # Save to history before deletion
        save_to_history(cur, "session_instance", "DELETE", session_instance_id)

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
            save_to_history(cur, "session_instance_tune", "DELETE", tune_record[0])

        # Explicitly delete session_instance_tune records first
        cur.execute(
            """
            DELETE FROM session_instance_tune WHERE session_instance_id = %s
        """,
            (session_instance_id,),
        )

        # Then delete the session instance
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
                "message": f"Session instance for {date} deleted successfully!",
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "message": f"Failed to delete session instance: {str(e)}",
            }
        )


def mark_session_log_complete_ajax(session_path, date):
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

        # Check if the session instance exists
        cur.execute(
            """
            SELECT session_instance_id, log_complete_date
            FROM session_instance
            WHERE session_id = %s AND date = %s
        """,
            (session_id, date),
        )

        instance_result = cur.fetchone()
        if not instance_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id, current_log_complete_date = instance_result

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
        save_to_history(cur, "session_instance", "UPDATE", session_instance_id)

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


def mark_session_log_incomplete_ajax(session_path, date):
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

        # Check if the session instance exists
        cur.execute(
            """
            SELECT session_instance_id, log_complete_date
            FROM session_instance
            WHERE session_id = %s AND date = %s
        """,
            (session_id, date),
        )

        instance_result = cur.fetchone()
        if not instance_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id, current_log_complete_date = instance_result

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
        save_to_history(cur, "session_instance", "UPDATE", session_instance_id)

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


def search_sessions_ajax():
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    search_query = request.json.get("query")
    if not search_query:
        return jsonify({"success": False, "message": "Search query is required"})

    try:
        # Search sessions on thesession.org API
        api_url = f"https://thesession.org/sessions/search?q={search_query}&format=json"
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

        # Return first 5 results with formatted data and existence check
        results = []
        for session_item in sessions[:5]:
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


def add_session_ajax():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "No JSON data provided"})

    # Validate required fields
    required_fields = ["name", "path", "city", "state", "country"]
    for field in required_fields:
        if not data.get(field, "").strip():
            return jsonify(
                {"success": False, "message": f"{field.title()} is required"}
            )

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if path is already taken
        cur.execute("SELECT session_id FROM session WHERE path = %s", (data["path"],))
        existing_session = cur.fetchone()
        if existing_session:
            cur.close()
            conn.close()
            return jsonify(
                {"success": False, "message": f'Path "{data["path"]}" is already taken'}
            )

        # Check if TheSession.org ID is already used
        if data.get("thesession_id"):
            cur.execute(
                "SELECT session_id FROM session WHERE thesession_id = %s",
                (data["thesession_id"],),
            )
            existing_thesession = cur.fetchone()
            if existing_thesession:
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "message": f'TheSession.org session {data["thesession_id"]} is already in the database',
                    }
                )

        # Insert new session
        cur.execute(
            """
            INSERT INTO session (
                thesession_id, name, path, location_name, location_phone, location_website,
                city, state, country, initiation_date, recurrence, created_date, last_modified_date
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING session_id
        """,
            (
                data.get("thesession_id") or None,
                data["name"],
                data["path"],
                data.get("location_name") or None,
                data.get("location_phone") or None,
                data.get("location_website") or None,
                data["city"],
                data["state"],
                data["country"],
                data.get("inception_date") or None,
                data.get("recurrence") or None,
            ),
        )

        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Failed to create session"})

        session_id = session_result[0]

        # Save the newly created session to history
        save_to_history(cur, "session", "INSERT", session_id)

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f'Session "{data["name"]}" created successfully!',
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Failed to create session: {str(e)}"}
        )


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
            # Get the highest order number (last tune) to find the last set
            cur.execute(
                """
                SELECT order_number
                FROM session_instance_tune sit
                JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                WHERE si.session_id = %s AND si.date = %s
                ORDER BY sit.order_number DESC
                LIMIT 1
            """,
                (session_id, date),
            )

            last_tune_result = cur.fetchone()
            if last_tune_result:
                # There are existing tunes, so we can append to the last set
                # last_order_number = last_tune_result[0]

                # Parse all the tune names from all lines and add them to the existing last set
                all_tune_names = []
                for line in lines:
                    tune_names_in_line = [
                        normalize_apostrophes(name.strip())
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
                        cur.execute(
                            "SELECT insert_session_instance_tune(%s, %s, %s, %s, %s, %s)",
                            (
                                session_id,
                                date,
                                tune_id,
                                None,
                                final_name if tune_id is None else None,
                                False,
                            ),
                        )  # starts_set = False (continues existing set)
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
                normalize_apostrophes(name.strip())
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
                # First tune in each set starts a new set (continues_set = False), subsequent tunes continue the set (continues_set = True)
                starts_set = i == 0

                # Use the existing stored procedure for both tune_id and name-based records
                cur.execute(
                    "SELECT insert_session_instance_tune(%s, %s, %s, %s, %s, %s)",
                    (
                        session_id,
                        date,
                        tune_id,
                        None,
                        name if tune_id is None else None,
                        starts_set,
                    ),
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


def delete_tune_by_order_ajax(session_path, date, order_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the tune info and session_instance_tune_id for history
        cur.execute(
            """
            SELECT
                COALESCE(sit.name, st.alias, t.name) AS tune_name,
                sit.continues_set,
                sit.session_instance_id,
                sit.tune_id,
                sit.session_instance_tune_id
            FROM session_instance_tune sit
            LEFT JOIN tune t ON sit.tune_id = t.tune_id
            LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                SELECT si.session_id
                FROM session_instance si
                WHERE si.session_instance_id = sit.session_instance_id
            )
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s AND sit.order_number = %s
        """,
            (session_path, date, order_number),
        )

        tune_info = cur.fetchone()
        if not tune_info:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found"})

        (
            tune_name,
            continues_set,
            session_instance_id,
            tune_id,
            session_instance_tune_id,
        ) = tune_info

        # Save to history before making changes
        save_to_history(
            cur, "session_instance_tune", "DELETE", session_instance_tune_id
        )

        # If this tune starts a set (continues_set = False) and there's a next tune,
        # update the next tune to start the set
        if not continues_set:
            # Get the next tune's ID for history
            cur.execute(
                """
                SELECT session_instance_tune_id
                FROM session_instance_tune
                WHERE session_instance_id = %s AND order_number = %s
            """,
                (session_instance_id, order_number + 1),
            )
            next_tune_result = cur.fetchone()

            if next_tune_result:
                next_tune_id = next_tune_result[0]
                save_to_history(cur, "session_instance_tune", "UPDATE", next_tune_id)

            cur.execute(
                """
                UPDATE session_instance_tune
                SET continues_set = FALSE
                WHERE session_instance_id = %s
                AND order_number = %s
            """,
                (session_instance_id, order_number + 1),
            )

        # Delete the tune by order number (works for both tune_id and name-based records)
        cur.execute(
            """
            DELETE FROM session_instance_tune
            WHERE session_instance_id = %s
            AND order_number = %s
        """,
            (session_instance_id, order_number),
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f"{tune_name} deleted from position {order_number} in the set.",
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Failed to delete tune: {str(e)}"}
        )


def link_tune_ajax(session_path, date):
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    tune_input = request.json.get("tune_id", "").strip()
    tune_name = normalize_apostrophes(request.json.get("tune_name", "").strip())
    order_number = request.json.get("order_number")

    if not tune_input or not tune_name or order_number is None:
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

        # Get session instance ID
        cur.execute(
            """
            SELECT session_instance_id FROM session_instance
            WHERE session_id = %s AND date = %s
        """,
            (session_id, date),
        )
        session_instance_result = cur.fetchone()
        if not session_instance_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id = session_instance_result[0]

        # Check if tune_id is already in session_tune for this session
        cur.execute(
            """
            SELECT tune_id FROM session_tune
            WHERE session_id = %s AND tune_id = %s
        """,
            (session_id, tune_id),
        )
        session_tune_exists = cur.fetchone()

        if session_tune_exists:
            # Get the session_instance_tune_id for history
            cur.execute(
                """
                SELECT session_instance_tune_id
                FROM session_instance_tune
                WHERE session_instance_id = %s AND order_number = %s
            """,
                (session_instance_id, order_number),
            )
            sit_result = cur.fetchone()

            if sit_result:
                sit_id = sit_result[0]
                save_to_history(cur, "session_instance_tune", "UPDATE", sit_id)

            # Tune already in session_tune, just update session_instance_tune
            # Use setting_id as setting_override if provided
            cur.execute(
                """
                UPDATE session_instance_tune
                SET tune_id = %s, name = %s, setting_override = %s
                WHERE session_instance_id = %s AND order_number = %s
            """,
                (tune_id, tune_name, setting_id, session_instance_id, order_number),
            )

            setting_msg = f" with setting #{setting_id}" if setting_id else ""
            message = f'Linked "{tune_name}" to existing tune in session{setting_msg}'
        else:
            # Check if tune exists in tune table
            cur.execute("SELECT name FROM tune WHERE tune_id = %s", (tune_id,))
            tune_exists = cur.fetchone()

            if tune_exists:
                # Add to session_tune with alias and setting_id
                cur.execute(
                    """
                    INSERT INTO session_tune (session_id, tune_id, alias, setting_id)
                    VALUES (%s, %s, %s, %s)
                """,
                    (session_id, tune_id, tune_name, setting_id),
                )

                # Save the newly inserted record to history
                save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id))

                # Get the session_instance_tune_id for history before update
                cur.execute(
                    """
                    SELECT session_instance_tune_id
                    FROM session_instance_tune
                    WHERE session_instance_id = %s AND order_number = %s
                """,
                    (session_instance_id, order_number),
                )
                sit_result = cur.fetchone()

                if sit_result:
                    sit_id = sit_result[0]
                    save_to_history(cur, "session_instance_tune", "UPDATE", sit_id)

                # Update session_instance_tune
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET tune_id = %s, name = NULL
                    WHERE session_instance_id = %s AND order_number = %s
                """,
                    (tune_id, session_instance_id, order_number),
                )

                setting_msg = f" with setting #{setting_id}" if setting_id else ""
                message = f'Added "{tune_name}" to session and linked{setting_msg}'
            else:
                # Tune doesn't exist in our database, fetch from thesession.org
                try:
                    # Fetch data from thesession.org API
                    api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
                    response = requests.get(api_url, timeout=10)

                    if response.status_code == 404:
                        cur.close()
                        conn.close()
                        return jsonify(
                            {
                                "success": False,
                                "message": f"Tune #{tune_id} not found on thesession.org",
                            }
                        )
                    elif response.status_code != 200:
                        cur.close()
                        conn.close()
                        return jsonify(
                            {
                                "success": False,
                                "message": f"Failed to fetch tune data from thesession.org (status: {response.status_code})",
                            }
                        )

                    data = response.json()

                    # Extract required fields
                    if "name" not in data or "type" not in data:
                        cur.close()
                        conn.close()
                        return jsonify(
                            {
                                "success": False,
                                "message": "Invalid tune data received from thesession.org",
                            }
                        )

                    tune_name_from_api = data["name"]
                    tune_type = data["type"].title()  # Convert to title case
                    tunebook_count = data.get(
                        "tunebooks", 0
                    )  # Default to 0 if not present

                    # Insert new tune into tune table
                    cur.execute(
                        """
                        INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date)
                        VALUES (%s, %s, %s, %s, CURRENT_DATE)
                    """,
                        (tune_id, tune_name_from_api, tune_type, tunebook_count),
                    )

                    # Save the newly inserted tune to history
                    save_to_history(cur, "tune", "INSERT", tune_id)

                    # Determine if we need to use an alias
                    alias = tune_name if tune_name != tune_name_from_api else None

                    # Add to session_tune with alias and setting_id
                    cur.execute(
                        """
                        INSERT INTO session_tune (session_id, tune_id, alias, setting_id)
                        VALUES (%s, %s, %s, %s)
                    """,
                        (session_id, tune_id, alias, setting_id),
                    )

                    # Save the newly inserted session_tune to history
                    save_to_history(
                        cur, "session_tune", "INSERT", (session_id, tune_id)
                    )

                    # Update session_instance_tune
                    cur.execute(
                        """
                        UPDATE session_instance_tune
                        SET tune_id = %s, name = NULL
                        WHERE session_instance_id = %s AND order_number = %s
                    """,
                        (tune_id, session_instance_id, order_number),
                    )

                    setting_msg = f" with setting #{setting_id}" if setting_id else ""
                    message = f'Fetched "{tune_name_from_api}" from thesession.org and added to session{setting_msg}'

                except requests.exceptions.Timeout:
                    cur.close()
                    conn.close()
                    return jsonify(
                        {
                            "success": False,
                            "message": "Timeout connecting to thesession.org",
                        }
                    )
                except requests.exceptions.RequestException as e:
                    cur.close()
                    conn.close()
                    return jsonify(
                        {
                            "success": False,
                            "message": f"Error connecting to thesession.org: {str(e)}",
                        }
                    )
                except Exception as e:
                    cur.close()
                    conn.close()
                    return jsonify(
                        {
                            "success": False,
                            "message": f"Error processing tune data: {str(e)}",
                        }
                    )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": message})

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to link tune: {str(e)}"})


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
            return jsonify({"success": False, "message": "Session instance not found"})

        session_instance_id = session_instance[0]

        # Get tunes played in this session instance
        cur.execute(
            """
            SELECT
                sit.order_number,
                sit.continues_set,
                sit.tune_id,
                COALESCE(sit.name, st.alias, t.name) AS tune_name,
                COALESCE(sit.setting_override, st.setting_id) AS setting,
                t.tune_type
            FROM session_instance_tune sit
            LEFT JOIN tune t ON sit.tune_id = t.tune_id
            LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                SELECT si2.session_id
                FROM session_instance si2
                WHERE si2.session_instance_id = %s
            )
            WHERE sit.session_instance_id = %s
            ORDER BY sit.order_number
        """,
            (session_instance_id, session_instance_id),
        )

        tunes = cur.fetchall()
        cur.close()
        conn.close()

        # Group tunes into sets
        sets = []
        current_set = []
        for tune in tunes:
            if (
                not tune[1] and current_set
            ):  # continues_set is False and we have a current set
                sets.append(current_set)
                current_set = []
            current_set.append(tune)
        if current_set:
            sets.append(current_set)

        return jsonify({"success": True, "tune_sets": sets})

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to get tunes: {str(e)}"})


def move_set_ajax(session_path, date):
    data = request.get_json()
    order_number = data.get("order_number")
    direction = data.get("direction")  # 'up' or 'down'

    if not order_number or not direction or direction not in ["up", "down"]:
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

        # Get all tunes ordered by order_number
        cur.execute(
            """
            SELECT order_number, continues_set, session_instance_tune_id
            FROM session_instance_tune
            WHERE session_instance_id = %s
            ORDER BY order_number
        """,
            (session_instance_id,),
        )

        all_tunes = cur.fetchall()
        if not all_tunes:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "No tunes found"})

        # Find the tune and its set
        target_tune_index = next(
            (i for i, tune in enumerate(all_tunes) if tune[0] == order_number), -1
        )
        if target_tune_index == -1:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found"})

        # Group tunes into sets to identify set boundaries
        sets = []
        current_set = []
        for tune in all_tunes:
            if (
                not tune[1] and current_set
            ):  # continues_set is False and we have a current set
                sets.append(current_set)
                current_set = []
            current_set.append(tune)
        if current_set:
            sets.append(current_set)

        # Find which set the target tune belongs to
        target_set_index = -1
        for set_index, tune_set in enumerate(sets):
            if any(tune[0] == order_number for tune in tune_set):
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

        # Save to history before making changes
        for tune_set in sets:
            for tune in tune_set:
                save_to_history(
                    cur, "session_instance_tune", "UPDATE", tune[2], "move_set"
                )

        # Perform the move
        target_set = sets[target_set_index]

        if direction == "up":
            # Move set up - swap with previous set
            prev_set = sets[target_set_index - 1]

            # Get the order numbers where each set should go
            prev_set_start_order = prev_set[0][0]
            target_set_start_order = target_set[0][0]

            # Update order numbers - target set goes where prev set was
            for i, tune in enumerate(target_set):
                new_order = prev_set_start_order + i
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET order_number = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_order, tune[2]),
                )

            # Previous set goes after target set
            for i, tune in enumerate(prev_set):
                new_order = prev_set_start_order + len(target_set) + i
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET order_number = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_order, tune[2]),
                )

        else:  # direction == 'down'
            # Move set down - swap with next set
            next_set = sets[target_set_index + 1]

            # Get the order numbers where each set should go
            target_set_start_order = target_set[0][0]
            # next_set_start_order = next_set[0][0]

            # Next set goes where target set was
            for i, tune in enumerate(next_set):
                new_order = target_set_start_order + i
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET order_number = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_order, tune[2]),
                )

            # Target set goes after next set
            for i, tune in enumerate(target_set):
                new_order = target_set_start_order + len(next_set) + i
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET order_number = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_order, tune[2]),
                )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"success": True, "message": f"Set moved {direction} successfully"}
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to move set: {str(e)}"})


def move_tune_ajax(session_path, date):
    data = request.get_json()
    order_number = data.get("order_number")
    direction = data.get("direction")  # 'left' or 'right'

    if not order_number or not direction or direction not in ["left", "right"]:
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

        # Get tune info and adjacent tunes
        cur.execute(
            """
            SELECT order_number, continues_set, session_instance_tune_id
            FROM session_instance_tune
            WHERE session_instance_id = %s
            ORDER BY order_number
        """,
            (session_instance_id,),
        )

        all_tunes = cur.fetchall()

        # Find the target tune
        target_tune_index = next(
            (i for i, tune in enumerate(all_tunes) if tune[0] == order_number), -1
        )
        if target_tune_index == -1:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found"})

        target_tune = all_tunes[target_tune_index]

        if direction == "left":
            # Move tune left within its set
            if target_tune_index == 0:
                cur.close()
                conn.close()
                return jsonify(
                    {"success": False, "message": "Cannot move first tune left"}
                )

            prev_tune = all_tunes[target_tune_index - 1]

            # Check if previous tune is in the same set (continues_set = True for target or prev is first tune)
            if (
                not target_tune[1] and prev_tune[1]
            ):  # target starts set, prev continues set - different sets
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "message": "Cannot move tune left across set boundary",
                    }
                )

            # Save to history
            save_to_history(
                cur, "session_instance_tune", "UPDATE", target_tune[2], "move_tune"
            )
            save_to_history(
                cur, "session_instance_tune", "UPDATE", prev_tune[2], "move_tune"
            )

            # Swap order numbers
            cur.execute(
                """
                UPDATE session_instance_tune
                SET order_number = %s
                WHERE session_instance_tune_id = %s
            """,
                (prev_tune[0], target_tune[2]),
            )

            cur.execute(
                """
                UPDATE session_instance_tune
                SET order_number = %s
                WHERE session_instance_tune_id = %s
            """,
                (target_tune[0], prev_tune[2]),
            )

            # If target tune was starting a set and prev was continuing, swap continues_set values
            if not target_tune[1] and prev_tune[1]:
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET continues_set = FALSE
                    WHERE session_instance_tune_id = %s
                """,
                    (prev_tune[2]),
                )

                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET continues_set = TRUE
                    WHERE session_instance_tune_id = %s
                """,
                    (target_tune[2]),
                )

        else:  # direction == 'right'
            # Move tune right within its set
            if target_tune_index == len(all_tunes) - 1:
                cur.close()
                conn.close()
                return jsonify(
                    {"success": False, "message": "Cannot move last tune right"}
                )

            next_tune = all_tunes[target_tune_index + 1]

            # Check if next tune is in the same set
            if not next_tune[1]:  # next tune starts a new set
                cur.close()
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "message": "Cannot move tune right across set boundary",
                    }
                )

            # Save to history
            save_to_history(
                cur, "session_instance_tune", "UPDATE", target_tune[2], "move_tune"
            )
            save_to_history(
                cur, "session_instance_tune", "UPDATE", next_tune[2], "move_tune"
            )

            # Swap order numbers
            cur.execute(
                """
                UPDATE session_instance_tune
                SET order_number = %s
                WHERE session_instance_tune_id = %s
            """,
                (next_tune[0], target_tune[2]),
            )

            cur.execute(
                """
                UPDATE session_instance_tune
                SET order_number = %s
                WHERE session_instance_tune_id = %s
            """,
                (target_tune[0], next_tune[2]),
            )

            # If target tune was starting a set, make next tune start the set
            if not target_tune[1]:
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET continues_set = FALSE
                    WHERE session_instance_tune_id = %s
                """,
                    (next_tune[2]),
                )

                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET continues_set = TRUE
                    WHERE session_instance_tune_id = %s
                """,
                    (target_tune[2]),
                )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify(
            {"success": True, "message": f"Tune moved {direction} successfully"}
        )

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to move tune: {str(e)}"})


def add_tunes_to_set_ajax(session_path, date):
    data = request.get_json()
    tune_names_input = data.get("tune_names", "").strip()
    reference_order_number = data.get("reference_order_number")

    if not tune_names_input or reference_order_number is None:
        return jsonify({"success": False, "message": "Missing required parameters"})

    # Parse comma-separated tune names
    tune_names = [
        normalize_apostrophes(name.strip())
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
            cur.execute(
                "SELECT insert_session_instance_tune(%s, %s, %s, %s, %s, %s)",
                (
                    session_id,
                    date,
                    tune_id,
                    reference_order_number,
                    final_name if tune_id is None else None,
                    False,
                ),
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


def edit_tune_ajax(session_path, date):
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    order_number = request.json.get("order_number")
    new_name = normalize_apostrophes(request.json.get("new_name", "").strip())
    original_name = request.json.get("original_name", "").strip()
    tune_id = request.json.get("tune_id")
    setting_id = request.json.get("setting_id")
    key_override = (
        request.json.get("key_override", "").strip()
        if request.json.get("key_override")
        else None
    )

    if order_number is None or not new_name:
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
            WHERE si.session_id = %s AND si.date = %s AND sit.order_number = %s
        """,
            (session_id, date, order_number),
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
            cur, "session_instance_tune", "UPDATE", session_instance_tune_id
        )

        if current_tune_id:
            # This is a linked tune - update as name override or potentially update alias
            if tune_id and current_tune_id == int(tune_id):
                # Same tune - update name override and setting override
                cur.execute(
                    """
                    UPDATE session_instance_tune
                    SET name = %s, setting_override = %s, key_override = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (
                        new_name if new_name != original_name else None,
                        setting_id,
                        key_override,
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
                    SET tune_id = NULL, name = %s, setting_override = NULL, key_override = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_name, key_override, session_instance_tune_id),
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
                    SET tune_id = %s, name = NULL, key_override = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (tune_id_match, key_override, session_instance_tune_id),
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
                    SET name = %s, key_override = %s
                    WHERE session_instance_tune_id = %s
                """,
                    (new_name, key_override, session_instance_tune_id),
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
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"error": "Session not found"}), 404

        session_id = session_result[0]

        # Get session players with person details and attendance stats
        cur.execute(
            """
            SELECT
                sp.session_person_id,
                sp.person_id,
                p.first_name,
                p.last_name,
                p.email,
                sp.is_regular,
                sp.is_admin,
                sp.gets_email_reminder,
                sp.gets_email_followup,
                u.username,
                u.is_system_admin,
                COALESCE(person_session_count.attendance_count, 0) as attendance_count,
                person_session_count.last_attended
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
                WHERE si.session_id = %s AND sip.attended = true
                GROUP BY sip.person_id, si.session_id
            ) person_session_count ON p.person_id = person_session_count.person_id
            WHERE sp.session_id = %s
            ORDER BY sp.is_regular DESC, p.last_name, p.first_name
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
                    "is_regular": row[5],
                    "is_admin": row[6],
                    "gets_email_reminder": row[7],
                    "gets_email_followup": row[8],
                    "username": row[9] or "",
                    "is_system_admin": row[10] or False,
                    "attendance_count": row[11] or 0,
                    "last_attended": row[12].isoformat() if row[12] else None,
                }
            )

        cur.close()
        conn.close()

        return jsonify({"players": players})

    except Exception as e:
        return jsonify({"error": f"Failed to get session players: {str(e)}"}), 500


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
            LEFT JOIN session_instance_person sip ON si.session_instance_id = sip.session_instance_id
                AND sip.attended = true
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
                sip.attended
            FROM session_instance_person sip
            JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
            JOIN session s ON si.session_id = s.session_id
            WHERE sip.person_id = %s
            ORDER BY si.date DESC
        """,
            (person_id,),
        )

        attendance = []
        for row in cur.fetchall():
            session_name, instance_date, attended = row
            attendance.append(
                {
                    "session_name": session_name,
                    "instance_date": instance_date.strftime("%Y-%m-%d"),
                    "attended": attended,
                }
            )

        cur.close()
        conn.close()

        return jsonify({"success": True, "attendance": attendance})

    except Exception as e:
        return (
            jsonify(
                {"success": False, "error": f"Failed to get attendance data: {str(e)}"}
            ),
            500,
        )


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

        # Check if username exists, excluding current user if provided
        if current_user_id:
            cur.execute(
                "SELECT user_id FROM user_account WHERE username = %s AND user_id != %s",
                (username, current_user_id),
            )
        else:
            cur.execute(
                "SELECT user_id FROM user_account WHERE username = %s", (username,)
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


def update_person_details(person_id):
    """Update person and user details"""
    try:
        data = request.get_json()

        if not person_id:
            return jsonify({"success": False, "message": "Person ID is required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Update person details
        person_data = data.get("person", {})
        if person_data:
            save_to_history(cur, "person", "UPDATE", person_id, "admin_edit")
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

            # Check if username is being changed and is available
            username = user_data.get("username")
            if username:
                cur.execute(
                    "SELECT user_id FROM user_account WHERE username = %s AND user_id != %s",
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

            save_to_history(cur, "user_account", "UPDATE", user_id, "admin_edit")
            cur.execute(
                """
                UPDATE user_account
                SET username = %s, user_email = %s, is_active = %s, timezone = %s, last_modified_date = %s
                WHERE user_id = %s
            """,
                (
                    username,
                    user_data.get("user_email") or None,
                    user_data.get("is_active", True),
                    user_data.get("timezone") or "UTC",
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


def add_person_to_session():
    """Add a person to a session and send notification email"""
    try:
        data = request.get_json()
        person_id = data.get("person_id")
        session_id = data.get("session_id")
        role = data.get("role", "attendee")  # 'regular' or 'attendee'

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
            "SELECT first_name, last_name, email FROM person WHERE person_id = %s",
            (person_id,),
        )
        person_row = cur.fetchone()
        if not person_row:
            return jsonify({"success": False, "message": "Person not found"}), 404

        person_first_name, person_last_name, person_email = person_row
        person_name = f"{person_first_name} {person_last_name}"

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

        # Add person to session
        is_regular = role == "regular"
        is_admin = False

        save_to_history(
            cur,
            "session_person",
            "INSERT",
            None,
            f"admin_add_person:{person_id}:{session_id}",
        )
        cur.execute(
            """
            INSERT INTO session_person (person_id, session_id, is_regular, is_admin)
            VALUES (%s, %s, %s, %s)
        """,
            (person_id, session_id, is_regular, is_admin),
        )

        # Get session admins for email notification
        cur.execute(
            """
            SELECT p.first_name, p.last_name, p.email
            FROM person p
            JOIN session_person sp ON p.person_id = sp.person_id
            WHERE sp.session_id = %s AND sp.is_admin = TRUE AND p.email IS NOT NULL
        """,
            (session_id,),
        )

        session_admins = cur.fetchall()

        # If no session admins, get system admins
        if not session_admins:
            cur.execute(
                """
                SELECT p.first_name, p.last_name, p.email
                FROM person p
                JOIN user_account ua ON p.person_id = ua.person_id
                WHERE ua.is_system_admin = TRUE AND p.email IS NOT NULL
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

{person_name} has been added to the session "{session_name}" in {session_location} as a {role}.

Person Details:
- Name: {person_name}
- Email: {person_email or 'Not provided'}

You can review and modify this person's role in the session admin interface: https://ceol.io/admin/sessions/{session_path}/players

Best regards,
The Ceol.io Session Management System"""

                try:
                    send_email_via_sendgrid(admin_email, subject, body)
                except Exception as email_error:
                    print(f"Failed to send email to {admin_email}: {email_error}")

        return jsonify(
            {
                "success": True,
                "message": f"{person_name} has been added to {session_name} as a {role}",
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


def validate_thesession_user():
    """Validate and get user info from thesession.org"""
    try:
        data = request.get_json()
        user_input = data.get("user_input", "").strip()

        # Extract ID from URL or use direct ID
        thesession_id = None
        if user_input.startswith("https://thesession.org/members/"):
            try:
                thesession_id = int(user_input.split("/members/")[-1])
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
            save_to_history(cur, "person", "INSERT", None, "admin_create_person")
            cur.execute(
                """
                INSERT INTO person (first_name, last_name, email, sms_number, city, state, country, thesession_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                ),
            )

            result = cur.fetchone()
            if not result:
                return jsonify({"success": False, "message": "Failed to create person"})
            person_id = result[0]

            # Add to session if specified
            if session_id:
                save_to_history(
                    cur,
                    "session_person",
                    "INSERT",
                    None,
                    f"admin_create_person_add_session:{person_id}:{session_id}",
                )
                cur.execute(
                    """
                    INSERT INTO session_person (person_id, session_id, is_regular, is_admin)
                    VALUES (%s, %s, %s, %s)
                """,
                    (person_id, session_id, False, False),
                )  # Default to attendee, not admin

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


@login_required
def update_session_player_regular_status(session_path, person_id):
    """Update the regular status for a person in a specific session"""
    # Check if user is system admin
    if not session.get("is_system_admin"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        is_regular = data.get("is_regular", False)

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID first
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            return jsonify({"success": False, "error": "Session not found"}), 404

        session_id = session_result[0]

        # Update the regular status
        cur.execute(
            """
            UPDATE session_person
            SET is_regular = %s
            WHERE session_id = %s AND person_id = %s
        """,
            (is_regular, session_id, person_id),
        )

        if cur.rowcount == 0:
            return (
                jsonify(
                    {"success": False, "error": "Person not found in this session"}
                ),
                404,
            )

        # Save to history
        save_to_history(
            cur,
            "session_person",
            "UPDATE",
            None,
            f"admin_update_regular_status:{person_id}:{session_id}:{is_regular}",
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@login_required
def terminate_session(session_path):
    """Set the termination date for a session"""
    # Check if user is system admin
    if not session.get("is_system_admin"):
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
            None,
            f"admin_terminate_session:{session_id}:{termination_date}",
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@login_required
def reactivate_session(session_path):
    """Clear the termination date for a session to reactivate it"""
    # Check if user is system admin
    if not session.get("is_system_admin"):
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
            cur, "session", "UPDATE", None, f"admin_reactivate_session:{session_id}"
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def match_tune_ajax(session_path, date):
    """
    Match a tune name against the database without saving anything.
    Used by the beta tune pill editor for auto-matching typed text.
    Returns either a single exact match or up to 5 possible matches with wildcard search.
    """
    if not request.json:
        return jsonify({"success": False, "message": "No JSON data provided"})
    tune_name = normalize_apostrophes(request.json.get("tune_name", "").strip())
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

        session_id = session_result[0]

        # First, try to find an exact match using the existing function
        tune_id, final_name, error_message = find_matching_tune(
            cur, session_id, tune_name
        )

        # If we found exactly one match, return it
        if tune_id and not error_message:
            # Get the tune type for the matched tune
            cur.execute("SELECT tune_type FROM tune WHERE tune_id = %s", (tune_id,))
            tune_type_result = cur.fetchone()
            tune_type = tune_type_result[0] if tune_type_result else None

            cur.close()
            conn.close()

            return jsonify(
                {
                    "success": True,
                    "matched": True,
                    "exact_match": True,
                    "results": [
                        {
                            "tune_id": tune_id,
                            "tune_name": final_name,
                            "tune_type": tune_type,
                        }
                    ],
                }
            )

        # If no exact match or multiple matches, do wildcard search
        # Build the wildcard query with proper ordering
        wildcard_pattern = f"%{tune_name.lower()}%"

        # Debug logging
        print(
            f"Wildcard search for '{tune_name}' with previous_tune_type='{previous_tune_type}'"
        )

        # Query with all the ordering criteria
        query = """
            SELECT
                t.tune_id,
                COALESCE(st.alias, t.name) as display_name,
                t.tune_type,
                CASE WHEN t.tune_type = %s THEN 0 ELSE 1 END as preferred_tune_type,
                playcounts.plays
            FROM tune t
            LEFT OUTER JOIN session_tune st
                ON t.tune_id = st.tune_id AND st.session_id = %s
            LEFT OUTER JOIN (
                SELECT sit.tune_id, COUNT(*) as plays
                FROM session_instance si
                INNER JOIN session_instance_tune sit
                    ON si.session_instance_id = sit.session_instance_id
                WHERE si.session_id = %s
                GROUP BY sit.tune_id
            ) playcounts
                ON t.tune_id = playcounts.tune_id
            WHERE LOWER(COALESCE(st.alias, t.name)) LIKE %s
            ORDER BY
                preferred_tune_type ASC,
                playcounts.plays DESC NULLS LAST,
                t.tunebook_count_cached DESC NULLS LAST,
                LOWER(COALESCE(st.alias, t.name)) ASC
            LIMIT 5
        """

        cur.execute(
            query, (previous_tune_type, session_id, session_id, wildcard_pattern)
        )
        matches = cur.fetchall()

        # Debug logging of results
        print(f"Found {len(matches)} matches:")
        for match in matches:
            print(
                f"  - {match[1]} ({match[2]}) - preferred={match[3]}, plays={match[4]}"
            )

        cur.close()
        conn.close()

        if not matches:
            # No matches found at all
            return jsonify(
                {"success": True, "matched": False, "exact_match": False, "results": []}
            )

        # Format the results
        results = []
        for match in matches:
            results.append(
                {"tune_id": match[0], "tune_name": match[1], "tune_type": match[2]}
            )

        return jsonify(
            {
                "success": True,
                "matched": len(results)
                == 1,  # Only considered "matched" if exactly one result
                "exact_match": False,
                "results": results,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_login_required
def test_match_tune_ajax(session_path, date):
    """
    Test endpoint for the enhanced match_tune functionality.
    Accepts GET requests with query parameters for easier testing.
    """
    tune_name = normalize_apostrophes(request.args.get("tune_name", "").strip())
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


@api_login_required
def save_session_instance_tunes_ajax(session_path, date):
    """
    Save the complete tune list for a session instance from the beta page.
    Minimizes database modifications by only updating/inserting/deleting where necessary.
    """
    try:
        data = request.get_json()
        tune_sets = data.get("tune_sets", [])

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id and session_instance_id
        cur.execute(
            """
            SELECT s.session_id, si.session_instance_id
            FROM session s
            JOIN session_instance si ON s.session_id = si.session_id
            WHERE s.path = %s AND si.date = %s
        """,
            (session_path, date),
        )

        result = cur.fetchone()
        if not result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session instance not found"})

        session_id, session_instance_id = result

        # Get all existing tunes for this session instance
        cur.execute(
            """
            SELECT session_instance_tune_id, order_number, tune_id, name, continues_set
            FROM session_instance_tune
            WHERE session_instance_id = %s
            ORDER BY order_number
        """,
            (session_instance_id,),
        )

        existing_tunes = cur.fetchall()
        existing_dict = {row[1]: row for row in existing_tunes}  # Dict by order_number

        # Build new tune list from the sets
        new_tunes = []
        sequence_num = 1

        for set_idx, tune_set in enumerate(tune_sets):
            for tune_idx, tune_data in enumerate(tune_set):
                # Determine continues_set: false for first tune in set, true otherwise
                continues_set = tune_idx > 0

                # Extract tune data
                tune_id = tune_data.get("tune_id")
                tune_name = tune_data.get("name") or tune_data.get("tune_name")

                # Ensure we have either tune_id or name (required by database constraint)
                if not tune_id and not tune_name:
                    # Skip empty pills or provide a default name
                    tune_name = "Unknown tune"

                # If this is a matched tune (has tune_id), we typically don't store the name
                # But keep it if there's no tune_id
                if tune_id:
                    tune_name = None

                new_tunes.append(
                    {
                        "order_number": sequence_num,
                        "tune_id": tune_id,
                        "name": tune_name,
                        "continues_set": continues_set,
                    }
                )
                sequence_num += 1

        # Begin transaction
        cur.execute("BEGIN")

        try:
            modifications = 0

            # Process updates/inserts
            for new_tune in new_tunes:
                if not new_tune:
                    continue
                order_num = new_tune["order_number"]

                if order_num in existing_dict:
                    # Check if update is needed
                    existing = existing_dict[order_num]
                    if (
                        existing[2] != new_tune["tune_id"]
                        or existing[3] != new_tune["name"]
                        or existing[4] != new_tune["continues_set"]
                    ):
                        # Update existing record
                        save_to_history(
                            cur, "session_instance_tune", "UPDATE", existing[0]
                        )

                        cur.execute(
                            """
                            UPDATE session_instance_tune
                            SET tune_id = %s, name = %s, continues_set = %s, last_modified_date = NOW()
                            WHERE session_instance_tune_id = %s
                        """,
                            (
                                new_tune["tune_id"],
                                new_tune["name"],
                                new_tune["continues_set"],
                                existing[0],
                            ),
                        )
                        modifications += 1
                else:
                    # Insert new record
                    cur.execute(
                        """
                        INSERT INTO session_instance_tune
                        (session_instance_id, order_number, tune_id, name, continues_set, created_date, last_modified_date)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                        RETURNING session_instance_tune_id
                    """,
                        (
                            session_instance_id,
                            order_num,
                            new_tune["tune_id"],
                            new_tune["name"],
                            new_tune["continues_set"],
                        ),
                    )

                    result = cur.fetchone()
                    if not result:
                        continue
                    new_id = result[0]
                    save_to_history(cur, "session_instance_tune", "INSERT", new_id)
                    modifications += 1

            # Delete records that are beyond the new length
            max_new_order = len(new_tunes)
            for existing in existing_tunes:
                if existing[1] > max_new_order:
                    save_to_history(cur, "session_instance_tune", "DELETE", existing[0])
                    cur.execute(
                        """
                        DELETE FROM session_instance_tune
                        WHERE session_instance_tune_id = %s
                    """,
                        (existing[0],),
                    )
                    modifications += 1

            # Commit transaction
            cur.execute("COMMIT")

            cur.close()
            conn.close()

            return jsonify(
                {
                    "success": True,
                    "message": f"Session saved successfully ({modifications} modifications)",
                    "modifications": modifications,
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

        # Update user preference in database
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE user_account
            SET auto_save_tunes = %s,
                last_modified_date = NOW() AT TIME ZONE 'UTC'
            WHERE user_id = %s
        """,
            (auto_save, current_user.user_id),
        )

        save_to_history(cur, "user_account", "UPDATE", current_user.user_id)

        cur.close()
        conn.commit()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": "Auto-save preference updated",
                "auto_save": auto_save,
            }
        )

    except Exception as e:
        if "conn" in locals():
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500
