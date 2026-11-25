"""Exports (export_routes.py): My Tunes, a session's tunes and a session's logs
as JSON, CSV and PDF, against the seeded test database.

The seed gives sarah_fiddle (person 2) a tune list and membership of
austin/mueller, which has tunes and logged nights. Notation images are mostly
absent in the seed and the abc-renderer is not running, so the PDFs here carry
"No notation" lines; the point is that the file builds and the shape holds."""

import csv
import io
import json

import pytest

MUELLER = "austin/mueller"


def _ids(cur, sql, *args):
    cur.execute(sql, args)
    return [r[0] for r in cur.fetchall()]


def _filename(response):
    disposition = response.headers.get("Content-Disposition", "")
    assert "attachment" in disposition
    return disposition.split("filename=")[-1].strip('"; ')


@pytest.mark.integration
class TestExportMyTunes:
    def test_requires_sign_in(self, client):
        r = client.post(
            "/api/export/my-tunes", json={"format": "json", "tune_ids": [1]}
        )
        assert r.status_code == 401

    def test_rejects_bad_requests(self, client, authenticated_user):
        with authenticated_user:
            assert (
                client.post(
                    "/api/export/my-tunes", json={"format": "xlsx", "tune_ids": [1]}
                ).status_code
                == 400
            )
            assert (
                client.post(
                    "/api/export/my-tunes", json={"format": "json", "tune_ids": []}
                ).status_code
                == 400
            )
            assert (
                client.post(
                    "/api/export/my-tunes", json={"format": "json", "tune_ids": ["a"]}
                ).status_code
                == 400
            )
            big = client.post(
                "/api/export/my-tunes",
                json={"format": "json", "tune_ids": list(range(5001))},
            )
            assert big.status_code == 413

    def test_json_keeps_order_and_resolves_settings(
        self, client, authenticated_user, db_cursor
    ):
        ids = _ids(
            db_cursor,
            "SELECT tune_id FROM person_tune WHERE person_id = 2 ORDER BY tune_id",
        )
        assert len(ids) >= 3
        wanted = [ids[2], ids[0], ids[1], ids[0]]  # out of order, with a repeat
        with authenticated_user:
            r = client.post(
                "/api/export/my-tunes",
                json={
                    "format": "json",
                    "tune_ids": wanted,
                    "filters": ["Status: Learning", 7],
                },
            )
        assert r.status_code == 200
        assert r.mimetype == "application/json"
        assert _filename(r).startswith("ceol-my-tunes-") and _filename(r).endswith(
            ".json"
        )
        body = json.loads(r.data.decode("utf-8"))
        assert body["source"] == "my-tunes"
        assert body["filters"] == ["Status: Learning", "7"]
        assert [t["tune_id"] for t in body["tunes"]] == [ids[2], ids[0], ids[1]]
        first = body["tunes"][0]
        for key in (
            "name",
            "catalogue_name",
            "tune_type",
            "learn_status",
            "tags",
            "notes",
            "instrument_statuses",
            "setting_id",
            "setting_key",
            "abc",
            "thesession_url",
        ):
            assert key in first
        # Every tune with a setting on thesession.org resolves to one.
        db_cursor.execute(
            "SELECT tune_id FROM tune_setting WHERE tune_id = ANY(%s)",
            ([ids[2], ids[0], ids[1]],),
        )
        with_settings = {r[0] for r in db_cursor.fetchall()}
        for t in body["tunes"]:
            if t["tune_id"] in with_settings:
                assert t["setting_id"] is not None and t["abc"]

    def test_tunes_not_on_the_list_are_dropped(
        self, client, authenticated_user, db_cursor
    ):
        mine = _ids(db_cursor, "SELECT tune_id FROM person_tune WHERE person_id = 2")
        others = _ids(
            db_cursor, "SELECT tune_id FROM tune WHERE tune_id <> ALL(%s) LIMIT 2", mine
        )
        with authenticated_user:
            r = client.post(
                "/api/export/my-tunes", json={"format": "json", "tune_ids": others}
            )
            assert r.status_code == 404
            r = client.post(
                "/api/export/my-tunes",
                json={"format": "json", "tune_ids": others + mine[:1]},
            )
        assert r.status_code == 200
        assert [t["tune_id"] for t in json.loads(r.data)["tunes"]] == mine[:1]

    def test_csv(self, client, authenticated_user, db_cursor):
        ids = _ids(
            db_cursor,
            "SELECT tune_id FROM person_tune WHERE person_id = 2 ORDER BY tune_id LIMIT 3",
        )
        with authenticated_user:
            r = client.post(
                "/api/export/my-tunes", json={"format": "csv", "tune_ids": ids}
            )
        assert r.status_code == 200
        assert r.mimetype == "text/csv"
        text = r.data.decode("utf-8")
        assert text.startswith("﻿")
        rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
        assert rows[0][:4] == ["tune_id", "name", "catalogue_name", "tune_type"]
        assert rows[0][-1] == "abc"
        assert len(rows) == 1 + len(ids)
        assert [int(r[0]) for r in rows[1:]] == ids

    def test_pdf_check_then_file(self, client, authenticated_user, db_cursor):
        ids = _ids(
            db_cursor,
            "SELECT tune_id FROM person_tune WHERE person_id = 2 ORDER BY tune_id LIMIT 3",
        )
        with authenticated_user:
            check = client.post(
                "/api/export/my-tunes",
                json={"format": "pdf", "tune_ids": ids, "check": True},
            )
            assert check.status_code == 200
            body = check.get_json()
            assert body["success"] is True
            assert isinstance(body["missing_setting_ids"], list)
            assert body["total"] >= 0
            r = client.post(
                "/api/export/my-tunes", json={"format": "pdf", "tune_ids": ids}
            )
        assert r.status_code == 200
        assert r.mimetype == "application/pdf"
        assert r.data[:5] == b"%PDF-"
        assert _filename(r).endswith(".pdf")


@pytest.mark.integration
class TestExportSessionTunes:
    def test_public_json(self, client, db_cursor):
        db_cursor.execute(
            "SELECT session_id, name FROM session WHERE path = %s", (MUELLER,)
        )
        session_id, name = db_cursor.fetchone()
        ids = _ids(
            db_cursor,
            "SELECT tune_id FROM session_tune WHERE session_id = %s ORDER BY tune_id",
            session_id,
        )
        assert len(ids) >= 3
        r = client.post(
            f"/api/export/sessions/{MUELLER}/tunes",
            json={"format": "json", "tune_ids": ids[::-1]},
        )
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["source"] == "session-tunes"
        assert body["session"] == {"path": MUELLER, "name": name}
        assert [t["tune_id"] for t in body["tunes"]] == ids[::-1]
        for key in (
            "name",
            "catalogue_name",
            "tune_type",
            "play_count",
            "tunebook_count",
            "key",
            "setting_id",
            "abc",
        ):
            assert key in body["tunes"][0]
        assert _filename(r).startswith("ceol-austin-mueller-tunes-")

    def test_unknown_session(self, client):
        r = client.post(
            "/api/export/sessions/nowhere/none/tunes",
            json={"format": "json", "tune_ids": [1]},
        )
        assert r.status_code == 404

    def test_csv_and_pdf(self, client, db_cursor):
        db_cursor.execute("SELECT session_id FROM session WHERE path = %s", (MUELLER,))
        (session_id,) = db_cursor.fetchone()
        ids = _ids(
            db_cursor,
            "SELECT tune_id FROM session_tune WHERE session_id = %s ORDER BY tune_id LIMIT 4",
            session_id,
        )
        r = client.post(
            f"/api/export/sessions/{MUELLER}/tunes",
            json={"format": "csv", "tune_ids": ids},
        )
        assert r.status_code == 200 and r.mimetype == "text/csv"
        rows = list(csv.reader(io.StringIO(r.data.decode("utf-8").lstrip("﻿"))))
        assert rows[0][0] == "tune_id" and len(rows) == 1 + len(ids)
        r = client.post(
            f"/api/export/sessions/{MUELLER}/tunes",
            json={"format": "pdf", "tune_ids": ids},
        )
        assert (
            r.status_code == 200
            and r.mimetype == "application/pdf"
            and r.data[:5] == b"%PDF-"
        )


@pytest.mark.integration
class TestExportSessionLogs:
    def _nights(self, cur):
        cur.execute("SELECT session_id FROM session WHERE path = %s", (MUELLER,))
        (session_id,) = cur.fetchone()
        return session_id, _ids(
            cur,
            """SELECT si.session_instance_id FROM session_instance si
               WHERE si.session_id = %s
                 AND EXISTS (SELECT 1 FROM session_instance_tune sit
                             WHERE sit.session_instance_id = si.session_instance_id AND NOT sit.deleted)
               ORDER BY si.date DESC""",
            session_id,
        )

    def test_anonymous_gets_no_people(self, client, db_cursor):
        session_id, nights = self._nights(db_cursor)
        assert nights
        r = client.post(
            f"/api/export/sessions/{MUELLER}/logs",
            json={"format": "json", "instance_ids": nights[:3]},
        )
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["source"] == "session-logs"
        assert body["includes_people"] is False
        assert [n["session_instance_id"] for n in body["nights"]] == nights[:3]
        night = body["nights"][0]
        assert "attendees" not in night
        assert night["sets"], "a logged night has at least one set"
        first_set = night["sets"][0]
        assert first_set["number"] == 1 and first_set["label"]
        assert first_set["started_by"] is None
        tune = first_set["tunes"][0]
        for key in (
            "position",
            "tune_id",
            "name",
            "tune_type",
            "key",
            "setting_id",
            "abc",
            "unlinked",
        ):
            assert key in tune
        # Sets are numbered 1..n and positions restart in each set.
        assert [s["number"] for s in night["sets"]] == list(
            range(1, len(night["sets"]) + 1)
        )
        assert all(s["tunes"][0]["position"] == 1 for s in night["sets"])

    def test_member_gets_people(self, client, authenticated_user, db_cursor):
        session_id, nights = self._nights(db_cursor)
        with authenticated_user:
            r = client.post(
                f"/api/export/sessions/{MUELLER}/logs",
                json={"format": "json", "instance_ids": nights[:2]},
            )
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["includes_people"] is True
        assert all("attendees" in n for n in body["nights"])

    def test_sets_follow_break_rows(self, client, db_cursor):
        session_id, nights = self._nights(db_cursor)
        night_id = nights[0]
        db_cursor.execute(
            """SELECT record_type FROM session_instance_tune
               WHERE session_instance_id = %s AND NOT deleted ORDER BY order_position""",
            (night_id,),
        )
        types = [r[0] for r in db_cursor.fetchall()]
        expected_sets, run = 0, 0
        for t in types:
            if t == "break":
                expected_sets += 1 if run else 0
                run = 0
            else:
                run += 1
        expected_sets += 1 if run else 0
        r = client.post(
            f"/api/export/sessions/{MUELLER}/logs",
            json={"format": "json", "instance_ids": [night_id]},
        )
        body = json.loads(r.data)
        assert len(body["nights"][0]["sets"]) == expected_sets
        assert sum(len(s["tunes"]) for s in body["nights"][0]["sets"]) == types.count(
            "tune"
        )

    def test_other_sessions_nights_are_refused(self, client, db_cursor):
        db_cursor.execute("SELECT session_id FROM session WHERE path = %s", (MUELLER,))
        (session_id,) = db_cursor.fetchone()
        foreign = _ids(
            db_cursor,
            "SELECT session_instance_id FROM session_instance WHERE session_id <> %s LIMIT 2",
            session_id,
        )
        r = client.post(
            f"/api/export/sessions/{MUELLER}/logs",
            json={"format": "json", "instance_ids": foreign},
        )
        assert r.status_code == 404

    def test_csv_and_pdf(self, client, db_cursor):
        session_id, nights = self._nights(db_cursor)
        r = client.post(
            f"/api/export/sessions/{MUELLER}/logs",
            json={"format": "csv", "instance_ids": nights[:2]},
        )
        assert r.status_code == 200 and r.mimetype == "text/csv"
        rows = list(csv.reader(io.StringIO(r.data.decode("utf-8").lstrip("﻿"))))
        assert rows[0][:4] == [
            "night_date",
            "session_instance_id",
            "set_number",
            "set_label",
        ]
        assert len(rows) > 1
        r = client.post(
            f"/api/export/sessions/{MUELLER}/logs",
            json={"format": "pdf", "instance_ids": nights[:2]},
        )
        assert (
            r.status_code == 200
            and r.mimetype == "application/pdf"
            and r.data[:5] == b"%PDF-"
        )
        assert _filename(r).startswith("ceol-austin-mueller-logs-")


@pytest.mark.integration
class TestExportChooserAndBuild:
    def test_build(self, client):
        r = client.get("/api/build")
        assert r.status_code == 200
        body = r.get_json()
        assert (
            body["success"] is True and isinstance(body["build"], str) and body["build"]
        )

    def test_options_need_sign_in(self, client):
        assert client.get("/api/export/options").status_code == 401
        page = client.get("/export")
        assert page.status_code in (302, 401)

    def test_options(self, client, authenticated_user):
        with authenticated_user:
            r = client.get("/api/export/options")
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert any(s["path"] == MUELLER for s in body["my_sessions"])
        assert any(s["path"] == MUELLER for s in body["all_sessions"])
        assert set(body["all_sessions"][0]) == {"path", "name", "place"}


@pytest.mark.integration
class TestExportCheckTwins:
    """The native surface's /check paths: the same handlers forced into check mode."""

    def test_my_tunes_check(self, client, authenticated_user, db_cursor):
        ids = _ids(
            db_cursor,
            "SELECT tune_id FROM person_tune WHERE person_id = 2 ORDER BY tune_id LIMIT 3",
        )
        with authenticated_user:
            r = client.post(
                "/api/export/my-tunes/check", json={"format": "pdf", "tune_ids": ids}
            )
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True and isinstance(body["missing_setting_ids"], list)
        assert "total" in body

    def test_session_checks_are_public_and_report_codes(self, client, db_cursor):
        db_cursor.execute("SELECT session_id FROM session WHERE path = %s", (MUELLER,))
        (session_id,) = db_cursor.fetchone()
        ids = _ids(
            db_cursor,
            "SELECT tune_id FROM session_tune WHERE session_id = %s LIMIT 2",
            session_id,
        )
        r = client.post(
            f"/api/export/sessions/{MUELLER}/tunes/check",
            json={"format": "csv", "tune_ids": ids},
        )
        assert r.status_code == 200 and r.get_json()["success"] is True
        nights = _ids(
            db_cursor,
            "SELECT session_instance_id FROM session_instance WHERE session_id = %s LIMIT 2",
            session_id,
        )
        r = client.post(
            f"/api/export/sessions/{MUELLER}/logs/check",
            json={"format": "pdf", "instance_ids": nights},
        )
        assert r.status_code == 200 and "missing_setting_ids" in r.get_json()
        bad = client.post(
            f"/api/export/sessions/{MUELLER}/tunes/check",
            json={"format": "docx", "tune_ids": ids},
        )
        assert bad.status_code == 400 and bad.get_json()["code"] == "invalid_format"
        gone = client.post(
            "/api/export/sessions/no/such/tunes/check",
            json={"format": "pdf", "tune_ids": ids},
        )
        assert gone.status_code == 404 and gone.get_json()["code"] == "not_found"
