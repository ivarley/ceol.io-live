"""Validation for `session.path` — the URL slug that identifies a session.

A session's path IS its URL: every page and API route is keyed on it
(`/sessions/<path>`, `/admin/sessions/<path>`, `/api/sessions/<path>/...`). That
makes a malformed path uniquely damaging: there is no screen that can repair one,
because reaching the admin screen requires the path you'd be trying to fix. The
session becomes unreachable and only a direct UPDATE against the database gets
it back.

The failure that motivated this: a path of "/" or "." (or a pasted zero-width
space) passes a bare `.strip()` truthiness check but collapses to nothing when a
browser resolves the URL, so the admin list renders a link to
`/admin/sessions/` and the session is stranded.

So: validate structure at every write, not just non-emptiness. Mirrored on the
client in frontend/src/shared/sessionpath.js — keep the two in lockstep.
"""

import re
import unicodedata

MAX_PATH_LENGTH = 255  # session.path is VARCHAR(255)
MAX_SEGMENTS = 4
MAX_SEGMENT_LENGTH = 100

# RFC 3986 "unreserved" characters — safe in a URL path segment unescaped.
_SEGMENT_ALLOWED = re.compile(r"^[A-Za-z0-9._~-]+$")
_HAS_ALPHANUMERIC = re.compile(r"[A-Za-z0-9]")

# Control, format (zero-width spaces, bidi marks) and the separator categories.
# These survive .strip() but render as nothing.
_INVISIBLE_CATEGORIES = ("Cc", "Cf", "Zs", "Zl", "Zp")


def normalize_session_path(value):
    """Validate a session path.

    Returns (path, error): on success the trimmed path and None; on failure
    None and a message suitable for showing to the user.
    """
    if not isinstance(value, str):
        return None, "Path is required"

    path = value.strip()
    if not path:
        return None, "Path is required"

    if any(unicodedata.category(ch) in _INVISIBLE_CATEGORIES for ch in path):
        return None, "Path can't contain spaces or invisible characters"

    if len(path) > MAX_PATH_LENGTH:
        return None, f"Path must be {MAX_PATH_LENGTH} characters or fewer"

    if path.startswith("/") or path.endswith("/"):
        return None, "Path can't start or end with a slash"

    segments = path.split("/")
    if len(segments) > MAX_SEGMENTS:
        return None, f"Path can have at most {MAX_SEGMENTS} slash-separated parts"

    for segment in segments:
        if not segment:
            return None, "Path can't contain an empty part (//)"
        if len(segment) > MAX_SEGMENT_LENGTH:
            return (
                None,
                f"Each part of the path must be {MAX_SEGMENT_LENGTH} characters or fewer",
            )
        if not _SEGMENT_ALLOWED.match(segment):
            return (
                None,
                "Path can only contain letters, numbers, hyphens, underscores, "
                "periods and slashes",
            )
        # Kills "." and ".." segments, which a browser resolves away entirely.
        if not _HAS_ALPHANUMERIC.search(segment):
            return None, "Each part of the path must contain a letter or number"

    return path, None
