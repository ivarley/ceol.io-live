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
