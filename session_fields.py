"""Validation for the session fields that both write paths share.

`session.path` has its own module (session_path.py) because a bad one strands the
session. These four are less dangerous but were, until now, unreachable: they had
no editor at all on `/admin/sessions/<path>`, so a wrong value could only be fixed
with SQL. Now that both the create form (POST /api/add-session) and the admin form
(PUT /api/sessions/<path>/admin-update) write them, the coercion and the error
wording live here so the two can't drift.

`parse_thesession_session_id` is mirrored on the client in
frontend/src/shared/parse.js (parseThesessionSessionId) — keep them in lockstep.
"""

import re

SESSION_TYPES = ("regular", "festival")

# The "happening now" window can't be negative, and a day either side is already
# far past anything real — a wider value almost certainly means someone typed
# hours into a minutes box.
MAX_ACTIVE_BUFFER_MINUTES = 1440

_SESSION_URL = re.compile(r"thesession\.org/sessions/(\d+)")


def parse_thesession_session_id(raw):
    """Coerce a thesession.org SESSION reference to an int id.

    Accepts an int, a numeric string, or a /sessions/<id> URL. Empty (or None)
    means "no link" and yields (None, None) — clearing the field is a legitimate
    edit, not an error. Returns (id_or_None, error).

    Deliberately does NOT accept a /tunes/<id> URL: tunes and sessions share the
    same id space on thesession.org, so a mis-pasted tune link would otherwise
    silently point a session at a tune's page.
    """
    if raw is None:
        return None, None
    if isinstance(raw, bool):  # bool is an int subclass; never a valid id
        return None, "Enter a thesession.org session URL or numeric ID"
    if isinstance(raw, int):
        return (raw, None) if raw > 0 else (None, "TheSession.org ID must be a positive number")

    s = str(raw).strip()
    if not s:
        return None, None

    m = _SESSION_URL.search(s)
    if m:
        return int(m.group(1)), None
    if s.isdigit():
        value = int(s)
        return (value, None) if value > 0 else (None, "TheSession.org ID must be a positive number")
    return None, "Enter a thesession.org session URL (thesession.org/sessions/1234) or numeric ID"


def normalize_session_type(raw):
    """Validate session.session_type. Returns (value, error); blank means 'regular'."""
    if raw is None:
        return "regular", None
    value = str(raw).strip().lower()
    if not value:
        return "regular", None
    if value not in SESSION_TYPES:
        return None, f"Session type must be one of: {', '.join(SESSION_TYPES)}"
    return value, None


def normalize_active_buffer(raw, label="Active window"):
    """Validate one of the active_buffer_minutes_* columns. Returns (minutes, error);
    blank falls back to the column default (60)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return 60, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, f"{label} must be a whole number of minutes"
    # int() truncates 2.5 to 2 — a fraction of a minute is a typo, not a rounding
    # request, so say so rather than storing something the user didn't ask for.
    if float(raw) != value:
        return None, f"{label} must be a whole number of minutes"
    if value < 0:
        return None, f"{label} can't be negative"
    if value > MAX_ACTIVE_BUFFER_MINUTES:
        return None, f"{label} must be {MAX_ACTIVE_BUFFER_MINUTES} minutes or fewer"
    return value, None
