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
    return decorated_function
