"""The app-shell API (spec 052 A1/A2/A7): everything a native client needs before it
can render a screen, and nothing a page already serves.

- The auth handshake: token-returning login (shared with web_routes.login_password_api
  via establish_session), the one-time-token exchange behind magic-link and
  verification Universal Links, logout, resend-verification, set-password.
- Identity and config: GET /api/me, GET /api/me/profile + PUT (the JSON twin of
  /auth/setup-profile), GET /api/app-config.
- GET /api/home — the home screen payload (serializers.build_home_payload, the same
  dict the Jinja home renders).
- GET /api/resolve — turns a ceol.io URL/path into ids, so a client opening a
  Universal Link never re-implements web_routes.session_handler's path rules.
- POST /api/auth/web-session — app -> web handoff for admin/help (mints a one-time
  login link).

Every handler here returns JSON only; the cookie is set only when the caller is the
web (api_auth.is_native_client() false). A native caller gets a Bearer token — the
same user_session row a cookie session records — and never a Set-Cookie.
"""

import os
import re
from datetime import timedelta

import bcrypt
from flask import jsonify, request, session, url_for
from flask_login import current_user, login_user, logout_user

from api_auth import (
    api_error,
    api_login_required,
    current_client,
    is_native_client,
    public_api,
    request_client_info,
)
from auth import (
    User,
    cleanup_expired_sessions,
    create_session,
    generate_login_token,
    generate_verification_token,
    log_login_event,
    needs_profile_setup,
)
from database import get_db_connection, save_to_history
from email_utils import send_verification_email
from instruments import CANONICAL_INSTRUMENTS, normalize_instruments
from timezone_utils import now_utc


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def user_payload(user, *, profile_incomplete=None):
    """The identity block every login response and GET /api/me carry."""
    if profile_incomplete is None:
        profile_incomplete = needs_profile_setup(user.person_id)
    return {
        "user_id": user.user_id,
        "person_id": user.person_id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_system_admin": bool(user.is_system_admin),
        "timezone": user.timezone or "UTC",
        "email_verified": bool(user.email_verified),
        "has_password": bool(user.has_password()),
        "needs_profile_setup": bool(profile_incomplete),
    }


def _next_step(user, profile_incomplete):
    """What the web flow redirects to after a fresh login, as a value the app can
    switch on: the optional password prompt for magic-link users, then profile setup."""
    if not user.has_password():
        return "set_password"
    if profile_incomplete:
        return "setup_profile"
    return None


def _cache_admin_session_ids(user):
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
        session["admin_session_ids"] = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def establish_session(user, method, identifier=None):
    """Record a successful login the way every web login path does — a user_session
    row, a LOGIN_SUCCESS login_history row, expired-session cleanup — and return the
    JSON body for it.

    Web caller (no/`web` X-Ceol-Client): also logs the user in with Flask-Login so
    the cookie is set; body carries no token.
    Native caller: no cookie at all; body carries the user_session id as a Bearer
    token, which app.py's request_loader and the streaming sidecar both honor.
    """
    native = is_native_client()
    ip_address, user_agent = request_client_info()
    session_id = create_session(user.user_id, ip_address, user_agent)
    log_login_event(
        user.user_id,
        identifier or user.email or user.username,
        "LOGIN_SUCCESS",
        ip_address,
        user_agent,
        session_id=session_id,
        additional_data={"method": method, "client": current_client()["platform"]},
    )
    if not native:
        login_user(user, remember=True)
        session.permanent = True
        session["db_session_id"] = session_id
        _cache_admin_session_ids(user)
    cleanup_expired_sessions()

    profile_incomplete = needs_profile_setup(user.person_id)
    body = {
        "success": True,
        "user": user_payload(user, profile_incomplete=profile_incomplete),
        "next": _next_step(user, profile_incomplete),
        "method": method,
    }
    if native:
        body["token"] = session_id
        body["token_type"] = "Bearer"
    return body


# ---------------------------------------------------------------------------
# POST /api/auth/exchange — one-time token -> session (magic link / verification)
# ---------------------------------------------------------------------------


@public_api  # the login flow itself: consumes a one-time emailed token
def auth_exchange():
    """Consume a magic-link login token OR an email-verification token and start a
    session (spec 052 A1.2).

    The web reaches these tokens by clicking /auth/login/<token> and
    /verify-email/<token>. A native app registers both as Universal Links, so the
    tap opens the app instead of Safari — and the app then POSTs the token here.
    Both token kinds are accepted so the app has one call, whichever email the
    person tapped; the response's `method` says which it was.
    """
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return api_error("token is required", 400, "missing_token")

    ip_address, user_agent = request_client_info()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Magic-link login token (15-minute expiry, set by check-email).
        cur.execute(
            """
            SELECT user_id FROM user_account
            WHERE login_token = %s AND login_token_expires > %s
            """,
            (token, now_utc()),
        )
        row = cur.fetchone()
        method = "magic_link"
        if not row:
            # Email-verification token (24-hour expiry, set at registration / resend).
            cur.execute(
                """
                SELECT user_id FROM user_account
                WHERE verification_token = %s AND verification_token_expires > %s
                  AND email_verified = FALSE
                """,
                (token, now_utc()),
            )
            row = cur.fetchone()
            method = "email_verification"
        if not row:
            log_login_event(
                None,
                None,
                "LOGIN_FAILURE",
                ip_address,
                user_agent,
                failure_reason="INVALID_LOGIN_TOKEN",
            )
            return api_error(
                "Invalid or expired link. Please request a new one.",
                401,
                "invalid_token",
            )
        user_id = row[0]

        if method == "magic_link":
            cur.execute(
                """
                UPDATE user_account
                SET login_token = NULL, login_token_expires = NULL, last_modified_date = %s
                WHERE user_id = %s
                """,
                (now_utc(), user_id),
            )
        else:
            save_to_history(cur, "user_account", "UPDATE", user_id, user_id=None)
            cur.execute(
                """
                UPDATE user_account
                SET email_verified = TRUE, verification_token = NULL,
                    verification_token_expires = NULL,
                    last_modified_date = %s, last_modified_user_id = NULL
                WHERE user_id = %s
                """,
                (now_utc(), user_id),
            )
        conn.commit()
    finally:
        conn.close()

    user = User.get_by_id(user_id)
    if not user or not user.is_active:
        return api_error("This account has been deactivated.", 403, "account_inactive")
    return jsonify(establish_session(user, method))


# ---------------------------------------------------------------------------
# POST /api/auth/resend-verification
# ---------------------------------------------------------------------------


@public_api  # pre-login by definition; never reveals whether the address exists
def auth_resend_verification():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return api_error("Email address is required", 400, "missing_email")

    generic = {
        "success": True,
        "message": "If an unverified account with that email exists, a verification email has been sent.",
    }
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ua.user_id, ua.username, p.first_name, p.last_name, ua.user_email
            FROM user_account ua
            JOIN person p ON ua.person_id = p.person_id
            WHERE LOWER(ua.user_email) = LOWER(%s) AND ua.email_verified = FALSE AND ua.is_active = TRUE
            """,
            (email,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify(generic)
        token = generate_verification_token()
        expires = now_utc() + timedelta(hours=24)
        save_to_history(cur, "user_account", "UPDATE", row[0], user_id=None)
        cur.execute(
            """
            UPDATE user_account
            SET verification_token = %s, verification_token_expires = %s, last_modified_user_id = NULL
            WHERE user_id = %s
            """,
            (token, expires, row[0]),
        )
        conn.commit()
    finally:
        conn.close()

    user = User(row[0], None, row[1], email=row[4], first_name=row[2], last_name=row[3])
    send_verification_email(user, token)
    return jsonify(generic)


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------


@api_login_required
def auth_logout():
    """Revoke the calling session: the Bearer token if one was presented, else the
    cookie session's user_session row. Idempotent — a second call is a 401 (no
    session), which is the truthful answer."""
    ip_address, user_agent = request_client_info()
    auth_header = request.headers.get("Authorization", "")
    token = (
        auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else None
    )
    db_session_id = token or session.get("db_session_id")

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
    log_login_event(
        current_user.user_id,
        current_user.username,
        "LOGOUT",
        ip_address,
        user_agent,
        session_id=db_session_id,
    )
    if not token:
        session.clear()
    # Always: drops Flask-Login's per-context user cache too, so a token caller is
    # anonymous from this instant even inside one long-lived app context.
    logout_user()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# POST /api/auth/set-password  (the optional step after a magic-link login)
# ---------------------------------------------------------------------------


@api_login_required
def auth_set_password():
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    if len(password) < 8:
        return api_error(
            "Password must be at least 8 characters.", 400, "password_too_short"
        )
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
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
        cur.execute(
            """
            UPDATE user_account
            SET hashed_password = %s, last_modified_date = %s, last_modified_user_id = %s
            WHERE user_id = %s
            """,
            (hashed, now_utc(), current_user.user_id, current_user.user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# GET /api/me
# ---------------------------------------------------------------------------


@api_login_required
def api_me():
    return jsonify({"success": True, "user": user_payload(current_user)})


# ---------------------------------------------------------------------------
# GET|PUT /api/me/profile — the JSON twin of /auth/setup-profile
# ---------------------------------------------------------------------------

_TIMEZONE_CHOICES = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "America/Toronto",
    "America/Vancouver",
    "America/Phoenix",
    "Europe/London",
    "Europe/Dublin",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Rome",
    "Europe/Madrid",
    "Europe/Amsterdam",
    "Australia/Sydney",
    "Australia/Melbourne",
    "Australia/Perth",
    "Pacific/Auckland",
    "Asia/Tokyo",
    "Asia/Singapore",
]


def _load_profile(cur, person_id, user_id):
    cur.execute(
        "SELECT first_name, last_name, city, state, country FROM person WHERE person_id = %s",
        (person_id,),
    )
    p = cur.fetchone() or ("", "", None, None, None)
    cur.execute("SELECT timezone FROM user_account WHERE user_id = %s", (user_id,))
    tz = (cur.fetchone() or ["UTC"])[0] or "UTC"
    cur.execute(
        "SELECT instrument FROM person_instrument WHERE person_id = %s ORDER BY instrument",
        (person_id,),
    )
    instruments = [r[0] for r in cur.fetchall()]
    return {
        "first_name": p[0] or "",
        "last_name": p[1] or "",
        "city": p[2] or "",
        "state": p[3] or "",
        "country": p[4] or "",
        "timezone": tz,
        "instruments": instruments,
    }


def _profile_body(cur):
    from timezone_utils import get_timezone_display_with_offset

    profile = _load_profile(cur, current_user.person_id, current_user.user_id)
    return {
        "success": True,
        "profile": profile,
        "needs_profile_setup": needs_profile_setup(current_user.person_id),
        "canonical_instruments": list(CANONICAL_INSTRUMENTS),
        "timezone_options": [
            {"value": tz, "label": get_timezone_display_with_offset(tz)}
            for tz in _TIMEZONE_CHOICES
        ],
    }


@api_login_required
def me_profile():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if request.method == "GET":
            return jsonify(_profile_body(cur))

        data = request.get_json(silent=True) or {}

        def s(key):
            v = data.get(key)
            return (v or "").strip() if isinstance(v, str) else ""

        instruments = data.get("instruments")
        if instruments is not None and not isinstance(instruments, list):
            return api_error("instruments must be a list", 400, "invalid")
        timezone = s("timezone") or None

        save_to_history(
            cur,
            "person",
            "UPDATE",
            current_user.person_id,
            user_id=current_user.user_id,
        )
        cur.execute(
            """
            UPDATE person
            SET first_name = COALESCE(NULLIF(%s, ''), first_name),
                last_name = COALESCE(NULLIF(%s, ''), last_name),
                city = COALESCE(NULLIF(%s, ''), CASE WHEN %s THEN NULL ELSE city END),
                state = COALESCE(NULLIF(%s, ''), CASE WHEN %s THEN NULL ELSE state END),
                country = COALESCE(NULLIF(%s, ''), CASE WHEN %s THEN NULL ELSE country END),
                last_modified_date = %s, last_modified_user_id = %s
            WHERE person_id = %s
            """,
            (
                s("first_name"),
                s("last_name"),
                s("city"),
                "city" in data,
                s("state"),
                "state" in data,
                s("country"),
                "country" in data,
                now_utc(),
                current_user.user_id,
                current_user.person_id,
            ),
        )
        if timezone:
            save_to_history(
                cur,
                "user_account",
                "UPDATE",
                current_user.user_id,
                user_id=current_user.user_id,
            )
            cur.execute(
                """
                UPDATE user_account
                SET timezone = %s, last_modified_date = %s, last_modified_user_id = %s
                WHERE user_id = %s
                """,
                (timezone, now_utc(), current_user.user_id, current_user.user_id),
            )
        if instruments is not None:
            instruments = normalize_instruments(
                [i for i in instruments if isinstance(i, str)]
            )
            cur.execute(
                "DELETE FROM person_instrument WHERE person_id = %s",
                (current_user.person_id,),
            )
            for instrument in instruments:
                if instrument:
                    cur.execute(
                        """
                        INSERT INTO person_instrument (person_id, instrument)
                        VALUES (%s, %s) ON CONFLICT (person_id, instrument) DO NOTHING
                        """,
                        (current_user.person_id, instrument),
                    )
        conn.commit()
        return jsonify(_profile_body(cur))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /api/app-config — what a binary needs to know before its first real call
# ---------------------------------------------------------------------------


def _version_tuple(v):
    parts = re.findall(r"\d+", v or "")
    return tuple(int(p) for p in parts[:4]) or (0,)


@public_api  # read before login; carries nothing personal
def app_config():
    """Server-steered client configuration (spec 052 A1.6 / A8).

    `min_client_version` is per platform from MIN_CLIENT_VERSION_<PLATFORM> env vars
    (e.g. MIN_CLIENT_VERSION_IOS=1.2.0). `force_upgrade` is that rule applied to the
    caller's X-Ceol-Client, so the app has a single boolean to act on. The streaming
    base URL used to reach clients only via the Jinja live-logger shell.
    """
    client = current_client()
    min_versions = {}
    for platform in ("ios", "android", "macos"):
        v = os.environ.get(f"MIN_CLIENT_VERSION_{platform.upper()}")
        if v:
            min_versions[platform] = v
    force_upgrade = False
    floor = min_versions.get(client["platform"])
    if floor and client["version"]:
        force_upgrade = _version_tuple(client["version"]) < _version_tuple(floor)

    return jsonify(
        {
            "success": True,
            "streaming_base_url": os.environ.get(
                "STREAMING_BASE_URL", "http://localhost:8080"
            ),
            "web_base_url": request.url_root.rstrip("/"),
            "min_client_version": min_versions,
            "force_upgrade": force_upgrade,
            "client": {"platform": client["platform"], "version": client["version"]},
            "server_version": os.environ.get("RENDER_GIT_COMMIT", "")[:8] or None,
            "features": {
                "live_logging": True,
                "recordings": True,
                "push_notifications": False,
            },
        }
    )


# ---------------------------------------------------------------------------
# GET /api/home
# ---------------------------------------------------------------------------


@api_login_required
def api_home():
    from serializers import build_home_payload

    conn = get_db_connection()
    try:
        return jsonify(build_home_payload(conn, current_user))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /api/resolve?path=...
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID_RE = re.compile(r"^\d+$")


def _session_block(row):
    return {"session_id": row[0], "path": row[1], "name": row[2]}


def _instance_block(row):
    return {"session_instance_id": row[0], "date": row[1], "location_override": row[2]}


@public_api  # session pages are public; it returns only what the URL already says
def resolve_path():
    """Turn a ceol.io URL or path into ids (spec 052 A7).

    Accepts `?path=` as a bare session path (`oflahertys/2025-09-20`), a site path
    (`/sessions/oflahertys/123`, `/live/instances/123`), or a full URL. Applies the
    same rule as web_routes.session_handler: a trailing date or number is an
    instance UNLESS the whole path is itself a session (`oflahertys/2025`).
    """
    raw = (request.args.get("path") or "").strip()
    if not raw:
        return api_error("path is required", 400, "missing_path")
    path = raw
    if "://" in path:
        path = path.split("://", 1)[1]
        slash = path.find("/")
        path = path[slash:] if slash >= 0 else ""
    path = path.split("?", 1)[0].split("#", 1)[0].strip("/")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        m = re.match(r"^live/instances/(\d+)$", path)
        if m:
            cur.execute(
                """
                SELECT s.session_id, s.path, s.name, si.session_instance_id, si.date, si.location_override
                FROM session_instance si JOIN session s ON s.session_id = si.session_id
                WHERE si.session_instance_id = %s
                """,
                (int(m.group(1)),),
            )
            row = cur.fetchone()
            if not row:
                return api_error("Not found", 404)
            return jsonify(
                {
                    "success": True,
                    "kind": "instance",
                    "session": _session_block(row[:3]),
                    "instance": _instance_block(row[3:]),
                }
            )

        if path.startswith("sessions/"):
            path = path.removeprefix("sessions/")
        # Tab suffixes on a session page are not part of the path.
        for suffix in ("/tunes", "/logs", "/people", "/players", "/about"):
            if path.endswith(suffix):
                path = path.removesuffix(suffix)
                break
        if not path:
            return api_error("Not found", 404)

        cur.execute(
            "SELECT session_id, path, name FROM session WHERE path = %s", (path,)
        )
        srow = cur.fetchone()
        if srow:
            return jsonify(
                {
                    "success": True,
                    "kind": "session",
                    "session": _session_block(srow),
                    "instance": None,
                }
            )

        parts = path.split("/")
        last = parts[-1]
        session_path = "/".join(parts[:-1])
        if len(parts) < 2 or not (_DATE_RE.match(last) or _ID_RE.match(last)):
            return api_error("Not found", 404)
        if _DATE_RE.match(last):
            cur.execute(
                """
                SELECT s.session_id, s.path, s.name, si.session_instance_id, si.date, si.location_override
                FROM session_instance si JOIN session s ON s.session_id = si.session_id
                WHERE s.path = %s AND si.date = %s
                ORDER BY si.session_instance_id ASC LIMIT 1
                """,
                (session_path, last),
            )
        else:
            cur.execute(
                """
                SELECT s.session_id, s.path, s.name, si.session_instance_id, si.date, si.location_override
                FROM session_instance si JOIN session s ON s.session_id = si.session_id
                WHERE s.path = %s AND si.session_instance_id = %s
                """,
                (session_path, int(last)),
            )
        row = cur.fetchone()
        if not row:
            return api_error("Not found", 404)
        return jsonify(
            {
                "success": True,
                "kind": "instance",
                "session": _session_block(row[:3]),
                "instance": _instance_block(row[3:]),
            }
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST /api/auth/web-session — app -> web handoff
# ---------------------------------------------------------------------------

WEB_SESSION_TOKEN_MINUTES = 5


@api_login_required
def auth_web_session():
    """Mint a one-time login link so the app can open the web (admin, help, anything
    not native) already signed in (spec 052 A7). Reuses the magic-link route:
    /auth/login/<token>?next=<path>. Short-lived, single use, same user."""
    data = request.get_json(silent=True) or {}
    next_path = (data.get("next") or "/").strip()
    if not next_path.startswith("/") or next_path.startswith("//"):
        return api_error("next must be a site-relative path", 400, "invalid_next")

    token = generate_login_token()
    expires = now_utc() + timedelta(minutes=WEB_SESSION_TOKEN_MINUTES)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_account
            SET login_token = %s, login_token_expires = %s, last_modified_date = %s
            WHERE user_id = %s
            """,
            (token, expires, now_utc(), current_user.user_id),
        )
        conn.commit()
    finally:
        conn.close()
    url = url_for("login_with_token", token=token, next=next_path, _external=True)
    return jsonify({"success": True, "url": url, "expires_at": expires})


# ---------------------------------------------------------------------------
# /.well-known/apple-app-site-association
# ---------------------------------------------------------------------------

# The URL families the app claims. Kept next to the resolver that understands
# them so adding a link kind is one edit.
UNIVERSAL_LINK_PATHS = [
    "/sessions/*",
    "/live/instances/*",
    "/auth/login/*",
    "/verify-email/*",
    "/share",
    "/my-tunes",
    "/me",
]


def apple_app_site_association():
    """Serve the AASA file when IOS_APP_IDS (comma-separated TEAMID.bundle.id) is set;
    404 otherwise so an unconfigured deploy claims nothing."""
    app_ids = [
        a.strip() for a in os.environ.get("IOS_APP_IDS", "").split(",") if a.strip()
    ]
    if not app_ids:
        return api_error("Not configured", 404, "not_configured")
    body = {
        "applinks": {
            "apps": [],
            "details": [{"appIDs": app_ids, "paths": UNIVERSAL_LINK_PATHS}],
        },
        "webcredentials": {"apps": app_ids},
    }
    resp = jsonify(body)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp
