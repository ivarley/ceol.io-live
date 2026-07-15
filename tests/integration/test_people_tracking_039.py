"""Spec 039 — per-session people-tracking flags.

Three independent switches on `session`, all default TRUE (opt-out):
  show_people_list    the members roster (the People tab)
  track_attendance    check-ins; off => attendance excluded from every display, app-wide
  track_set_starters  the "started by" pill; requires attendance (a DB CHECK)

These tests pin the pieces that are easy to get subtly wrong: the app-wide attendance
exclusion (the point is that a session hiding attendance hides it everywhere, historic
included, not only on its own page), the People-tab gate applying even to admins, the
create/admin write paths, and the constraint.
"""
import json

import psycopg2
import pytest


@pytest.fixture
def people_fixture(db_cursor, db_conn):
    """A session with one instance, one member who attended that instance, and the tune
    played there. Everything defaults to flags-on; individual tests flip them."""
    db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
    session_id, path = db_cursor.fetchone()
    db_cursor.execute(
        "SELECT session_instance_id FROM session_instance WHERE session_id = %s ORDER BY date DESC LIMIT 1",
        (session_id,),
    )
    instance_id = db_cursor.fetchone()[0]
    # user_id 2 / person_id 2 is the seeded non-admin (sarah_fiddle).
    person_id = 2
    db_cursor.execute(
        """INSERT INTO session_instance_person (session_instance_id, person_id, attendance)
           VALUES (%s, %s, 'yes')
           ON CONFLICT (session_instance_id, person_id) DO UPDATE SET attendance = 'yes'""",
        (instance_id, person_id),
    )
    db_cursor.execute(
        "UPDATE session SET show_people_list = TRUE, track_attendance = TRUE, track_set_starters = TRUE WHERE session_id = %s",
        (session_id,),
    )
    db_conn.commit()
    yield {"session_id": session_id, "path": path, "instance_id": instance_id, "person_id": person_id}
    # These tests COMMIT flag changes (the endpoints open their own connections), and the
    # test DB is reseeded once per session, not per file — so a session left with
    # attendance off would contaminate any later test that shares it. Restore the flags.
    # (Attendance rows are left as-is: person 2 already attends this instance in seed.)
    db_cursor.execute(
        "UPDATE session SET show_people_list = TRUE, track_attendance = TRUE, track_set_starters = TRUE WHERE session_id = %s",
        (session_id,),
    )
    db_conn.commit()


def _set(db_cursor, db_conn, session_id, **flags):
    cols = ", ".join(f"{k} = %s" for k in flags)
    db_cursor.execute(f"UPDATE session SET {cols} WHERE session_id = %s", (*flags.values(), session_id))
    db_conn.commit()


class TestConstraint:
    def test_starters_cannot_be_on_without_attendance(self, people_fixture, db_cursor, db_conn):
        try:
            with pytest.raises(psycopg2.errors.CheckViolation):
                db_cursor.execute(
                    "UPDATE session SET track_attendance = FALSE, track_set_starters = TRUE WHERE session_id = %s",
                    (people_fixture["session_id"],),
                )
        finally:
            db_conn.rollback()


class TestPeopleTabGate:
    def test_people_tab_hidden_from_admin_when_show_people_list_off(self, people_fixture, db_cursor, db_conn):
        """Gone for everyone, admins included: an admin who wants the roster manages
        membership on the admin page, which this flag doesn't touch."""
        from serializers import build_session_detail_payload
        import database

        _set(db_cursor, db_conn, people_fixture["session_id"], show_people_list=False)
        conn = database.get_db_connection()
        try:
            payload = build_session_detail_payload(
                conn, people_fixture["path"], person_id=1, is_logged_in=True, is_system_admin=True, first_page=5
            )
        finally:
            conn.close()
        assert payload["permissions"]["can_view_people"] is False
        # ...but administering the session is untouched.
        assert payload["permissions"]["is_session_admin"] is True


class TestAttendanceExclusion:
    def test_person_attended_tab_excludes_off_session(
        self, client, authenticated_user, people_fixture, db_cursor, db_conn
    ):
        pid = people_fixture["person_id"]
        db_cursor.execute("SELECT name FROM session WHERE session_id = %s", (people_fixture["session_id"],))
        off_name = db_cursor.fetchone()[0]
        with authenticated_user:
            # Attendance on: the night shows.
            rows = json.loads(client.get(f"/api/person/{pid}/attended").data)["attendance"]
            assert off_name in {r["session_name"] for r in rows}, "seeded check-in should appear"

            # Attendance off: the person's OWN Attended tab stops showing it — the profile
            # must not leak what the session hides.
            _set(db_cursor, db_conn, people_fixture["session_id"], track_attendance=False, track_set_starters=False)
            rows = json.loads(client.get(f"/api/person/{pid}/attended").data)["attendance"]
            assert off_name not in {r["session_name"] for r in rows}

    def test_admin_people_checked_in_count_excludes_off_session(self, people_fixture, db_cursor, db_conn):
        from serializers import build_admin_people_payload
        import database

        def checked_in_for(pid):
            conn = database.get_db_connection()
            try:
                payload = build_admin_people_payload(conn)
            finally:
                conn.close()
            person = next((p for p in payload["people"] if p["person_id"] == pid), None)
            return person["session_instance_count"] if person else 0

        # The person may have attended several instances of the fixture session; the count
        # should drop by exactly that many when the session stops tracking attendance.
        db_cursor.execute(
            """SELECT COUNT(*) FROM session_instance_person sip
               JOIN session_instance si ON si.session_instance_id = sip.session_instance_id
               WHERE si.session_id = %s AND sip.person_id = %s AND sip.attendance = 'yes'""",
            (people_fixture["session_id"], people_fixture["person_id"]),
        )
        at_this_session = db_cursor.fetchone()[0]
        assert at_this_session >= 1

        before = checked_in_for(people_fixture["person_id"])
        _set(db_cursor, db_conn, people_fixture["session_id"], track_attendance=False, track_set_starters=False)
        after = checked_in_for(people_fixture["person_id"])
        # The column keeps existing; this session's rows just drop out of the count.
        assert after == before - at_this_session

    def test_r4_lens_excludes_off_session(self, people_fixture, db_cursor, db_conn):
        """"While I was there" gets its holes here: the R4 predicate stops counting the
        night once the session turns attendance off."""
        from services import person_scope
        import database

        db_cursor.execute(
            "SELECT tune_id FROM session_instance_tune WHERE session_instance_id = %s AND tune_id IS NOT NULL LIMIT 1",
            (people_fixture["instance_id"],),
        )
        r = db_cursor.fetchone()
        if not r:
            pytest.skip("no played tune at the fixture instance")
        tune_id = r[0]

        conn = database.get_db_connection()
        try:
            cur = conn.cursor()

            def attended_count():
                cur.execute(
                    person_scope.person_tune_play_counts_sql(),
                    {"person_id": people_fixture["person_id"], "tune_ids": [tune_id]},
                )
                row = cur.fetchone()
                return row[2] if row else 0  # attended_play_count

            # How many of this person's attended plays of the tune are at the fixture
            # session — the count must drop by exactly that when it turns attendance off.
            db_cursor.execute(
                """SELECT COUNT(DISTINCT sip.session_instance_id)
                   FROM session_instance_person sip
                   JOIN session_instance si ON si.session_instance_id = sip.session_instance_id
                   JOIN session_instance_tune sit ON sit.session_instance_id = sip.session_instance_id
                   WHERE si.session_id = %s AND sip.person_id = %s AND sip.attendance = 'yes'
                     AND sit.tune_id = %s AND sit.deleted = FALSE""",
                (people_fixture["session_id"], people_fixture["person_id"], tune_id),
            )
            at_this_session = db_cursor.fetchone()[0]

            _set(db_cursor, db_conn, people_fixture["session_id"], track_attendance=True, track_set_starters=True)
            with_on = attended_count()
            _set(db_cursor, db_conn, people_fixture["session_id"], track_attendance=False, track_set_starters=False)
            with_off = attended_count()
        finally:
            conn.close()
        assert at_this_session >= 1
        assert with_off == with_on - at_this_session


class TestWritePaths:
    def test_admin_details_update_forces_starters_off_with_attendance(
        self, client, admin_user, people_fixture, db_cursor
    ):
        """Turning attendance off in one save must not leave starters dangling on — the
        endpoint normalizes so the CHECK can never be hit."""
        path = people_fixture["path"]
        with admin_user:
            resp = client.put(
                f"/api/sessions/{path}/admin-update",
                data=json.dumps({"track_attendance": False, "track_set_starters": True}),
                content_type="application/json",
            )
        assert resp.status_code == 200, resp.data
        db_cursor.execute(
            "SELECT track_attendance, track_set_starters FROM session WHERE path = %s", (path,)
        )
        assert db_cursor.fetchone() == (False, False)

    def test_create_defaults_all_on_and_respects_opt_out(self, client, admin_user, db_cursor, db_conn):
        with admin_user:
            # Default: nothing sent => all on.
            r1 = client.post(
                "/api/add-session",
                data=json.dumps({"name": "Flags Default 039", "path": "test/flags-default-039",
                                 "city": "Austin", "state": "TX", "country": "USA"}),
                content_type="application/json",
            )
            assert r1.status_code in (200, 201), r1.data
            # Opt out of attendance => starters forced off too.
            r2 = client.post(
                "/api/add-session",
                data=json.dumps({"name": "Flags Off 039", "path": "test/flags-off-039",
                                 "city": "Austin", "state": "TX", "country": "USA",
                                 "track_attendance": False, "track_set_starters": True}),
                content_type="application/json",
            )
            assert r2.status_code in (200, 201), r2.data
        try:
            db_cursor.execute(
                "SELECT show_people_list, track_attendance, track_set_starters FROM session WHERE path = 'test/flags-default-039'"
            )
            assert db_cursor.fetchone() == (True, True, True)
            db_cursor.execute(
                "SELECT track_attendance, track_set_starters FROM session WHERE path = 'test/flags-off-039'"
            )
            assert db_cursor.fetchone() == (False, False)
        finally:
            db_cursor.execute("DELETE FROM session WHERE path IN ('test/flags-default-039', 'test/flags-off-039')")
            db_conn.commit()
