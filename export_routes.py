# i18n-converted
"""Export: a person's tune list, a session's tunes, or a session's logs, as a
file (JSON, CSV or PDF).

The pages do the choosing. My Tunes and the session page already filter on the
client with their state in the URL, so "export mode" on those pages (`?export=1`)
is the real page with its real filters plus an export bar; the bar POSTs the ids
it is showing, in display order, and this module turns them into the file. The
server never re-derives the filters; it only resolves names, keys, settings and
notation for the ids it is handed, so the file always matches the screen.

Names and settings follow the chains the rest of the app uses:

  My Tunes       your name for the tune, else the catalogue's;
                 your setting, else the tune's first.
  Session tunes  the session's name ("we call this"), else the catalogue's;
                 the session's setting, else the tune's first.
  Session logs   the name used that night, else the session's, else the
                 catalogue's; the night's setting, else the session's, else
                 the tune's first; the same for the key.

People in a session's logs (who started a set, who was there) appear only for
a member of that session, as on the public live log.

PDF notation comes from tune_setting.image, the abc-renderer's cached PNG. A
`check: true` request answers with the settings still lacking one, so the
client can warm them through the existing setting-image endpoint before asking
for the file; the file request itself renders at most a handful inline.
"""

import csv
import datetime
import io
import json
import re

from flask import jsonify, request, send_file
from flask_babel import format_date, gettext as _, gettext as tr
from flask_login import current_user

from api_auth import api_error, api_login_required, public_api
from database import get_db_connection

FORMATS = ("json", "csv", "pdf")
MAX_IDS = 5000
# Uncached notation images the file request will render itself. Beyond this the
# client should have warmed them first (it checks before it asks).
MAX_INLINE_RENDERS = 30
MAX_FILTER_LINES = 40


# ---------------------------------------------------------------------------
# request parsing and small helpers
# ---------------------------------------------------------------------------


def _parse(body, ids_key):
    """A dict {fmt, ids, filters, check}, or an api_error response (a tuple)."""
    if not isinstance(body, dict):
        return api_error(_("No JSON data provided"), 400)
    fmt = str(body.get("format") or "").lower()
    if fmt not in FORMATS:
        return api_error(_("Choose JSON, CSV or PDF."), 400, code="invalid_format")
    ids = body.get(ids_key)
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        return api_error(_("Nothing to export."), 400, code="nothing_to_export")
    if not ids:
        return api_error(
            _("Nothing to export: the list is empty."), 400, code="nothing_to_export"
        )
    if len(ids) > MAX_IDS:
        return api_error(
            _(
                "That is too much for one file (%(max)s at most). Narrow the filters.",
                max=MAX_IDS,
            ),
            413,
            code="too_many",
        )
    filters = body.get("filters") or []
    if not isinstance(filters, list):
        filters = []
    filters = [str(f)[:200] for f in filters if isinstance(f, (str, int, float))][
        :MAX_FILTER_LINES
    ]
    # Keep the client's order but drop repeats.
    seen = set()
    ids = [i for i in ids if not (i in seen or seen.add(i))]
    return {
        "fmt": fmt,
        "ids": ids,
        "filters": filters,
        "check": bool(body.get("check")),
    }


def _viewer_person_id():
    if not current_user.is_authenticated:
        return None
    return getattr(current_user, "person_id", None)


def _display_name(first, last):
    if not first:
        return None
    return f"{first} {last[0]}" if last else first


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "ceol"


def _today():
    return datetime.date.today().isoformat()


def _resolve_session(cur, session_path):
    """(session_id, path, name) for a session path, following aliases; None if
    there is no such session."""
    from places import resolve_session_path

    hit = resolve_session_path(cur, session_path)
    if not hit or hit.get("kind") != "session":
        return None
    cur.execute("SELECT name FROM session WHERE session_id = %s", (hit["session_id"],))
    row = cur.fetchone()
    return (hit["session_id"], hit["path"], row[0] if row else session_path)


def _first_settings(cur, tune_ids):
    """tune_id -> its first setting_id, for tunes with no chosen setting."""
    if not tune_ids:
        return {}
    cur.execute(
        """
        SELECT DISTINCT ON (tune_id) tune_id, setting_id
        FROM tune_setting WHERE tune_id = ANY(%s)
        ORDER BY tune_id, setting_id ASC
        """,
        (list(tune_ids),),
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def _load_settings(cur, setting_ids, with_images):
    """setting_id -> {abc, key, image}. Images are bytes or None."""
    ids = [s for s in set(setting_ids) if s is not None]
    if not ids:
        return {}
    cols = "setting_id, abc, key" + (", image" if with_images else "")
    cur.execute(f"SELECT {cols} FROM tune_setting WHERE setting_id = ANY(%s)", (ids,))
    out = {}
    for row in cur.fetchall():
        image = _image_bytes(row[3]) if with_images and row[3] is not None else None
        out[row[0]] = {"abc": row[1], "key": row[2], "image": image}
    return out


def _image_bytes(data):
    """tune_setting.image as bytes. The column is declared TEXT but written as
    bytea, so psycopg2 may hand back a memoryview, bytes, or a '\\x…' hex
    string (the same cases api_routes.bytea_to_base64 handles)."""
    if isinstance(data, memoryview):
        return data.tobytes()
    if isinstance(data, str):
        if data.startswith("\\x"):
            return bytes.fromhex(data[2:])
        return data.encode("latin1")
    return bytes(data)


def _missing_images(cur, setting_ids):
    """The settings among `setting_ids` with ABC but no cached full image."""
    ids = [s for s in set(setting_ids) if s is not None]
    if not ids:
        return []
    cur.execute(
        """
        SELECT setting_id FROM tune_setting
        WHERE setting_id = ANY(%s) AND image IS NULL AND abc IS NOT NULL AND abc <> ''
        ORDER BY setting_id
        """,
        (ids,),
    )
    return [row[0] for row in cur.fetchall()]


def _render_inline(conn, cur, missing):
    """Render the few images the check left behind (or that nobody checked for).
    Returns an api_error response when there are too many to do in one request."""
    if len(missing) > MAX_INLINE_RENDERS:
        return api_error(
            _(
                "The notation for %(n)s tunes still has to be drawn. Try again in a moment.",
                n=len(missing),
            ),
            409,
            code="notation_pending",
        )
    from live_logging_routes import _ensure_setting_image

    for setting_id in missing:
        try:
            _ensure_setting_image(cur, setting_id, "full")
            conn.commit()
        except Exception:
            conn.rollback()
    return None


def _check_response(cur, setting_ids):
    missing = _missing_images(cur, setting_ids)
    return jsonify(
        {
            "success": True,
            "missing_setting_ids": missing,
            "total": len(set(s for s in setting_ids if s)),
        }
    )


def _file(data, mimetype, filename):
    return send_file(
        io.BytesIO(data),
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )


def _json_file(payload, stem):
    data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode(
        "utf-8"
    )
    return _file(data, "application/json", f"{stem}.json")


def _csv_file(columns, rows, stem):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    # A BOM so spreadsheets open the accents correctly.
    data = ("﻿" + buf.getvalue()).encode("utf-8")
    return _file(data, "text/csv; charset=utf-8", f"{stem}.csv")


def _pdf_file(data, stem):
    return _file(data, "application/pdf", f"{stem}.pdf")


def _exported_line():
    return _(
        "Exported from ceol.app on %(date)s",
        date=format_date(datetime.date.today(), "long"),
    )


def _tags(value):
    return ";".join(value) if isinstance(value, list) else (value or "")


# ---------------------------------------------------------------------------
# My Tunes
# ---------------------------------------------------------------------------


def _my_tunes_rows(cur, person_id, tune_ids):
    """One dict per tune in `tune_ids` order, name and setting resolved."""
    cur.execute(
        """
        SELECT pt.tune_id, COALESCE(pt.name_alias, t.name) AS name, t.name AS catalogue_name,
               t.tune_type, pt.learn_status, pt.heard_count, pt.tags, pt.notes,
               pt.learned_date, pt.created_date, pt.key, pt.setting_id
        FROM person_tune pt LEFT JOIN tune t ON t.tune_id = pt.tune_id
        WHERE pt.person_id = %s AND pt.tune_id = ANY(%s)
        """,
        (person_id, tune_ids),
    )
    by_id = {}
    for r in cur.fetchall():
        by_id[r[0]] = {
            "tune_id": r[0],
            "name": r[1],
            "catalogue_name": r[2],
            "tune_type": r[3],
            "learn_status": r[4],
            "heard_count": r[5],
            "tags": list(r[6] or []),
            "notes": r[7],
            "learned_date": r[8].isoformat() if r[8] else None,
            "added_date": r[9].isoformat() if r[9] else None,
            "key": r[10],
            "setting_id": r[11],
        }
    cur.execute(
        "SELECT tune_id, instrument, status FROM person_tune_instrument WHERE person_id = %s AND tune_id = ANY(%s)",
        (person_id, tune_ids),
    )
    for tune_id, instrument, status in cur.fetchall():
        if tune_id in by_id:
            by_id[tune_id].setdefault("instrument_statuses", {})[instrument] = status
    rows = [by_id[i] for i in tune_ids if i in by_id]
    firsts = _first_settings(cur, [r["tune_id"] for r in rows if not r["setting_id"]])
    for r in rows:
        r.setdefault("instrument_statuses", {})
        if not r["setting_id"]:
            r["setting_id"] = firsts.get(r["tune_id"])
        r["thesession_url"] = f"https://thesession.org/tunes/{r['tune_id']}" + (
            f"?setting={r['setting_id']}#setting{r['setting_id']}"
            if r["setting_id"]
            else ""
        )
    return rows


def _attach_settings(cur, rows, with_images):
    settings = _load_settings(cur, [r["setting_id"] for r in rows], with_images)
    for r in rows:
        s = settings.get(r["setting_id"]) or {}
        r["setting_key"] = s.get("key")
        r["abc"] = s.get("abc")
        if not r.get("key"):
            r["key"] = s.get("key")
        if with_images:
            r["image"] = s.get("image")


_TUNE_CSV_COLUMNS = [
    "tune_id",
    "name",
    "catalogue_name",
    "tune_type",
    "learn_status",
    "heard_count",
    "tags",
    "notes",
    "learned_date",
    "added_date",
    "key",
    "setting_id",
    "setting_key",
    "thesession_url",
    "abc",
]


@api_login_required
def export_my_tunes(force_check=False):
    """POST /api/export/my-tunes  {format, tune_ids, filters, check?}"""
    parsed = _parse(request.get_json(silent=True), "tune_ids")
    if not isinstance(parsed, dict):
        return parsed
    fmt, tune_ids, filters, check = (
        parsed["fmt"],
        parsed["ids"],
        parsed["filters"],
        parsed["check"],
    )
    check = check or force_check
    person_id = _viewer_person_id()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT first_name, last_name FROM person WHERE person_id = %s",
            (person_id,),
        )
        who = cur.fetchone()
        person_name = f"{who[0]} {who[1]}".strip() if who else ""
        rows = _my_tunes_rows(cur, person_id, tune_ids)
        if not rows:
            return api_error(
                _("None of those tunes are on your list."), 404, code="not_found"
            )
        if check and (fmt == "pdf" or force_check):
            return _check_response(cur, [r["setting_id"] for r in rows])
        if fmt == "pdf":
            err = _render_inline(
                conn, cur, _missing_images(cur, [r["setting_id"] for r in rows])
            )
            if err:
                return err
        _attach_settings(cur, rows, with_images=(fmt == "pdf"))
        stem = f"ceol-my-tunes-{_today()}"
        if fmt == "json":
            return _json_file(
                {
                    "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
                    "source": "my-tunes",
                    "person": {"name": person_name},
                    "filters": filters,
                    "tunes": rows,
                },
                stem,
            )
        if fmt == "csv":
            return _csv_file(
                _TUNE_CSV_COLUMNS,
                [
                    [
                        r["tune_id"],
                        r["name"],
                        r["catalogue_name"],
                        r["tune_type"],
                        r["learn_status"],
                        r["heard_count"],
                        _tags(r["tags"]),
                        r["notes"],
                        r["learned_date"],
                        r["added_date"],
                        r["key"],
                        r["setting_id"],
                        r["setting_key"],
                        r["thesession_url"],
                        r["abc"],
                    ]
                    for r in rows
                ],
                stem,
            )
        from export_pdf import tunes_pdf

        title = (
            _("My Tunes · %(name)s", name=person_name) if person_name else _("My Tunes")
        )
        return _pdf_file(tunes_pdf(title, _exported_line(), filters, rows), stem)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session tunes
# ---------------------------------------------------------------------------


def _session_tune_rows(cur, session_id, tune_ids):
    from services import person_scope

    cur.execute(
        f"""
        SELECT st.tune_id, COALESCE(st.alias, t.name) AS name, t.name AS catalogue_name,
               t.tune_type, st.key, st.setting_id,
               COALESCE(pc.play_count, 0) AS play_count,
               COALESCE(t.tunebook_count_cached, 0) AS tunebook_count
        FROM session_tune st
        LEFT JOIN tune t ON t.tune_id = st.tune_id
        LEFT JOIN (
            SELECT sit.tune_id, COUNT(*) AS play_count
            FROM session_instance_tune sit
            JOIN session_instance si ON si.session_instance_id = sit.session_instance_id
            WHERE si.session_id = %s AND {person_scope.SIT_COUNTABLE}
            GROUP BY sit.tune_id
        ) pc ON pc.tune_id = st.tune_id
        WHERE st.session_id = %s AND st.tune_id = ANY(%s)
        """,
        (session_id, session_id, tune_ids),
    )
    by_id = {
        r[0]: {
            "tune_id": r[0],
            "name": r[1],
            "catalogue_name": r[2],
            "tune_type": r[3],
            "key": r[4],
            "setting_id": r[5],
            "play_count": r[6],
            "tunebook_count": r[7],
        }
        for r in cur.fetchall()
    }
    rows = [by_id[i] for i in tune_ids if i in by_id]
    firsts = _first_settings(cur, [r["tune_id"] for r in rows if not r["setting_id"]])
    for r in rows:
        if not r["setting_id"]:
            r["setting_id"] = firsts.get(r["tune_id"])
        r["thesession_url"] = f"https://thesession.org/tunes/{r['tune_id']}" + (
            f"?setting={r['setting_id']}#setting{r['setting_id']}"
            if r["setting_id"]
            else ""
        )
    return rows


_SESSION_TUNE_CSV_COLUMNS = [
    "tune_id",
    "name",
    "catalogue_name",
    "tune_type",
    "play_count",
    "tunebook_count",
    "key",
    "setting_id",
    "setting_key",
    "thesession_url",
    "abc",
]


@public_api
def export_session_tunes(session_path, force_check=False):
    """POST /api/export/sessions/<path>/tunes  {format, tune_ids, filters, check?}
    Public: a session's tunes are public on its page."""
    parsed = _parse(request.get_json(silent=True), "tune_ids")
    if not isinstance(parsed, dict):
        return parsed
    fmt, tune_ids, filters, check = (
        parsed["fmt"],
        parsed["ids"],
        parsed["filters"],
        parsed["check"],
    )
    check = check or force_check
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        found = _resolve_session(cur, session_path)
        if not found:
            return api_error(_("Session not found"), 404, code="not_found")
        session_id, path, session_name = found
        rows = _session_tune_rows(cur, session_id, tune_ids)
        if not rows:
            return api_error(
                _("None of those tunes are on this session's list."),
                404,
                code="not_found",
            )
        if check and (fmt == "pdf" or force_check):
            return _check_response(cur, [r["setting_id"] for r in rows])
        if fmt == "pdf":
            err = _render_inline(
                conn, cur, _missing_images(cur, [r["setting_id"] for r in rows])
            )
            if err:
                return err
        _attach_settings(cur, rows, with_images=(fmt == "pdf"))
        stem = f"ceol-{_slug(path)}-tunes-{_today()}"
        if fmt == "json":
            return _json_file(
                {
                    "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
                    "source": "session-tunes",
                    "session": {"path": path, "name": session_name},
                    "filters": filters,
                    "tunes": rows,
                },
                stem,
            )
        if fmt == "csv":
            return _csv_file(
                _SESSION_TUNE_CSV_COLUMNS,
                [
                    [
                        r["tune_id"],
                        r["name"],
                        r["catalogue_name"],
                        r["tune_type"],
                        r["play_count"],
                        r["tunebook_count"],
                        r["key"],
                        r["setting_id"],
                        r["setting_key"],
                        r["thesession_url"],
                        r["abc"],
                    ]
                    for r in rows
                ],
                stem,
            )
        from export_pdf import tunes_pdf

        return _pdf_file(
            tunes_pdf(
                _("%(session)s · Tunes", session=session_name),
                _exported_line(),
                filters,
                rows,
            ),
            stem,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session logs
# ---------------------------------------------------------------------------


def _set_label(tunes):
    """The set's type, or Mixed, in the viewer's language."""
    types = {t["tune_type"] for t in tunes if t.get("tune_type")}
    if len(types) == 1:
        return tr(next(iter(types)))  # the type names are in the catalog (export_pdf)
    return _("Mixed") if types else _("Tunes")


def _night_rows(cur, session_id, instance_ids, include_people):
    """One dict per night in `instance_ids` order: the night's details, its
    people (members only) and its sets with their tunes, overrides resolved."""
    cur.execute(
        """
        SELECT session_instance_id, date, start_time, end_time, location_override,
               comments, is_cancelled
        FROM session_instance
        WHERE session_id = %s AND session_instance_id = ANY(%s)
        """,
        (session_id, instance_ids),
    )
    nights = {}
    for r in cur.fetchall():
        nights[r[0]] = {
            "session_instance_id": r[0],
            "date": r[1].isoformat() if r[1] else None,
            "start_time": r[2].strftime("%H:%M") if r[2] else None,
            "end_time": r[3].strftime("%H:%M") if r[3] else None,
            "location": r[4],
            "notes": r[5],
            "is_cancelled": bool(r[6]),
            "sets": [],
        }
    ordered_ids = [i for i in instance_ids if i in nights]
    if not ordered_ids:
        return []

    # Every record of every night, in log order; break rows close a set.
    cur.execute(
        """
        SELECT sit.session_instance_id, sit.record_type, sit.tune_id,
               COALESCE(sit.name, st.alias, t.name) AS name, t.name AS catalogue_name,
               t.tune_type, sit.key_override, st.key, sit.setting_override, st.setting_id,
               sp.first_name, sp.last_name
        FROM session_instance_tune sit
        LEFT JOIN tune t ON t.tune_id = sit.tune_id
        LEFT JOIN session_tune st ON st.session_id = %s AND st.tune_id = sit.tune_id
        LEFT JOIN person sp ON sp.person_id = sit.started_by_person_id
        WHERE sit.session_instance_id = ANY(%s) AND NOT sit.deleted
        ORDER BY sit.session_instance_id, sit.order_position
        """,
        (session_id, ordered_ids),
    )
    current = {}  # instance_id -> the open set's tune list

    def close(instance_id):
        tunes = current.pop(instance_id, None)
        if tunes:
            night = nights[instance_id]
            night["sets"].append(
                {
                    "number": len(night["sets"]) + 1,
                    "label": _set_label(tunes),
                    "started_by": tunes[0].pop("_started_by", None)
                    if include_people
                    else None,
                    "tunes": tunes,
                }
            )
        for t in tunes or []:
            t.pop("_started_by", None)

    for r in cur.fetchall():
        instance_id = r[0]
        if r[1] == "break":
            close(instance_id)
            continue
        tunes = current.setdefault(instance_id, [])
        tunes.append(
            {
                "position": len(tunes) + 1,
                "tune_id": r[2],
                "name": r[3],
                "catalogue_name": r[4],
                "tune_type": r[5],
                "key": r[6] or r[7],
                "setting_id": r[8] or r[9],
                "unlinked": r[2] is None,
                "_started_by": _display_name(r[10], r[11]),
            }
        )
    for instance_id in list(current):
        close(instance_id)

    # Tunes with neither a night's nor the session's setting take the tune's first.
    unresolved = {
        t["tune_id"]
        for n in nights.values()
        for s in n["sets"]
        for t in s["tunes"]
        if t["tune_id"] and not t["setting_id"]
    }
    firsts = _first_settings(cur, unresolved)
    for n in nights.values():
        for s in n["sets"]:
            for t in s["tunes"]:
                if t["tune_id"] and not t["setting_id"]:
                    t["setting_id"] = firsts.get(t["tune_id"])

    if include_people:
        cur.execute(
            """
            SELECT sip.session_instance_id, p.first_name, p.last_name
            FROM session_instance_person sip JOIN person p ON p.person_id = sip.person_id
            WHERE sip.session_instance_id = ANY(%s) AND sip.attendance = 'yes'
            ORDER BY p.first_name, p.last_name
            """,
            (ordered_ids,),
        )
        for instance_id, first, last in cur.fetchall():
            nights[instance_id].setdefault("attendees", []).append(
                _display_name(first, last)
            )
        for n in nights.values():
            n.setdefault("attendees", [])
    return [nights[i] for i in ordered_ids]


def _all_log_tunes(nights):
    return [t for n in nights for s in n["sets"] for t in s["tunes"]]


_LOG_CSV_COLUMNS = [
    "night_date",
    "session_instance_id",
    "set_number",
    "set_label",
    "started_by",
    "position",
    "tune_id",
    "name",
    "catalogue_name",
    "tune_type",
    "key",
    "setting_id",
    "setting_key",
    "abc",
]


def _night_heading(night):
    """'Thursday 13 November 2025' in the viewer's language, with the time range."""
    date = datetime.date.fromisoformat(night["date"]) if night["date"] else None
    heading = format_date(date, "full") if date else _("Undated")
    if night.get("start_time"):
        heading += f"  ·  {night['start_time']}"
        if night.get("end_time"):
            heading += f"–{night['end_time']}"
    if night.get("is_cancelled"):
        heading += "  ·  " + _("Cancelled")
    return heading


@public_api
def export_session_logs(session_path, force_check=False):
    """POST /api/export/sessions/<path>/logs  {format, instance_ids, filters, check?}
    Public: logs are public on the session page. People only for a member."""
    parsed = _parse(request.get_json(silent=True), "instance_ids")
    if not isinstance(parsed, dict):
        return parsed
    fmt, instance_ids, filters, check = (
        parsed["fmt"],
        parsed["ids"],
        parsed["filters"],
        parsed["check"],
    )
    check = check or force_check
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        found = _resolve_session(cur, session_path)
        if not found:
            return api_error(_("Session not found"), 404, code="not_found")
        session_id, path, session_name = found
        from api_routes import is_session_member_for

        include_people = is_session_member_for(cur, session_id, _viewer_person_id())
        nights = _night_rows(cur, session_id, instance_ids, include_people)
        if not nights:
            return api_error(
                _("None of those nights belong to this session."), 404, code="not_found"
            )
        tunes = _all_log_tunes(nights)
        setting_ids = [t["setting_id"] for t in tunes]
        if check and (fmt == "pdf" or force_check):
            return _check_response(cur, setting_ids)
        if fmt == "pdf":
            err = _render_inline(conn, cur, _missing_images(cur, setting_ids))
            if err:
                return err
        settings = _load_settings(cur, setting_ids, with_images=(fmt == "pdf"))
        for t in tunes:
            s = settings.get(t["setting_id"]) or {}
            t["setting_key"] = s.get("key")
            t["abc"] = s.get("abc")
            if not t.get("key"):
                t["key"] = s.get("key")
            if fmt == "pdf":
                t["image"] = s.get("image")
        stem = f"ceol-{_slug(path)}-logs-{_today()}"
        if fmt == "json":
            return _json_file(
                {
                    "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
                    "source": "session-logs",
                    "session": {"path": path, "name": session_name},
                    "filters": filters,
                    "includes_people": bool(include_people),
                    "nights": nights,
                },
                stem,
            )
        if fmt == "csv":
            rows = []
            for n in nights:
                for s in n["sets"]:
                    for t in s["tunes"]:
                        rows.append(
                            [
                                n["date"],
                                n["session_instance_id"],
                                s["number"],
                                s["label"],
                                s.get("started_by"),
                                t["position"],
                                t["tune_id"],
                                t["name"],
                                t["catalogue_name"],
                                t["tune_type"],
                                t["key"],
                                t["setting_id"],
                                t["setting_key"],
                                t["abc"],
                            ]
                        )
            return _csv_file(_LOG_CSV_COLUMNS, rows, stem)
        from export_pdf import logs_pdf

        for n in nights:
            n["heading"] = _night_heading(n)
            n["where"] = n.get("location")
            if include_people and n.get("attendees"):
                n["attendees"] = _("There: %(names)s", names=", ".join(n["attendees"]))
            else:
                n["attendees"] = None
        return _pdf_file(
            logs_pdf(
                _("%(session)s · Logs", session=session_name),
                _exported_line(),
                filters,
                nights,
            ),
            stem,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# the chooser's data
# ---------------------------------------------------------------------------


@api_login_required
def export_options():
    """GET /api/export/options: the same payload the /export page embeds."""
    from serializers import build_export_options_payload

    conn = get_db_connection()
    try:
        return jsonify(build_export_options_payload(conn, _viewer_person_id()))
    finally:
        conn.close()
