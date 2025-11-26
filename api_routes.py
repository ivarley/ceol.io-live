from flask import request, jsonify, session, send_file
from collections import Counter
import requests
import re
import os
import base64
import psycopg2
from flask_login import login_required
from database import (
    get_db_connection,
    save_to_history,
    find_matching_tune,
    normalize_apostrophes,
    check_in_person as db_check_in_person,
)
from email_utils import send_email_via_sendgrid
from timezone_utils import now_utc, format_datetime_with_timezone, utc_to_local
from flask_login import current_user
from functools import wraps
import qrcode
from io import BytesIO
from recurrence_utils import validate_recurrence_json, to_human_readable


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


@login_required
def update_session_ajax(session_path):
    """Update session details from admin page"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})

        # Validate recurrence if provided
        if "recurrence" in data and data["recurrence"]:
            is_valid, error_msg = validate_recurrence_json(data["recurrence"])
            if not is_valid:
                return jsonify({
                    "success": False,
                    "error": f"Invalid recurrence pattern: {error_msg}"
                })

        conn = get_db_connection()
        cur = conn.cursor()

        # Get current session details for history tracking
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Session not found"})

        # Save to history before making changes
        session_id = session_result[0]
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


@login_required
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


@login_required
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

        changed_by = current_user.username if hasattr(current_user, 'username') else 'system'

        if existing_setting:
            # Save to history before updating
            save_to_history(cur, 'tune_setting', 'UPDATE', setting_id, changed_by=changed_by)

            # Update existing setting
            cur.execute("""
                UPDATE tune_setting
                SET key = %s, abc = %s, incipit_abc = %s, cache_updated_date = (NOW() AT TIME ZONE 'UTC'),
                    last_modified_date = (NOW() AT TIME ZONE 'UTC')
                WHERE setting_id = %s
            """, (key, abc, incipit_abc, setting_id))
            action = "updated"
        else:
            # Insert new setting
            cur.execute("""
                INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc, cache_updated_date)
                VALUES (%s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
            """, (setting_id, tune_id, key, abc, incipit_abc))

            # Log INSERT to history (manually since record was just created)
            cur.execute("""
                INSERT INTO tune_setting_history
                (setting_id, operation, changed_by, tune_id, key, abc, image, incipit_abc,
                 incipit_image, cache_updated_date, created_date, last_modified_date)
                SELECT setting_id, %s, %s, tune_id, key, abc, image, incipit_abc,
                       incipit_image, cache_updated_date, created_date, last_modified_date
                FROM tune_setting WHERE setting_id = %s
            """, ('INSERT', changed_by, setting_id))
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


def get_session_tune_detail(session_path, tune_id):
    """Get detailed information about a tune in the context of a session"""
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
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Tune not found"})

        tune_name, tune_type, tunebook_count, tunebook_count_cached_date = tune_info

        # Get session-specific tune info
        cur.execute(
            """
            SELECT alias, setting_id, key
            FROM session_tune
            WHERE session_id = %s AND tune_id = %s
        """,
            (session_id, tune_id),
        )
        session_tune_info = cur.fetchone()

        alias = None
        setting_id = None
        key = None

        if session_tune_info:
            alias, setting_id, key = session_tune_info

        # Get ABC notation from tune_setting
        # If setting_id is specified, use that; otherwise, use the first setting for this tune
        abc_notation = None
        incipit_abc = None
        abc_image = None
        incipit_image = None
        if setting_id:
            cur.execute(
                "SELECT abc, incipit_abc, image, incipit_image FROM tune_setting WHERE setting_id = %s",
                (setting_id,)
            )
        else:
            # Fall back to the first setting for this tune (ordered by setting_id)
            cur.execute(
                """SELECT abc, incipit_abc, image, incipit_image
                   FROM tune_setting
                   WHERE tune_id = %s
                   ORDER BY setting_id ASC
                   LIMIT 1""",
                (tune_id,)
            )
        abc_result = cur.fetchone()
        if abc_result:
            abc_notation = abc_result[0]
            incipit_abc = abc_result[1]
            abc_image = abc_result[2]
            incipit_image = abc_result[3]

        # Get all aliases from session_tune_alias table
        cur.execute(
            """
            SELECT alias
            FROM session_tune_alias
            WHERE session_id = %s AND tune_id = %s
            ORDER BY created_date ASC
        """,
            (session_id, tune_id),
        )
        alias_rows = cur.fetchall()
        aliases = [row[0] for row in alias_rows]

        # Get play count for this session
        cur.execute(
            """
            SELECT COUNT(*)
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s
        """,
            (session_id, tune_id),
        )
        play_count_result = cur.fetchone()
        times_played = play_count_result[0] if play_count_result else 0

        # Get detailed play history
        cur.execute(
            """
            SELECT
                si.date,
                sit.order_number,
                sit.name,
                sit.key_override,
                sit.setting_override,
                si.session_instance_id
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s
            ORDER BY si.date DESC
        """,
            (session_id, tune_id),
        )
        play_instances_raw = cur.fetchall()
        play_instances = [
            {
                "date": row[0].isoformat() if row[0] else None,
                "position_in_set": row[1],
                "name_override": row[2],
                "key_override": row[3],
                "setting_id_override": row[4],
                "session_instance_id": row[5],
            }
            for row in play_instances_raw
        ]

        # Get person_tune status if user is logged in
        person_tune_status = None
        if current_user.is_authenticated:
            cur = conn.cursor()
            cur.execute(
                "SELECT person_id FROM user_account WHERE user_id = %s",
                (current_user.user_id,)
            )
            person_row = cur.fetchone()
            if person_row:
                person_id = person_row[0]
                cur.execute(
                    """
                    SELECT person_tune_id, learn_status, heard_count
                    FROM person_tune
                    WHERE person_id = %s AND tune_id = %s
                    """,
                    (person_id, tune_id)
                )
                tune_row = cur.fetchone()
                if tune_row:
                    person_tune_status = {
                        "on_list": True,
                        "person_tune_id": tune_row[0],
                        "learn_status": tune_row[1],
                        "heard_count": tune_row[2]
                    }
                else:
                    person_tune_status = {
                        "on_list": False,
                        "person_tune_id": None,
                        "learn_status": None,
                        "heard_count": None
                    }
            cur.close()

        # Get global play count (all sessions)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*)
            FROM session_instance_tune
            WHERE tune_id = %s
        """,
            (tune_id,),
        )
        global_play_result = cur.fetchone()
        global_play_count = global_play_result[0] if global_play_result else 0
        cur.close()

        conn.close()

        # Build response
        return jsonify(
            {
                "success": True,
                "session_tune": {
                    "tune_id": tune_id,
                    "tune_name": tune_name,
                    "tune_type": tune_type,
                    "alias": alias,
                    "aliases": aliases,
                    "setting_id": setting_id,
                    "key": key,
                    "abc": abc_notation,
                    "incipit_abc": incipit_abc,
                    "image": bytea_to_base64(abc_image),
                    "incipit_image": bytea_to_base64(incipit_image),
                    "tunebook_count": tunebook_count,
                    "tunebook_count_cached_date": (
                        tunebook_count_cached_date.isoformat()
                        if tunebook_count_cached_date
                        else None
                    ),
                    "times_played": times_played,
                    "global_play_count": global_play_count,
                    "play_instances": play_instances,
                    "person_tune_status": person_tune_status,
                },
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error retrieving tune details: {str(e)}"}
        )


@login_required
def update_session_tune_details(session_path, tune_id):
    """Update session-specific tune details (setting_id, key, alias, and aliases)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"})

        setting_id = data.get("setting_id", "").strip()
        key = data.get("key", "").strip()
        alias = data.get("alias")  # Single alias for session_tune table
        aliases_str = data.get("aliases", "").strip()  # Multiple aliases for session_tune_alias table

        # Parse setting_id - convert to int or None
        parsed_setting_id = None
        if setting_id:
            try:
                parsed_setting_id = int(setting_id)
            except ValueError:
                return jsonify(
                    {
                        "success": False,
                        "message": "Setting ID must be a number",
                    }
                )

        # Parse alias - convert empty string to None
        parsed_alias = alias.strip() if alias and alias.strip() else None

        # Parse aliases - split by comma and clean up
        new_aliases = []
        if aliases_str:
            new_aliases = [a.strip() for a in aliases_str.split(",") if a.strip()]

        # Convert empty strings to None for key
        parsed_key = key if key else None

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

        # Check if tune exists in session_tune
        cur.execute(
            "SELECT tune_id FROM session_tune WHERE session_id = %s AND tune_id = %s",
            (session_id, tune_id),
        )
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "message": "Tune not found in this session",
                }
            )

        # Save to history before making changes
        save_to_history(cur, "session_tune", "UPDATE", (session_id, tune_id))

        # Update session_tune with setting_id, key, and alias
        cur.execute(
            """
            UPDATE session_tune
            SET setting_id = %s, key = %s, alias = %s
            WHERE session_id = %s AND tune_id = %s
        """,
            (parsed_setting_id, parsed_key, parsed_alias, session_id, tune_id),
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
                INSERT INTO session_tune_alias (session_id, tune_id, alias)
                VALUES (%s, %s, %s)
                RETURNING session_tune_alias_id
            """,
                (session_id, tune_id, alias),
            )
            alias_id = cur.fetchone()[0]
            save_to_history(cur, "session_tune_alias", "INSERT", alias_id)

        # Remove old aliases
        for alias in aliases_to_remove:
            alias_id = existing_alias_map[alias]
            save_to_history(cur, "session_tune_alias", "DELETE", alias_id)
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


@login_required
def add_session_tune(session_path):
    """Add a tune to a session's session_tune table"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        tune_id = data.get("tune_id")
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

        # Check if tune exists in tune table
        cur.execute("SELECT tune_id FROM tune WHERE tune_id = %s", (tune_id,))
        if not cur.fetchone():
            # If new_tune data provided, insert it
            if data.get("new_tune"):
                new_tune_data = data.get("new_tune")
                cur.execute(
                    """
                    INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date)
                    VALUES (%s, %s, %s, %s, CURRENT_DATE)
                    ON CONFLICT (tune_id) DO NOTHING
                """,
                    (
                        new_tune_data.get("tune_id"),
                        new_tune_data.get("name"),
                        new_tune_data.get("tune_type"),
                        new_tune_data.get("tunebook_count", 0),
                    ),
                )
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

        # Insert into session_tune
        cur.execute(
            """
            INSERT INTO session_tune (session_id, tune_id, alias, setting_id, key)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (session_id, tune_id, alias, parsed_setting_id, key),
        )

        # Save to history
        save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Tune added to session successfully"}), 201

    except Exception as e:
        return jsonify({"success": False, "error": f"Error adding tune: {str(e)}"}), 500


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


@login_required
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


@login_required
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


@login_required
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
            INSERT INTO session_instance (session_id, date, start_time, end_time, location_override, is_cancelled, comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING session_instance_id
        """,
            (session_id, date, start_time, end_time, location_override, cancelled, comments),
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


@login_required
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


@login_required
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
        save_to_history(cur, "session_instance", "UPDATE", session_instance_id)

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


@login_required
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
            save_to_history(cur, "session_instance_person", "DELETE", person_record)

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


@login_required
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


@login_required
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


@login_required
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


@login_required
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


@login_required
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


@login_required
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


def get_session_people_list(session_path):
    """
    Get list of people in a session.

    GET /api/sessions/<session_path>/people

    Returns:
    {
        "success": true,
        "people": [
            {
                "person_id": int,
                "first_name": str,
                "last_name": str,
                "city": str or null,
                "state": str or null,
                "country": str or null,
                "thesession_user_id": int or null,
                "has_user_account": bool,
                "instruments": [str],
                "attendance_count": int
            }
        ]
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

        # Fetch people list
        cur.execute(
            """
            SELECT p.person_id, p.first_name, p.last_name, p.city, p.state, p.country, p.thesession_user_id,
                   CASE WHEN u.user_id IS NOT NULL THEN true ELSE false END as has_user_account,
                   COALESCE(
                       array_agg(DISTINCT pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                       '{}'::text[]
                   ) as instruments,
                   COUNT(DISTINCT sip.session_instance_person_id) FILTER (WHERE sip.attendance = 'yes' AND si.session_id = %s) as attendance_count,
                   sp.is_regular
            FROM session_person sp
            JOIN person p ON sp.person_id = p.person_id
            LEFT JOIN user_account u ON p.person_id = u.person_id
            LEFT JOIN person_instrument pi ON p.person_id = pi.person_id
            LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id
            LEFT JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
            WHERE sp.session_id = %s
            GROUP BY p.person_id, p.first_name, p.last_name, p.city, p.state, p.country, p.thesession_user_id, u.user_id, sp.is_regular
            ORDER BY p.first_name, p.last_name
            """,
            (session_id, session_id)
        )

        people_data = cur.fetchall()
        people = []

        for row in people_data:
            people.append({
                'person_id': row[0],
                'first_name': row[1],
                'last_name': row[2],
                'city': row[3],
                'state': row[4],
                'country': row[5],
                'thesession_user_id': row[6],
                'has_user_account': row[7],
                'instruments': row[8] if row[8] else [],
                'attendance_count': row[9] or 0,
                'is_regular': row[10] or False
            })

        cur.close()
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
    """
    Add a new person to a session from the People tab.

    POST /api/sessions/<session_path>/people/add

    Request body:
    {
        "first_name": str,
        "last_name": str,
        "instruments": [str],
        "thesession_user_id": int or null
    }

    Returns:
    {
        "success": true,
        "person_id": int,
        "message": str
    }
    """
    # Check authentication
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        instruments = data.get('instruments', [])
        thesession_user_id = data.get('thesession_user_id')
        is_regular = data.get('is_regular', False)

        # Validate required fields
        if not first_name or not last_name:
            return jsonify({"success": False, "message": "First name and last name are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID from path
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()

        if not session_result:
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id = session_result[0]

        # Verify current user is a member of this session (only members can add people)
        user_person_id = getattr(current_user, 'person_id', None)
        if not user_person_id:
            return jsonify({"success": False, "message": "User not linked to person"}), 403

        cur.execute(
            "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, user_person_id)
        )
        if not cur.fetchone():
            return jsonify({"success": False, "message": "Not a member of this session"}), 403

        # Check if person already exists (by name)
        cur.execute(
            "SELECT person_id FROM person WHERE LOWER(first_name) = LOWER(%s) AND LOWER(last_name) = LOWER(%s)",
            (first_name, last_name)
        )
        existing_person = cur.fetchone()

        if existing_person:
            person_id = existing_person[0]

            # Check if already in this session
            cur.execute(
                "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
                (session_id, person_id)
            )
            if cur.fetchone():
                return jsonify({"success": False, "message": f"{first_name} {last_name} is already in this session"}), 400

        else:
            # Create new person
            cur.execute(
                """
                INSERT INTO person (first_name, last_name, thesession_user_id)
                VALUES (%s, %s, %s)
                RETURNING person_id
                """,
                (first_name, last_name, thesession_user_id)
            )
            person_id = cur.fetchone()[0]

            # Add instruments
            if instruments:
                for instrument in instruments:
                    cur.execute(
                        """
                        INSERT INTO person_instrument (person_id, instrument)
                        VALUES (%s, %s)
                        ON CONFLICT (person_id, instrument) DO NOTHING
                        """,
                        (person_id, instrument)
                    )

        # Add person to session with specified is_regular value
        cur.execute(
            """
            INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
            VALUES (%s, %s, %s, false)
            """,
            (session_id, person_id, is_regular)
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "person_id": person_id,
            "message": f"{first_name} {last_name} added to session"
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to add person: {str(e)}"}), 500


def search_people_for_session(session_path):
    """
    Search for people to add to a session.
    Excludes people already in this session.

    GET /api/sessions/<session_path>/people/search?q=<query>

    Returns:
    {
        "success": true,
        "people": [
            {
                "person_id": int,
                "first_name": str,
                "last_name": str,
                "email": str or null,
                "city": str or null,
                "state": str or null,
                "country": str or null,
                "instruments": [str]
            }
        ]
    }
    """
    # Check authentication
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    try:
        query = request.args.get('q', '').strip()

        if not query or len(query) < 2:
            return jsonify({"success": True, "people": []})

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

        # Search for people not already in this session
        search_pattern = f"%{query}%"
        cur.execute(
            """
            SELECT p.person_id, p.first_name, p.last_name, p.email, p.city, p.state, p.country,
                   COALESCE(
                       array_agg(DISTINCT pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                       '{}'::text[]
                   ) as instruments
            FROM person p
            LEFT JOIN person_instrument pi ON p.person_id = pi.person_id
            WHERE (
                LOWER(p.first_name) LIKE LOWER(%s)
                OR LOWER(p.last_name) LIKE LOWER(%s)
                OR LOWER(CONCAT(p.first_name, ' ', p.last_name)) LIKE LOWER(%s)
            )
            AND p.person_id NOT IN (
                SELECT person_id FROM session_person WHERE session_id = %s
            )
            GROUP BY p.person_id, p.first_name, p.last_name, p.email, p.city, p.state, p.country
            ORDER BY p.first_name, p.last_name
            LIMIT 20
            """,
            (search_pattern, search_pattern, search_pattern, session_id)
        )

        people_data = cur.fetchall()
        people = []

        for row in people_data:
            people.append({
                'person_id': row[0],
                'first_name': row[1],
                'last_name': row[2],
                'email': row[3],
                'city': row[4],
                'state': row[5],
                'country': row[6],
                'instruments': row[7] if row[7] else []
            })

        cur.close()
        conn.close()

        return jsonify({"success": True, "people": people})

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to search people: {str(e)}"}), 500


def add_existing_person_to_session(session_path):
    """
    Add an existing person to a session.

    POST /api/sessions/<session_path>/people/add-existing

    Request body:
    {
        "person_id": int,
        "is_regular": bool
    }

    Returns:
    {
        "success": true,
        "message": str
    }
    """
    # Check authentication
    if not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        person_id = data.get('person_id')
        is_regular = data.get('is_regular', False)

        if not person_id:
            return jsonify({"success": False, "message": "person_id is required"}), 400

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

        # Verify person exists
        cur.execute("SELECT first_name, last_name FROM person WHERE person_id = %s", (person_id,))
        person_result = cur.fetchone()

        if not person_result:
            return jsonify({"success": False, "message": "Person not found"}), 404

        first_name, last_name = person_result

        # Check if person is already in this session
        cur.execute(
            "SELECT 1 FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id)
        )
        if cur.fetchone():
            return jsonify({"success": False, "message": f"{first_name} {last_name} is already in this session"}), 400

        # Add person to session
        cur.execute(
            """
            INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
            VALUES (%s, %s, %s, false)
            """,
            (session_id, person_id, is_regular)
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"{first_name} {last_name} added to session"
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to add person: {str(e)}"}), 500


@login_required
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


@login_required
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


@login_required
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


@login_required
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
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    
    # Check if current user is a system admin
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT is_system_admin FROM user_account WHERE user_id = %s",
            (current_user.user_id,)
        )
        user_row = cur.fetchone()
        if not user_row or not user_row[0]:
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403

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
                WHERE si.session_id = %s AND sip.attendance = 'yes'
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


def get_person_tunes_ajax(person_id):
    """Get person_tune list for a person"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get person_tune records with tune details
        cur.execute(
            """
            SELECT
                pt.person_tune_id,
                pt.tune_id,
                COALESCE(pt.name_alias, t.name) as tune_name,
                t.tune_type,
                pt.learn_status,
                pt.heard_count,
                pt.learned_date,
                pt.setting_id,
                pt.created_date,
                pt.last_modified_date
            FROM person_tune pt
            JOIN tune t ON pt.tune_id = t.tune_id
            WHERE pt.person_id = %s
            ORDER BY pt.last_modified_date DESC
        """,
            (person_id,),
        )

        tunes = []
        for row in cur.fetchall():
            (
                person_tune_id,
                tune_id,
                tune_name,
                tune_type,
                learn_status,
                heard_count,
                learned_date,
                setting_id,
                created_date,
                last_modified_date,
            ) = row

            tunes.append(
                {
                    "person_tune_id": person_tune_id,
                    "tune_id": tune_id,
                    "tune_name": tune_name,
                    "tune_type": tune_type or "Unknown",
                    "learn_status": learn_status,
                    "heard_count": heard_count or 0,
                    "learned_date": learned_date.strftime("%Y-%m-%d") if learned_date else None,
                    "setting_id": setting_id,
                    "created_date": created_date.strftime("%Y-%m-%d") if created_date else None,
                    "last_modified_date": last_modified_date.strftime("%Y-%m-%d") if last_modified_date else None,
                }
            )

        cur.close()
        conn.close()

        return jsonify(
            {
                "success": True,
                "tunes": tunes,
            }
        )

    except Exception as e:
        return (
            jsonify(
                {"success": False, "error": f"Failed to get person tunes: {str(e)}"}
            ),
            500,
        )


def get_person_tunes_stats(person_id):
    """Get tune statistics for a person (total counts, by status, by type)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get total count and counts by learn_status
        cur.execute(
            """
            SELECT
                COUNT(*) as total_tunes,
                COUNT(CASE WHEN learn_status = 'learned' THEN 1 END) as learned,
                COUNT(CASE WHEN learn_status = 'learning' THEN 1 END) as learning,
                COUNT(CASE WHEN learn_status = 'bookmarked' THEN 1 END) as bookmarked
            FROM person_tune
            WHERE person_id = %s
            """,
            (person_id,),
        )
        row = cur.fetchone()
        total_tunes, learned, learning, bookmarked = row if row else (0, 0, 0, 0)

        # Get counts by tune type
        cur.execute(
            """
            SELECT
                COALESCE(t.tune_type, 'Unknown') as tune_type,
                COUNT(*) as count
            FROM person_tune pt
            JOIN tune t ON pt.tune_id = t.tune_id
            WHERE pt.person_id = %s
            GROUP BY t.tune_type
            ORDER BY count DESC
            """,
            (person_id,),
        )
        by_type = {}
        for type_row in cur.fetchall():
            by_type[type_row[0] or 'Unknown'] = type_row[1]

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


@login_required
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
            cur, "user_account", "UPDATE", user_id_db, "admin_email_verification"
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
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    
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
        is_regular = data.get("is_regular", False)

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
def update_session_player_details(session_path, person_id):
    """Update person details for session admins"""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    
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
            if 'is_regular' in data:
                # Update regular status in session_person table
                cur.execute(
                    """UPDATE session_person SET is_regular = %s 
                       WHERE session_id = %s AND person_id = %s""",
                    (data['is_regular'], session_id, person_id)
                )
                save_to_history(
                    cur,
                    "session_person",
                    "UPDATE",
                    None,
                    f"admin_update_regular_status:{person_id}:{session_id}:{data['is_regular']}",
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
                    None,
                    f"admin_update_person_details:{person_id}:{','.join(data.keys())}",
                )
            
            # Also update regular status if provided
            if 'is_regular' in data:
                cur.execute(
                    """UPDATE session_person SET is_regular = %s 
                       WHERE session_id = %s AND person_id = %s""",
                    (data['is_regular'], session_id, person_id)
                )
                save_to_history(
                    cur,
                    "session_person",
                    "UPDATE",
                    None,
                    f"admin_update_regular_status:{person_id}:{session_id}:{data['is_regular']}",
                )

        conn.commit()
        return jsonify({"success": True})

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@login_required
def delete_session_player(session_path, person_id):
    """Delete a player from a session and potentially the person record if orphaned"""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401
    
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
                None,
                f"admin_delete_orphaned_person:{person_id}",
            )
            person_deleted = True

        conn.commit()
        
        response_data = {"success": True}
        if person_deleted:
            response_data["message"] = "Player removed from session and person record deleted (no other session associations)"
        else:
            response_data["message"] = "Player successfully removed from session"
            
        return jsonify(response_data)

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@login_required
def leave_session_membership(session_path):
    """Allow user to remove themselves from a session membership.

    This only removes them from session_person (membership), preserving
    all historical data like attendance records in session_instance_person.
    """
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Authentication required"}), 401

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


@login_required
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
            cur, "session", "UPDATE", None, f"admin_reactivate_session:{session_id}"
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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

        # Query with all the ordering criteria (accent insensitive)
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
            WHERE LOWER(unaccent(COALESCE(st.alias, t.name))) LIKE %s
            ORDER BY
                preferred_tune_type ASC,
                playcounts.plays DESC NULLS LAST,
                t.tunebook_count_cached DESC NULLS LAST,
                LOWER(unaccent(COALESCE(st.alias, t.name))) ASC
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


def ensure_tune_exists_in_table(cur, tune_id, user_provided_name):
    """
    Ensure a tune exists in the tune table. If not, fetch from thesession.org.
    
    Returns:
        tuple: (success, error_message, final_name_for_alias)
            - success: True if tune exists/was created, False if failed
            - error_message: Error message if failed, None if successful
            - final_name_for_alias: Name to use as alias if different from API name
    """
    if not tune_id:
        return True, None, None  # No tune_id to validate
    
    try:
        # Check if tune already exists in tune table
        cur.execute("SELECT name FROM tune WHERE tune_id = %s", (tune_id,))
        tune_exists = cur.fetchone()
        
        if tune_exists:
            # Tune exists, determine if we need an alias
            api_name = tune_exists[0]
            alias_needed = user_provided_name and user_provided_name != api_name
            return True, None, user_provided_name if alias_needed else None
        
        # Tune doesn't exist, fetch from thesession.org
        api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 404:
            return False, f"Tune #{tune_id} not found on thesession.org", None
        elif response.status_code != 200:
            return False, f"Failed to fetch tune data from thesession.org (status: {response.status_code})", None
        
        data = response.json()
        
        # Extract required fields
        if "name" not in data or "type" not in data:
            return False, "Invalid tune data received from thesession.org", None
        
        tune_name_from_api = data["name"]
        tune_type = data["type"].title()  # Convert to title case
        tunebook_count = data.get("tunebooks", 0)  # Default to 0 if not present
        
        # Try to insert new tune into tune table (handle race condition gracefully)
        try:
            cur.execute(
                """
                INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date)
                VALUES (%s, %s, %s, %s, CURRENT_DATE)
            """,
                (tune_id, tune_name_from_api, tune_type, tunebook_count),
            )
            
            # Save the newly inserted tune to history
            save_to_history(cur, "tune", "INSERT", tune_id)
            
        except Exception as insert_error:
            # Check if this was a duplicate key error (race condition - someone else inserted it)
            if "duplicate key" in str(insert_error).lower() or "already exists" in str(insert_error).lower():
                # Someone else inserted it, that's fine - just get the name they used
                cur.execute("SELECT name FROM tune WHERE tune_id = %s", (tune_id,))
                existing_tune = cur.fetchone()
                if existing_tune:
                    tune_name_from_api = existing_tune[0]
                else:
                    return False, f"Race condition error inserting tune {tune_id}", None
            else:
                # Some other database error
                return False, f"Database error inserting tune {tune_id}: {str(insert_error)}", None
        
        # Determine if we need to use an alias
        alias_needed = user_provided_name and user_provided_name != tune_name_from_api
        return True, None, user_provided_name if alias_needed else None
        
    except requests.exceptions.Timeout:
        return False, "Timeout connecting to thesession.org", None
    except requests.exceptions.RequestException as e:
        return False, f"Error connecting to thesession.org: {str(e)}", None
    except Exception as e:
        return False, f"Error processing tune data: {str(e)}", None


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

        # Get all existing tunes for this session instance
        cur.execute(
            """
            SELECT session_instance_tune_id, order_number, tune_id, name, continues_set, started_by_person_id
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
                # Determine continues_set: false for first tune in set, true otherwise
                continues_set = tune_idx > 0

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

                new_tunes.append(
                    {
                        "order_number": sequence_num,
                        "tune_id": tune_id,
                        "name": tune_name,
                        "continues_set": continues_set,
                        "started_by_person_id": started_by_person_id,
                    }
                )
                sequence_num += 1

        # Validate and ensure all linked tunes exist in the tune table
        # This handles the race condition where tunes were linked but may not exist yet
        tunes_to_add_to_session = {}  # Dict to track unique tunes we need to add to session_tune table (tune_id -> alias_name)
        aliases_to_create = []  # Track aliases we need to add to session_tune_alias table

        for new_tune in new_tunes:
            tune_id = new_tune.get("tune_id")
            user_provided_name = new_tune.get("name")

            if tune_id:
                # Ensure tune exists in tune table, get alias info
                success, error_message, alias_name = ensure_tune_exists_in_table(cur, tune_id, user_provided_name)

                if not success:
                    cur.close()
                    conn.close()
                    return jsonify({"success": False, "message": f"Failed to validate tune #{tune_id}: {error_message}"})

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
                        INSERT INTO session_tune (session_id, tune_id, alias, setting_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (session_id, tune_id) DO NOTHING
                    """,
                        (session_id, tune_id, alias_name, None),
                    )
                    # Only save to history and count modification if row was actually inserted
                    if cur.rowcount > 0:
                        save_to_history(cur, "session_tune", "INSERT", (session_id, tune_id))
                        modifications += 1
                except Exception as e:
                    # Log the error but continue - this shouldn't fail the entire save
                    print(f"Warning: Failed to insert tune {tune_id} into session_tune: {str(e)}")
                    # If it's already there, that's fine; if it's a different error, we'll catch it in the outer try-except

            # Add any new aliases to session_tune_alias table
            for session_id_val, tune_id, alias_name in aliases_to_create:
                cur.execute(
                    """
                    INSERT INTO session_tune_alias (session_id, tune_id, alias)
                    VALUES (%s, %s, %s)
                    """,
                    (session_id_val, tune_id, alias_name),
                )
                modifications += 1

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
                        or existing[5] != new_tune["started_by_person_id"]
                    ):
                        # Update existing record
                        save_to_history(
                            cur, "session_instance_tune", "UPDATE", existing[0]
                        )

                        cur.execute(
                            """
                            UPDATE session_instance_tune
                            SET tune_id = %s, name = %s, continues_set = %s, started_by_person_id = %s, last_modified_date = NOW()
                            WHERE session_instance_tune_id = %s
                        """,
                            (
                                new_tune["tune_id"],
                                new_tune["name"],
                                new_tune["continues_set"],
                                new_tune["started_by_person_id"],
                                existing[0],
                            ),
                        )
                        modifications += 1
                else:
                    # Insert new record
                    cur.execute(
                        """
                        INSERT INTO session_instance_tune
                        (session_instance_id, order_number, tune_id, name, continues_set, started_by_person_id, created_date, last_modified_date)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                        RETURNING session_instance_tune_id
                    """,
                        (
                            session_instance_id,
                            order_num,
                            new_tune["tune_id"],
                            new_tune["name"],
                            new_tune["continues_set"],
                            new_tune["started_by_person_id"],
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

        save_to_history(cur, "user_account", "UPDATE", current_user.user_id)

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
    """Check if user can view attendance for a session instance"""
    if not current_user.is_authenticated:
        return False
    
    # System admins can view any attendance
    if current_user.is_system_admin:
        return True
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session_id from session_instance_id
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        session_result = cur.fetchone()
        if not session_result:
            return False
        
        session_id = session_result[0]
        
        # Check if user is regular or admin for this session
        cur.execute("""
            SELECT is_regular, is_admin FROM session_person 
            WHERE session_id = %s AND person_id = %s
        """, (session_id, user_person_id))
        
        session_person = cur.fetchone()
        if session_person and (session_person[0] or session_person[1]):  # is_regular or is_admin
            return True
        
        # Check if user is attending this specific instance
        cur.execute("""
            SELECT 1 FROM session_instance_person 
            WHERE session_instance_id = %s AND person_id = %s AND attendance IN ('yes', 'maybe')
        """, (session_instance_id, user_person_id))
        
        attending = cur.fetchone()
        return attending is not None
        
    except Exception:
        return False
    finally:
        if 'conn' in locals():
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
                COALESCE(sp.is_regular, false) as is_regular,
                COALESCE(sp.is_admin, false) as is_admin,
                ARRAY_AGG(pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL) as instruments
            FROM person p
            JOIN session_instance_person sip ON p.person_id = sip.person_id
            LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
            LEFT JOIN person_instrument pi ON p.person_id = pi.person_id
            WHERE sip.session_instance_id = %s
            GROUP BY p.person_id, p.first_name, p.last_name, sip.attendance, sip.comment, sp.is_regular, sp.is_admin
            ORDER BY p.first_name, p.last_name
        """, (session_id, session_instance_id))

        attendees_data = cur.fetchall()
        attendees = []

        for row in attendees_data:
            person_id, first_name, last_name, attendance, comment, is_regular, is_admin, instruments = row
            attendees.append({
                'person_id': person_id,
                'first_name': first_name,
                'last_name': last_name,
                'display_name': f"{first_name} {last_name[0]}" if last_name else first_name,
                'instruments': instruments or [],
                'attendance': attendance,
                'is_regular': is_regular,
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
        
        user_session_admin = cur.fetchone()
        is_session_admin = user_session_admin and user_session_admin[0]
        is_system_admin = current_user.is_system_admin
        is_self_checkin = (person_id == current_person_id)
        
        # Permission rules:
        # - System admins can manage anyone
        # - Session admins can manage anyone in their session  
        # - Regular users can only manage themselves
        if not (is_system_admin or is_session_admin or is_self_checkin):
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
            f"user_{current_user_id}"  # changed_by parameter
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
                       COALESCE(sp.is_regular, FALSE) as is_regular,
                       COALESCE(
                           array_agg(pi.instrument ORDER BY pi.instrument) FILTER (WHERE pi.instrument IS NOT NULL),
                           '{}'::text[]
                       ) as instruments
                FROM person p
                LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
                LEFT JOIN person_instrument pi ON p.person_id = pi.person_id
                WHERE p.person_id = %s
                GROUP BY p.person_id, p.first_name, p.last_name, p.email, sp.is_regular
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
                    "is_regular": attendee_data[4]
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
        
        # Clean and normalize instruments - accept any non-empty instrument name
        normalized_instruments = []
        for instrument in instruments:
            if isinstance(instrument, str) and instrument.strip():
                normalized = instrument.strip().lower()
                if normalized not in normalized_instruments:  # Remove duplicates
                    normalized_instruments.append(normalized)
        
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
                INSERT INTO person (first_name, last_name, email, created_date)
                VALUES (%s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
                RETURNING person_id
                """,
                (first_name, last_name, email)
            )
            
            person_id = cur.fetchone()[0]
            
            # Log person creation to history
            save_to_history(
                cur,
                'person',
                'INSERT',
                person_id,
                current_user.user_id
            )
            
            # Insert instruments
            for instrument in normalized_instruments:
                cur.execute(
                    """
                    INSERT INTO person_instrument (person_id, instrument, created_date)
                    VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'))
                    """,
                    (person_id, instrument)
                )
                
                # Log instrument creation to history
                save_to_history(
                    cur,
                    'person_instrument',
                    'INSERT',
                    (person_id, instrument),
                    current_user.user_id
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
        
        # Get person's instruments
        cur.execute(
            """
            SELECT instrument 
            FROM person_instrument 
            WHERE person_id = %s 
            ORDER BY instrument
            """,
            (person_id,)
        )
        
        instrument_results = cur.fetchall()
        instruments = [row[0] for row in instrument_results]
        
        cur.close()
        conn.close()
        
        # Get person's name for response
        person_name = f"{person_result[1]} {person_result[2]}"
        
        return jsonify({
            "success": True,
            "data": instruments,
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
        
        # Clean and normalize instruments - accept any non-empty instrument name
        normalized_instruments = []
        for instrument in instruments:
            if isinstance(instrument, str) and instrument.strip():
                normalized = instrument.strip().lower()
                if normalized not in normalized_instruments:  # Remove duplicates
                    normalized_instruments.append(normalized)
        
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
                    current_user_id
                )
                
                cur.execute(
                    "DELETE FROM person_instrument WHERE person_id = %s AND instrument = %s",
                    (person_id, instrument)
                )
            
            # Add new instruments
            instruments_to_add = new_instruments - existing_instruments
            for instrument in instruments_to_add:
                cur.execute(
                    """
                    INSERT INTO person_instrument (person_id, instrument, created_date)
                    VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'))
                    """,
                    (person_id, instrument)
                )
                
                # Log addition to history
                save_to_history(
                    cur,
                    'person_instrument',
                    'INSERT',
                    (person_id, instrument),
                    current_user_id
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
        
        user_session_admin = cur.fetchone()
        is_session_admin = user_session_admin and user_session_admin[0]
        is_system_admin = current_user.is_system_admin
        is_self_removal = (person_id == current_person_id)
        
        # Permission rules:
        # - System admins can remove anyone
        # - Session admins can remove anyone from their session  
        # - Regular users can only remove themselves
        if not (is_system_admin or is_session_admin or is_self_removal):
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
        
        # Search for people associated with this session
        # Priority order: regulars first, then attendees, then alphabetical within each group
        search_pattern = f"%{search_query.lower()}%"
        
        cur.execute(
            """
            WITH session_people AS (
                -- Get all people who have been associated with this session
                SELECT DISTINCT p.person_id, p.first_name, p.last_name, p.email,
                       COALESCE(sp.is_regular, FALSE) as is_regular,
                       COALESCE(sp.is_admin, FALSE) as is_session_admin
                FROM person p
                LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
                LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id
                LEFT JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                WHERE (sp.session_id = %s OR si.session_id = %s)
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
            )
            SELECT sp.person_id, sp.first_name, sp.last_name, sp.email,
                   sp.is_regular, sp.is_session_admin,
                   pi.instruments,
                   CASE 
                       WHEN sp.first_name = sp.last_name THEN sp.first_name
                       ELSE CONCAT(sp.first_name, ' ', sp.last_name)
                   END as display_name
            FROM session_people sp
            JOIN person_instruments pi ON sp.person_id = pi.person_id
            ORDER BY 
                sp.is_regular DESC,  -- Regulars first
                display_name         -- Then alphabetical
            LIMIT %s
            """,
            (session_id, session_id, session_id, search_pattern, search_pattern, search_pattern, limit)
        )
        
        results = cur.fetchall()
        
        # Format results
        people = []
        for row in results:
            person_id, first_name, last_name, email, is_regular, is_session_admin, instruments, display_name = row
            
            people.append({
                'person_id': person_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'display_name': display_name,
                'is_regular': is_regular,
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
                -- Get all people who are associated with this session (regulars, admins, or have attended)
                SELECT DISTINCT p.person_id, p.first_name, p.last_name, p.email,
                       COALESCE(sp.is_regular, FALSE) as is_regular,
                       COALESCE(sp.is_admin, FALSE) as is_session_admin
                FROM person p
                LEFT JOIN session_person sp ON p.person_id = sp.person_id AND sp.session_id = %s
                LEFT JOIN session_instance_person sip ON p.person_id = sip.person_id
                LEFT JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                WHERE (sp.session_id = %s OR si.session_id = %s)
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
            )
            SELECT sap.person_id, sap.first_name, sap.last_name, sap.email,
                   sap.is_regular, sap.is_session_admin,
                   pi.instruments,
                   CASE
                       WHEN sap.first_name = sap.last_name THEN sap.first_name
                       ELSE CONCAT(sap.first_name, ' ', sap.last_name)
                   END as display_name
            FROM session_all_people sap
            JOIN person_instruments pi ON sap.person_id = pi.person_id
            ORDER BY
                sap.is_regular DESC,  -- Regulars first
                display_name          -- Then alphabetical
            """,
            (session_id, session_id, session_id)
        )
        
        results = cur.fetchall()
        
        # Format results
        people = []
        for row in results:
            person_id, first_name, last_name, email, is_regular, is_session_admin, instruments, display_name = row
            
            people.append({
                'person_id': person_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'display_name': display_name,
                'is_regular': is_regular,
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
        'is_regular': False
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
            elif 'regular' in header:
                person['is_regular'] = value.lower().strip() in ['x', 'true', 'yes', 't', '1']
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
    
    # Clean and normalize instruments
    person['instruments'] = [inst.lower().strip() for inst in person['instruments'] if inst.strip()]
    
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
        # First check by email (exact match)
        if person_data.get('email'):
            cur.execute(
                "SELECT person_id FROM person WHERE email = %s",
                (person_data['email'],)
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
                    INSERT INTO person (first_name, last_name, email, sms_number, city, state, country, created_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
                    RETURNING person_id
                    """,
                    (
                        person_data.get('first_name', '').strip(),
                        person_data.get('last_name', '').strip(),
                        person_data.get('email'),
                        person_data.get('sms_number'),
                        person_data.get('city'),
                        person_data.get('state'),
                        person_data.get('country')
                    )
                )
                
                person_id = cur.fetchone()[0]
                
                # Log person creation
                save_to_history(cur, 'person', 'INSERT', person_id, current_user.user_id)
                
                # Create instruments
                instruments = person_data.get('instruments', [])
                for instrument in instruments:
                    if instrument and instrument.strip():
                        cur.execute(
                            """
                            INSERT INTO person_instrument (person_id, instrument, created_date)
                            VALUES (%s, %s, (NOW() AT TIME ZONE 'UTC'))
                            """,
                            (person_id, instrument.strip().lower())
                        )
                        
                        # Log instrument creation
                        save_to_history(cur, 'person_instrument', 'INSERT', 
                                      (person_id, instrument.strip().lower()), current_user.user_id)
                
                # Create session_person record
                is_regular = person_data.get('is_regular', False)
                cur.execute(
                    """
                    INSERT INTO session_person (session_id, person_id, is_regular, created_date)
                    VALUES (%s, %s, %s, (NOW() AT TIME ZONE 'UTC'))
                    """,
                    (session_id, person_id, is_regular)
                )
                
                # Log session_person creation
                save_to_history(cur, 'session_person', 'INSERT', 
                              (session_id, person_id), current_user.user_id)
                
                created_count += 1
                created_people.append({
                    "person_id": person_id,
                    "first_name": person_data.get('first_name', ''),
                    "last_name": person_data.get('last_name', ''),
                    "email": person_data.get('email'),
                    "instruments": instruments,
                    "is_regular": is_regular
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


def get_sessions_with_today_status():
    """
    Get all sessions with indicators for today's status:
    - has_instance_today: Boolean indicating if an instance exists for today
    - instance_id_today: The session_instance_id if one exists for today
    - recurrence: The recurrence pattern for client-side parsing

    NOTE: "Today" is determined based on each session's timezone, not server time.
    """
    try:
        from timezone_utils import get_today_in_timezone

        conn = get_db_connection()
        cur = conn.cursor()

        # Get user's person_id if logged in
        user_person_id = None
        if current_user.is_authenticated:
            user_person_id = getattr(current_user, 'person_id', None)

        # Get all sessions with their timezone and user membership
        cur.execute(
            """
            SELECT
                s.session_id,
                s.name,
                s.path,
                s.city,
                s.state,
                s.country,
                s.termination_date,
                s.recurrence,
                s.timezone,
                CASE WHEN sp.person_id IS NOT NULL THEN TRUE ELSE FALSE END as user_is_member,
                s.location_name
            FROM session s
            LEFT JOIN session_person sp ON s.session_id = sp.session_id AND sp.person_id = %s
            ORDER BY s.name
            """,
            (user_person_id,)
        )

        # Fetch all sessions first
        session_rows = cur.fetchall()

        # Get ALL active instances in one query (much more efficient!)
        # Active instances are marked with is_active = TRUE
        cur.execute(
            """
            SELECT session_id, session_instance_id, date, start_time, end_time, location_override
            FROM session_instance
            WHERE is_active = TRUE
            ORDER BY session_id, date, start_time
            """
        )

        # Group active instances by session_id
        active_instances_by_session = {}
        for active_row in cur.fetchall():
            session_id = active_row[0]
            if session_id not in active_instances_by_session:
                active_instances_by_session[session_id] = []

            active_instances_by_session[session_id].append({
                'session_instance_id': active_row[1],
                'date': active_row[2].isoformat(),
                'start_time': active_row[3].isoformat() if active_row[3] else None,
                'end_time': active_row[4].isoformat() if active_row[4] else None,
                'location_override': active_row[5]
            })

        # Now build the sessions list
        sessions = []
        for row in session_rows:
            session_id = row[0]

            # Get active instances for this session from our pre-fetched dict
            active_instances = active_instances_by_session.get(session_id, [])

            sessions.append({
                'session_id': session_id,
                'name': row[1],
                'path': row[2],
                'city': row[3],
                'state': row[4],
                'country': row[5],
                'termination_date': row[6].isoformat() if row[6] else None,
                'recurrence': row[7],
                'user_is_member': row[9],
                'location_name': row[10],
                'active_instances': active_instances
            })

        cur.close()
        conn.close()

        # Return "today" in user's timezone if logged in, otherwise UTC
        user_timezone = "UTC"
        if current_user.is_authenticated and hasattr(current_user, 'timezone'):
            user_timezone = current_user.timezone or "UTC"
        today_for_user = get_today_in_timezone(user_timezone)

        return jsonify({
            'success': True,
            'sessions': sessions,
            'today': today_for_user.isoformat()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
            INSERT INTO session_instance (session_id, date, comments)
            VALUES (%s, %s, %s)
            RETURNING session_instance_id
            """,
            (session_id, today, None),
        )
        new_instance = cur.fetchone()

        if not new_instance:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Failed to create session instance"}), 500

        session_instance_id = new_instance[0]

        # Save to history
        save_to_history(cur, "session_instance", "INSERT", session_instance_id, f"Created instance for {today}")

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
                t.tunebook_count_cached
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
                "tunebook_count_cached": row[5] or 0
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
            current_user.username if current_user.is_authenticated else "system"
        )

        # Update the tune name
        cur.execute(
            "UPDATE tune SET name = %s, last_modified_date = CURRENT_TIMESTAMP WHERE tune_id = %s",
            (name, tune_id)
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
# Person Tune Management API Endpoints
# ============================================================================


@api_login_required
def get_person_tune_status(tune_id):
    """
    Get the status of a tune on the current user's tune list.

    GET /api/person/tunes/<int:tune_id>

    Returns:
    {
        "success": true,
        "on_list": boolean,
        "tune_status": {
            "learn_status": "want to learn" | "learning" | "learned",
            "heard_count": int
        } or null if not on list
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

        # Check if tune is on user's list
        cur.execute(
            """
            SELECT person_tune_id, learn_status, heard_count
            FROM person_tune
            WHERE person_id = %s AND tune_id = %s
            """,
            (person_id, tune_id)
        )
        tune_row = cur.fetchone()

        if tune_row:
            return jsonify({
                "success": True,
                "on_list": True,
                "tune_status": {
                    "person_tune_id": tune_row[0],
                    "learn_status": tune_row[1],
                    "heard_count": tune_row[2]
                }
            })
        else:
            return jsonify({
                "success": True,
                "on_list": False,
                "tune_status": None
            })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def add_person_tune():
    """
    Add a tune to the current user's tune list.

    POST /api/person/tunes

    Request body:
    {
        "tune_id": int,
        "learn_status": "want to learn" | "learning" | "learned",
        "heard_count": int (optional, defaults to 1)
    }

    Returns:
    {
        "success": true,
        "message": string
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    tune_id = data.get("tune_id")
    learn_status = data.get("learn_status", "want to learn")
    heard_count = data.get("heard_count", 1)

    if not tune_id:
        return jsonify({"success": False, "error": "tune_id is required"}), 400

    # Validate learn_status
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

        # Check if tune exists
        cur.execute("SELECT tune_id FROM tune WHERE tune_id = %s", (tune_id,))
        if not cur.fetchone():
            return jsonify({"success": False, "error": "Tune not found"}), 404

        # Insert into person_tune
        cur.execute(
            """
            INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (person_id, tune_id)
            DO UPDATE SET
                learn_status = EXCLUDED.learn_status,
                heard_count = EXCLUDED.heard_count,
                last_modified_date = (NOW() AT TIME ZONE 'UTC')
            """,
            (person_id, tune_id, learn_status, heard_count)
        )
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Tune added to your list"
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def update_person_tune_status(tune_id):
    """
    Update the learn status of a tune on the current user's list.

    PUT /api/person/tunes/<int:tune_id>/status

    Request body:
    {
        "learn_status": "want to learn" | "learning" | "learned"
    }

    Returns:
    {
        "success": true,
        "message": string
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    learn_status = data.get("learn_status")
    if not learn_status:
        return jsonify({"success": False, "error": "learn_status is required"}), 400

    # Validate learn_status
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

        # Update the learn_status
        cur.execute(
            """
            UPDATE person_tune
            SET learn_status = %s,
                last_modified_date = (NOW() AT TIME ZONE 'UTC')
            WHERE person_id = %s AND tune_id = %s
            """,
            (learn_status, person_id, tune_id)
        )

        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Tune not found on your list"}), 404

        conn.commit()

        return jsonify({
            "success": True,
            "message": "Status updated"
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@api_login_required
def increment_person_tune_heard_count(tune_id):
    """
    Increment the heard count of a tune on the current user's list.

    PUT /api/person/tunes/<int:tune_id>/increment_heard

    Returns:
    {
        "success": true,
        "new_count": int,
        "message": string
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

        # Increment the heard_count
        cur.execute(
            """
            UPDATE person_tune
            SET heard_count = heard_count + 1,
                last_modified_date = (NOW() AT TIME ZONE 'UTC')
            WHERE person_id = %s AND tune_id = %s
            RETURNING heard_count
            """,
            (person_id, tune_id)
        )

        result = cur.fetchone()
        if not result:
            return jsonify({"success": False, "error": "Tune not found on your list"}), 404

        new_count = result[0]
        conn.commit()

        return jsonify({
            "success": True,
            "new_count": new_count,
            "message": "Count updated"
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# Session Instance Tune Detail Endpoints
# ============================================================================

def get_session_instance_tune_detail(session_path, date_or_id, tune_id):
    """
    Get detailed information about a tune in the context of a specific session instance.

    GET /api/sessions/<session_path>/<date_or_id>/tunes/<tune_id>

    Returns tune details with session_instance_tune overrides and history.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session_id
        # First try the session_path as-is
        cur.execute("SELECT session_id FROM session WHERE path = %s", (session_path,))
        session_result = cur.fetchone()

        # If not found, check if session_path + date_or_id forms a valid session path
        # This handles cases like "oflahertys/2025" where routing splits it incorrectly
        if not session_result:
            combined_path = f"{session_path}/{date_or_id}"
            cur.execute("SELECT session_id FROM session WHERE path = %s", (combined_path,))
            combined_result = cur.fetchone()

            if combined_result:
                # The date_or_id was actually part of the session path
                # Close this connection and redirect to session-level tune detail logic
                cur.close()
                conn.close()
                return get_session_tune_detail(combined_path, tune_id)
            else:
                return jsonify({"success": False, "message": "Session not found"}), 404
        else:
            session_id = session_result[0]

        # Get session_instance_id
        session_instance_id = get_session_instance_id(cur, session_id, date_or_id)
        if not session_instance_id:
            return jsonify({"success": False, "message": "Session instance not found"}), 404

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

        # Get session-level defaults from session_tune
        cur.execute(
            """
            SELECT alias, setting_id, key
            FROM session_tune
            WHERE session_id = %s AND tune_id = %s
        """,
            (session_id, tune_id),
        )
        session_tune_info = cur.fetchone()

        session_alias = None
        session_setting_id = None
        session_key = None

        if session_tune_info:
            session_alias, session_setting_id, session_key = session_tune_info

        # Get instance-specific overrides from session_instance_tune
        cur.execute(
            """
            SELECT name, key_override, setting_override, order_number
            FROM session_instance_tune
            WHERE session_instance_id = %s AND tune_id = %s
        """,
            (session_instance_id, tune_id),
        )
        instance_tune_info = cur.fetchone()

        name_override = None
        key_override = None
        setting_override = None
        order_number = None

        if instance_tune_info:
            name_override, key_override, setting_override, order_number = instance_tune_info

        # Get ABC notation from tune_setting
        # Prefer setting_override if available, otherwise use session_setting_id, or fall back to first setting
        abc_notation = None
        incipit_abc = None
        abc_image = None
        incipit_image = None
        effective_setting_id = setting_override if setting_override else session_setting_id
        if effective_setting_id:
            cur.execute(
                "SELECT abc, incipit_abc, image, incipit_image FROM tune_setting WHERE setting_id = %s",
                (effective_setting_id,)
            )
        else:
            # Fall back to the first setting for this tune (ordered by setting_id)
            cur.execute(
                """SELECT abc, incipit_abc, image, incipit_image
                   FROM tune_setting
                   WHERE tune_id = %s
                   ORDER BY setting_id ASC
                   LIMIT 1""",
                (tune_id,)
            )
        abc_result = cur.fetchone()
        if abc_result:
            abc_notation = abc_result[0]
            incipit_abc = abc_result[1]
            abc_image = abc_result[2]
            incipit_image = abc_result[3]

        # Get play count for this session (all instances)
        cur.execute(
            """
            SELECT COUNT(*)
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s
        """,
            (session_id, tune_id),
        )
        play_count_result = cur.fetchone()
        times_played = play_count_result[0] if play_count_result else 0

        # Get detailed play history for this session
        cur.execute(
            """
            SELECT
                si.date,
                sit.order_number,
                sit.name,
                sit.key_override,
                sit.setting_override,
                si.session_instance_id
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s
            ORDER BY si.date DESC
        """,
            (session_id, tune_id),
        )
        play_instances_raw = cur.fetchall()
        play_instances = [
            {
                "date": row[0].isoformat() if row[0] else None,
                "position_in_set": row[1],
                "name_override": row[2],
                "key_override": row[3],
                "setting_id_override": row[4],
                "session_instance_id": row[5],
            }
            for row in play_instances_raw
        ]

        # Get person_tune status if user is logged in
        person_tune_status = None
        if current_user.is_authenticated:
            cur.execute(
                "SELECT person_id FROM user_account WHERE user_id = %s",
                (current_user.user_id,)
            )
            person_row = cur.fetchone()
            if person_row:
                person_id = person_row[0]
                cur.execute(
                    """
                    SELECT person_tune_id, learn_status, heard_count
                    FROM person_tune
                    WHERE person_id = %s AND tune_id = %s
                    """,
                    (person_id, tune_id)
                )
                tune_row = cur.fetchone()
                if tune_row:
                    person_tune_status = {
                        "on_list": True,
                        "person_tune_id": tune_row[0],
                        "learn_status": tune_row[1],
                        "heard_count": tune_row[2]
                    }
                else:
                    person_tune_status = {
                        "on_list": False,
                        "person_tune_id": None,
                        "learn_status": None,
                        "heard_count": None
                    }

        # Get global play count (all sessions)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*)
            FROM session_instance_tune
            WHERE tune_id = %s
        """,
            (tune_id,),
        )
        global_play_result = cur.fetchone()
        global_play_count = global_play_result[0] if global_play_result else 0
        cur.close()

        conn.close()

        # Build response - includes both session defaults and instance overrides
        return jsonify(
            {
                "success": True,
                "session_tune": {
                    "tune_id": tune_id,
                    "tune_name": tune_name,
                    "tune_type": tune_type,
                    # Session-level defaults
                    "alias": session_alias,
                    "setting_id": session_setting_id,
                    "key": session_key,
                    # Instance-specific overrides
                    "name": name_override,
                    "key_override": key_override,
                    "setting_override": setting_override,
                    "order_number": order_number,
                    # ABC notation
                    "abc": abc_notation,
                    "incipit_abc": incipit_abc,
                    "image": bytea_to_base64(abc_image),
                    "incipit_image": bytea_to_base64(incipit_image),
                    # Stats
                    "tunebook_count": tunebook_count,
                    "tunebook_count_cached_date": (
                        tunebook_count_cached_date.isoformat()
                        if tunebook_count_cached_date
                        else None
                    ),
                    "times_played": times_played,
                    "global_play_count": global_play_count,
                    "play_instances": play_instances,
                    "person_tune_status": person_tune_status,
                },
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error retrieving tune details: {str(e)}"}
        ), 500


@login_required
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

        # Check if user has permission to edit this session
        if not current_user.is_system_admin:
            cur.execute(
                """
                SELECT is_admin FROM session_person
                WHERE session_id = %s AND person_id = %s
            """,
                (session_id, current_user.person_id),
            )
            permission = cur.fetchone()
            if not permission or not permission[0]:
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

        # Extract fields from request
        name = data.get("name", "").strip() or None
        key_override = data.get("key_override", "").strip() or None
        setting_override = data.get("setting_override")

        # Convert setting_override to int or None
        if setting_override is not None:
            if setting_override == "" or setting_override == "null":
                setting_override = None
            else:
                try:
                    setting_override = int(setting_override)
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "Invalid setting_override value"}), 400

        # Update the session_instance_tune record
        cur.execute(
            """
            UPDATE session_instance_tune
            SET name = %s,
                key_override = %s,
                setting_override = %s
            WHERE session_instance_id = %s AND tune_id = %s
        """,
            (name, key_override, setting_override, session_instance_id, tune_id),
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Tune details updated successfully"
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

        # Check if user has permission to edit this session
        if not current_user.is_system_admin:
            cur.execute(
                """
                SELECT is_admin FROM session_person
                WHERE session_id = %s AND person_id = %s
            """,
                (session_id, current_user.person_id),
            )
            permission = cur.fetchone()
            if not permission or not permission[0]:
                return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Get all tunes for this session instance ordered by order_number
        cur.execute(
            """
            SELECT session_instance_tune_id, order_number, continues_set
            FROM session_instance_tune
            WHERE session_instance_id = %s
            ORDER BY order_number
        """,
            (session_instance_id,),
        )
        tunes = cur.fetchall()

        if not tunes:
            return jsonify({"success": False, "message": "No tunes found"}), 404

        # Group tunes into sets (same logic as frontend)
        sets = []
        current_set = []
        for tune in tunes:
            if not tune[2] and current_set:  # continues_set is False and we have a current set
                sets.append(current_set)
                current_set = []
            current_set.append(tune)
        if current_set:
            sets.append(current_set)

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
            SET started_by_person_id = %s, last_modified_date = NOW()
            WHERE session_instance_tune_id = ANY(%s)
        """,
            (person_id, tune_ids),
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
        cur.execute(
            """
            SELECT setting_id, abc, incipit_abc, image, incipit_image
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

        # Get detailed play history across all sessions
        cur.execute(
            """
            SELECT
                S.name,
                S.path,
                SI.date,
                SIT.order_number,
                SIT.name,
                SIT.key_override,
                SIT.setting_override,
                SI.session_instance_id
            FROM session_instance_tune SIT
            INNER JOIN session_instance SI ON SIT.session_instance_id = SI.session_instance_id
            INNER JOIN session S ON SI.session_id = S.session_id
            WHERE SIT.tune_id = %s
            ORDER BY SI.date DESC
            LIMIT 100
        """,
            (tune_id,),
        )
        play_instances_raw = cur.fetchall()
        play_instances = []
        for row in play_instances_raw:
            session_name = row[0]
            session_path = row[1]
            date = row[2]
            order_number = row[3]
            name_override = row[4]
            key_override = row[5]
            setting_override = row[6]
            session_instance_id = row[7]

            # Build full name for display: "Session Name - YYYY-MM-DD"
            full_name = f"{session_name} - {date.strftime('%Y-%m-%d')}" if date else session_name
            # Build link to session instance
            link = f"/sessions/{session_path}/{session_instance_id}"

            play_instances.append({
                "full_name": full_name,
                "session_name": session_name,
                "session_path": session_path,
                "date": date.isoformat() if date else None,
                "position_in_set": order_number,
                "name_override": name_override,
                "key_override": key_override,
                "setting_id_override": setting_override,
                "session_instance_id": session_instance_id,
                "link": link
            })

        conn.close()

        # Build response
        return jsonify(
            {
                "success": True,
                "tune": {
                    "tune_id": tune_id,
                    "name": tune_name,
                    "tune_name": tune_name,
                    "tune_type": tune_type,
                    "setting_id": first_setting_id,
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
                    "play_instances": play_instances,
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


@login_required
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


@login_required
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
                   COUNT(*) OVER (PARTITION BY si.date) as instances_on_date
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
                    'multiple_on_date': instance[5] > 1
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
                    'multiple_on_date': instance[5] > 1
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


def get_session_tunes_remaining(session_path):
    """
    Get remaining session tunes (after the first 20) for a session.
    No authentication required - public endpoint.

    Returns:
    {
        "success": true,
        "tunes": [...]
    }
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get session ID
        cur.execute(
            "SELECT session_id FROM session WHERE path = %s",
            (session_path,)
        )
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Session not found"}), 404

        session_id = session_result[0]

        # Get remaining session tunes (skip first 20)
        # Optimized: Use subquery to calculate play counts more efficiently
        cur.execute(
            """
            SELECT
                st.tune_id,
                COALESCE(st.alias, t.name) AS tune_name,
                t.tune_type,
                COALESCE(play_counts.play_count, 0) AS play_count,
                COALESCE(t.tunebook_count_cached, 0) AS tunebook_count,
                st.setting_id
            FROM session_tune st
            LEFT JOIN tune t ON st.tune_id = t.tune_id
            LEFT JOIN (
                SELECT sit.tune_id, COUNT(*) as play_count
                FROM session_instance_tune sit
                JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                WHERE si.session_id = %s
                GROUP BY sit.tune_id
            ) play_counts ON st.tune_id = play_counts.tune_id
            WHERE st.session_id = %s
            ORDER BY play_count DESC, tunebook_count DESC, tune_name ASC
            OFFSET 20
        """,
            (session_id, session_id),
        )

        tunes = cur.fetchall()
        cur.close()
        conn.close()

        # Convert to list of dicts for JSON serialization
        tunes_list = [
            {
                'tune_id': tune[0],
                'tune_name': tune[1],
                'tune_type': tune[2],
                'play_count': tune[3],
                'tunebook_count': tune[4],
                'setting_id': tune[5]
            }
            for tune in tunes
        ]

        return jsonify({
            "success": True,
            "tunes": tunes_list
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@api_login_required
def join_session(session_path):
    """
    Allow a logged-in user to add themselves as a member (non-regular) of a session.

    POST /api/sessions/<session_path>/join

    Returns:
        JSON response with success status
    """
    try:
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

        # Add user as a member (not regular, not admin)
        cur.execute(
            """
            INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
            VALUES (%s, %s, false, false)
            """,
            (session_id, user_person_id)
        )

        # Save to history
        save_to_history(
            cur,
            "session_person",
            "INSERT",
            None,
            f"user_self_join:{user_person_id}:{session_id}",
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Successfully joined session"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to join session: {str(e)}"}), 500
