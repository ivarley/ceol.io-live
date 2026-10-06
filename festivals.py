"""Festival years (spec 056).

A festival is a `place` row of kind 'festival' whose years are the sessions under
its slug: `{slug}/{yyyy}`, `session_type = 'festival'`, `place_id` = its town. This
module answers the cross-year questions: which years a festival has, which one
`/sessions/{slug}` should land on (the window rule), and the `festival` block the
session payloads carry for the year switcher.

The weekday nudge that moves a year's dates to another year is client logic (the
copy form recomputes it as the year is edited): frontend/src/festival/dates.js.
"""

import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo

import places

# /sessions/{festival} jumps to a year when today, in the festival's timezone, is
# within [initiation_date - BEFORE, end + AFTER]. Constants, not per-festival
# columns, until a festival needs otherwise.
FESTIVAL_WINDOW_BEFORE_DAYS = 7
FESTIVAL_WINDOW_AFTER_DAYS = 30


def festival_of_path(cur, path):
    """The festival place a session path lives under, or None."""
    if not path or path.count("/") != 1:
        return None
    place = places.get_place_by_slug(cur, path.split("/")[0])
    return place if place and place["kind"] == "festival" else None


def festival_years(cur, festival):
    """Every year of a festival, oldest first, each with how many of its instances
    have logged tunes."""
    cur.execute(
        """
        SELECT s.session_id, s.path, s.name, s.initiation_date, s.termination_date,
               COALESCE(s.timezone, 'UTC'),
               (SELECT COUNT(*) FROM session_instance si
                 WHERE si.session_id = s.session_id
                   AND EXISTS (SELECT 1 FROM session_instance_tune sit
                                WHERE sit.session_instance_id = si.session_instance_id
                                  AND sit.record_type <> 'break'
                                  AND NOT COALESCE(sit.deleted, FALSE)))
        FROM session s
        WHERE s.path LIKE %s AND s.path ~ %s
        """,
        (f"{festival['slug']}/%", r"^[^/]+/\d{4}$"),
    )
    years = [
        {
            "session_id": row[0],
            "path": row[1],
            "name": row[2],
            "year": int(row[1].split("/")[1]),
            "initiation_date": row[3],
            "termination_date": row[4],
            "timezone": row[5],
            "logged_instances": row[6],
        }
        for row in cur.fetchall()
    ]
    years.sort(key=lambda y: y["year"])
    return years


def _today_in(tz_name, now_utc):
    try:
        return now_utc.astimezone(ZoneInfo(tz_name)).date()
    except Exception:
        return now_utc.date()


def window_pick(years, now_utc=None):
    """The year `/sessions/{festival}` lands on, or None for the picker.

    One year: that year, whatever the date — there is nothing to pick. Otherwise a
    year whose window holds today (in that year's timezone); two in the window → the
    one whose initiation_date is nearer today.
    """
    if not years:
        return None
    if len(years) == 1:
        return years[0]
    now_utc = now_utc or datetime.datetime.now(datetime.timezone.utc)
    best = None
    for y in years:
        start = y["initiation_date"]
        if start is None:
            continue
        end = y["termination_date"] or start
        today = _today_in(y["timezone"], now_utc)
        opens = start - datetime.timedelta(days=FESTIVAL_WINDOW_BEFORE_DAYS)
        closes = end + datetime.timedelta(days=FESTIVAL_WINDOW_AFTER_DAYS)
        if opens <= today <= closes:
            distance = abs((start - today).days)
            if best is None or distance < best[0]:
                best = (distance, y)
    return best[1] if best else None


def picker_order(years, now_utc=None):
    """The picker's order: upcoming years first, the nearest leading, then the
    rest newest first."""
    now_utc = now_utc or datetime.datetime.now(datetime.timezone.utc)
    upcoming, past = [], []
    for y in years:
        start = y["initiation_date"]
        if start is not None and start > _today_in(y["timezone"], now_utc):
            upcoming.append(y)
        else:
            past.append(y)
    upcoming.sort(key=lambda y: y["initiation_date"])
    past.sort(key=lambda y: y["year"], reverse=True)
    return upcoming + past


def year_wire(y):
    """One year on the wire (spec 056 "API")."""
    return {
        "session_id": y["session_id"],
        "path": y["path"],
        "year": y["year"],
        "name": y["name"],
        "initiation_date": y["initiation_date"].isoformat()
        if y["initiation_date"]
        else None,
        "termination_date": y["termination_date"].isoformat()
        if y["termination_date"]
        else None,
        "logged_instances": y["logged_instances"],
    }


def festival_block(cur, session_path):
    """`festival: {place, years}` for a festival year's payloads; None otherwise.
    Years oldest first, which is the order the switcher lists them in."""
    festival = festival_of_path(cur, session_path)
    if festival is None:
        return None
    return {
        "place": places.place_summary(cur, festival),
        "years": [year_wire(y) for y in festival_years(cur, festival)],
    }
