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
            CASE WHEN sp.person_id IS NOT NULL THEN TRUE ELSE FALSE END AS user_is_member,
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
# session detail — the /sessions/<path> page and GET /api/sessions/<path>/detail
# ---------------------------------------------------------------------------

# One session_tune row shape for the whole page: the embedded first page, the
# /tunes/remaining continuation, and anything else listing a session's tunes.
# (This is where the legacy tuple-reshaping hack died — everything is dicts.)
_SESSION_TUNES_SQL = """
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
        WHERE si.session_id = %s
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


def load_session_tunes(conn, session_id: int, *, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
    """A session's repertoire, ordered by play count / popularity / name."""
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
    return [session_tune_to_dict(r) for r in cur.fetchall()]


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
               session_type, timezone
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
    }

    # Human-readable recurrence; legacy freeform text passes through unchanged.
    if session["recurrence"]:
        try:
            from recurrence_utils import to_human_readable

            _json.loads(session["recurrence"])
            session["recurrence_readable"] = to_human_readable(session["recurrence"])
        except (ValueError, TypeError):
            session["recurrence_readable"] = session["recurrence"]
    else:
        session["recurrence_readable"] = None

    session_id = session["session_id"]

    # Permission flags (formerly Jinja-only).
    is_session_admin = bool(is_system_admin)
    is_session_member = False
    if person_id:
        cur.execute(
            "SELECT is_admin FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        member_row = cur.fetchone()
        if member_row is not None:
            is_session_member = True
            if member_row["is_admin"]:
                is_session_admin = True

    # Today in the SESSION's timezone (drives the logs tab's add-instance default).
    try:
        today_in_session_tz = datetime.datetime.now(ZoneInfo(session["timezone"])).date()
    except Exception:
        today_in_session_tz = datetime.datetime.now(ZoneInfo("UTC")).date()

    # Top 20 most-played tunes at this session (includes instance-only tunes).
    cur.execute(
        """
        WITH tune_counts AS (
            SELECT
                COALESCE(sit.name, st.alias, t.name) AS tune_name,
                sit.tune_id,
                COUNT(*) AS play_count,
                COALESCE(t.tunebook_count_cached, 0) AS tunebook_count
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            LEFT JOIN tune t ON sit.tune_id = t.tune_id
            LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = %s
            WHERE si.session_id = %s AND COALESCE(sit.name, st.alias, t.name) IS NOT NULL
            GROUP BY COALESCE(sit.name, st.alias, t.name), sit.tune_id, COALESCE(t.tunebook_count_cached, 0)
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

    tunes = load_session_tunes(conn, session_id, limit=first_page)

    return {
        "success": True,
        "session": session,
        "permissions": {
            "is_logged_in": is_logged_in,
            "is_session_admin": is_session_admin,
            "is_session_member": is_session_member,
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
    pt.heard_count, pt.learned_date, pt.notes, pt.setting_id, pt.name_alias,
    pt.created_date, pt.last_modified_date,
    COALESCE(pt.name_alias, t.name) AS tune_name,
    t.tune_type,
    t.tunebook_count_cached AS tunebook_count
"""

PERSON_TUNE_FROM = "FROM person_tune pt LEFT JOIN tune t ON pt.tune_id = t.tune_id"

# Times played at sessions the person attended (distinct instances). Correlated
# subquery per row of the filtered set; index lookups, fine at this app's scale.
PLAYS_SORT_EXPR = (
    "(SELECT COUNT(DISTINCT sit.session_instance_id)"
    " FROM session_instance_tune sit"
    " INNER JOIN session_instance_person sip"
    " ON sit.session_instance_id = sip.session_instance_id"
    " WHERE sip.person_id = pt.person_id AND sit.tune_id = pt.tune_id)"
)


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
        "created_date": row["created_date"].isoformat() if row["created_date"] else None,
        "last_modified_date": row["last_modified_date"].isoformat() if row["last_modified_date"] else None,
        "tune_name": row["tune_name"],
        "tune_type": row["tune_type"],
        "tunebook_count": row["tunebook_count"],
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


def _attach_session_play_counts(cur, person_id: int, tunes: List[Dict[str, Any]]) -> None:
    """Attach session_play_count (distinct instances the person attended), batched."""
    tune_ids = [t["tune_id"] for t in tunes if t["tune_id"] is not None]
    play_counts: Dict[int, int] = {}
    if tune_ids:
        cur.execute(
            """SELECT sit.tune_id, COUNT(DISTINCT sit.session_instance_id) AS n
               FROM session_instance_tune sit
               INNER JOIN session_instance_person sip
                   ON sit.session_instance_id = sip.session_instance_id
               WHERE sip.person_id = %s AND sit.tune_id = ANY(%s)
               GROUP BY sit.tune_id""",
            (person_id, tune_ids),
        )
        play_counts = {r["tune_id"]: r["n"] for r in cur.fetchall()}
    for t in tunes:
        t["session_play_count"] = play_counts.get(t["tune_id"], 0)


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
    "plays-desc": f"{PLAYS_SORT_EXPR} DESC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
    "plays-asc": f"{PLAYS_SORT_EXPR} ASC, t.tunebook_count_cached DESC NULLS LAST, LOWER(COALESCE(pt.name_alias, t.name)) ASC",
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
    _attach_session_play_counts(cur, person_id, tunes)
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
    return {
        "success": True,
        "tunes": tunes,
        # The person's instruments + auto/manual flags, so the client can resolve
        # per-instrument status alongside each tune's sparse instrument_status overrides.
        "instruments": load_person_instruments(conn, person_id),
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


def load_person_tune(conn, person_tune_id: int) -> Optional[Dict[str, Any]]:
    """Single-record loader: same mapper and enrichments as the list."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        f"SELECT {PERSON_TUNE_COLS} {PERSON_TUNE_FROM} WHERE pt.person_tune_id = %s",
        (person_tune_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = person_tune_to_dict(row)
    _attach_instrument_overrides(cur, d["person_id"], [d])
    _attach_session_play_counts(cur, d["person_id"], [d])
    return d


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
           FROM session_instance_tune WHERE tune_id = %s""",
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
