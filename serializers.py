"""Serializer layer (spec 035 §1d).

One place defines each wire shape; every producer of that shape — the JSON API
endpoint AND the page shell's embedded first-paint payload — funnels through it,
so they cannot drift.

Pattern rules (deliberately different from live_logging_routes.py's first cut):
  * Mappers are PURE: (row) -> dict. No DB connection, ever. Anything that needs
    a query happens in a loader, batched (no N+1 in a loop).
  * Rows are read BY NAME via RealDictCursor, never by position, so the column
    list and the mapper can't silently fall out of sync.
  * Loaders take a connection and open their own RealDictCursor; callers keep
    owning the connection/transaction.

Currently covers person_tune (the My Tunes page, spec 035 Step 2). Later page
migrations add their shapes here.
"""

from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extras

from services import person_scope


def bytea_to_base64(data):
    """Convert PostgreSQL bytea data to a base64 string (bytes/memoryview/hex str)."""
    import base64

    if not data:
        return None
    if isinstance(data, memoryview):
        data = data.tobytes()
    elif isinstance(data, str):
        if data.startswith("\\x"):
            data = bytes.fromhex(data[2:])
        else:
            data = data.encode("latin1")
    elif not isinstance(data, bytes):
        data = bytes(data)
    return base64.b64encode(data).decode("utf-8")


# ---------------------------------------------------------------------------
# timezone options — the shared dropdown source (person details + session admin
# pages). One list of tz names; the display labels come from timezone_utils.
# ---------------------------------------------------------------------------

_TIMEZONE_NAMES = [
    "UTC",
    # Americas
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "America/Toronto",
    "America/Vancouver",
    "America/Mexico_City",
    "America/Buenos_Aires",
    "America/Sao_Paulo",
    # Europe
    "Europe/London",
    "Europe/Dublin",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Rome",
    "Europe/Madrid",
    "Europe/Amsterdam",
    "Europe/Brussels",
    "Europe/Zurich",
    "Europe/Stockholm",
    "Europe/Oslo",
    "Europe/Copenhagen",
    "Europe/Helsinki",
    "Europe/Athens",
    "Europe/Moscow",
    # Africa & Middle East
    "Africa/Cairo",
    "Africa/Johannesburg",
    "Africa/Lagos",
    "Asia/Dubai",
    "Asia/Jerusalem",
    # Asia
    "Asia/Kolkata",
    "Asia/Bangkok",
    "Asia/Singapore",
    "Asia/Hong_Kong",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Asia/Seoul",
    # Australia & Pacific
    "Australia/Perth",
    "Australia/Sydney",
    "Australia/Melbourne",
    "Pacific/Auckland",
]


def timezone_options() -> List[Dict[str, str]]:
    """The timezone dropdown, as JSON-friendly {value, label} dicts. Replaces the
    (tz, display) tuple list that was duplicated verbatim in web_routes.person_details
    and web_routes.session_admin (spec 035 Step 5)."""
    from timezone_utils import get_timezone_display_with_offset

    return [
        {"value": tz, "label": get_timezone_display_with_offset(tz)}
        for tz in _TIMEZONE_NAMES
    ]


# ---------------------------------------------------------------------------
# add-session — the public /add-session page and GET /api/add-session
# ---------------------------------------------------------------------------


def build_add_session_payload(logged_in: bool = False) -> Dict[str, Any]:
    """The /add-session page payload (spec 035 final migration). The page is
    payload-light — its data comes from thesession.org at interaction time —
    but the shell==API invariant still holds: the shell embeds THIS dict and
    GET /api/add-session returns it. `logged_in` drives the "Add me as" control
    (anyone can browse the wizard; only the final POST /api/add-session is gated).
    """
    return {
        "success": True,
        "timezone_options": timezone_options(),
        # The wizard's fallback when the country/state guess has no opinion.
        "default_timezone": "America/Chicago",
        "viewer": {"logged_in": bool(logged_in)},
    }


# ---------------------------------------------------------------------------
# admin people — the /admin/people page and GET /api/admin/people
# ---------------------------------------------------------------------------

_ADMIN_PEOPLE_SQL = """
    SELECT
        p.person_id,
        p.first_name,
        p.last_name,
        p.email,
        p.city,
        p.state,
        p.country,
        p.thesession_user_id,
        p.active,
        ua.username,
        ua.is_system_admin,
        ua.user_email,
        ua.is_active AS account_active,
        ua.receive_update_emails,
        us.last_login,
        COALESCE(sp.session_count, 0) AS session_count,
        COALESCE(sip.session_instance_count, 0) AS session_instance_count,
        latest_si.latest_date,
        latest_si.session_name,
        COALESCE(pt.tune_count, 0) AS tune_count,
        llt.last_logged_tune,
        pt.last_tunebook_update
    FROM person p
    LEFT JOIN user_account ua ON p.person_id = ua.person_id
    -- login_history is append-only, so it survives logout and session expiry.
    -- user_session rows are deleted on both, which made the old
    -- MAX(user_session.last_accessed) read as "Never" for anyone without a
    -- currently-live session.
    LEFT JOIN (
        SELECT user_id, MAX(timestamp) AS last_login
        FROM login_history
        WHERE event_type = 'LOGIN_SUCCESS'
        GROUP BY user_id
    ) us ON ua.user_id = us.user_id
    LEFT JOIN (
        SELECT person_id, COUNT(*) AS session_count
        FROM session_person
        GROUP BY person_id
    ) sp ON p.person_id = sp.person_id
    LEFT JOIN (
        -- Real check-ins only (spec 033): a 'no'/'maybe' RSVP is not a sighting. And
        -- (spec 039) a session with track_attendance off contributes nothing — the
        -- "Checked In" column keeps existing, but such a session's rows drop out.
        SELECT sip.person_id, COUNT(*) AS session_instance_count
        FROM session_instance_person sip
        JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
        JOIN session s ON s.session_id = si.session_id AND s.track_attendance
        WHERE sip.attendance = 'yes'
        GROUP BY sip.person_id
    ) sip ON p.person_id = sip.person_id
    LEFT JOIN (
        SELECT DISTINCT ON (sip.person_id)
            sip.person_id,
            si.date AS latest_date,
            s.name AS session_name
        FROM session_instance_person sip
        JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
        JOIN session s ON si.session_id = s.session_id AND s.track_attendance
        WHERE sip.attendance = 'yes'
        ORDER BY sip.person_id, si.date DESC
    ) latest_si ON p.person_id = latest_si.person_id
    LEFT JOIN (
        SELECT person_id, COUNT(*) AS tune_count,
               MAX(last_modified_date) AS last_tunebook_update
        FROM person_tune
        GROUP BY person_id
    ) pt ON p.person_id = pt.person_id
    LEFT JOIN (
        SELECT ua_l.person_id, MAX(sit.created_date) AS last_logged_tune
        FROM session_instance_tune sit
        JOIN user_account ua_l ON sit.created_by_user_id = ua_l.user_id
        WHERE sit.record_type <> 'break'
        GROUP BY ua_l.person_id
    ) llt ON p.person_id = llt.person_id
    ORDER BY p.last_name, p.first_name
"""


def admin_person_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Pure mapper: one _ADMIN_PEOPLE_SQL row -> the wire dict. Raw values only
    (ISO strings, nulls) — display strings ("Never", "No account", "date - name")
    are the client's job."""
    return {
        "person_id": row["person_id"],
        "name": f"{row['first_name']} {row['last_name']}",
        "email": row["email"],
        "city": row["city"],
        "state": row["state"],
        "country": row["country"],
        "thesession_user_id": row["thesession_user_id"],
        "active": row["active"],
        "username": row["username"],
        "is_system_admin": bool(row["is_system_admin"]) if row["username"] else False,
        # account-level fields (null for people with no login account). user_email
        # is the address update emails actually go to — distinct from person.email,
        # which is the "email" key above (spec 027 / api_routes.py:492).
        "user_email": row["user_email"],
        "account_active": bool(row["account_active"]) if row["username"] else None,
        "receive_update_emails": bool(row["receive_update_emails"]) if row["username"] else None,
        # timestamps as naive-local ISO strings; date-only for latest_session_date
        "last_login": row["last_login"].isoformat() if row["last_login"] else None,
        "session_count": row["session_count"],
        "session_instance_count": row["session_instance_count"],
        "latest_session_date": row["latest_date"].isoformat() if row["latest_date"] else None,
        "latest_session_name": row["session_name"],
        "tune_count": row["tune_count"],
        "last_logged_tune": row["last_logged_tune"].isoformat() if row["last_logged_tune"] else None,
        "last_tunebook_update": (
            row["last_tunebook_update"].isoformat() if row["last_tunebook_update"] else None
        ),
    }


def build_admin_people_payload(conn) -> Dict[str, Any]:
    """The /admin/people page payload (system-admin only): every person with
    account/login info and activity roll-ups, one batched query. The page shell
    embeds this dict and GET /api/admin/people returns it — one function, no
    drift. Search/sort are client-side."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(_ADMIN_PEOPLE_SQL)
        people = [admin_person_to_dict(r) for r in cur.fetchall()]
    return {"success": True, "people": people}


# ---------------------------------------------------------------------------
# person details — the /me and /admin/people/<id> page and
# GET /api/me/details / GET /api/admin/people/<id>/details
# ---------------------------------------------------------------------------


def build_person_details_payload(
    conn,
    person_id: int,
    *,
    is_user_profile: bool,
    is_system_admin: bool,
) -> Optional[Dict[str, Any]]:
    """The COMPLETE person-details payload (spec 035 Step 5a): the person row with
    formatted location + instruments, the linked user account (or None), and the
    person's sessions with a derived role. GET /api/me/details (and the
    system-admin /api/admin/people/<id>/details flavor) returns exactly this, and
    the /me / /admin/people/<id> page shell embeds exactly this — one function,
    so they cannot drift. Returns None when the person doesn't exist.
    """
    from timezone_utils import get_timezone_display_name

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT person_id, first_name, last_name, email, sms_number, city, state,
               country, thesession_user_id, active
        FROM person
        WHERE person_id = %s
        """,
        (person_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    location_parts = [p for p in (row["city"], row["state"], row["country"]) if p]
    person = {
        "id": row["person_id"],
        "name": f"{row['first_name']} {row['last_name']}",
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "email": row["email"],
        "sms_number": row["sms_number"],
        "city": row["city"],
        "state": row["state"],
        "country": row["country"],
        "location": ", ".join(location_parts) if location_parts else None,
        "thesession_user_id": row["thesession_user_id"],
        "active": row["active"],
    }

    cur.execute(
        "SELECT instrument FROM person_instrument WHERE person_id = %s ORDER BY instrument",
        (person_id,),
    )
    person["instruments"] = [r["instrument"] for r in cur.fetchall()]

    # Linked user account (or None).
    cur.execute(
        """
        SELECT user_id, username, user_email, email_verified, is_system_admin,
               is_active, created_date, timezone, hashed_password,
               beta_live_logging, receive_update_emails
        FROM user_account
        WHERE person_id = %s
        """,
        (person_id,),
    )
    urow = cur.fetchone()
    user = None
    if urow:
        cur.execute(
            "SELECT MAX(last_accessed) AS last_login FROM user_session WHERE user_id = %s",
            (urow["user_id"],),
        )
        ll_row = cur.fetchone()
        last_login = ll_row["last_login"] if ll_row else None
        user = {
            "user_id": urow["user_id"],
            "username": urow["username"],
            "user_email": urow["user_email"],
            "email_verified": urow["email_verified"],
            "is_system_admin": urow["is_system_admin"],
            "is_active": urow["is_active"],
            "created_at": urow["created_date"].isoformat() if urow["created_date"] else None,
            "last_login": last_login.isoformat() if last_login else None,
            "timezone": urow["timezone"],
            "timezone_display": get_timezone_display_name(urow["timezone"] or "UTC"),
            "has_password": urow["hashed_password"] is not None and urow["hashed_password"] != "",
            "beta_live_logging": urow["beta_live_logging"],
            "receive_update_emails": urow["receive_update_emails"],
        }

    # Sessions this person is associated with (spec 034). `relationship` and `is_admin` are
    # orthogonal axes, and the tab filters on each independently -- so ship both raw. `role`
    # is display sugar only: Admin outranks the relationship in the badge, but an admin is
    # still a member or a visitor underneath.
    cur.execute(
        """
        SELECT s.name AS session_name, s.city, s.state, s.country,
               sp.relationship, sp.is_admin, sp.confirmed, s.path AS session_path
        FROM session_person sp
        JOIN session s ON sp.session_id = s.session_id
        WHERE sp.person_id = %s
        ORDER BY s.name
        """,
        (person_id,),
    )
    sessions = []
    for r in cur.fetchall():
        if r["is_admin"]:
            role = "Admin"
        elif r["relationship"] == "visitor":
            role = "Visitor"
        else:
            role = "Member"
        loc_parts = [p for p in (r["city"], r["state"], r["country"]) if p]
        sessions.append(
            {
                "session_name": r["session_name"],
                "location": ", ".join(loc_parts) if loc_parts else "Unknown",
                "role": role,
                "is_admin": r["is_admin"],
                "relationship": r["relationship"],
                "confirmed": r["confirmed"],
                "session_path": r["session_path"],
            }
        )

    return {
        "success": True,
        "person": person,
        "user": user,
        "sessions": sessions,
        "is_user_profile": is_user_profile,
        "is_system_admin": is_system_admin,
        "timezone_options": timezone_options(),
    }


# ---------------------------------------------------------------------------
# session admin — the /admin/sessions/<path> page and
# GET /api/admin/sessions/<path>/admin-detail. (Auth — the session-admin check —
# stays in the route/endpoint; this only shapes data.)
# ---------------------------------------------------------------------------


def build_session_admin_payload(conn, session_path: str) -> Optional[Dict[str, Any]]:
    """The COMPLETE session-admin payload (spec 035 Step 5b): the session row with
    timezone_display, recurrence_readable, and the auto-create / live-cache
    settings, plus the timezone dropdown. GET
    /api/admin/sessions/<path>/admin-detail returns exactly this, and the
    /admin/sessions/<path> page shell embeds exactly this — one function, so they
    cannot drift. Returns None when the path doesn't exist.
    """
    import json as _json

    from timezone_utils import get_timezone_display_name

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT session_id, thesession_id, name, path, location_name, location_website,
               location_phone,
               location_street, city, state, country, comments, unlisted_address,
               initiation_date, termination_date, recurrence, timezone,
               COALESCE(session_type, 'regular') AS session_type,
               COALESCE(active_buffer_minutes_before, 60) AS active_buffer_minutes_before,
               COALESCE(active_buffer_minutes_after, 60) AS active_buffer_minutes_after,
               COALESCE(auto_create_instances, FALSE) AS auto_create_instances,
               COALESCE(auto_create_hours_ahead, 24) AS auto_create_hours_ahead,
               COALESCE(live_cache_session_limit, 200) AS live_cache_session_limit,
               COALESCE(live_cache_global_limit, 25) AS live_cache_global_limit,
               show_people_list, track_attendance, track_set_starters
        FROM session
        WHERE path = %s
        """,
        (session_path,),
    )
    row = cur.fetchone()
    if not row:
        return None

    session = {
        "session_id": row["session_id"],
        # The four the admin form had no editor for until now: the upstream link, the
        # regular/festival switch (which reorders the public page's tabs), and the
        # "happening now" window active_session_manager reads.
        "thesession_id": row["thesession_id"],
        "session_type": row["session_type"],
        "active_buffer_minutes_before": row["active_buffer_minutes_before"],
        "active_buffer_minutes_after": row["active_buffer_minutes_after"],
        "name": row["name"],
        "path": row["path"],
        "location_name": row["location_name"],
        "location_website": row["location_website"],
        "location_phone": row["location_phone"],
        "location_street": row["location_street"],
        "city": row["city"],
        "state": row["state"],
        "country": row["country"],
        "comments": row["comments"],
        "unlisted_address": row["unlisted_address"],
        "initiation_date": row["initiation_date"].isoformat() if row["initiation_date"] else None,
        "termination_date": row["termination_date"].isoformat() if row["termination_date"] else None,
        "recurrence": row["recurrence"],
        "timezone": row["timezone"],
        "timezone_display": get_timezone_display_name(row["timezone"] or "UTC"),
        "auto_create_instances": row["auto_create_instances"],
        "auto_create_hours_ahead": row["auto_create_hours_ahead"],
        "live_cache_session_limit": row["live_cache_session_limit"],
        "live_cache_global_limit": row["live_cache_global_limit"],
        # Per-session people-tracking flags (spec 039) — the DetailsTab checkboxes, and
        # the PeopleAdminTab reads track_attendance to hide its attendance columns.
        "show_people_list": bool(row["show_people_list"]),
        "track_attendance": bool(row["track_attendance"]),
        "track_set_starters": bool(row["track_set_starters"]),
    }

    session["recurrence_readable"] = recurrence_readable(session["recurrence"])

    return {
        "success": True,
        "session": session,
        "timezone_options": timezone_options(),
    }



def recurrence_readable(recurrence: Optional[str]) -> Optional[str]:
    """Human-readable form of a session's recurrence. JSON recurrences render via
    recurrence_utils.to_human_readable; legacy freeform text passes through."""
    if not recurrence:
        return None
    import json as _json

    try:
        from recurrence_utils import to_human_readable

        _json.loads(recurrence)
        return to_human_readable(recurrence)
    except (ValueError, TypeError):
        return recurrence


def instance_labels(
    session_name: Optional[str],
    session_type: Optional[str],
    date: Any,
    location_override: Optional[str],
    session_location_name: Optional[str] = None,
) -> Dict[str, str]:
    """Spec 006's unique names for a session instance, in both the forms a list needs.

    Returns ``{"full_name": ..., "instance_label": ...}`` — the same string with and
    without the session's name on the front, because a cross-session list has to say
    WHICH session and an in-session list already knows.

    The date alone identifies an instance of a REGULAR session, and that is all those
    labels have ever carried. It does not identify one at a FESTIVAL: a festival runs
    several sessions a day, so 'Hill Country Trad Fest - 2026-06-06' can name two
    different rooms three hours apart. Festivals therefore always append the place,
    falling back to the session's own venue when the instance doesn't override it —
    the same `location_override or location_name` the Logs tab renders.

    Spec 006 wrote the festival date as mm/dd. It's spelled the full way here: these
    labels appear in "All Sessions" lists that span years, where a bare mm/dd is worse
    than ambiguous. The regular-session label is unchanged either way.
    """
    date_str = date.strftime("%Y-%m-%d") if date else None
    is_festival = (session_type or "regular") == "festival"
    place = (location_override or session_location_name or "").strip() if is_festival else ""

    parts = [p for p in (date_str, place or None) if p]
    instance_label = " - ".join(parts)
    full_name = " - ".join([p for p in ([session_name] + parts) if p]) or (session_name or "")
    return {"full_name": full_name, "instance_label": instance_label or (date_str or "")}


# ---------------------------------------------------------------------------
# sessions directory — the /sessions page and GET /api/sessions/with-today-status
# ---------------------------------------------------------------------------


def build_sessions_directory_payload(conn, person_id, user_timezone="UTC"):
    """The COMPLETE /api/sessions/with-today-status response body. The API endpoint
    returns exactly this and the /sessions page shell embeds exactly this — one
    function, so they cannot drift (spec 035's core invariant).

    Each session carries `active_instances` (is_active=TRUE instances, batched in
    one query) and `user_is_member` for the logged-in person. `today` is in the
    USER's timezone (per-session "today" is derived client-side from recurrence).
    """
    from timezone_utils import get_today_in_timezone

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT
            s.session_id, s.name, s.path, s.city, s.state, s.country,
            s.termination_date, s.recurrence, s.timezone,
            -- Member-strict (spec 033): a visitor row is an association, not membership.
            CASE WHEN sp.relationship = 'member' THEN TRUE ELSE FALSE END AS user_is_member,
            sp.relationship AS user_relationship,
            s.location_name
        FROM session s
        LEFT JOIN session_person sp ON s.session_id = sp.session_id AND sp.person_id = %s
        ORDER BY s.name
        """,
        (person_id,),
    )
    session_rows = cur.fetchall()

    cur.execute(
        """
        SELECT session_id, session_instance_id, date, start_time, end_time, location_override
        FROM session_instance
        WHERE is_active = TRUE
        ORDER BY session_id, date, start_time
        """
    )
    active_by_session = {}
    for r in cur.fetchall():
        active_by_session.setdefault(r["session_id"], []).append(
            {
                "session_instance_id": r["session_instance_id"],
                "date": r["date"].isoformat(),
                "start_time": r["start_time"].isoformat() if r["start_time"] else None,
                "end_time": r["end_time"].isoformat() if r["end_time"] else None,
                "location_override": r["location_override"],
            }
        )

    sessions = [
        {
            "session_id": r["session_id"],
            "name": r["name"],
            "path": r["path"],
            "city": r["city"],
            "state": r["state"],
            "country": r["country"],
            "termination_date": r["termination_date"].isoformat() if r["termination_date"] else None,
            "recurrence": r["recurrence"],
            "user_is_member": r["user_is_member"],
            "user_relationship": r["user_relationship"],
            "location_name": r["location_name"],
            "active_instances": active_by_session.get(r["session_id"], []),
        }
        for r in session_rows
    ]

    return {
        "success": True,
        "sessions": sessions,
        "today": get_today_in_timezone(user_timezone or "UTC").isoformat(),
    }


# ---------------------------------------------------------------------------
# session people — the roster (spec 034)
# ---------------------------------------------------------------------------

# ONE query behind every roster surface: the session People tab, the live logger's
# PersonPicker, and the session-admin people grid. Before 034 each of these had its own
# hand-rolled tuple SQL with subtly different columns and ordering.
#
# "Regular-ness" is COMPUTED here, never stored: distinct instances attended in a trailing
# 6-month window, then lifetime, then name. It is advisory only -- it decides sort order and
# who appears in a quick-pick shortlist, and nothing else. A wrong guess costs two keystrokes.
_SESSION_PEOPLE_SQL = """
    WITH attendance AS (
        SELECT sip.person_id,
               COUNT(DISTINCT sip.session_instance_id)
                   FILTER (WHERE sip.attendance = 'yes') AS lifetime_count,
               COUNT(DISTINCT sip.session_instance_id)
                   FILTER (WHERE sip.attendance = 'yes'
                           AND si.date >= (CURRENT_DATE - INTERVAL '6 months')) AS recent_count,
               MAX(si.date) FILTER (WHERE sip.attendance = 'yes') AS last_attended
        FROM session_instance_person sip
        JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
        WHERE si.session_id = %(session_id)s
        GROUP BY sip.person_id
    ),
    instruments AS (
        SELECT pi.person_id,
               array_agg(pi.instrument ORDER BY pi.instrument) AS instruments
        FROM person_instrument pi
        GROUP BY pi.person_id
    )
    SELECT p.person_id, p.first_name, p.last_name, p.email,
           p.city, p.state, p.country, p.thesession_user_id,
           (u.user_id IS NOT NULL) AS has_user_account,
           COALESCE(i.instruments, '{}'::text[]) AS instruments,
           sp.relationship, sp.confirmed, sp.archived,
           COALESCE(sp.is_admin, FALSE) AS is_admin,
           COALESCE(a.lifetime_count, 0) AS attendance_count,
           COALESCE(a.recent_count, 0) AS recent_attendance_count,
           a.last_attended,
           EXISTS (
               SELECT 1 FROM session_instance_person me
               WHERE me.person_id = p.person_id
                 AND me.session_instance_id = %(instance_id)s
                 AND me.attendance = 'yes'
           ) AS attending
    FROM session_person sp
    JOIN person p ON sp.person_id = p.person_id
    LEFT JOIN user_account u ON p.person_id = u.person_id
    LEFT JOIN instruments i ON p.person_id = i.person_id
    LEFT JOIN attendance a ON p.person_id = a.person_id
    WHERE sp.session_id = %(session_id)s
      AND p.active = TRUE
    ORDER BY COALESCE(a.recent_count, 0) DESC,
             COALESCE(a.lifetime_count, 0) DESC,
             p.first_name, p.last_name
"""


def session_person_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Pure mapper: one _SESSION_PEOPLE_SQL row -> the wire dict."""
    return {
        "person_id": row["person_id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "display_name": f"{row['first_name']} {row['last_name']}".strip(),
        "email": row["email"],
        "city": row["city"],
        "state": row["state"],
        "country": row["country"],
        "thesession_user_id": row["thesession_user_id"],
        "has_user_account": row["has_user_account"],
        "instruments": list(row["instruments"] or []),
        "relationship": row["relationship"],
        "confirmed": row["confirmed"],
        "archived": row["archived"],
        "is_admin": row["is_admin"],
        "attendance_count": row["attendance_count"],
        "recent_attendance_count": row["recent_attendance_count"],
        "last_attended": row["last_attended"].isoformat() if row["last_attended"] else None,
        "attending": row["attending"],
    }


def load_session_people(
    conn,
    session_id: int,
    *,
    instance_id: Optional[int] = None,
    include_archived: bool = True,
) -> List[Dict[str, Any]]:
    """This session's roster, ordered by computed regular-ness.

    `instance_id` fills each row's `attending` flag (checked in to that instance) — the
    PersonPicker's tier-1/tier-2 split. Without it, `attending` is always False.

    `include_archived=False` drops archived people. Callers showing a DEFAULT list pass
    False; callers responding to a typed query pass True, because archived must mean
    "hidden", never "unfindable" — otherwise a member back for one night is invisible in
    the picker and whoever's logging creates a duplicate person for her.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(_SESSION_PEOPLE_SQL, {"session_id": session_id, "instance_id": instance_id})
        people = [session_person_to_dict(r) for r in cur.fetchall()]
    if not include_archived:
        people = [p for p in people if not p["archived"]]
    return people


# ---------------------------------------------------------------------------
# session detail — the /sessions/<path> page and GET /api/sessions/<path>/detail
# ---------------------------------------------------------------------------

# One session_tune row shape for the whole page: the embedded first page, the
# /tunes/remaining continuation, and anything else listing a session's tunes.
# (This is where the legacy tuple-reshaping hack died — everything is dicts.)
_SESSION_TUNES_SQL = f"""
    SELECT
        st.tune_id,
        COALESCE(st.alias, t.name) AS tune_name,
        t.tune_type,
        COALESCE(play_counts.play_count, 0) AS play_count,
        COALESCE(t.tunebook_count_cached, 0) AS tunebook_count,
        st.setting_id
    FROM session_tune st
    LEFT JOIN tune t ON st.tune_id = t.tune_id
    LEFT JOIN (
        SELECT sit.tune_id, COUNT(*) AS play_count
        FROM session_instance_tune sit
        JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
        WHERE si.session_id = %s AND {person_scope.SIT_COUNTABLE}
        GROUP BY sit.tune_id
    ) play_counts ON st.tune_id = play_counts.tune_id
    WHERE st.session_id = %s
    ORDER BY play_count DESC, tunebook_count DESC, tune_name ASC
"""


def session_tune_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Pure mapper: one session_tune row (RealDictRow over _SESSION_TUNES_SQL) -> wire dict."""
    return {
        "tune_id": row["tune_id"],
        "tune_name": row["tune_name"],
        "tune_type": row["tune_type"],
        "play_count": row["play_count"],
        "tunebook_count": row["tunebook_count"],
        "setting_id": row["setting_id"],
    }


def _attach_session_attended_counts(cur, session_id: int, person_id: int, tunes: List[Dict[str, Any]]) -> None:
    """Attach attended_play_count (spec 033 R4, scoped to THIS session): distinct
    instances of this session the person attended (attendance='yes') where each
    tune was played. One batched query, bounded by the person's check-ins here."""
    tune_ids = [t["tune_id"] for t in tunes if t["tune_id"] is not None]
    counts: Dict[int, int] = {}
    if tune_ids:
        cur.execute(
            f"""SELECT sit.tune_id, COUNT(DISTINCT sit.session_instance_id) AS n
               FROM session_instance_tune sit
               JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
                   AND si.session_id = %(session_id)s
               JOIN session_instance_person sip ON sip.session_instance_id = sit.session_instance_id
                   AND sip.person_id = %(person_id)s AND sip.attendance = 'yes'
               WHERE sit.tune_id = ANY(%(tune_ids)s) AND {person_scope.SIT_COUNTABLE}
               GROUP BY sit.tune_id""",
            {"session_id": session_id, "person_id": person_id, "tune_ids": tune_ids},
        )
        counts = {r["tune_id"]: r["n"] for r in cur.fetchall()}
    for t in tunes:
        t["attended_play_count"] = counts.get(t["tune_id"], 0)


def load_session_tunes(
    conn,
    session_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
    person_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """A session's repertoire, ordered by play count / popularity / name.
    With a person_id, each row also carries attended_play_count (spec 033 R4,
    this-session scope) for the Tunes tab's "Nights I attended" filter."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = _SESSION_TUNES_SQL
    params: List[Any] = [session_id, session_id]
    if limit is not None:
        sql += " LIMIT %s"
        params.append(limit)
    if offset:
        sql += " OFFSET %s"
        params.append(offset)
    cur.execute(sql, params)
    tunes = [session_tune_to_dict(r) for r in cur.fetchall()]
    if person_id:
        _attach_session_attended_counts(cur, session_id, person_id, tunes)
    return tunes


def build_session_detail_payload(
    conn,
    session_path: str,
    *,
    person_id: Optional[int] = None,
    is_system_admin: bool = False,
    is_logged_in: bool = False,
    first_page: int = 20,
) -> Optional[Dict[str, Any]]:
    """The aggregate session-detail payload (spec 035 Step 4b): everything that
    used to exist only in the Jinja context — the session row with
    recurrence_readable, the permission flags, today in the session's timezone,
    the default tab — plus the first page of the repertoire and the popular list.

    GET /api/sessions/<path>/detail returns exactly this, and the /sessions/<path>
    page shell embeds exactly this — one function, so they cannot drift.
    Returns None when the path doesn't exist.
    """
    import datetime
    import json as _json

    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        from backports.zoneinfo import ZoneInfo

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT session_id, thesession_id, name, path, location_name, location_website,
               location_phone, location_street, city, state, country, comments,
               unlisted_address, initiation_date, termination_date, recurrence,
               session_type, timezone,
               show_people_list, track_attendance, track_set_starters
        FROM session
        WHERE path = %s
        """,
        (session_path,),
    )
    row = cur.fetchone()
    if not row:
        return None

    session = {
        "session_id": row["session_id"],
        "thesession_id": row["thesession_id"],
        "name": row["name"],
        "path": row["path"],
        "location_name": row["location_name"],
        "location_website": row["location_website"],
        "location_phone": row["location_phone"],
        "location_street": row["location_street"],
        "city": row["city"],
        "state": row["state"],
        "country": row["country"],
        "comments": row["comments"],
        "unlisted_address": row["unlisted_address"],
        "initiation_date": row["initiation_date"].isoformat() if row["initiation_date"] else None,
        "termination_date": row["termination_date"].isoformat() if row["termination_date"] else None,
        "recurrence": row["recurrence"],
        "session_type": row["session_type"] or "regular",
        "timezone": row["timezone"] or "UTC",
        # Per-session people-tracking flags (spec 039).
        "show_people_list": bool(row["show_people_list"]),
        "track_attendance": bool(row["track_attendance"]),
        "track_set_starters": bool(row["track_set_starters"]),
    }

    session["recurrence_readable"] = recurrence_readable(session["recurrence"])

    session_id = session["session_id"]

    # Permission flags (formerly Jinja-only).
    #
    # Spec 034: three distinct things, deliberately not collapsed.
    #   is_session_member -- any session_person row (member OR visitor). Association.
    #   relationship      -- the viewer's own 'member'/'visitor', for the role badge.
    #   can_view_people   -- is_admin OR confirmed. The SOLE gate on the People tab.
    # A member is not automatically allowed to see people: joining a session must not hand
    # you its roster.
    is_session_admin = bool(is_system_admin)
    is_session_member = False
    relationship = None
    is_confirmed = False
    if person_id:
        cur.execute(
            """
            SELECT is_admin, relationship, confirmed
            FROM session_person WHERE session_id = %s AND person_id = %s
            """,
            (session_id, person_id),
        )
        member_row = cur.fetchone()
        if member_row is not None:
            is_session_member = True
            relationship = member_row["relationship"]
            is_confirmed = bool(member_row["confirmed"])
            if member_row["is_admin"]:
                is_session_admin = True
    # is_admin OR confirmed is the visibility gate — but the session-page People tab is
    # ALSO switched off entirely when show_people_list is false (spec 039). Gone for
    # everyone including admins: an admin who wants the roster manages membership on the
    # admin page, which is unaffected by this flag. (can_view_people gates only the
    # session-page tab; is_session_admin, which gates administering the session, is left
    # untouched.)
    can_view_people = (is_session_admin or is_confirmed) and session["show_people_list"]

    # Today in the SESSION's timezone (drives the logs tab's add-instance default).
    try:
        today_in_session_tz = datetime.datetime.now(ZoneInfo(session["timezone"])).date()
    except Exception:
        today_in_session_tz = datetime.datetime.now(ZoneInfo("UTC")).date()

    # Top 20 most-played tunes at this session (includes instance-only tunes).
    #
    # Counted in two passes on purpose. The obvious single GROUP BY on
    # COALESCE(sit.name, st.alias, t.name) makes the grouping key a ~500-byte
    # text expression, so Postgres sorts every play row in the session's whole
    # history before aggregating (GroupAggregate). Grouping first on the narrow
    # (tune_id, sit.name) pair collapses ~16k rows to ~1.3k BEFORE the wide
    # joins, and both passes then fit in a HashAggregate — no sort at all.
    #
    # Equivalent, not approximate: (tune_id, sit.name) is a strictly finer
    # partition than the display name, since the alias/name fallbacks are
    # functions of tune_id, so SUM() over the sub-counts recovers the same
    # groups. Verified against production: identical rows for all 29 sessions,
    # including the 523 plays that carry a free-text name override.
    # Measured on the busiest session: 461ms -> 172ms.
    cur.execute(
        f"""
        WITH raw_counts AS (
            SELECT sit.tune_id, sit.name AS override_name, COUNT(*) AS play_count
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND {person_scope.SIT_COUNTABLE}
            GROUP BY sit.tune_id, sit.name
        ),
        tune_counts AS (
            SELECT
                COALESCE(rc.override_name, st.alias, t.name) AS tune_name,
                rc.tune_id,
                -- ::bigint because SUM(bigint) is numeric, which psycopg2 hands
                -- back as Decimal — COUNT(*) gave a plain int, and the payload
                -- (and its JSON encoding) must not change shape here.
                SUM(rc.play_count)::bigint AS play_count,
                COALESCE(t.tunebook_count_cached, 0) AS tunebook_count
            FROM raw_counts rc
            LEFT JOIN tune t ON rc.tune_id = t.tune_id
            LEFT JOIN session_tune st ON rc.tune_id = st.tune_id AND st.session_id = %s
            WHERE COALESCE(rc.override_name, st.alias, t.name) IS NOT NULL
            GROUP BY COALESCE(rc.override_name, st.alias, t.name), rc.tune_id,
                     COALESCE(t.tunebook_count_cached, 0)
        )
        SELECT tune_name, tune_id, play_count, tunebook_count
        FROM tune_counts
        ORDER BY play_count DESC, tunebook_count DESC, tune_name ASC
        LIMIT 20
        """,
        (session_id, session_id),
    )
    popular_tunes = [
        {
            "tune_name": r["tune_name"],
            "tune_id": r["tune_id"],
            "play_count": r["play_count"],
            "tunebook_count": r["tunebook_count"],
        }
        for r in cur.fetchall()
    ]

    cur.execute("SELECT COUNT(DISTINCT tune_id) AS n FROM session_tune WHERE session_id = %s", (session_id,))
    total_tunes_count = cur.fetchone()["n"]

    tunes = load_session_tunes(conn, session_id, limit=first_page, person_id=person_id)

    return {
        "success": True,
        "session": session,
        "permissions": {
            "is_logged_in": is_logged_in,
            "is_session_admin": is_session_admin,
            "is_session_member": is_session_member,
            "relationship": relationship,  # 'member' | 'visitor' | None — drives the badge
            "is_confirmed": is_confirmed,
            "can_view_people": can_view_people,  # (is_admin OR confirmed) AND show_people_list
        },
        "today_in_session_tz": today_in_session_tz.isoformat(),
        "default_tab": "logs" if session["session_type"] == "festival" else "tunes",
        "tunes": tunes,
        "total_tunes_count": total_tunes_count,
        "has_more_tunes": total_tunes_count > first_page,
        "popular_tunes": popular_tunes,
    }


# ---------------------------------------------------------------------------
# person_tune — "a tune on my list" (list rows, detail, and write responses all
# share this core shape; the detail view extends it via attach_* helpers below)
# ---------------------------------------------------------------------------

PERSON_TUNE_COLS = """
    pt.person_tune_id, pt.person_id, pt.tune_id, pt.learn_status,
    pt.heard_count, pt.learned_date, pt.notes, pt.setting_id, pt.name_alias, pt.key,
    pt.tags,
    pt.created_date, pt.last_modified_date,
    COALESCE(pt.name_alias, t.name) AS tune_name,
    t.tune_type,
    t.tunebook_count_cached AS tunebook_count,
    t.tunebook_count_cached_date
"""

PERSON_TUNE_FROM = "FROM person_tune pt LEFT JOIN tune t ON pt.tune_id = t.tune_id"

# Times played under the spec 033 lenses (distinct instances; correlated subquery
# per row of the filtered set — see person_scope.plays_sort_expr for the join
# rewrite if this ever measures slow). 'plays' = R3 member lens; 'attended' = R4.
MEMBER_PLAYS_SORT_EXPR = person_scope.plays_sort_expr("member")
ATTENDED_PLAYS_SORT_EXPR = person_scope.plays_sort_expr("attended")


def person_tune_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Pure mapper: one person_tune row (RealDictRow over PERSON_TUNE_COLS) -> wire dict."""
    tune_id = row["tune_id"]
    setting_id = row["setting_id"]
    thesession_url = None
    if tune_id is not None:
        thesession_url = f"https://thesession.org/tunes/{tune_id}"
        if setting_id:
            thesession_url = f"{thesession_url}?setting={setting_id}#setting{setting_id}"
    return {
        "person_tune_id": row["person_tune_id"],
        "person_id": row["person_id"],
        "tune_id": tune_id,
        "learn_status": row["learn_status"],
        "heard_count": row["heard_count"],
        "learned_date": row["learned_date"].isoformat() if row["learned_date"] else None,
        "notes": row["notes"],
        "setting_id": setting_id,
        "name_alias": row["name_alias"],
        # "I play this in ..." (spec 037). Label only — it does not drive notation.
        "key": row["key"],
        # Freeform per-person tags (spec 042). TEXT[] -> list; NULL-safe to [].
        "tags": row["tags"] or [],
        "created_date": row["created_date"].isoformat() if row["created_date"] else None,
        "last_modified_date": row["last_modified_date"].isoformat() if row["last_modified_date"] else None,
        "tune_name": row["tune_name"],
        "tune_type": row["tune_type"],
        "tunebook_count": row["tunebook_count"],
        # The drawer shows "Last Updated" beside the tunebook-count refresh;
        # the global detail payload has always carried this — keep in sync.
        "tunebook_count_cached_date": row["tunebook_count_cached_date"].isoformat()
        if row["tunebook_count_cached_date"]
        else None,
        "thesession_url": thesession_url,
    }


def _attach_instrument_overrides(cur, person_id: int, tunes: List[Dict[str, Any]]) -> None:
    """Attach sparse per-instrument status overrides to each dict, in ONE query.

    Only stored overrides appear; the client resolves the rest (auto instruments
    follow learn_status, manual-with-no-row is untracked) from the person's
    instrument/auto list.
    """
    tune_ids = [t["tune_id"] for t in tunes if t["tune_id"] is not None]
    overrides_by_tune: Dict[int, Dict[str, str]] = {}
    if tune_ids:
        cur.execute(
            """SELECT tune_id, instrument, status
               FROM person_tune_instrument
               WHERE person_id = %s AND tune_id = ANY(%s)""",
            (person_id, tune_ids),
        )
        for r in cur.fetchall():
            overrides_by_tune.setdefault(r["tune_id"], {})[r["instrument"]] = r["status"]
    for t in tunes:
        t["instrument_status"] = overrides_by_tune.get(t["tune_id"], {})


def _attach_person_play_counts(cur, person_id: int, tunes: List[Dict[str, Any]]) -> None:
    """Attach the spec 033 play-count lenses, batched in ONE query:

    member_play_count   — R3: distinct instances of sessions the person is a MEMBER of
    attended_play_count — R4: distinct instances the person ATTENDED (attendance='yes')
    session_play_count  — deprecated alias of member_play_count; remove with the
                          ?person=me alias once no stale offline caches remain
    """
    tune_ids = [t["tune_id"] for t in tunes if t["tune_id"] is not None]
    counts: Dict[int, Dict[str, int]] = {}
    if tune_ids:
        cur.execute(
            person_scope.person_tune_play_counts_sql(),
            {"person_id": person_id, "tune_ids": tune_ids},
        )
        counts = {
            r["tune_id"]: {
                "member": r["member_play_count"],
                "attended": r["attended_play_count"],
            }
            for r in cur.fetchall()
        }
    for t in tunes:
        c = counts.get(t["tune_id"], {})
        t["member_play_count"] = c.get("member", 0)
        t["attended_play_count"] = c.get("attended", 0)
        t["session_play_count"] = t["member_play_count"]


# Accent- and quote-insensitive match, applied identically to both sides.
# Normalizes all apostrophe/quote variants: ' ' ‛ ʼ ´ ` " "
_SEARCH_NORMALIZE = """translate(
    translate(LOWER({expr}),
             'áàâäãåāéèêëēíìîïīóòôöõøōúùûüūýÿçñ',
             'aaaaaaaeeeeeiiiiioooooooouuuuuyycn'),
    '''‛ʼ´`""',
    ''''''''
)"""

_SORT_MAP = {
    "alpha-asc": "LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "alpha-desc": "LOWER(COALESCE(pt.name_alias, t.name)) DESC",
    "popularity-desc": "t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "popularity-asc": "t.tunebook_count_cached ASC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "heard-desc": "pt.heard_count DESC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "heard-asc": "pt.heard_count ASC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "plays-desc": f"{MEMBER_PLAYS_SORT_EXPR} DESC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "plays-asc": f"{MEMBER_PLAYS_SORT_EXPR} ASC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "attended-desc": f"{ATTENDED_PLAYS_SORT_EXPR} DESC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "attended-asc": f"{ATTENDED_PLAYS_SORT_EXPR} ASC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
}

VALID_PERSON_TUNE_SORTS = tuple(_SORT_MAP)


def load_person_tunes(
    conn,
    person_id: int,
    *,
    learn_status: Optional[str] = None,
    tune_type: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "alpha-asc",
    page: int = 1,
    per_page: int = 2000,
) -> Tuple[List[Dict[str, Any]], int]:
    """List loader: the person's tunes with details, filtered/sorted/paginated.

    Returns (tunes, total_count). Every row goes through person_tune_to_dict, so
    a list row and a detail response agree exactly on the core shape.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = f"SELECT {PERSON_TUNE_COLS} {PERSON_TUNE_FROM} WHERE pt.person_id = %s"
    params: List[Any] = [person_id]

    if learn_status:
        query += " AND pt.learn_status = %s"
        params.append(learn_status)
    if tune_type:
        query += " AND LOWER(t.tune_type) = LOWER(%s)"
        params.append(tune_type)
    if search:
        lhs = _SEARCH_NORMALIZE.format(expr="COALESCE(pt.name_alias, t.name)")
        rhs = _SEARCH_NORMALIZE.format(expr="%s")
        query += f" AND ({lhs} LIKE {rhs})"
        params.append(f"%{search}%")

    cur.execute(f"SELECT COUNT(*) AS n FROM ({query}) AS filtered", params)
    total_count = cur.fetchone()["n"]

    order_by = _SORT_MAP.get(sort, _SORT_MAP["alpha-asc"])
    query += f" ORDER BY {order_by} LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])

    cur.execute(query, params)
    tunes = [person_tune_to_dict(row) for row in cur.fetchall()]

    _attach_instrument_overrides(cur, person_id, tunes)
    _attach_person_play_counts(cur, person_id, tunes)
    return tunes, total_count


def load_person_instruments(conn, person_id: int) -> List[Dict[str, Any]]:
    """The person's instruments with their auto/manual flag."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT instrument, is_auto FROM person_instrument WHERE person_id = %s ORDER BY instrument",
        (person_id,),
    )
    return [{"instrument": r["instrument"], "is_auto": r["is_auto"]} for r in cur.fetchall()]


def build_my_tunes_payload(
    conn,
    person_id: int,
    *,
    learn_status: Optional[str] = None,
    tune_type: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "alpha-asc",
    page: int = 1,
    per_page: int = 2000,
) -> Dict[str, Any]:
    """The COMPLETE /api/my-tunes response body. GET /api/my-tunes returns exactly
    this, and the /my-tunes page shell embeds exactly this as window.__PAGE_DATA__
    — one function, so the two cannot drift (spec 035's core invariant)."""
    tunes, total_count = load_person_tunes(
        conn,
        person_id,
        learn_status=learn_status,
        tune_type=tune_type,
        search=search,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    total_pages = (total_count + per_page - 1) // per_page
    cur = conn.cursor()
    cur.execute("SELECT thesession_user_id FROM person WHERE person_id = %s", (person_id,))
    row = cur.fetchone()
    return {
        "success": True,
        "tunes": tunes,
        # The person's instruments + auto/manual flags, so the client can resolve
        # per-instrument status alongside each tune's sparse instrument_status overrides.
        "instruments": load_person_instruments(conn, person_id),
        # The saved thesession.org member ID, prefilling the add pane's sync view.
        "thesession_user_id": row[0] if row else None,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
        "filters": {
            "learn_status": learn_status,
            "tune_type": tune_type,
            "search": search or "",
        },
    }


def _load_person_tune_where(conn, where_sql: str, params: Tuple) -> Optional[Dict[str, Any]]:
    """Single-record core shared by the ptid- and (person, tune)-keyed loaders:
    same mapper and enrichments as the list."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"SELECT {PERSON_TUNE_COLS} {PERSON_TUNE_FROM} WHERE {where_sql}", params)
    row = cur.fetchone()
    if not row:
        return None
    d = person_tune_to_dict(row)
    _attach_instrument_overrides(cur, d["person_id"], [d])
    _attach_person_play_counts(cur, d["person_id"], [d])
    return d


def load_person_tune(conn, person_tune_id: int) -> Optional[Dict[str, Any]]:
    """Single-record loader keyed by person_tune_id."""
    return _load_person_tune_where(conn, "pt.person_tune_id = %s", (person_tune_id,))


def load_person_tune_by_tune(conn, person_id: int, tune_id: int) -> Optional[Dict[str, Any]]:
    """Single-record loader keyed by (person, tune) — the tune-detail drawer's
    person_tune_status block uses this so it carries the SAME core shape as
    /api/my-tunes rows (no parallel queries to drift)."""
    return _load_person_tune_where(conn, "pt.person_id = %s AND pt.tune_id = %s", (person_id, tune_id))


def attach_person_tune_detail(conn, d: Dict[str, Any]) -> Dict[str, Any]:
    """Extend a core person_tune dict with the detail-only (expensive) fields:
    notation (abc/incipit/images/setting_key), the person's instrument list, and
    the global popularity counts. Everything else is the shared core shape.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    d["instruments"] = load_person_instruments(conn, d["person_id"])

    # Notation: the saved setting if any, else the tune's first setting.
    if d["setting_id"]:
        cur.execute(
            """SELECT abc, incipit_abc, image, incipit_image, key
               FROM tune_setting WHERE setting_id = %s""",
            (d["setting_id"],),
        )
    else:
        cur.execute(
            """SELECT abc, incipit_abc, image, incipit_image, key
               FROM tune_setting
               WHERE tune_id = %s
               ORDER BY setting_id ASC
               LIMIT 1""",
            (d["tune_id"],),
        )
    setting = cur.fetchone()
    d["abc"] = setting["abc"] if setting else None
    if setting:
        d["incipit_abc"] = setting["incipit_abc"]
        d["image"] = bytea_to_base64(setting["image"])
        d["incipit_image"] = bytea_to_base64(setting["incipit_image"])
        d["setting_key"] = setting["key"]

    cur.execute(
        """SELECT COUNT(DISTINCT session_instance_id) AS n
           FROM session_instance_tune WHERE tune_id = %s AND deleted = FALSE""",
        (d["tune_id"],),
    )
    d["global_play_count"] = cur.fetchone()["n"]

    cur.execute("SELECT COUNT(*) AS n FROM person_tune WHERE tune_id = %s", (d["tune_id"],))
    d["person_list_count"] = cur.fetchone()["n"]
    return d


def build_person_tune_detail(conn, person_tune_id: int) -> Optional[Dict[str, Any]]:
    """Core + detail extension in one call — what the detail endpoints return."""
    d = load_person_tune(conn, person_tune_id)
    if d is not None:
        attach_person_tune_detail(conn, d)
    return d

# ---------------------------------------------------------------------------
# The tune-detail drawer payload (GET /api/tunes/<id>/detail — THE drawer feed)
#
# The drawer derives its own mode (my-tunes variant / session / instance /
# admin / read-only) from this one superset payload instead of trusting call
# sites to hand-assemble configs:
#   * viewer        — logged_in / is_admin / is_session_admin, from the session
#                     cookie server-side: the source of truth for login-gated
#                     affordances (status seg, Add, Generate Notation).
#   * person_tune_status — the FULL person-tune core shape (same loader as
#                     /api/my-tunes rows) when the viewer has the tune on their
#                     list; a minimal on_list:false block when not; None anon.
#   * session scope — ?session=<path> (+ &instance=<date-or-id>) merges in the
#                     session_tune block the legacy per-session endpoints
#                     return; those endpoints now delegate here too, so the
#                     queries live once.
# ---------------------------------------------------------------------------


class SessionNotFound(Exception):
    """?session= named a session path that doesn't exist."""


class SessionInstanceNotFound(Exception):
    """&instance= named a date/id with no instance for the session."""


def _find_session_instance_id(cur, session_id: int, date_or_id: str) -> Optional[int]:
    """date_or_id is either a YYYY-MM-DD date (first instance that day) or a
    numeric instance id (verified to belong to the session)."""
    import re as _re

    if _re.match(r"^\d+$", str(date_or_id)) and not _re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_or_id)):
        cur.execute(
            "SELECT session_instance_id FROM session_instance WHERE session_instance_id = %s AND session_id = %s",
            (int(date_or_id), session_id),
        )
    else:
        cur.execute(
            """SELECT session_instance_id FROM session_instance
               WHERE session_id = %s AND date = %s
               ORDER BY session_instance_id ASC LIMIT 1""",
            (session_id, date_or_id),
        )
    row = cur.fetchone()
    return row["session_instance_id"] if row else None


def _load_session_scope(conn, tune_id: int, session_path: str, date_or_id: Optional[str]) -> Dict[str, Any]:
    """The session (and optional instance) scope block for the drawer payload."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT session_id, name, track_attendance FROM session WHERE path = %s", (session_path,))
    srow = cur.fetchone()
    if not srow:
        raise SessionNotFound(session_path)
    session_id = srow["session_id"]

    scope: Dict[str, Any] = {
        "path": session_path,
        "session_id": session_id,
        # The Session tab heads with the session's name, linked to its page.
        "session_name": srow["name"],
        # Spec 039: the History tab's "while I was there" checkbox hides when the drawer
        # is scoped to a session that doesn't track attendance — the filter is
        # meaningless there (the counts already exclude it app-wide).
        "track_attendance": bool(srow["track_attendance"]),
        "date_or_id": date_or_id,
        "alias": None,
        "setting_id": None,
        "key": None,
        "aliases": [],
        "in_repertoire": False,
        "name_override": None,
        "key_override": None,
        "setting_override": None,
        "played_instances": [],
    }

    cur.execute(
        "SELECT alias, setting_id, key FROM session_tune WHERE session_id = %s AND tune_id = %s",
        (session_id, tune_id),
    )
    st = cur.fetchone()
    if st:
        scope.update(
            {"alias": st["alias"], "setting_id": st["setting_id"], "key": st["key"], "in_repertoire": True}
        )

    cur.execute(
        """SELECT alias FROM session_tune_alias
           WHERE session_id = %s AND tune_id = %s ORDER BY created_date ASC""",
        (session_id, tune_id),
    )
    scope["aliases"] = [r["alias"] for r in cur.fetchall()]

    cur.execute(
        """SELECT COUNT(*) AS n
           FROM session_instance_tune sit
           JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
           WHERE si.session_id = %s AND sit.tune_id = %s AND sit.deleted = FALSE""",
        (session_id, tune_id),
    )
    scope["times_played"] = cur.fetchone()["n"]

    # The Session tab's droplist (spec 037): the instances this tune was actually
    # played at — the only ones session_instance_tune can hold overrides for — each
    # with the humane "Set 3, tune 2" coordinates of every time it came round that
    # night (usually one; a tune played twice has two).
    #
    # The set/position window is the same trick as GET /api/tunes/<id>/history: a
    # running SUM over break records numbers the sets (spec 023), and the breaks are
    # dropped AFTER the window is computed so they never take a tune number.
    # order_position is a fractional index, hence the id tiebreak.
    cur.execute(
        """
        WITH rows AS (
            SELECT sit.session_instance_id, sit.session_instance_tune_id, sit.tune_id,
                   sit.record_type, sit.order_position,
                   SUM(CASE WHEN sit.record_type = 'break' THEN 1 ELSE 0 END)
                       OVER (PARTITION BY sit.session_instance_id
                             ORDER BY sit.order_position, sit.session_instance_tune_id) AS set_idx
            FROM session_instance_tune sit
            JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
            WHERE si.session_id = %(session_id)s AND sit.deleted = FALSE
        ),
        positioned AS (
            SELECT session_instance_id, session_instance_tune_id, tune_id,
                   set_idx + 1 AS set_number,
                   ROW_NUMBER() OVER (PARTITION BY session_instance_id, set_idx
                                      ORDER BY order_position, session_instance_tune_id) AS position_in_set
            FROM rows
            WHERE record_type <> 'break'
        )
        SELECT si.session_instance_id, si.date, si.start_time, si.location_override,
               p.session_instance_tune_id, p.set_number, p.position_in_set
        FROM positioned p
        JOIN session_instance si ON si.session_instance_id = p.session_instance_id
        WHERE p.tune_id = %(tune_id)s
        ORDER BY si.date DESC, si.start_time DESC NULLS LAST,
                 p.set_number ASC, p.position_in_set ASC
        """,
        {"session_id": session_id, "tune_id": tune_id},
    )
    by_instance: Dict[int, Dict[str, Any]] = {}
    for r in cur.fetchall():
        entry = by_instance.setdefault(
            r["session_instance_id"],
            {
                "session_instance_id": r["session_instance_id"],
                "date": r["date"].isoformat(),
                "start_time": r["start_time"].isoformat() if r["start_time"] else None,
                "location_override": r["location_override"],
                "positions": [],
            },
        )
        entry["positions"].append(
            {
                "session_instance_tune_id": r["session_instance_tune_id"],
                "set_number": r["set_number"],
                "position_in_set": r["position_in_set"],
            }
        )
    scope["played_instances"] = list(by_instance.values())

    if date_or_id is not None:
        instance_id = _find_session_instance_id(cur, session_id, date_or_id)
        if instance_id is None:
            raise SessionInstanceNotFound(date_or_id)
        scope["session_instance_id"] = instance_id
        cur.execute(
            """SELECT name, key_override, setting_override
               FROM session_instance_tune
               WHERE session_instance_id = %s AND tune_id = %s""",
            (instance_id, tune_id),
        )
        it = cur.fetchone()
        if it:
            scope.update(
                {
                    "name_override": it["name"],
                    "key_override": it["key_override"],
                    "setting_override": it["setting_override"],
                }
            )
    return scope


def _load_setting_notation(conn, tune_id: int, setting_id: Optional[int]) -> Dict[str, Any]:
    """Notation for a specific setting, falling back to the tune's first setting.
    setting_id in the result is the setting actually resolved."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if setting_id:
        cur.execute(
            "SELECT setting_id, abc, incipit_abc, image, incipit_image, key FROM tune_setting WHERE setting_id = %s",
            (setting_id,),
        )
    else:
        cur.execute(
            """SELECT setting_id, abc, incipit_abc, image, incipit_image, key
               FROM tune_setting WHERE tune_id = %s
               ORDER BY setting_id ASC LIMIT 1""",
            (tune_id,),
        )
    row = cur.fetchone()
    if not row:
        return {"setting_id": None, "abc": None, "incipit_abc": None, "image": None, "incipit_image": None, "setting_key": None}
    return {
        "setting_id": row["setting_id"],
        "abc": row["abc"],
        "incipit_abc": row["incipit_abc"],
        "image": bytea_to_base64(row["image"]),
        "incipit_image": bytea_to_base64(row["incipit_image"]),
        "setting_key": row["key"],
    }


def build_tune_detail_payload(
    conn,
    tune_id: int,
    *,
    person_id: Optional[int] = None,
    logged_in: bool = False,
    is_admin: bool = False,
    session_path: Optional[str] = None,
    date_or_id: Optional[str] = None,
    redirected_from: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """The complete drawer payload. Returns None when the tune doesn't exist;
    raises SessionNotFound / SessionInstanceNotFound for a bad scope."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """SELECT name, tune_type, tunebook_count_cached, tunebook_count_cached_date
           FROM tune WHERE tune_id = %s""",
        (tune_id,),
    )
    t = cur.fetchone()
    if not t:
        return None

    scope = _load_session_scope(conn, tune_id, session_path, date_or_id) if session_path else None

    # The viewer's own relationship to the tune — full core shape when on-list.
    person_tune_status = None
    if logged_in and person_id:
        pt = load_person_tune_by_tune(conn, person_id, tune_id)
        if pt:
            person_tune_status = dict(pt)
            person_tune_status["on_list"] = True
            person_tune_status["instruments"] = load_person_instruments(conn, person_id)
        else:
            person_tune_status = {
                "on_list": False,
                "person_tune_id": None,
                "learn_status": None,
                "heard_count": None,
                "instruments": [],
                "instrument_status": {},
            }

    # Session-admin flag (system admins administer every session). is_session_member
    # is a weaker grant the Session tab needs on its own: spec 037 lets any member
    # edit a specific instance's overrides, while the session's own alias/setting/key
    # stays admin-only.
    is_session_admin = bool(is_admin)
    is_session_member = bool(is_admin)
    if scope and person_id:
        cur.execute(
            "SELECT is_admin FROM session_person WHERE session_id = %s AND person_id = %s",
            (scope["session_id"], person_id),
        )
        m = cur.fetchone()
        if m:
            is_session_member = True
            is_session_admin = is_session_admin or bool(m["is_admin"])

    # Notation precedence mirrors what each legacy variant showed: the instance
    # override, else the session's setting, else the viewer's saved setting,
    # else the tune's first setting.
    effective_setting_id = None
    if scope:
        effective_setting_id = scope["setting_override"] or scope["setting_id"]
    if not effective_setting_id and person_tune_status and person_tune_status.get("setting_id"):
        effective_setting_id = person_tune_status["setting_id"]
    notation = _load_setting_notation(conn, tune_id, effective_setting_id)

    cur.execute(
        "SELECT COUNT(*) AS n FROM session_instance_tune WHERE tune_id = %s AND deleted = FALSE",
        (tune_id,),
    )
    global_play_count = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM person_tune WHERE tune_id = %s", (tune_id,))
    person_list_count = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(DISTINCT session_id) AS n FROM session_tune WHERE tune_id = %s", (tune_id,))
    session_count = cur.fetchone()["n"]

    # The viewer's spec 033 lenses: R3 (member sessions) / R4 (attended nights).
    # Only for logged-in viewers; the keys are absent for anonymous ones and the
    # drawer's stats cards key off their presence.
    member_play_count = None
    attended_play_count = None
    if logged_in and person_id:
        cur.execute(
            person_scope.person_tune_play_counts_sql(),
            {"person_id": person_id, "tune_ids": [tune_id]},
        )
        pc = cur.fetchone()
        member_play_count = pc["member_play_count"] if pc else 0
        attended_play_count = pc["attended_play_count"] if pc else 0

    session_tune: Dict[str, Any] = {
        "tune_id": tune_id,
        "tune_name": t["name"],
        "tune_type": t["tune_type"],
        # Session scope (null / absent semantics match the legacy global shape)
        "alias": scope["alias"] if scope else None,
        "aliases": scope["aliases"] if scope else [],
        "key": scope["key"] if scope else None,
        "name": scope["name_override"] if scope else None,
        "key_override": scope["key_override"] if scope else None,
        "setting_override": scope["setting_override"] if scope else None,
        # setting_id keeps each legacy variant's meaning: the session's setting
        # under a session scope, else the setting the notation was resolved from
        # (the viewer's saved setting when on-list, else the tune's first).
        "setting_id": scope["setting_id"] if scope else notation["setting_id"],
        "setting_key": notation["setting_key"],
        "abc": notation["abc"],
        "incipit_abc": notation["incipit_abc"],
        "image": notation["image"],
        "incipit_image": notation["incipit_image"],
        "tunebook_count": t["tunebook_count_cached"],
        "tunebook_count_cached_date": (
            t["tunebook_count_cached_date"].isoformat() if t["tunebook_count_cached_date"] else None
        ),
        "times_played": scope["times_played"] if scope else 0,
        "global_play_count": global_play_count,
        "person_list_count": person_list_count,
        "session_count": session_count,
        "person_tune_status": person_tune_status,
        **(
            {"member_play_count": member_play_count, "attended_play_count": attended_play_count}
            if member_play_count is not None
            else {}
        ),
        # Scope marker the drawer derives its session wording from, and everything
        # the Session tab renders (spec 037): which session, what it's played at,
        # and who may edit which layer.
        "session_scope": (
            {
                "path": scope["path"],
                "session_name": scope["session_name"],
                "track_attendance": scope["track_attendance"],
                "instance": scope.get("session_instance_id"),
                "date_or_id": scope["date_or_id"],
                "in_repertoire": scope["in_repertoire"],
                "played_instances": scope["played_instances"],
                # The session's own alias/setting/key is the session speaking about
                # its repertoire — admins only. A specific instance is a record of
                # what happened in a room the member was in — any member.
                "can_edit_session": is_session_admin,
                "can_edit_instance": is_session_member,
                # Un-enrolling only ever means "a tune that was never actually
                # played here"; with plays present the link doesn't render at all.
                "can_remove_from_session": is_session_admin and scope["times_played"] == 0,
            }
            if scope
            else None
        ),
    }

    return {
        "success": True,
        "redirected_from": redirected_from,
        "viewer": {
            "logged_in": bool(logged_in),
            "is_admin": bool(is_admin),
            "is_session_admin": is_session_admin,
            "is_session_member": is_session_member,
        },
        "session_tune": session_tune,
    }


# ---------------------------------------------------------------------------
# recording segmenter (spec 050) — the audio-to-tune timestamping tool.
#
# One payload carries everything the tool needs: the recording (with a presigned
# audio URL), the instance's tune log flattened into set-aware order, and each
# tune's segment if it already has one. The operator's whole job is filling in
# the `segment` field on each of those tunes, so log and segments must arrive
# together and in the SAME order the tunes were played.
# ---------------------------------------------------------------------------


def _segment_row_to_dict(row) -> Dict[str, Any]:
    """Pure mapper: a recording_tune_segment row -> wire shape.

    end_ms stays None when implicit. The client, not the server, resolves an
    implicit end to the next tune's start, because it re-resolves live on every
    keystroke as marks move; the DB view does the same for the export.
    """
    return {
        "recording_tune_segment_id": row["recording_tune_segment_id"],
        "session_instance_tune_id": row["session_instance_tune_id"],
        "start_ms": int(row["start_ms"]),
        "end_ms": int(row["end_ms"]) if row["end_ms"] is not None else None,
    }


def _load_instance_tune_log(conn, session_instance_id: int, session_id: int) -> List[Dict[str, Any]]:
    """The instance's played tunes in order, with set numbers.

    Set membership comes from the interleaved record_type='break' marker rows
    (the live logger's representation), which are consumed here and never
    surfaced: the segmenter shows tunes, grouped.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT sit.session_instance_tune_id, sit.tune_id, sit.record_type, sit.order_position,
               COALESCE(sit.name, st.alias, t.name) AS display_name,
               t.tune_type
        FROM session_instance_tune sit
        LEFT JOIN tune t ON t.tune_id = sit.tune_id
        LEFT JOIN session_tune st ON st.tune_id = sit.tune_id AND st.session_id = %s
        WHERE sit.session_instance_id = %s AND sit.deleted = FALSE
        ORDER BY sit.order_position
        """,
        (session_id, session_instance_id),
    )

    tunes: List[Dict[str, Any]] = []
    set_number = 1
    position_in_set = 0
    for row in cur.fetchall():
        if row["record_type"] == "break":
            # Only advance on a break that actually closed a set; leading or
            # doubled break markers would otherwise leave gaps in the numbering.
            if position_in_set:
                set_number += 1
                position_in_set = 0
            continue
        position_in_set += 1
        tunes.append(
            {
                "session_instance_tune_id": row["session_instance_tune_id"],
                "tune_id": row["tune_id"],
                "name": row["display_name"] or "(unnamed)",
                "tune_type": row["tune_type"],
                "order_position": row["order_position"],
                "set_number": set_number,
                "position_in_set": position_in_set,
                "segment": None,
            }
        )

    # Mark the last tune of each set: those are the ones that need an EXPLICIT
    # end, because nothing follows them closely enough to imply it.
    for idx, tune in enumerate(tunes):
        nxt = tunes[idx + 1] if idx + 1 < len(tunes) else None
        tune["is_set_end"] = nxt is None or nxt["set_number"] != tune["set_number"]

    return tunes


def build_recording_segmenter_payload(
    conn, recording_id: int, *, include_audio_url: bool = True
) -> Optional[Dict[str, Any]]:
    """Everything the segmenter page needs for recording `recording_id`.

    GET /api/recordings/<id>/segmenter returns exactly this and the page shell
    embeds exactly this — one function, so they cannot drift.
    Returns None when the recording doesn't exist.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT r.recording_id, r.session_instance_id, r.person_id, r.label, r.storage_key, r.mime_type,
               r.stream_key, r.stream_mime_type, r.stream_size_bytes,
               r.duration_ms, r.file_size_bytes, r.sample_rate, r.channels,
               r.is_clock_anchor, r.clock_offset_ms, r.started_at, r.peaks_hz, r.notes,
               r.status, r.status_detail,
               (r.peaks IS NOT NULL) AS has_peaks,
               si.session_instance_id AS si_id, si.date, si.session_id,
               s.name AS session_name, s.path AS session_path
        FROM recording r
        JOIN session_instance si ON si.session_instance_id = r.session_instance_id
        JOIN session s ON s.session_id = si.session_id
        WHERE r.recording_id = %s
        """,
        (recording_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    # BOTH sources go to the client, proxy first, so the operator can switch on
    # the fly -- the right trade-off depends on the connection they happen to be
    # on, which is not knowable at import time. Presigning is local HMAC, so a
    # second URL costs nothing.
    #
    # The EXPORT deliberately ignores all of this and keeps naming the master:
    # the training corpus must never be cut from a lossy mono encode.
    audio_sources = []
    audio_error = None
    if include_audio_url:
        try:
            from recording import generate_presigned_url

            if row["stream_key"]:
                audio_sources.append(
                    {
                        "id": "proxy",
                        "label": "low",
                        "url": generate_presigned_url(row["stream_key"]),
                        "mime_type": row["stream_mime_type"] or "audio/mp4",
                        "size_bytes": int(row["stream_size_bytes"]) if row["stream_size_bytes"] else None,
                    }
                )
            audio_sources.append(
                {
                    "id": "master",
                    "label": "full",
                    "url": generate_presigned_url(row["storage_key"]),
                    "mime_type": row["mime_type"],
                    "size_bytes": int(row["file_size_bytes"]) if row["file_size_bytes"] else None,
                }
            )
        except Exception as exc:  # object store misconfigured — the page says so
            audio_sources = []
            audio_error = str(exc)

    tunes = _load_instance_tune_log(conn, row["session_instance_id"], row["session_id"])

    cur.execute(
        """
        SELECT recording_tune_segment_id, session_instance_tune_id, start_ms, end_ms
        FROM recording_tune_segment
        WHERE recording_id = %s
        """,
        (recording_id,),
    )
    by_tune = {r["session_instance_tune_id"]: _segment_row_to_dict(r) for r in cur.fetchall()}
    for tune in tunes:
        tune["segment"] = by_tune.get(tune["session_instance_tune_id"])

    cur.execute(
        """
        SELECT recording_id, label, duration_ms, is_clock_anchor, clock_offset_ms
        FROM recording
        WHERE session_instance_id = %s AND recording_id <> %s
        ORDER BY clock_offset_ms, recording_id
        """,
        (row["session_instance_id"], recording_id),
    )
    others = [
        {
            "recording_id": r["recording_id"],
            "label": r["label"],
            "duration_ms": int(r["duration_ms"]),
            "is_clock_anchor": r["is_clock_anchor"],
            "clock_offset_ms": int(r["clock_offset_ms"]),
        }
        for r in cur.fetchall()
    ]

    return {
        "success": True,
        "recording": {
            "recording_id": row["recording_id"],
            "session_instance_id": row["session_instance_id"],
            "person_id": row["person_id"],
            "label": row["label"],
            "mime_type": row["mime_type"],
            "duration_ms": int(row["duration_ms"]),
            "file_size_bytes": int(row["file_size_bytes"]) if row["file_size_bytes"] else None,
            "sample_rate": row["sample_rate"],
            "channels": row["channels"],
            "is_clock_anchor": row["is_clock_anchor"],
            "clock_offset_ms": int(row["clock_offset_ms"]),
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "peaks_hz": float(row["peaks_hz"]) if row["peaks_hz"] is not None else None,
            "has_peaks": row["has_peaks"],
            "peaks_url": f"/api/recordings/{row['recording_id']}/peaks",
            # Ordered: the first entry is the default the page opens on.
            "audio_sources": audio_sources,
            "audio_error": audio_error,
            "has_proxy": bool(row["stream_key"]),
            "notes": row["notes"],
            # Ingest state (schema/052). Anything but 'ready' means the waveform
            # and the real duration are not there yet, so the tool refuses to
            # open rather than showing a flat line against a guessed length.
            "status": row["status"],
            "status_detail": row["status_detail"],
        },
        "session_instance": {
            "session_instance_id": row["si_id"],
            "date": row["date"].isoformat() if row["date"] else None,
            "session_id": row["session_id"],
            "session_name": row["session_name"],
            "session_path": row["session_path"],
        },
        "tunes": tunes,
        "other_recordings": others,
    }


def build_instance_recordings_payload(conn, session_instance_id: int) -> Dict[str, Any]:
    """Recordings attached to one session instance, with segmenting progress.

    Backs GET /api/session-instances/<id>/recordings and the admin index —
    "which nights are done" is the question this answers.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT r.recording_id, r.label, r.duration_ms, r.is_clock_anchor, r.clock_offset_ms,
               r.started_at, r.mime_type, r.file_size_bytes, r.status, r.status_detail,
               (SELECT count(*) FROM recording_tune_segment rts WHERE rts.recording_id = r.recording_id)
                   AS segment_count
        FROM recording r
        WHERE r.session_instance_id = %s
        ORDER BY r.clock_offset_ms, r.recording_id
        """,
        (session_instance_id,),
    )
    recordings = [
        {
            "recording_id": r["recording_id"],
            "label": r["label"],
            "duration_ms": int(r["duration_ms"]),
            "is_clock_anchor": r["is_clock_anchor"],
            "clock_offset_ms": int(r["clock_offset_ms"]),
            "started_at": r["started_at"].isoformat() if r["started_at"] else None,
            "mime_type": r["mime_type"],
            "file_size_bytes": int(r["file_size_bytes"]) if r["file_size_bytes"] else None,
            "segment_count": r["segment_count"],
            # Ingest state (schema/052): the in-log Recordings modal shows a
            # freshly uploaded row while it is still being processed, so it needs
            # to say so rather than presenting a guessed duration as fact.
            "status": r["status"],
            "status_detail": r["status_detail"],
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT count(*) AS n FROM session_instance_tune
        WHERE session_instance_id = %s AND deleted = FALSE AND record_type <> 'break'
        """,
        (session_instance_id,),
    )
    tune_count = cur.fetchone()["n"]

    return {
        "success": True,
        "session_instance_id": session_instance_id,
        "tune_count": tune_count,
        "recordings": recordings,
    }


def build_instance_audio_payload(conn, session_instance_id: int) -> Dict[str, Any]:
    """Playback data for the session-instance page: one recording and its marks.

    The segmenter's payload is the wrong shape for listening — it carries the
    whole tune log, both audio sources, the waveform, and the other recordings,
    because its job is EDITING the marks. This one answers a much smaller
    question: "is there audio for this night, and where does each tune sit in
    it?" The page already knows the tune log; it only needs the offsets.

    A `recording` of None is the ordinary case (most nights have no audio) and
    is not an error — the page simply shows no play buttons.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Only a recording that is both playable and timestamped is any use here, so
    # segment_count > 0 is part of the selection rather than something the caller
    # discovers afterwards. Where a night has several, the most-segmented one is
    # the one someone actually worked on; the anchor breaks the tie because a
    # second recording's clock_offset_ms is still unsettable in the UI (spec 050),
    # so only the anchor's offsets can be trusted against the log.
    cur.execute(
        """
        SELECT r.recording_id, r.label, r.duration_ms, r.storage_key, r.mime_type,
               r.file_size_bytes, r.stream_key, r.stream_mime_type, r.stream_size_bytes,
               (SELECT count(*) FROM recording_tune_segment rts
                 WHERE rts.recording_id = r.recording_id) AS segment_count
        FROM recording r
        WHERE r.session_instance_id = %s AND r.status = 'ready'
        ORDER BY segment_count DESC, r.is_clock_anchor DESC, r.recording_id
        LIMIT 1
        """,
        (session_instance_id,),
    )
    row = cur.fetchone()
    if not row or not row["segment_count"]:
        return {
            "success": True,
            "session_instance_id": session_instance_id,
            "recording": None,
            "segments": [],
        }

    # Both encodes, proxy FIRST -- the page opens on it, because this is listening
    # rather than corpus work: 32kbps mono is indistinguishable for "what was that
    # tune?" and at a fraction of the bytes it makes a mid-set seek on a phone
    # instant instead of a stall. The master rides along as the HD option for
    # someone on a connection that can take it.
    #
    # Both go down in ONE payload rather than the page re-asking when HD is
    # picked: presigning is local HMAC, so the second URL is free, and having it
    # in hand is what lets the switch keep the listener's place instead of
    # stalling on a round trip mid-tune.
    #
    # `size_bytes` is not decoration -- it is the only honest basis the listener
    # has for deciding whether HD is a good idea on the connection they're on.
    audio_sources = []
    audio_error = None
    try:
        from recording import generate_presigned_url

        if row["stream_key"]:
            audio_sources.append(
                {
                    "id": "proxy",
                    "url": generate_presigned_url(row["stream_key"]),
                    "mime_type": row["stream_mime_type"] or "audio/mp4",
                    "size_bytes": int(row["stream_size_bytes"]) if row["stream_size_bytes"] else None,
                }
            )
        # Always present: the HD option when a proxy exists, and the only thing
        # there is to play when one doesn't (ingest predating schema/051, or a
        # transcode that failed).
        audio_sources.append(
            {
                "id": "master",
                "url": generate_presigned_url(row["storage_key"]),
                "mime_type": row["mime_type"] or "audio/mp4",
                "size_bytes": int(row["file_size_bytes"]) if row["file_size_bytes"] else None,
            }
        )
    except Exception as exc:  # object store misconfigured — the page says so
        audio_sources = []
        audio_error = str(exc)

    cur.execute(
        """
        SELECT rts.session_instance_tune_id, rts.start_ms, rts.end_ms
        FROM recording_tune_segment rts
        JOIN session_instance_tune sit
          ON sit.session_instance_tune_id = rts.session_instance_tune_id
        WHERE rts.recording_id = %s AND sit.deleted = FALSE
        ORDER BY rts.start_ms
        """,
        (row["recording_id"],),
    )
    # end_ms stays None when implicit, exactly as the segmenter sends it: the
    # client resolves it to the next placed tune's start with the same shared
    # resolveSegments() both pages use, so a tune's extent can never differ
    # between the tool that marked it and the page that plays it.
    segments = [
        {
            "session_instance_tune_id": s["session_instance_tune_id"],
            "start_ms": int(s["start_ms"]),
            "end_ms": int(s["end_ms"]) if s["end_ms"] is not None else None,
        }
        for s in cur.fetchall()
    ]

    return {
        "success": True,
        "session_instance_id": session_instance_id,
        "recording": {
            "recording_id": row["recording_id"],
            "label": row["label"],
            "duration_ms": int(row["duration_ms"]),
            # Ordered: the first entry is the one the page opens on.
            "audio_sources": audio_sources,
            "audio_error": audio_error,
        },
        "segments": segments,
    }
