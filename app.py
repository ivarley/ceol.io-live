from flask import Flask, render_template, request, session
from flask_login import LoginManager
from werkzeug.routing import BaseConverter
import os
import random
import logging
from datetime import timedelta
from dotenv import load_dotenv

# Import our custom modules
from auth import User, SESSION_LIFETIME_WEEKS
from api_routes import *
from web_routes import *
from api_person_tune_routes import (
    get_my_tunes,
    get_person_tune_detail,
    add_my_tune,
    update_person_tune,
    delete_person_tune,
    increment_tune_heard_count,
    decrement_tune_heard_count,
    sync_my_tunes,
    search_tunes,
    update_my_profile,
    get_common_tunes
)
from timezone_utils import format_datetime_with_timezone, utc_to_local
from flask_login import current_user

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Log to stdout (captured by Render/Gunicorn)
    ]
)

# Custom URL converter for date or ID
class DateOrIdConverter(BaseConverter):
    """Matches dates in YYYY-MM-DD format or numeric IDs"""
    regex = r'\d{4}-\d{2}-\d{2}|\d+'

app = Flask(__name__)
app.url_map.converters['date_or_id'] = DateOrIdConverter

# Secret key required for Flask sessions (used by flash messages to store temporary messages in signed cookies)
app.secret_key = os.environ.get(
    "FLASK_SESSION_SECRET_KEY", "dev-secret-key-change-in-production"
)

# Configure permanent session lifetime to match database session expiration
# This ensures Flask session cookies persist for the full session duration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(weeks=SESSION_LIFETIME_WEEKS)

# Configure Flask to handle trailing slashes consistently
app.url_map.strict_slashes = False

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # type: ignore
login_manager.login_message = "Please log in to access this page."

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))

# Before request handler to capture referrer parameter
@app.before_request
def capture_referrer():
    """
    Capture the referrer parameter from URLs and store it in the session.
    This allows tracking which person referred a new user to the site.
    """
    referrer = request.args.get('referrer')
    if referrer:
        # Store in session for later use during registration
        session['referred_by_person_id'] = referrer

# Template filters for timezone handling
@app.template_filter("format_datetime_tz")
def format_datetime_tz(dt, session_timezone=None, format_str="%Y-%m-%d %H:%M"):
    """
    Format datetime with appropriate timezone conversion for templates.

    Args:
        dt: UTC datetime from database
        session_timezone: Session's timezone (optional)
        format_str: strftime format string

    Returns:
        Formatted datetime string with timezone abbreviation
    """
    if not dt:
        return ""

    # Determine which timezone to use for display
    try:
        # If user is logged in, use their timezone
        if hasattr(current_user, "timezone") and current_user.timezone:
            user_timezone = current_user.timezone
            return format_datetime_with_timezone(dt, user_timezone, format_str)
    except Exception:
        pass

    # If session timezone provided, use that
    if session_timezone:
        return format_datetime_with_timezone(dt, session_timezone, format_str)

    # Default: show as UTC
    return format_datetime_with_timezone(dt, "UTC", format_str)

@app.template_filter("to_user_timezone")
def to_user_timezone(dt, session_timezone=None):
    """Convert UTC datetime to user's timezone (or session timezone if no user)"""
    if not dt:
        return None

    try:
        # If user is logged in, use their timezone
        if hasattr(current_user, "timezone") and current_user.timezone:
            return utc_to_local(dt, current_user.timezone)
    except Exception:
        pass

    # If session timezone provided, use that
    if session_timezone:
        return utc_to_local(dt, session_timezone)

    # Default: return as UTC
    return dt

@app.template_global("get_user_timezone")
def get_user_timezone():
    """Get current user's timezone for use in templates"""
    try:
        if hasattr(current_user, "timezone") and current_user.timezone:
            return current_user.timezone
    except Exception:
        pass
    return "UTC"

@app.template_filter("instance_url_id")
def instance_url_id(instance):
    """
    Generate the URL identifier for a session instance.
    Returns the session_instance_id if there are multiple instances on the same date,
    otherwise returns the date string for backwards compatibility.

    Args:
        instance: Dictionary with 'date', 'session_instance_id', and 'multiple_on_date' keys

    Returns:
        String identifier to use in URL (either date string or numeric ID)
    """
    if instance.get('multiple_on_date', False):
        return str(instance['session_instance_id'])
    else:
        # Return date as string in YYYY-MM-DD format
        date = instance['date']
        if hasattr(date, 'strftime'):
            return date.strftime('%Y-%m-%d')
        return str(date)

# Register web page routes
app.add_url_rule("/", "home", home)
app.add_url_rule("/magic", "magic", magic)
app.add_url_rule("/db-test", "db_test", db_test)
app.add_url_rule("/sessions", "sessions", sessions)
app.add_url_rule("/sessions/<path:session_path>/tunes", "session_tunes", session_tunes)
app.add_url_rule(
    "/sessions/<path:session_path>/tunes/<int:tune_id>",
    "session_tune_info",
    session_tune_info,
)
app.add_url_rule("/sessions/<path:session_path>/people", "session_people", session_people)
app.add_url_rule("/sessions/<path:session_path>/people/<int:person_id>", "session_person_detail", session_person_detail)
app.add_url_rule("/sessions/<path:session_path>/logs", "session_logs", session_logs)
app.add_url_rule("/sessions/<path:full_path>", "session_handler", session_handler)
app.add_url_rule("/sessions/<path:full_path>/players", "session_instance_players", session_instance_players)
app.add_url_rule("/add-session", "add_session", add_session)
app.add_url_rule("/help", "help_page", help_page)
app.add_url_rule("/share", "share_page", share_page)
app.add_url_rule("/help/my-tunes", "help_my_tunes", help_my_tunes)
app.add_url_rule("/register", "register", register, methods=["GET", "POST"])
app.add_url_rule("/login", "login", login, methods=["GET", "POST"])
app.add_url_rule("/logout", "logout", logout)
app.add_url_rule(
    "/forgot-password", "forgot_password", forgot_password, methods=["GET", "POST"]
)
app.add_url_rule(
    "/reset-password/<token>", "reset_password", reset_password, methods=["GET", "POST"]
)
app.add_url_rule(
    "/change-password", "change_password", change_password, methods=["GET", "POST"]
)
app.add_url_rule("/me", "user_profile", person_details)
app.add_url_rule("/my-tunes", "my_tunes", my_tunes)
app.add_url_rule("/my-tunes/add", "add_my_tune_page", add_my_tune_page)
app.add_url_rule("/my-tunes/sync", "sync_my_tunes_page", sync_my_tunes_page)
app.add_url_rule("/me/and/<int:person_id>", "common_tunes", common_tunes)
app.add_url_rule(
    "/sessions/<path:session_path>/tunes/add",
    "add_session_tune_page",
    add_session_tune_page,
)
app.add_url_rule("/verify-email/<token>", "verify_email", verify_email)
app.add_url_rule(
    "/resend-verification",
    "resend_verification",
    resend_verification,
    methods=["GET", "POST"],
)
app.add_url_rule("/admin", "admin", admin)
app.add_url_rule("/admin/sessions", "admin_sessions_list", admin_sessions_list)
app.add_url_rule("/admin/login-sessions", "admin_login_sessions", admin_login_sessions)
app.add_url_rule("/admin/login-history", "admin_login_history", admin_login_history)
app.add_url_rule("/admin/people", "admin_people", admin_people)
app.add_url_rule("/admin/tunes", "admin_tunes", admin_tunes)
app.add_url_rule("/admin/test-links", "admin_test_links", admin_test_links)
app.add_url_rule("/admin/cache-settings", "admin_cache_settings", admin_cache_settings)
app.add_url_rule("/admin/people/<int:person_id>", "person_details", person_details)
app.add_url_rule("/admin/sessions/<path:session_path>", "session_admin", session_admin)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/players",
    "session_admin_players",
    session_admin_players,
)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/players/<int:person_id>",
    "session_admin_person",
    session_admin_person,
)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/logs", "session_admin_logs", session_admin_logs
)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/bulk-import",
    "session_admin_bulk_import",
    session_admin_bulk_import,
)

# Register API routes
app.add_url_rule("/api/sessions/data", "sessions_data", sessions_data)

# SESSION routes - MUST come BEFORE session_instance routes!
# These have fewer segments, so <path:session_path> will greedily match the full path
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/<int:tune_id>/refresh_tunebook_count",
    "refresh_tunebook_count_ajax",
    refresh_tunebook_count_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/tunes/<int:tune_id>/settings/cache",
    "cache_tune_setting_ajax",
    cache_tune_setting_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/<int:tune_id>",
    "get_session_tune_detail",
    get_session_tune_detail,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/<int:tune_id>",
    "update_session_tune_details",
    update_session_tune_details,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes",
    "add_session_tune",
    add_session_tune,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/<int:tune_id>/aliases",
    "get_session_tune_aliases",
    get_session_tune_aliases,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/<int:tune_id>/aliases",
    "add_session_tune_alias",
    add_session_tune_alias,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/<int:tune_id>/aliases/<int:alias_id>",
    "delete_session_tune_alias",
    delete_session_tune_alias,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/admin-update",
    "update_session_ajax",
    update_session_ajax,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/add_instance",
    "add_session_instance_ajax",
    add_session_instance_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/next_instance_suggestion",
    "get_next_session_instance_suggestion_ajax",
    get_next_session_instance_suggestion_ajax,
    methods=["GET"],
)

# SESSION INSTANCE routes - MUST come AFTER session routes!
# These use custom date_or_id converter to only match dates/IDs, not arbitrary path segments
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/tunes/<int:tune_id>",
    "get_session_instance_tune_detail",
    get_session_instance_tune_detail,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/tunes/<int:tune_id>",
    "update_session_instance_tune_details",
    update_session_instance_tune_details,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/update",
    "update_session_instance_ajax",
    update_session_instance_ajax,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/tune_count",
    "get_session_tune_count_ajax",
    get_session_tune_count_ajax,
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/delete",
    "delete_session_instance_ajax",
    delete_session_instance_ajax,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/mark_complete",
    "mark_session_log_complete_ajax",
    mark_session_log_complete_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/mark_incomplete",
    "mark_session_log_incomplete_ajax",
    mark_session_log_incomplete_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/add_tune",
    "add_tune_ajax",
    add_tune_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/delete_tune_by_order/<int:order_number>",
    "delete_tune_by_order_ajax",
    delete_tune_by_order_ajax,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/link_tune",
    "link_tune_ajax",
    link_tune_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/tunes",
    "get_session_tunes_ajax",
    get_session_tunes_ajax,
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/move_set",
    "move_set_ajax",
    move_set_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/move_tune",
    "move_tune_ajax",
    move_tune_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/add_tunes_to_set",
    "add_tunes_to_set_ajax",
    add_tunes_to_set_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/edit_tune",
    "edit_tune_ajax",
    edit_tune_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/match_tune",
    "match_tune_ajax",
    match_tune_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/test_match_tune",
    "test_match_tune_ajax",
    test_match_tune_ajax,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/save_tunes",
    "save_session_instance_tunes_ajax",
    save_session_instance_tunes_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/check-existing-session",
    "check_existing_session_ajax",
    check_existing_session_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/search-sessions",
    "search_sessions_ajax",
    search_sessions_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/fetch-session-data",
    "fetch_session_data_ajax",
    fetch_session_data_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/add-session", "add_session_ajax", add_session_ajax, methods=["POST"]
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/players",
    "get_session_players_ajax",
    get_session_players_ajax,
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/players/<int:person_id>/regular",
    "update_session_player_regular_status",
    update_session_player_regular_status,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/players/<int:person_id>/details",
    "update_session_player_details",
    update_session_player_details,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/players/<int:person_id>",
    "delete_session_player",
    delete_session_player,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/logs",
    "get_session_logs_ajax",
    get_session_logs_ajax,
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/terminate",
    "terminate_session",
    terminate_session,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/reactivate",
    "reactivate_session",
    reactivate_session,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/person/<int:person_id>/attended",
    "get_person_attendance_ajax",
    get_person_attendance_ajax,
)
app.add_url_rule(
    "/api/person/<int:person_id>/logins",
    "get_person_logins_ajax",
    get_person_logins_ajax,
)
app.add_url_rule(
    "/api/person/<int:person_id>/tunes",
    "get_person_tunes_ajax",
    get_person_tunes_ajax,
)
app.add_url_rule(
    "/api/check-username-availability",
    "check_username_availability",
    check_username_availability,
    methods=["POST"],
)
app.add_url_rule(
    "/api/person/<int:person_id>/update",
    "update_person_details",
    update_person_details,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/admin/user/<int:user_id>/verify-email",
    "admin_verify_email",
    admin_verify_email,
    methods=["POST"],
)
app.add_url_rule(
    "/api/person/<int:person_id>/available-sessions",
    "get_available_sessions_for_person",
    get_available_sessions_for_person,
)
app.add_url_rule(
    "/api/person/<int:person_id>/search-sessions",
    "search_sessions_for_person",
    search_sessions_for_person,
    methods=["POST"],
)
app.add_url_rule(
    "/api/add-person-to-session",
    "add_person_to_session",
    add_person_to_session,
    methods=["POST"],
)
app.add_url_rule(
    "/api/validate-thesession-user",
    "validate_thesession_user",
    validate_thesession_user,
    methods=["POST"],
)
app.add_url_rule(
    "/api/parse-person-name", "parse_person_name", parse_person_name, methods=["POST"]
)
app.add_url_rule(
    "/api/create-person", "create_new_person", create_new_person, methods=["POST"]
)
app.add_url_rule("/api/sessions/list", "get_available_sessions", get_available_sessions)
app.add_url_rule(
    "/api/sessions/<path:session_path>/people",
    "get_session_people_list",
    get_session_people_list,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/people/<int:person_id>",
    "get_session_person_detail",
    get_session_person_detail,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/people/add",
    "add_person_to_session_people_tab",
    add_person_to_session_people_tab,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/people/search",
    "search_people_for_session",
    search_people_for_session,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/people/add-existing",
    "add_existing_person_to_session",
    add_existing_person_to_session,
    methods=["POST"],
)
app.add_url_rule(
    "/api/user/auto-save-preference",
    "update_auto_save_preference",
    update_auto_save_preference,
    methods=["POST"],
)

# Attendance tracking endpoints
app.add_url_rule(
    "/api/session_instance/<int:session_instance_id>/attendees",
    "get_session_attendees",
    get_session_attendees,
    methods=["GET"],
)
app.add_url_rule(
    "/api/session_instance/<int:session_instance_id>/attendees/checkin",
    "check_in_person",
    check_in_person,
    methods=["POST"],
)
app.add_url_rule(
    "/api/person",
    "create_person_with_instruments",
    create_person_with_instruments,
    methods=["POST"],
)
app.add_url_rule(
    "/api/person/<int:person_id>/instruments",
    "get_person_instruments",
    get_person_instruments,
    methods=["GET"],
)
app.add_url_rule(
    "/api/person/<int:person_id>/instruments",
    "update_person_instruments",
    update_person_instruments,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/session_instance/<int:session_instance_id>/attendees/<int:person_id>",
    "remove_person_attendance",
    remove_person_attendance,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/session/<int:session_id>/people/search",
    "search_session_people",
    search_session_people,
    methods=["GET"],
)
app.add_url_rule(
    "/api/session/<int:session_id>/people/session-people",
    "get_session_people",
    get_session_people,
    methods=["GET"],
)
app.add_url_rule(
    "/api/session/<int:session_id>/active_instance",
    "get_session_active_instance",
    get_session_active_instance,
    methods=["GET"],
)
app.add_url_rule(
    "/api/person/<int:person_id>/active_session",
    "get_person_active_session",
    get_person_active_session,
    methods=["GET"],
)

# Bulk import endpoints
app.add_url_rule(
    "/api/session/<int:session_id>/bulk-import/preprocess",
    "bulk_import_preprocess_session",
    bulk_import_preprocess_session,
    methods=["POST"],
)
app.add_url_rule(
    "/api/session/<int:session_id>/bulk-import/save",
    "bulk_import_save_session",
    bulk_import_save_session,
    methods=["POST"],
)

# Personal tune management endpoints
app.add_url_rule(
    "/api/my-tunes",
    "get_my_tunes",
    get_my_tunes,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-tunes/<int:person_tune_id>",
    "get_person_tune_detail",
    get_person_tune_detail,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-tunes/<int:person_tune_id>",
    "update_person_tune",
    update_person_tune,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/my-tunes/<int:person_tune_id>",
    "delete_person_tune",
    delete_person_tune,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/my-tunes",
    "add_my_tune",
    add_my_tune,
    methods=["POST"],
)

app.add_url_rule(
    "/api/my-tunes/<int:person_tune_id>/heard",
    "increment_tune_heard_count",
    increment_tune_heard_count,
    methods=["POST"],
)
app.add_url_rule(
    "/api/my-tunes/<int:person_tune_id>/heard",
    "decrement_tune_heard_count",
    decrement_tune_heard_count,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/my-tunes/sync",
    "sync_my_tunes",
    sync_my_tunes,
    methods=["POST"],
)
app.add_url_rule(
    "/api/my-tunes/common/<int:other_person_id>",
    "get_common_tunes",
    get_common_tunes,
    methods=["GET"],
)
app.add_url_rule(
    "/api/tunes/search",
    "search_tunes",
    search_tunes,
    methods=["GET"],
)
app.add_url_rule(
    "/api/person/me",
    "update_my_profile",
    update_my_profile,
    methods=["PATCH"],
)

# Session today status endpoints
app.add_url_rule(
    "/api/sessions/with-today-status",
    "get_sessions_with_today_status",
    get_sessions_with_today_status,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/instances/today",
    "create_or_get_today_session_instance",
    create_or_get_today_session_instance,
    methods=["POST"],
)

# QR Code generation endpoints
app.add_url_rule(
    "/api/qr/<int:session_id>",
    "generate_qr_code_with_session",
    generate_qr_code,
    methods=["GET"],
)
app.add_url_rule(
    "/api/qr",
    "generate_qr_code_general",
    lambda: generate_qr_code(0),
    methods=["GET"],
)

# Admin tunes API endpoints
app.add_url_rule(
    "/api/admin/tunes",
    "get_admin_tunes",
    get_admin_tunes,
    methods=["GET"],
)
app.add_url_rule(
    "/api/admin/tunes/<int:tune_id>",
    "get_admin_tune_detail",
    get_admin_tune_detail,
    methods=["GET"],
)
app.add_url_rule(
    "/api/admin/tunes/<int:tune_id>",
    "update_admin_tune",
    update_admin_tune,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/admin/tunes/<int:tune_id>/refresh_tunebook_count",
    "refresh_admin_tune_tunebook_count",
    refresh_admin_tune_tunebook_count,
    methods=["POST"],
)
app.add_url_rule(
    "/api/admin/cache_settings/run",
    "run_cache_settings",
    run_cache_settings,
    methods=["POST"],
)
app.add_url_rule(
    "/api/admin/cache_settings/stats",
    "get_cache_settings_stats",
    get_cache_settings_stats,
    methods=["GET"],
)

# Person tune management routes
app.add_url_rule(
    "/api/person/tunes/<int:tune_id>",
    "get_person_tune_status",
    get_person_tune_status,
    methods=["GET"],
)
app.add_url_rule(
    "/api/person/tunes",
    "add_person_tune",
    add_person_tune,
    methods=["POST"],
)
app.add_url_rule(
    "/api/person/tunes/<int:tune_id>/status",
    "update_person_tune_status",
    update_person_tune_status,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/person/tunes/<int:tune_id>/increment_heard",
    "increment_person_tune_heard_count",
    increment_person_tune_heard_count,
    methods=["PUT"],
)

# Error handlers
FUNNY_ERROR_TEXTS = ["Stroh Piano Accordion", "Traditional Irish Djembe"]

FUNNY_ERROR_IMAGES = [
    # Placeholder - you can add image filenames here later
    "stroh.avif",
    "djembe.avif",
]

def get_random_funny_content():
    """Get random funny text and image for error pages"""
    if FUNNY_ERROR_TEXTS:
        # Use single random index to pair text and image together
        index = random.randint(0, len(FUNNY_ERROR_TEXTS) - 1)
        funny_text = FUNNY_ERROR_TEXTS[index]
        funny_image = (
            FUNNY_ERROR_IMAGES[index] if index < len(FUNNY_ERROR_IMAGES) else None
        )
        return funny_text, funny_image
    return None, None

def render_error_page(message, status_code=400):
    """Helper function to render error page with consistent formatting"""
    funny_text, funny_image = get_random_funny_content()
    return (
        render_template(
            "error.html",
            error_message=message,
            funny_text=funny_text,
            funny_image=funny_image,
        ),
        status_code,
    )

@app.errorhandler(404)
def not_found_error(error):  # pylint: disable=unused-argument
    funny_text, funny_image = get_random_funny_content()
    return (
        render_template(
            "error.html",
            error_message="Page not found. The session you're looking for might have ended, or the URL might be incorrect.",
            funny_text=funny_text,
            funny_image=funny_image,
        ),
        404,
    )

@app.errorhandler(403)
def forbidden_error(error):  # pylint: disable=unused-argument
    funny_text, funny_image = get_random_funny_content()
    return (
        render_template(
            "error.html",
            error_message="You don't have permission to access this page. You might need to log in or contact an admin.",
            funny_text=funny_text,
            funny_image=funny_image,
        ),
        403,
    )

@app.errorhandler(401)
def unauthorized_error(error):  # pylint: disable=unused-argument
    funny_text, funny_image = get_random_funny_content()
    return (
        render_template(
            "error.html",
            error_message="You must be logged in to access this page. Please log in and try again.",
            funny_text=funny_text,
            funny_image=funny_image,
        ),
        401,
    )

@app.errorhandler(500)
def internal_error(error):  # pylint: disable=unused-argument
    funny_text, funny_image = get_random_funny_content()
    return (
        render_template(
            "error.html",
            error_message="A server error occurred. Our team has been notified and will look into this issue.",
            funny_text=funny_text,
            funny_image=funny_image,
        ),
        500,
    )

@app.errorhandler(Exception)
def handle_exception(error):
    """Catch all other unhandled exceptions"""
    funny_text, funny_image = get_random_funny_content()
    # Log the error for debugging (in production you'd want proper logging)
    print(f"Unhandled exception: {error}")
    return (
        render_template(
            "error.html",
            error_message=f"An unexpected error occurred: {str(error)}",
            funny_text=funny_text,
            funny_image=funny_image,
        ),
        500,
    )

if __name__ == "__main__":
    app.run(
        debug=True, port=5001, host="127.0.0.1", use_reloader=True, use_debugger=True
    )
