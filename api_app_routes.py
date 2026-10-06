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
from flask import flash, jsonify, request, session, url_for
import i18n
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
    is_site_path,
    cleanup_expired_sessions,
    complete_pending_registration,
    create_session,
    generate_login_token,
    generate_verification_token,
    has_pending_registration,
    log_login_event,
    needs_profile_setup,
    start_pending_registration,
)
from database import get_db_connection, save_to_history
from email_utils import send_registration_email, send_verification_email
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
        # Spec 057: the interface language, 'en' or 'ga'.
        "language": i18n.user_language(user),
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

    # A registration link for an address with no account yet (migration 056):
    # the person and account are created now, already verified.
    status, user_id = complete_pending_registration(token)
    if status == "account_exists":
        return api_error(
            "There's already an account for this email address. Log in with it instead.",
            409,
            "account_exists",
        )
    if status == "created":
        user = User.get_by_id(user_id)
        if user:
            return jsonify(establish_session(user, "email_verification"))

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
            # An unverified account's verification token (24-hour expiry): accounts
            # made by /register, and links emailed before migration 056.
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
                SET login_token = NULL, login_token_expires = NULL, email_verified = TRUE,
                    last_modified_date = %s
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
            # No account, but maybe a registration whose link was never clicked
            # (migration 056): refresh it and send it again.
            if has_pending_registration(email):
                send_registration_email(email, start_pending_registration(email))
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
# POST /api/me/delete-account  (spec 054)
# ---------------------------------------------------------------------------


@api_login_required
def delete_account_api():
    """Delete the caller's account and private data, immediately. What goes and what
    stays is in services/account_deletion.py.

    The body must repeat the account's email (`confirm_email`, case-insensitive) —
    the same thing the web asks you to type — so a stray tap or a replayed request
    can't do it. On success every session and Bearer token of the account is gone
    (user_session cascades) and this caller is signed out."""
    from services.account_deletion import AccountDeletionRefused, delete_account

    data = request.get_json(silent=True) or {}
    typed = (data.get("confirm_email") or "").strip().lower()
    expected = (current_user.email or current_user.username or "").strip().lower()
    if not typed or typed != expected:
        return api_error(
            "Type your account's email address to confirm.",
            400,
            code="confirmation_mismatch",
        )

    user_id = current_user.user_id
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            delete_account(cur, user_id)
        except AccountDeletionRefused as e:
            conn.rollback()
            return api_error(e.message, 403, code=e.code)
        except LookupError:
            conn.rollback()
            return api_error("Account not found", 404)
        conn.commit()
    finally:
        conn.close()

    # Signed out everywhere already; this clears the calling browser's cookie session
    # and Flask-Login's cached user. The notice shows on the next page the web loads.
    session.clear()
    logout_user()
    flash("Your account has been deleted.", "success")
    return jsonify({"success": True})


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
        "SELECT first_name, last_name, city, state, country, sms_number, thesession_user_id"
        " FROM person WHERE person_id = %s",
        (person_id,),
    )
    p = cur.fetchone() or ("", "", None, None, None, None, None)
    cur.execute("SELECT timezone FROM user_account WHERE user_id = %s", (user_id,))
    tz = (cur.fetchone() or ["UTC"])[0] or "UTC"
    cur.execute(
        "SELECT instrument FROM person_instrument WHERE person_id = %s ORDER BY instrument",
        (person_id,),
    )
    # Older rows hold free spellings ("fiddle"); show the canonical names the
    # profile form offers, so its checkmarks line up.
    instruments = sorted(normalize_instruments([r[0] for r in cur.fetchall()]))
    return {
        "first_name": p[0] or "",
        "last_name": p[1] or "",
        "city": p[2] or "",
        "state": p[3] or "",
        "country": p[4] or "",
        "timezone": tz,
        "instruments": instruments,
        "sms_number": p[5] or "",
        "thesession_user_id": p[6],
    }


def _load_account(cur, user_id):
    """The account rows /me shows under Account: the login, the update-emails opt-in
    and, behind a Details row, when the account was made and last used."""
    cur.execute(
        """
        SELECT username, user_email, email_verified, hashed_password IS NOT NULL,
               receive_update_emails, created_date, language
        FROM user_account WHERE user_id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()
    cur.execute(
        "SELECT MAX(last_accessed) FROM user_session WHERE user_id = %s", (user_id,)
    )
    last = (cur.fetchone() or [None])[0]
    if not row:
        return None
    return {
        "username": row[0],
        "email": row[1],
        "email_verified": bool(row[2]),
        "has_password": bool(row[3]),
        "receive_update_emails": bool(row[4]),
        "created_at": row[5].isoformat() if row[5] else None,
        "language": row[6] or "en",
        "last_login": last.isoformat() if last else None,
    }


def _profile_body(cur):
    from timezone_utils import get_timezone_display_with_offset

    profile = _load_profile(cur, current_user.person_id, current_user.user_id)
    return {
        "success": True,
        "profile": profile,
        "account": _load_account(cur, current_user.user_id),
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

        # The rest of /me (spec 052): each is changed only when the request names it,
        # so the app can save one row at a time without resending the others.
        thesession_user_id = None
        if "thesession_user_id" in data:
            raw = data.get("thesession_user_id")
            text = str(raw).strip() if raw is not None else ""
            match = re.search(r"thesession\.org/members/(\d+)", text)
            if match:
                text = match.group(1)
            if text and not text.isdigit():
                return api_error(
                    "Enter your thesession.org member number or profile link",
                    400,
                    "invalid_thesession_user_id",
                )
            thesession_user_id = int(text) if text else None
        username = None
        if "username" in data:
            username = s("username")
            if not username:
                return api_error("Username can't be empty", 400, "invalid_username")
            cur.execute(
                "SELECT 1 FROM user_account WHERE LOWER(username) = LOWER(%s) AND user_id != %s",
                (username, current_user.user_id),
            )
            if cur.fetchone():
                return api_error("That username is taken", 400, "username_taken")
        language = data.get("language")
        if language is not None and language not in i18n.LANGUAGES:
            return api_error("language must be 'en' or 'ga'", 400, "invalid_language")
        receive_update_emails = data.get("receive_update_emails")
        if receive_update_emails is not None and not isinstance(
            receive_update_emails, bool
        ):
            return api_error(
                "receive_update_emails must be true or false", 400, "invalid"
            )

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
        if "sms_number" in data or "thesession_user_id" in data:
            cur.execute(
                """
                UPDATE person
                SET sms_number = CASE WHEN %s THEN %s ELSE sms_number END,
                    thesession_user_id = CASE WHEN %s THEN %s ELSE thesession_user_id END
                WHERE person_id = %s
                """,
                (
                    "sms_number" in data,
                    s("sms_number") or None,
                    "thesession_user_id" in data,
                    thesession_user_id,
                    current_user.person_id,
                ),
            )
        if language is not None:
            i18n.save_user_language(current_user.user_id, language)
            current_user.language = language
        if username is not None or receive_update_emails is not None:
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
                SET username = COALESCE(%s, username),
                    receive_update_emails = COALESCE(%s, receive_update_emails),
                    last_modified_date = %s, last_modified_user_id = %s
                WHERE user_id = %s
                """,
                (
                    username,
                    receive_update_emails,
                    now_utc(),
                    current_user.user_id,
                    current_user.user_id,
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
            # Only the difference: an instrument that stays keeps its row, and so
            # its is_auto flag (a manual per-instrument list must not turn auto
            # because the profile was saved). Matched case-insensitively, since
            # older rows hold free spellings.
            wanted = {i.lower() for i in instruments}
            cur.execute(
                "SELECT instrument FROM person_instrument WHERE person_id = %s",
                (current_user.person_id,),
            )
            have = [r[0] for r in cur.fetchall()]
            held = {normalize_instruments([h])[0].lower() for h in have}
            for h in have:
                if normalize_instruments([h])[0].lower() not in wanted:
                    cur.execute(
                        "DELETE FROM person_instrument WHERE person_id = %s AND instrument = %s",
                        (current_user.person_id, h),
                    )
            for instrument in instruments:
                if instrument.lower() not in held:
                    cur.execute(
                        """
                        INSERT INTO person_instrument (person_id, instrument, created_by_user_id)
                        VALUES (%s, %s, %s) ON CONFLICT (person_id, instrument) DO NOTHING
                        """,
                        (current_user.person_id, instrument, current_user.user_id),
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
    same resolution as web_routes.session_handler (spec 055, places.py): a bare
    place answers `kind: "place"`.
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

        # Spec 055 resolution, the same as web_routes.session_handler: exact path,
        # town/metro alias, path_redirect, then {path}/{date-or-id}. The payload
        # carries the session's real path, so an alias or an old link lands there.
        import places

        resolved = places.resolve_session_path(cur, path)
        if resolved is None:
            return api_error("Not found", 404)
        if resolved["kind"] == "place":
            # Spec 056: a festival answers with its years and the window rule's pick
            # (`current`, null when the picker applies); a town with just the place.
            if resolved["place"]["kind"] == "festival":
                from flask import session as flask_session
                from serializers import build_festival_payload

                payload = build_festival_payload(
                    conn,
                    resolved["place"],
                    person_id=getattr(current_user, "person_id", None)
                    if current_user.is_authenticated
                    else None,
                    is_system_admin=flask_session.get("is_system_admin", False),
                )
                return jsonify({"kind": "place", **payload})
            return jsonify(
                {
                    "success": True,
                    "kind": "place",
                    "place": places.place_summary(cur, resolved["place"]),
                }
            )
        cur.execute(
            "SELECT session_id, path, name FROM session WHERE session_id = %s",
            (resolved["session_id"],),
        )
        srow = cur.fetchone()
        if resolved["kind"] == "session":
            return jsonify(
                {
                    "success": True,
                    "kind": "session",
                    "session": _session_block(srow),
                    "instance": None,
                }
            )

        last = resolved["instance"]
        if _DATE_RE.match(last):
            cur.execute(
                """
                SELECT s.session_id, s.path, s.name, si.session_instance_id, si.date, si.location_override
                FROM session_instance si JOIN session s ON s.session_id = si.session_id
                WHERE s.session_id = %s AND si.date = %s
                ORDER BY si.session_instance_id ASC LIMIT 1
                """,
                (resolved["session_id"], last),
            )
        else:
            cur.execute(
                """
                SELECT s.session_id, s.path, s.name, si.session_instance_id, si.date, si.location_override
                FROM session_instance si JOIN session s ON s.session_id = si.session_id
                WHERE s.session_id = %s AND si.session_instance_id = %s
                """,
                (resolved["session_id"], int(last)),
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
    if not is_site_path(next_path):
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
    url = url_for("web_handoff_login", token=token, next=next_path, _external=True)
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
