"""
Integration tests for the session-instance attendee list.

History: an earlier feature (T047) pre-populated the list with every session
regular under an "unknown" status. That was intentionally reversed — the
attendee endpoint now only returns people who have actually been added/checked
in (it returns an empty `regulars` section and lists attendees in `attendees`,
each carrying their `is_regular` flag). These tests verify that current contract.

Rows are created with DB-assigned IDs (RETURNING) and torn down in FK order so
the tests don't collide with seed data or leak state between runs.
"""

import uuid
import json
from datetime import date

from database import get_db_connection


def _make_session_with_regular(cur, *, with_attendance=None, extra_regular=False):
    """Create a session, instance, and one or two regular members.

    `with_attendance`: attendance value ('yes'/'maybe'/'no') for the first
    regular, or None to leave them without an attendance record.
    Returns a dict of the created ids for assertions and cleanup.
    """
    unique = str(uuid.uuid4())[:8]
    cur.execute(
        """
        INSERT INTO session (name, path, location_name)
        VALUES (%s, %s, 'Test Location') RETURNING session_id
        """,
        (f"Attendee Test {unique}", f"attendee-test-{unique}"),
    )
    session_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO session_instance (session_id, date) VALUES (%s, %s) RETURNING session_instance_id",
        (session_id, date(2023, 1, 1)),
    )
    instance_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO person (first_name, last_name, email) VALUES ('Test', 'Regular', %s) RETURNING person_id",
        (f"reg-{unique}@example.com",),
    )
    regular_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO session_person (session_id, person_id, is_regular, is_admin) VALUES (%s, %s, true, false)",
        (session_id, regular_id),
    )
    if with_attendance is not None:
        cur.execute(
            """
            INSERT INTO session_instance_person (session_instance_id, person_id, attendance, comment)
            VALUES (%s, %s, %s, 'Note')
            """,
            (instance_id, regular_id, with_attendance),
        )

    second_id = None
    if extra_regular:
        cur.execute(
            "INSERT INTO person (first_name, last_name, email) VALUES ('Test', 'Regular2', %s) RETURNING person_id",
            (f"reg2-{unique}@example.com",),
        )
        second_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO session_person (session_id, person_id, is_regular, is_admin) VALUES (%s, %s, true, false)",
            (session_id, second_id),
        )

    return {
        "session_id": session_id,
        "instance_id": instance_id,
        "regular_id": regular_id,
        "second_id": second_id,
    }


def _cleanup(cur, ids):
    cur.execute("DELETE FROM session_instance_person WHERE session_instance_id = %s", (ids["instance_id"],))
    cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (ids["instance_id"],))
    cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (ids["instance_id"],))
    cur.execute("DELETE FROM session_person WHERE session_id = %s", (ids["session_id"],))
    person_ids = [p for p in (ids["regular_id"], ids["second_id"]) if p]
    cur.execute("DELETE FROM person WHERE person_id = ANY(%s)", (person_ids,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (ids["session_id"],))


class TestAttendeeList:
    """The attendee endpoint lists only people with attendance records."""

    def test_regular_without_attendance_is_not_listed(self, client, authenticated_admin_user):
        """A regular with no attendance record is no longer pre-populated."""
        conn = get_db_connection()
        cur = conn.cursor()
        ids = None
        try:
            ids = _make_session_with_regular(cur, with_attendance=None)
            conn.commit()

            with authenticated_admin_user:
                response = client.get(f"/api/session_instance/{ids['instance_id']}/attendees")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            # Not pre-populated: the regular does not appear anywhere.
            everyone = data["data"]["regulars"] + data["data"]["attendees"]
            assert ids["regular_id"] not in [p["person_id"] for p in everyone]
        finally:
            if ids is not None:
                _cleanup(cur, ids)
                conn.commit()
            cur.close()
            conn.close()

    def test_regular_with_attendance_shows_actual_status(self, client, authenticated_admin_user):
        """A regular who has checked in appears with their real status + flag."""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            ids = _make_session_with_regular(cur, with_attendance="yes")
            conn.commit()

            with authenticated_admin_user:
                response = client.get(f"/api/session_instance/{ids['instance_id']}/attendees")

            assert response.status_code == 200
            data = json.loads(response.data)
            attendees = data["data"]["attendees"]
            match = next((a for a in attendees if a["person_id"] == ids["regular_id"]), None)
            assert match is not None
            assert match["attendance"] == "yes"
            assert match["is_regular"] is True
        finally:
            if ids is not None:
                _cleanup(cur, ids)
                conn.commit()
            cur.close()
            conn.close()

    def test_mixed_only_attending_regulars_listed(self, client, authenticated_admin_user):
        """Of two regulars, only the one with an attendance record is listed."""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            ids = _make_session_with_regular(cur, with_attendance="maybe", extra_regular=True)
            conn.commit()

            with authenticated_admin_user:
                response = client.get(f"/api/session_instance/{ids['instance_id']}/attendees")

            assert response.status_code == 200
            data = json.loads(response.data)
            listed_ids = [a["person_id"] for a in data["data"]["attendees"]]

            # The regular with attendance appears...
            assert ids["regular_id"] in listed_ids
            match = next(a for a in data["data"]["attendees"] if a["person_id"] == ids["regular_id"])
            assert match["attendance"] == "maybe"
            # ...the regular without an attendance record does not.
            assert ids["second_id"] not in listed_ids
        finally:
            if ids is not None:
                _cleanup(cur, ids)
                conn.commit()
            cur.close()
            conn.close()
