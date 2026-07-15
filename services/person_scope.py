"""Canonical person↔tune relationship predicates (spec 033).

The app relates a person to tunes in exactly four ways, and every count, filter,
history scope, and sort MUST build on these fragments — never inline its own
join — so the semantics can't drift again:

  R1 tunebook    — person_tune row exists
  R3 member      — played at an instance of a session the person is a MEMBER of
  R4 attended    — played at an instance the person ATTENDED (attendance='yes')

(Spec 033 also defined R2 "repertoire" — session_tune of a member session — but
it is deliberately NOT surfaced: plays auto-enroll tunes into session_tune, so
R2 only differs from R3 for on-list-but-never-played tunes, which isn't a useful
question. Decision 2026-07-13.)

Ground rules (spec 033 §1):
  * Membership means session_person.relationship = 'member'. A 'visitor' row
    (spec 034 — e.g. auto-created by check-in) is NOT membership.
  * Attendance means session_instance_person.attendance = 'yes'. 'maybe' and
    'no' never count toward any tune relationship.
  * Play counts exclude soft-deleted rows and break records (spec 023) and
    count DISTINCT session_instance_id ("times played" = nights, not rows).
  * Membership is a current-state lens, deliberately retroactive: joining a
    session makes its whole history "played at my sessions"; leaving removes it.

Fragments use psycopg2 named params. Callers pick the param names; defaults
assume %(person_id)s.
"""

# WHERE-fragment for any count over session_instance_tune rows ("sit" alias).
SIT_COUNTABLE = "sit.deleted = FALSE AND sit.record_type <> 'break'"

VALID_TUNE_SCOPES = ("member", "attended", "session", "all")


def member_instance_predicate(instance_expr, person_param="%(person_id)s"):
    """R3 instance test: the instance belongs to a session the person is a
    member of. `instance_expr` is a SQL expression yielding a session_instance_id."""
    return (
        "EXISTS (SELECT 1 FROM session_instance msi"
        " JOIN session_person msp ON msp.session_id = msi.session_id"
        f" AND msp.person_id = {person_param}"
        " AND msp.relationship = 'member'"
        f" WHERE msi.session_instance_id = {instance_expr})"
    )


def attended_instance_predicate(instance_expr, person_param="%(person_id)s"):
    """R4 instance test: the person checked in to the instance with attendance='yes'.

    A session with track_attendance off shows nothing about who attended, historic
    included (spec 039), so its rows are excluded here — that's what gives "while I was
    there" its holes at such a session. The rows stay in the table, just unqueried; the
    join to `session` is on the already-selected instance, so it's cheap. (R3/member is
    NOT filtered: it reads the viewer's OWN session_person row, which the flag doesn't
    touch.)"""
    return (
        "EXISTS (SELECT 1 FROM session_instance_person asip"
        " JOIN session_instance asi ON asi.session_instance_id = asip.session_instance_id"
        " JOIN session ass ON ass.session_id = asi.session_id AND ass.track_attendance"
        f" WHERE asip.session_instance_id = {instance_expr}"
        f" AND asip.person_id = {person_param}"
        " AND asip.attendance = 'yes')"
    )


def scope_instance_predicate(scope, instance_expr, person_param="%(person_id)s"):
    """The instance-level predicate for a ?scope= value, or None when the scope
    adds no person-based instance filter ('session' is the caller's session_path
    filter; 'all' is unfiltered)."""
    if scope == "member":
        return member_instance_predicate(instance_expr, person_param)
    if scope == "attended":
        return attended_instance_predicate(instance_expr, person_param)
    return None


def person_tune_play_counts_sql():
    """ONE batched query for member_play_count (R3) + attended_play_count (R4)
    over a set of tunes. Params: person_id, tune_ids (ANY array).

    Seeded from the person's own instances (index scans on
    session_person(person_id) / session_instance_person(person_id)), never from
    the tunes' global play rows, so cost tracks the person's history size, not
    the tunes' popularity. Returns rows (tune_id, member_play_count,
    attended_play_count); tunes with no plays under either lens are absent.
    """
    return f"""
        WITH mine AS (
            SELECT session_instance_id,
                   BOOL_OR(is_member) AS is_member,
                   BOOL_OR(is_attended) AS is_attended
            FROM (
                SELECT si.session_instance_id, TRUE AS is_member, FALSE AS is_attended
                FROM session_instance si
                JOIN session_person sp ON sp.session_id = si.session_id
                WHERE sp.person_id = %(person_id)s AND sp.relationship = 'member'
                UNION ALL
                SELECT sip.session_instance_id, FALSE, TRUE
                FROM session_instance_person sip
                -- Spec 039: exclude attendance at sessions that no longer track it, so
                -- R4 ("while I was there") stops counting those nights. R3/member above
                -- is untouched — it reads the viewer's own session_person row.
                JOIN session_instance asi ON asi.session_instance_id = sip.session_instance_id
                JOIN session ass ON ass.session_id = asi.session_id AND ass.track_attendance
                WHERE sip.person_id = %(person_id)s AND sip.attendance = 'yes'
            ) u
            GROUP BY session_instance_id
        )
        SELECT sit.tune_id,
               COUNT(DISTINCT sit.session_instance_id) FILTER (WHERE m.is_member)   AS member_play_count,
               COUNT(DISTINCT sit.session_instance_id) FILTER (WHERE m.is_attended) AS attended_play_count
        FROM session_instance_tune sit
        JOIN mine m ON m.session_instance_id = sit.session_instance_id
        WHERE sit.tune_id = ANY(%(tune_ids)s) AND {SIT_COUNTABLE}
        GROUP BY sit.tune_id
    """


def plays_sort_expr(kind):
    """ORDER BY expression for the my-tunes list sorts: distinct instances where
    the tune was played under the R3 ('member') or R4 ('attended') lens,
    correlated on pt.person_id / pt.tune_id.

    Correlated-per-row like the sort it replaces — index lookups, fine at this
    app's scale. If it ever measures slow, rewrite as a LEFT JOIN on a
    person_tune_play_counts_sql()-shaped subquery keyed on person_id alone and
    sort on COALESCE(counts.<kind>_play_count, 0).
    """
    if kind == "member":
        rel_join = (
            " JOIN session_instance si ON si.session_instance_id = sit.session_instance_id"
            " JOIN session_person sp ON sp.session_id = si.session_id"
            " AND sp.person_id = pt.person_id AND sp.relationship = 'member'"
        )
    elif kind == "attended":
        # Spec 039: attendance at a track_attendance-off session doesn't count.
        rel_join = (
            " JOIN session_instance_person sip"
            " ON sip.session_instance_id = sit.session_instance_id"
            " AND sip.person_id = pt.person_id AND sip.attendance = 'yes'"
            " JOIN session_instance asi ON asi.session_instance_id = sip.session_instance_id"
            " JOIN session ass ON ass.session_id = asi.session_id AND ass.track_attendance"
        )
    else:
        raise ValueError(f"unknown plays sort kind: {kind}")
    return (
        "(SELECT COUNT(DISTINCT sit.session_instance_id)"
        " FROM session_instance_tune sit"
        f"{rel_join}"
        f" WHERE sit.tune_id = pt.tune_id AND {SIT_COUNTABLE})"
    )
