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

# i18n-converted
import re

from flask_babel import gettext as _

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
        return None, _("Enter a thesession.org session URL or numeric ID")
    if isinstance(raw, int):
        if raw <= 0:
            return None, _("TheSession.org ID must be a positive number")
        return raw, None

    s = str(raw).strip()
    if not s:
        return None, None

    m = _SESSION_URL.search(s)
    if m:
        return int(m.group(1)), None
    if s.isdigit():
        value = int(s)
        if value <= 0:
            return None, _("TheSession.org ID must be a positive number")
        return value, None
    return None, _(
        "Enter a thesession.org session URL (thesession.org/sessions/1234) or numeric ID"
    )


def normalize_session_type(raw):
    """Validate session.session_type. Returns (value, error); blank means 'regular'."""
    if raw is None:
        return "regular", None
    value = str(raw).strip().lower()
    if not value:
        return "regular", None
    if value not in SESSION_TYPES:
        return None, _(
            "Session type must be one of: %(types)s", types=", ".join(SESSION_TYPES)
        )
    return value, None


def normalize_active_buffer(raw, label="Active window"):
    """Validate one of the active_buffer_minutes_* columns. Returns (minutes, error);
    blank falls back to the column default (60)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return 60, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, _buffer_error(label, 0)
    # int() truncates 2.5 to 2 — a fraction of a minute is a typo, not a rounding
    # request, so say so rather than storing something the user didn't ask for.
    if float(raw) != value:
        return None, _buffer_error(label, 0)
    if value < 0:
        return None, _buffer_error(label, 1)
    if value > MAX_ACTIVE_BUFFER_MINUTES:
        return None, _buffer_error(label, 2)
    return value, None


def _buffer_error(label, problem):
    """normalize_active_buffer's sentence for `label`, whole, so each language can
    word it its own way. The labels the routes pass have their own sentences; any
    other label is placed into a general one. `problem`: 0 not a whole number,
    1 negative, 2 too large."""
    m = MAX_ACTIVE_BUFFER_MINUTES
    if label == "Minutes before":
        sentences = (
            _("Minutes before must be a whole number of minutes"),
            _("Minutes before can't be negative"),
            _("Minutes before must be %(max)d minutes or fewer", max=m),
        )
    elif label == "Minutes after":
        sentences = (
            _("Minutes after must be a whole number of minutes"),
            _("Minutes after can't be negative"),
            _("Minutes after must be %(max)d minutes or fewer", max=m),
        )
    elif label == "Active window":
        sentences = (
            _("Active window must be a whole number of minutes"),
            _("Active window can't be negative"),
            _("Active window must be %(max)d minutes or fewer", max=m),
        )
    else:
        sentences = (
            _("%(label)s must be a whole number of minutes", label=label),
            _("%(label)s can't be negative", label=label),
            _("%(label)s must be %(max)d minutes or fewer", label=label, max=m),
        )
    return sentences[problem]
