"""Shared auth decorator for JSON API endpoints (spec 035, 1e).

One definition, imported by api_routes.py and api_person_tune_routes.py. API
endpoints must return 401 JSON on missing auth — never flask_login's
@login_required, which 302-redirects to the HTML login page.
"""

from functools import wraps

from flask import jsonify
from flask_login import current_user


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
    decorated_function._auth_required = True  # machine-checkable marker (test_api_auth_coverage)
    return decorated_function


def public_api(f):
    """Explicit marker for API endpoints that are DELIBERATELY unauthenticated
    (they serve content that is public in the UI, e.g. a session's logs tab).

    A no-op at runtime. Its purpose is auditability: an /api/* handler with
    neither an auth decorator nor @public_api is a bug, not a decision —
    `grep -L` for both finds the forgotten ones. (Backstory: three handlers
    shipped unguarded for months because "public" and "forgot" looked the same.)
    """
    f._public_api = True
    return f


def api_admin_or_self_required(f):
    """For person-scoped endpoints (first arg/kwarg `person_id`): the caller must
    be authenticated AND either a system admin or that person. 401/403 JSON."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Authentication required"}), 401
        person_id = kwargs.get("person_id", args[0] if args else None)
        is_self = getattr(current_user, "person_id", None) == person_id
        if not (current_user.is_system_admin or is_self):
            return jsonify({"success": False, "error": "Not authorized"}), 403
        return f(*args, **kwargs)
    decorated_function._auth_required = True  # machine-checkable marker (test_api_auth_coverage)
    return decorated_function


# ---------------------------------------------------------------------------
# The one error envelope + client identification (spec 052 A3 / A8).
#
# Every /api/* error a client sees is
#     {"success": false, "error": "<human>", "message": "<human>", "code": "<machine>"}
# `error` and `message` carry the same string: the web reads both (`data.error ||
# data.message` and vice versa, ~40 sites), so neither can go away; `code` is what a
# native client switches on. Handlers should build errors with api_error(); the
# after_request normalizer in app.py back-fills the keys for the legacy sites that
# still hand-roll jsonify({...}), so the guarantee holds across all 182 rules.
# ---------------------------------------------------------------------------

# Default machine code per status when a handler didn't name one.
DEFAULT_ERROR_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    413: "too_large",
    422: "invalid",
    429: "rate_limited",
    500: "server_error",
    502: "upstream_error",
    503: "unavailable",
}


def error_code_for_status(status):
    return DEFAULT_ERROR_CODES.get(int(status), "error")


def api_error(message, status=400, code=None, **extra):
    """Build the canonical JSON error response: (body, status).

    `extra` rides along at the top level (e.g. action="resend_verification") so a
    client can branch on more than the code without a second shape."""
    body = {
        "success": False,
        "error": message,
        "message": message,
        "code": code or error_code_for_status(status),
    }
    body.update(extra)
    return jsonify(body), status


def normalize_error_body(body, status):
    """Back-fill the envelope keys on a legacy error dict, in place. Returns True if
    anything changed. Only touches dicts; a handler that returns a list or a string
    is left alone."""
    if not isinstance(body, dict):
        return False
    changed = False
    msg = body.get("error")
    if not isinstance(msg, str):
        msg = body.get("message") if isinstance(body.get("message"), str) else None
    if msg is None:
        msg = body.get("reason") if isinstance(body.get("reason"), str) else None
    if msg is None:
        msg = "Request failed"
    if body.get("success") is not False:
        body["success"] = False
        changed = True
    if not isinstance(body.get("error"), str):
        body["error"] = msg
        changed = True
    if not isinstance(body.get("message"), str):
        body["message"] = msg
        changed = True
    if not isinstance(body.get("code"), str):
        body["code"] = error_code_for_status(status)
        changed = True
    return changed


# --- Client identification ---------------------------------------------------
#
# Native and web clients announce themselves with `X-Ceol-Client: <platform>/<version>`
# (e.g. "ios/1.2.0 (build 57)", "web/abc12345"). The header is optional: a request
# without it is treated as the web (cookie) client. It is stored with the login
# session (user_session.user_agent) so a token can be traced to an install, and
# /api/app-config uses it to tell an obsolete binary to upgrade.

CLIENT_HEADER = "X-Ceol-Client"
NATIVE_PLATFORMS = ("ios", "android", "macos")


def parse_client_header(value):
    """'ios/1.2.0 (build 57)' -> {"platform": "ios", "version": "1.2.0", "raw": ...};
    None/blank -> {"platform": "web", "version": None, "raw": None}."""
    raw = (value or "").strip()
    if not raw:
        return {"platform": "web", "version": None, "raw": None}
    head = raw.split()[0]
    platform, _, version = head.partition("/")
    platform = platform.lower() or "web"
    return {"platform": platform, "version": version or None, "raw": raw}


def current_client():
    """The parsed X-Ceol-Client of the current request.

    Cached on the WSGI environ, not on `g`: `g` is app-context scoped, and the test
    client (and any code that pushes an outer app context) reuses one app context
    across requests, so a `g` cache would leak one request's client into the next."""
    from flask import request

    cached = request.environ.get("ceol.client")
    if cached is None:
        cached = parse_client_header(request.headers.get(CLIENT_HEADER))
        request.environ["ceol.client"] = cached
    return cached


def is_native_client():
    """True when the caller identified itself as a native app — the signal that a
    login response should carry a Bearer token instead of relying on the cookie."""
    return current_client()["platform"] in NATIVE_PLATFORMS


def request_client_info():
    """(ip_address, user_agent) as the login/session code has always recorded them,
    with the X-Ceol-Client string prefixed onto the user agent when present so a
    user_session row says which install minted it."""
    from flask import request

    ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR"))
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    ua = request.headers.get("User-Agent") or ""
    client = current_client()
    if client["raw"]:
        ua = f"{client['raw']} {ua}".strip()
    return ip, (ua or None)
