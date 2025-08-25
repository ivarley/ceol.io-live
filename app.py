from flask import Flask, render_template
from flask_login import LoginManager
import os
import random
from dotenv import load_dotenv

# Import our custom modules
from auth import User
from api_routes import *
from web_routes import *
from timezone_utils import format_datetime_with_timezone, utc_to_local
from flask_login import current_user

load_dotenv()

app = Flask(__name__)
# Secret key required for Flask sessions (used by flash messages to store temporary messages in signed cookies)
app.secret_key = os.environ.get(
    "FLASK_SESSION_SECRET_KEY", "dev-secret-key-change-in-production"
)

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
app.add_url_rule("/sessions/<path:full_path>", "session_handler", session_handler)
app.add_url_rule("/add-session", "add_session", add_session)
app.add_url_rule("/help", "help_page", help_page)
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
app.add_url_rule("/verify-email/<token>", "verify_email", verify_email)
app.add_url_rule(
    "/resend-verification",
    "resend_verification",
    resend_verification,
    methods=["GET", "POST"],
)
app.add_url_rule("/admin", "admin", admin)
app.add_url_rule("/admin/sessions", "admin_sessions", admin_sessions)
app.add_url_rule("/admin/login-history", "admin_login_history", admin_login_history)
app.add_url_rule("/admin/people", "admin_people", admin_people)
app.add_url_rule("/admin/test-links", "admin_test_links", admin_test_links)
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

# Register API routes
app.add_url_rule("/api/sessions/data", "sessions_data", sessions_data)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/<int:tune_id>/refresh_tunebook_count",
    "refresh_tunebook_count_ajax",
    refresh_tunebook_count_ajax,
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
    "/api/sessions/<path:session_path>/<date>/update",
    "update_session_instance_ajax",
    update_session_instance_ajax,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/tune_count",
    "get_session_tune_count_ajax",
    get_session_tune_count_ajax,
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/delete",
    "delete_session_instance_ajax",
    delete_session_instance_ajax,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/mark_complete",
    "mark_session_log_complete_ajax",
    mark_session_log_complete_ajax,
    methods=["POST"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date>/mark_incomplete",
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
    "/api/sessions/<path:session_path>/<date>/match_tune",
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
    "/api/sessions/<path:session_path>/<date>/save_tunes",
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
    "/api/person/<int:person_id>/attendance",
    "get_person_attendance_ajax",
    get_person_attendance_ajax,
)
app.add_url_rule(
    "/api/person/<int:person_id>/logins",
    "get_person_logins_ajax",
    get_person_logins_ajax,
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
    "/api/user/auto-save-preference",
    "update_auto_save_preference",
    update_auto_save_preference,
    methods=["POST"],
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
