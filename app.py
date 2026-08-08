from flask import Flask, render_template, request, session, send_from_directory, redirect
from flask_login import LoginManager
from werkzeug.routing import BaseConverter
import os
import random
import logging
from datetime import timedelta
from dotenv import load_dotenv

# Import our custom modules
from auth import User, SESSION_LIFETIME_WEEKS
from api_auth import public_api
from api_routes import *
from web_routes import *
from recording_routes import (
    get_recording_segmenter,
    get_recording_peaks,
    put_recording_segment,
    delete_recording_segment,
    get_instance_recordings,
    get_instance_audio,
    download_recording_segment,
    export_recording_segments,
    create_recording_upload_url,
    create_recording,
    get_recording_status,
    reprocess_recording,
    delete_recording,
    get_session_instances_for_admin,
)
from api_person_tune_routes import (
    get_my_tunes,
    get_person_tune_detail,
    add_my_tune,
    update_person_tune,
    delete_person_tune,
    increment_tune_heard_count,
    decrement_tune_heard_count,
    my_tunes_op,
    set_instrument_auto,
    get_popular_tunes,
    get_offline_bundle,
    get_my_sessions,
    sync_my_tunes,
    search_tunes,
    update_my_profile,
    get_common_tunes
)
from live_logging_routes import live_bootstrap, live_vocabulary, live_op, live_issue_token, live_tune_detail, live_people, live_deep_search, live_incipit, live_match, live_thesession_search, my_tunes_deep_search, my_tunes_thesession_search, my_tunes_incipit, session_tunes_deep_search, session_tunes_thesession_search, session_tunes_incipit, live_tune_preview, my_tunes_tune_preview, session_tunes_tune_preview, live_setting_image, my_tunes_setting_image, session_tunes_setting_image, live_thesession_preview, my_tunes_thesession_preview, session_tunes_thesession_preview, live_render_abc, my_tunes_render_abc, session_tunes_render_abc
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

# Share the session cookie across subdomains so the live-logging streaming sidecar
# (e.g. streaming.ceol.io) receives it (spec 024 §H / §A4). Subdomains of one
# registrable domain are same-site, so default SameSite=Lax still flows; we only
# need to broaden the cookie's Domain and mark it Secure in prod. Both are
# env-driven so local dev (env unset) keeps today's host-only, non-Secure cookie.
_cookie_domain = os.environ.get("SESSION_COOKIE_DOMAIN")  # e.g. ".ceol.io" in prod
if _cookie_domain:
    app.config['SESSION_COOKIE_DOMAIN'] = _cookie_domain
    app.config['REMEMBER_COOKIE_DOMAIN'] = _cookie_domain
if os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes"):
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['REMEMBER_COOKIE_SECURE'] = True

# Configure Flask to handle trailing slashes consistently
app.url_map.strict_slashes = False

# Serve static design mockups from the repo-root /mockups directory as
# self-contained mini-sites, e.g. /mockups/logging/ -> mockups/logging/index.html
MOCKUPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mockups")

def mockup_index(mockup):
    # ensure a trailing slash so the page's relative asset paths resolve correctly
    if not request.path.endswith("/"):
        return redirect(request.path + "/")
    return send_from_directory(MOCKUPS_DIR, os.path.join(mockup, "index.html"))

def mockup_file(mockup, filename):
    return send_from_directory(MOCKUPS_DIR, os.path.join(mockup, filename))

app.add_url_rule("/mockups/<mockup>/", "mockup_index", mockup_index)
app.add_url_rule("/mockups/<mockup>/<path:filename>", "mockup_file", mockup_file)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # type: ignore
login_manager.login_message = "Please log in to access this page."

@login_manager.user_loader
def load_user(user_id):
    """Resolve the signed session cookie's user id.

    Returning None means "not logged in", which is the right answer for a cookie
    this app did not mint -- and it WILL see some. Cookies are scoped by host and
    ignore the port, so every other Flask app on localhost shares this jar and
    the last one to log in wins the `session` cookie. A neighbour that keys users
    by UUID used to take the whole site down with

        ValueError: invalid literal for int() with base 10: '00000000-...-0001'

    on every request, since this runs before any route. A foreign cookie should
    log you out, not 500 you, so anything unparseable is simply nobody.
    """
    try:
        return User.get_by_id(int(user_id))
    except (TypeError, ValueError):
        return None

@login_manager.request_loader
def load_user_from_request(req):
    """Authenticate `Authorization: Bearer <user_session id>` against /api/* (spec 035).

    The tokens are minted by /api/live/token (live_issue_token -> auth.create_session)
    and were already honored by the streaming sidecar; this makes Flask honor them too.
    Mirrors the sidecar's validation (streaming/service.py, _user_id_from_bearer).
    Cookie sessions keep flowing through user_loader; this only runs when the session
    cookie is absent or invalid.
    """
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    from database import get_db_connection
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id FROM user_session
            WHERE session_id = %s AND expires_at > (NOW() AT TIME ZONE 'UTC')
            """,
            (token,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return User.get_by_id(row[0])

@app.context_processor
def inject_canonical_instruments():
    """Expose the single canonical instrument list to every template so all
    instrument pickers render from one source (see instruments.py)."""
    from instruments import CANONICAL_INSTRUMENTS
    return {"canonical_instruments": CANONICAL_INSTRUMENTS}

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
app.add_url_rule("/help/sessions", "help_sessions", help_sessions)
app.add_url_rule("/help/offline", "help_offline", help_offline)
app.add_url_rule("/help/my-tunes", "help_my_tunes", help_my_tunes)
app.add_url_rule("/help/session-tracking/tunes", "help_session_tunes", help_session_tunes)
app.add_url_rule("/help/session-tracking/logs", "help_session_logs", help_session_logs)
app.add_url_rule("/help/session-tracking/members", "help_session_members", help_session_members)
app.add_url_rule("/help/session-tracking/live-logger", "help_live_logger", help_live_logger)
app.add_url_rule("/help/release-notes/", "help_release_notes_index", help_release_notes_index)
app.add_url_rule("/help/release-notes/<month>", "help_release_notes", help_release_notes)
app.add_url_rule("/share", "share_page", share_page)
app.add_url_rule("/register", "register", register, methods=["GET", "POST"])
app.add_url_rule("/login", "login", login, methods=["GET", "POST"])
app.add_url_rule("/logout", "logout", logout)
# public_api: the login flow itself — necessarily unauthenticated (handlers live in web_routes.py)
app.add_url_rule("/api/auth/check-email", "check_email_api", public_api(check_email_api), methods=["POST"])
app.add_url_rule("/api/auth/login-password", "login_password_api", public_api(login_password_api), methods=["POST"])
app.add_url_rule("/auth/login/<token>", "login_with_token", login_with_token)
app.add_url_rule("/auth/set-password", "set_password_optional", set_password_optional, methods=["GET", "POST"])
app.add_url_rule("/auth/setup-profile", "setup_profile", setup_profile, methods=["GET", "POST"])
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
    "/unsubscribe/<token>",
    "unsubscribe_updates",
    unsubscribe_updates,
    methods=["GET", "POST"],
)
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
app.add_url_rule("/admin/activity", "admin_activity", admin_activity)
app.add_url_rule("/admin/people", "admin_people", admin_people)
app.add_url_rule("/admin/tunes", "admin_tunes", admin_tunes)
app.add_url_rule("/admin/tunes/merge", "admin_tune_merge", admin_tune_merge)
app.add_url_rule("/admin/tunes/<int:tune_id>", "admin_tune_detail", admin_tune_detail)
app.add_url_rule("/admin/test-links", "admin_test_links", admin_test_links)
app.add_url_rule("/admin/cache-settings", "admin_cache_settings", admin_cache_settings)
app.add_url_rule("/admin/email-updates", "admin_email_updates", admin_email_updates)
app.add_url_rule("/admin/people/<int:person_id>", "person_details", person_details)
app.add_url_rule("/admin/sessions/<path:session_path>", "session_admin", session_admin)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/people",
    "session_admin_players",
    session_admin_players,
)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/people/<int:person_id>",
    "session_admin_person",
    session_admin_person,
)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/tunes", "session_admin_tunes", session_admin_tunes
)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/logs", "session_admin_logs", session_admin_logs
)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/cache", "session_admin_cache", session_admin_cache
)
app.add_url_rule(
    "/admin/sessions/<path:session_path>/bulk-import",
    "session_admin_bulk_import",
    session_admin_bulk_import,
)

# Page-payload endpoints (spec 035 Step 5): the same serializer output the
# person-details and session-admin page shells embed.
app.add_url_rule(
    "/api/me/details",
    "get_me_details",
    get_person_details_api,
    methods=["GET"],
)
app.add_url_rule(
    "/api/admin/people/<int:person_id>/details",
    "get_person_details_api",
    get_person_details_api,
    methods=["GET"],
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/admin-detail",
    "get_session_admin_detail",
    get_session_admin_detail,
    methods=["GET"],
)
app.add_url_rule(
    "/api/add-session",
    "get_add_session_payload",
    get_add_session_payload,
    methods=["GET"],
)
app.add_url_rule(
    "/api/admin/people",
    "get_admin_people_api",
    get_admin_people_api,
    methods=["GET"],
)
app.add_url_rule(
    "/api/admin/people/merge",
    "merge_people",
    merge_people,
    methods=["POST"],
)

# Register API routes
# Live logging (spec 024) -- referee op endpoints + screen shell (Phase 0)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/bootstrap",
    "live_bootstrap",
    live_bootstrap,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/vocabulary",
    "live_vocabulary",
    live_vocabulary,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/ops",
    "live_op",
    live_op,
    methods=["POST"],
)
app.add_url_rule(
    "/api/live/token",
    "live_issue_token",
    live_issue_token,
    methods=["POST"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/tune/<int:tune_id>",
    "live_tune_detail",
    live_tune_detail,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/people",
    "live_people",
    live_people,
    methods=["GET"],
)
# Spec 034: /people/search is GONE. It ILIKE'd across every active person in the database,
# so anyone could enumerate people from sessions they had nothing to do with. The picker's
# universe is now this session's roster (returned whole by /people) and it filters locally.
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/deep-search",
    "live_deep_search",
    live_deep_search,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/incipit/<int:tune_id>",
    "live_incipit",
    live_incipit,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/match",
    "live_match",
    live_match,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/thesession-search",
    "live_thesession_search",
    live_thesession_search,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/tune-preview/<int:tune_id>",
    "live_tune_preview",
    live_tune_preview,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/setting-image/<int:setting_id>",
    "live_setting_image",
    live_setting_image,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/thesession-preview/<int:thesession_id>",
    "live_thesession_preview",
    live_thesession_preview,
    methods=["GET"],
)
app.add_url_rule(
    "/api/live/instances/<int:session_instance_id>/render-abc",
    "live_render_abc",
    live_render_abc,
    methods=["POST"],
)
app.add_url_rule(
    "/live/instances/<int:session_instance_id>",
    "live_logging_screen",
    live_logging_screen,
)

# Serve the live-screen service worker at /live/sw.js so its scope is /live/
# (it must control /live/instances/* navigations). Kept no-store so SW updates
# are picked up promptly.
def live_service_worker():
    resp = send_from_directory(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
        "live-sw.js",
        mimetype="application/javascript",
    )
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

app.add_url_rule("/live/sw.js", "live_service_worker", live_service_worker)


# Serve the main-app service worker at /sw.js so its scope is the whole origin
# (it must control all navigations except /live/, which has its own worker). Kept
# no-store so SW updates are picked up promptly.
def app_service_worker():
    resp = send_from_directory(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
        "service-worker.js",
        mimetype="application/javascript",
    )
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

app.add_url_rule("/sw.js", "app_service_worker", app_service_worker)


# Minimal, self-contained offline fallback shown by the service worker when an
# uncached page is requested with no connection. No template inheritance so it has
# zero asset dependencies.
def offline_page():
    return render_template("offline.html")

app.add_url_rule("/offline", "offline_page", offline_page)


# --- Versioned static assets (site-wide slow-network snappiness) -----------------
# Every url_for('static', ...) URL gets a content-hash ?v=<sha1[:8]>, and responses to
# v-stamped /static/ requests get a far-future immutable Cache-Control. The URL changes
# whenever the file's content changes, so long-lived caching can never serve a stale
# build — the same guarantee as filename fingerprinting, without renaming build outputs.
# Both service workers additionally serve v-stamped /static/ URLs CACHE-FIRST (exact
# URL match), so on a slow connection a page load only waits for the HTML document.
import hashlib

_static_versions = {}  # filename -> (mtime, size, hash) — mtime/size guard picks up dev rebuilds


def _static_version(filename):
    try:
        path = os.path.normpath(os.path.join(app.static_folder, filename))
        if not path.startswith(os.path.normpath(app.static_folder) + os.sep):
            return None
        st = os.stat(path)
        cached = _static_versions.get(filename)
        if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
            return cached[2]
        with open(path, "rb") as f:
            digest = hashlib.sha1(f.read()).hexdigest()[:8]
        _static_versions[filename] = (st.st_mtime, st.st_size, digest)
        return digest
    except OSError:
        return None


@app.url_defaults
def _stamp_static_version(endpoint, values):
    if endpoint == "static" and "filename" in values and "v" not in values:
        v = _static_version(values["filename"])
        if v:
            values["v"] = v


@app.after_request
def _immutable_versioned_static(resp):
    if request.path.startswith("/static/") and request.args.get("v") and resp.status_code == 200:
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp

# /api/sessions/data (positional-tuple sessions list) deleted — zero UI callers;
# /api/sessions/with-today-status is the serialized replacement (spec 035 follow-up).
app.add_url_rule(
    "/api/sessions/<path:session_path>/logs",
    "get_session_logs",
    get_session_logs,
    methods=["GET"],
)
# The Logs tab's tune filter. Deliberately NOT under .../tunes: that prefix is
# already a thicket of greedy <path:session_path> rules, and "logged-tunes" is
# the distinct thing anyway (tunes that appear in the logs, not the repertoire).
app.add_url_rule(
    "/api/sessions/<path:session_path>/logged-tunes",
    "get_session_logged_tunes",
    get_session_logged_tunes,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/logged-tunes/<int:tune_id>/instances",
    "get_session_tune_log_instances",
    get_session_tune_log_instances,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/remaining",
    "get_session_tunes_remaining",
    get_session_tunes_remaining,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/detail",
    "get_session_detail",
    get_session_detail,
    methods=["GET"],
)

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
    "/api/tunes/<int:tune_id>/incipit",
    "get_tune_incipit",
    get_tune_incipit,
    methods=["GET"],
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
    "/api/sessions/<path:session_path>/tunes/<int:tune_id>",
    "delete_session_tune",
    delete_session_tune,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes",
    "add_session_tune",
    add_session_tune,
    methods=["POST"],
)
# Add-to-session-tunes pane: the live screen's deep search, session-path flavor.
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/deep-search",
    "session_tunes_deep_search",
    session_tunes_deep_search,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/thesession-search",
    "session_tunes_thesession_search",
    session_tunes_thesession_search,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/incipit/<int:tune_id>",
    "session_tunes_incipit",
    session_tunes_incipit,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/tune-preview/<int:tune_id>",
    "session_tunes_tune_preview",
    session_tunes_tune_preview,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/setting-image/<int:setting_id>",
    "session_tunes_setting_image",
    session_tunes_setting_image,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/thesession-preview/<int:thesession_id>",
    "session_tunes_thesession_preview",
    session_tunes_thesession_preview,
    methods=["GET"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/tunes/render-abc",
    "session_tunes_render_abc",
    session_tunes_render_abc,
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
    "/api/admin/sessions/<path:session_path>/tune-cache",
    "session_tune_cache_preview",
    session_tune_cache_preview,
    methods=["GET"],
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
    "/api/session_instance/<int:session_instance_id>/sets/<int:set_index>/started_by",
    "update_set_started_by",
    update_set_started_by,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id:date_or_id>/update",
    "update_session_instance_ajax",
    update_session_instance_ajax,
    methods=["PUT"],
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
    "/api/sessions/delete_tune/<int:session_instance_tune_id>",
    "delete_tune_ajax",
    delete_tune_ajax,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/<date_or_id>/link_tune",
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
    "/api/tunes/<int:tune_id>/detail",
    "get_tune_detail_global",
    get_tune_detail_global,
    methods=["GET"],
)
app.add_url_rule(
    "/api/tunes/<int:tune_id>/history",
    "get_tune_history",
    get_tune_history,
    methods=["GET"],
)
app.add_url_rule(
    "/api/tunes/<int:tune_id>/played-with",
    "get_tune_played_with",
    get_tune_played_with,
    methods=["GET"],
)
app.add_url_rule(
    "/api/users/<int:user_id>/beta-logging",
    "set_beta_logging",
    set_beta_logging,
    methods=["POST"],
)
app.add_url_rule(
    "/api/admin/instances/<int:session_instance_id>/logging-mode",
    "admin_reset_logging_mode",
    admin_reset_logging_mode,
    methods=["POST"],
)
app.add_url_rule(
    "/api/admin/email-updates/test",
    "admin_email_updates_test",
    admin_email_updates_test,
    methods=["POST"],
)
app.add_url_rule(
    "/api/admin/email-updates/send",
    "admin_email_updates_send",
    admin_email_updates_send,
    methods=["POST"],
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
    "/api/admin/sessions/<path:session_path>/people",
    "get_session_players_ajax",
    get_session_players_ajax,
)
# Spec 034: .../people/<id>/regular is GONE. is_regular no longer exists; its successor is
# the session-scoped /people/<id>/relationship setter (below), which any session admin may
# use -- not just system admins, which was an oversight rather than a decision.
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/people/<int:person_id>/admin",
    "update_session_player_admin_status",
    update_session_player_admin_status,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/people/<int:person_id>/details",
    "update_session_player_details",
    update_session_player_details,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/people/<int:person_id>",
    "delete_session_player",
    delete_session_player,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/leave",
    "leave_session_membership",
    leave_session_membership,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/logs",
    "get_session_logs_ajax",
    get_session_logs_ajax,
)
app.add_url_rule(
    "/api/admin/sessions/<path:session_path>/tunes",
    "get_session_tunes_grid_ajax",
    get_session_tunes_grid_ajax,
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
    "/api/person/<int:person_id>/tunes-stats",
    "get_person_tunes_stats",
    get_person_tunes_stats,
)
app.add_url_rule(
    "/api/person/<int:person_id>/tunes",
    "get_person_tunes_list",
    get_person_tunes_list,
)
app.add_url_rule(
    "/api/person/<int:person_id>/logged-tunes",
    "get_person_logged_tunes",
    get_person_logged_tunes,
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
    "/api/admin/person/<int:person_id>/active",
    "toggle_person_active",
    toggle_person_active,
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
    "validate_thesession_entity",
    validate_thesession_entity,
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
# Spec 034: /people/search and /people/add-existing are GONE. They searched every person in
# the system (minus this session's roster), which let anyone with an account enumerate people
# from other sessions. There is no global person search: you filter this session's roster, and
# anyone else you type in fresh.
app.add_url_rule(
    "/api/sessions/<path:session_path>/people/<int:person_id>/relationship",
    "set_session_person_relationship",
    set_session_person_relationship,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/people/<int:person_id>/confirmed",
    "set_session_person_confirmed",
    set_session_person_confirmed,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/people/<int:person_id>/archived",
    "set_session_person_archived",
    set_session_person_archived,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/sessions/<path:session_path>/join",
    "join_session",
    join_session,
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
    "/api/person/<int:person_id>/instrument-auto",
    "set_person_instrument_auto",
    set_person_instrument_auto,
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
    "/api/my-tunes/ops",
    "my_tunes_op",
    my_tunes_op,
    methods=["POST"],
)
app.add_url_rule(
    "/api/my-tunes/instrument-auto",
    "set_instrument_auto",
    set_instrument_auto,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/my-tunes/sync",
    "sync_my_tunes",
    sync_my_tunes,
    methods=["POST"],
)
# Add-to-My-Tunes pane: the live screen's deep search, personal (session-less) flavor.
app.add_url_rule(
    "/api/my-tunes/deep-search",
    "my_tunes_deep_search",
    my_tunes_deep_search,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-tunes/thesession-search",
    "my_tunes_thesession_search",
    my_tunes_thesession_search,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-tunes/incipit/<int:tune_id>",
    "my_tunes_incipit",
    my_tunes_incipit,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-tunes/tune-preview/<int:tune_id>",
    "my_tunes_tune_preview",
    my_tunes_tune_preview,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-tunes/setting-image/<int:setting_id>",
    "my_tunes_setting_image",
    my_tunes_setting_image,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-tunes/thesession-preview/<int:thesession_id>",
    "my_tunes_thesession_preview",
    my_tunes_thesession_preview,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-tunes/render-abc",
    "my_tunes_render_abc",
    my_tunes_render_abc,
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
    "/api/tunes/popular",
    "get_popular_tunes",
    get_popular_tunes,
    methods=["GET"],
)
app.add_url_rule(
    "/api/my-sessions",
    "get_my_sessions",
    get_my_sessions,
    methods=["GET"],
)
app.add_url_rule(
    "/api/offline/bundle",
    "get_offline_bundle",
    get_offline_bundle,
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
    public_api(lambda: generate_qr_code(0)),  # backs the public /share page QR image
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
    "/api/admin/tunes/merge",
    "merge_tune",
    merge_tune,
    methods=["POST"],
)
app.add_url_rule(
    "/api/admin/tunes/merge-scan",
    "start_merge_scan",
    start_merge_scan,
    methods=["POST"],
)
app.add_url_rule(
    "/api/admin/tunes/merge-scan",
    "get_merge_scan",
    get_merge_scan,
    methods=["GET"],
)
app.add_url_rule(
    "/api/admin/tunes/merge-scan",
    "cancel_merge_scan",
    cancel_merge_scan,
    methods=["DELETE"],
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
app.add_url_rule(
    "/api/admin/history/<entity_type>/<path:entity_id>",
    "api_admin_history",
    api_admin_history,
    methods=["GET"],
)

app.add_url_rule(
    "/api/user/admin-sessions",
    "get_user_admin_sessions",
    get_user_admin_sessions,
    methods=["GET"],
)
app.add_url_rule(
    "/api/tunes/copy",
    "copy_tunes_to_destination",
    copy_tunes_to_destination,
    methods=["POST"],
)

# Recording segmenter (spec 050): audio -> per-tune timestamps, the data-prep
# step for the eventual tune-recognition model. All system-admin only.
app.add_url_rule(
    "/admin/recordings",
    "admin_recordings",
    admin_recordings,
)
app.add_url_rule(
    "/admin/recordings/<int:recording_id>/segment",
    "segment_recording",
    segment_recording,
)
app.add_url_rule(
    "/api/recordings/<int:recording_id>/segmenter",
    "get_recording_segmenter",
    get_recording_segmenter,
    methods=["GET"],
)
# In-app upload: sign, confirm, then poll while the waveform and proxy are built.
# The audio itself goes browser -> S3 and never touches Flask.
app.add_url_rule(
    "/api/recordings/upload-url",
    "create_recording_upload_url",
    create_recording_upload_url,
    methods=["POST"],
)
app.add_url_rule(
    "/api/recordings",
    "create_recording",
    create_recording,
    methods=["POST"],
)
app.add_url_rule(
    "/api/recordings/<int:recording_id>/status",
    "get_recording_status",
    get_recording_status,
    methods=["GET"],
)
app.add_url_rule(
    "/api/recordings/<int:recording_id>/reprocess",
    "reprocess_recording",
    reprocess_recording,
    methods=["POST"],
)
app.add_url_rule(
    "/api/recordings/<int:recording_id>",
    "delete_recording",
    delete_recording,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/admin/sessions/<int:session_id>/instances",
    "get_session_instances_for_admin",
    get_session_instances_for_admin,
    methods=["GET"],
)
app.add_url_rule(
    "/api/recordings/<int:recording_id>/peaks",
    "get_recording_peaks",
    get_recording_peaks,
    methods=["GET"],
)
app.add_url_rule(
    "/api/recordings/<int:recording_id>/segments/<int:session_instance_tune_id>",
    "put_recording_segment",
    put_recording_segment,
    methods=["PUT"],
)
app.add_url_rule(
    "/api/recordings/<int:recording_id>/segments/<int:session_instance_tune_id>",
    "delete_recording_segment",
    delete_recording_segment,
    methods=["DELETE"],
)
app.add_url_rule(
    "/api/recordings/<int:recording_id>/export",
    "export_recording_segments",
    export_recording_segments,
    methods=["GET"],
)
app.add_url_rule(
    "/api/session-instances/<int:session_instance_id>/recordings",
    "get_instance_recordings",
    get_instance_recordings,
    methods=["GET"],
)
# Playback: the read side of the segmenter's work, for the session-instance page.
app.add_url_rule(
    "/api/session-instances/<int:session_instance_id>/audio",
    "get_instance_audio",
    get_instance_audio,
    methods=["GET"],
)
# One tune, cut out of the master as a file. The only audio that goes through Flask.
app.add_url_rule(
    "/api/recordings/<int:recording_id>/segments/<int:session_instance_tune_id>/download",
    "download_recording_segment",
    download_recording_segment,
    methods=["GET"],
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
        debug=True, port=5002, host="127.0.0.1", use_reloader=True, use_debugger=True
    )
