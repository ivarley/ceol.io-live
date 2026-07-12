"""Spec 034: `confirmed` is the sole gate on people-visibility.

The property under test is the one the whole field exists for:

    People-visibility is granted BY THE SESSION, never claimed by joining it.

Anyone with an account can self-join any session. If membership granted roster access, a
stranger could join and read every member's name, city and instrument off the People tab.
So joining lands `confirmed = FALSE`, and only a session admin can flip it.

The counter-intuitive assertions here are the important ones:
  * a CONFIRMED VISITOR can see people   (confirmed is orthogonal to member/visitor)
  * an UNCONFIRMED MEMBER cannot         (membership is not access)
  * CHECK-IN never confirms anyone       (logging who's in the room != vouching for them)
"""

import json
import uuid

import pytest


def _mk_person(cur, first="Test"):
    unique = uuid.uuid4().hex[:8]
    cur.execute(
        """
        INSERT INTO person (first_name, last_name, email)
        VALUES (%s, %s, %s) RETURNING person_id
        """,
        (first, f"Person{unique}", f"{first.lower()}-{unique}@example.com"),
    )
    return cur.fetchone()[0]


class TestConfirmedGatesPeopleVisibility:
    """GET /api/sessions/<path>/people -- is_admin OR confirmed, nothing else."""

    def _session(self, db_cursor):
        db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
        return db_cursor.fetchone()

    def _set_relationship(self, db_conn, db_cursor, session_id, person_id, relationship, confirmed):
        db_cursor.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        db_cursor.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed, archived, is_admin)
            VALUES (%s, %s, %s, %s, FALSE, FALSE)
            """,
            (session_id, person_id, relationship, confirmed),
        )
        db_conn.commit()

    def test_unconfirmed_member_cannot_see_people(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        """Membership is NOT access. This is the self-join hole, closed."""
        session_id, session_path = self._session(db_cursor)
        person_id = authenticated_regular_user.person_id
        self._set_relationship(db_conn, db_cursor, session_id, person_id, "member", False)

        with authenticated_regular_user:
            response = client.get(f"/api/sessions/{session_path}/people")

        assert response.status_code == 403
        assert json.loads(response.data)["success"] is False

    def test_confirmed_visitor_CAN_see_people(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        """`confirmed` is orthogonal to member/visitor.

        A visitor the session has vouched for -- a known friend who lives elsewhere -- sees
        the roster. Being a visitor is a statement about whose session it is, not about trust.
        """
        session_id, session_path = self._session(db_cursor)
        person_id = authenticated_regular_user.person_id
        self._set_relationship(db_conn, db_cursor, session_id, person_id, "visitor", True)

        with authenticated_regular_user:
            response = client.get(f"/api/sessions/{session_path}/people")

        assert response.status_code == 200
        assert json.loads(response.data)["success"] is True

    def test_confirmed_member_can_see_people(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        session_id, session_path = self._session(db_cursor)
        person_id = authenticated_regular_user.person_id
        self._set_relationship(db_conn, db_cursor, session_id, person_id, "member", True)

        with authenticated_regular_user:
            response = client.get(f"/api/sessions/{session_path}/people")

        assert response.status_code == 200


class TestJoinLandsUnconfirmed:
    def test_self_join_does_not_confirm(self, client, authenticated_regular_user, db_conn, db_cursor):
        """The whole point: joining a session must not hand you its roster."""
        db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id DESC LIMIT 1")
        session_id, session_path = db_cursor.fetchone()
        person_id = authenticated_regular_user.person_id

        db_cursor.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        db_conn.commit()

        with authenticated_regular_user:
            response = client.post(
                f"/api/sessions/{session_path}/join",
                data=json.dumps({"relationship": "member"}),
                content_type="application/json",
            )
        assert response.status_code == 200

        db_cursor.execute(
            "SELECT relationship, confirmed FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        relationship, confirmed = db_cursor.fetchone()
        assert relationship == "member"
        assert confirmed is False, "self-join must never confirm -- that is the hole this closes"

        # ...and the roster stays shut until an admin says otherwise.
        with authenticated_regular_user:
            people = client.get(f"/api/sessions/{session_path}/people")
        assert people.status_code == 403

    def test_join_as_visitor(self, client, authenticated_regular_user, db_conn, db_cursor):
        db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id DESC LIMIT 1")
        session_id, session_path = db_cursor.fetchone()
        person_id = authenticated_regular_user.person_id
        db_cursor.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        db_conn.commit()

        with authenticated_regular_user:
            response = client.post(
                f"/api/sessions/{session_path}/join",
                data=json.dumps({"relationship": "visitor"}),
                content_type="application/json",
            )
        assert response.status_code == 200

        db_cursor.execute(
            "SELECT relationship FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        assert db_cursor.fetchone()[0] == "visitor"

    def test_join_rejects_bad_relationship(self, client, authenticated_regular_user, db_cursor):
        db_cursor.execute("SELECT path FROM session ORDER BY session_id DESC LIMIT 1")
        session_path = db_cursor.fetchone()[0]
        with authenticated_regular_user:
            response = client.post(
                f"/api/sessions/{session_path}/join",
                data=json.dumps({"relationship": "regular"}),  # the deleted vocabulary
                content_type="application/json",
            )
        assert response.status_code == 400


class TestCheckinNeverConfirms:
    def test_checkin_by_admin_does_not_confirm_the_walk_in(
        self, client, authenticated_admin_user, db_conn, db_cursor
    ):
        """The creepy-guy case, in test form.

        An admin checking someone in is a LOGGING act, performed in a pub, mid-tune, about
        whoever is in the room. If it granted roster access, the admin logging a stranger's
        attendance would thereby hand him every member's name -- including the name of the
        woman who deliberately didn't give it to him.
        """
        db_cursor.execute(
            """
            SELECT si.session_instance_id, si.session_id
            FROM session_instance si ORDER BY si.session_instance_id LIMIT 1
            """
        )
        instance_id, session_id = db_cursor.fetchone()
        walk_in = _mk_person(db_cursor, "Walkin")
        db_cursor.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, walk_in),
        )
        db_conn.commit()

        with authenticated_admin_user:
            response = client.post(
                f"/api/session_instance/{instance_id}/attendees/checkin",
                data=json.dumps({"person_id": walk_in, "attendance": "yes"}),
                content_type="application/json",
            )
        assert response.status_code in (200, 201)

        db_cursor.execute(
            "SELECT relationship, confirmed, archived FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, walk_in),
        )
        relationship, confirmed, archived = db_cursor.fetchone()
        assert relationship == "visitor"
        assert confirmed is False, "CHECK-IN MUST NEVER CONFIRM -- see the docstring"
        assert archived is False


class TestArchived:
    def test_archived_person_is_returned_but_flagged(
        self, client, authenticated_admin_user, db_conn, db_cursor
    ):
        """Archived means "hidden from the DEFAULT list", never "unfindable".

        The API keeps returning them (flagged); hiding is the client's job. If the API
        dropped them, a member back for one night would be invisible in the check-in picker
        and whoever's logging would create a DUPLICATE PERSON for her -- much worse than
        seeing a name you'd rather not see.
        """
        db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
        session_id, session_path = db_cursor.fetchone()

        gone = _mk_person(db_cursor, "Movedaway")
        db_cursor.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed, archived)
            VALUES (%s, %s, 'member', TRUE, TRUE)
            """,
            (session_id, gone),
        )
        db_conn.commit()

        with authenticated_admin_user:
            response = client.get(f"/api/sessions/{session_path}/people")

        assert response.status_code == 200
        people = json.loads(response.data)["people"]
        match = next((p for p in people if p["person_id"] == gone), None)
        assert match is not None, "archived people must still be RETURNED, just flagged"
        assert match["archived"] is True


class TestSetters:
    def test_person_can_set_their_own_relationship(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        """member<->visitor is a claim about your own life. You get to make it."""
        db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
        session_id, session_path = db_cursor.fetchone()
        person_id = authenticated_regular_user.person_id
        db_cursor.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        db_cursor.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed)
            VALUES (%s, %s, 'visitor', FALSE)
            """,
            (session_id, person_id),
        )
        db_conn.commit()

        with authenticated_regular_user:
            response = client.put(
                f"/api/sessions/{session_path}/people/{person_id}/relationship",
                json={"relationship": "member"},
            )
        assert response.status_code == 200

        db_cursor.execute(
            "SELECT relationship FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        assert db_cursor.fetchone()[0] == "member"

    def test_person_cannot_confirm_themselves(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        """Self-confirmation would defeat the entire gate."""
        db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
        session_id, session_path = db_cursor.fetchone()
        person_id = authenticated_regular_user.person_id
        db_cursor.execute(
            "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        db_cursor.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed, is_admin)
            VALUES (%s, %s, 'member', FALSE, FALSE)
            """,
            (session_id, person_id),
        )
        db_conn.commit()

        with authenticated_regular_user:
            response = client.put(
                f"/api/sessions/{session_path}/people/{person_id}/confirmed",
                json={"confirmed": True},
            )
        assert response.status_code == 403

        db_cursor.execute(
            "SELECT confirmed FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, person_id),
        )
        assert db_cursor.fetchone()[0] is False

    def test_admin_can_confirm_and_archive(
        self, client, authenticated_admin_user, db_conn, db_cursor
    ):
        db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
        session_id, session_path = db_cursor.fetchone()
        target = _mk_person(db_cursor, "Target")
        db_cursor.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed, archived)
            VALUES (%s, %s, 'visitor', FALSE, FALSE)
            """,
            (session_id, target),
        )
        db_conn.commit()

        with authenticated_admin_user:
            r1 = client.put(
                f"/api/sessions/{session_path}/people/{target}/confirmed", json={"confirmed": True}
            )
            r2 = client.put(
                f"/api/sessions/{session_path}/people/{target}/archived", json={"archived": True}
            )
        assert r1.status_code == 200
        assert r2.status_code == 200

        db_cursor.execute(
            "SELECT confirmed, archived FROM session_person WHERE session_id = %s AND person_id = %s",
            (session_id, target),
        )
        confirmed, archived = db_cursor.fetchone()
        assert confirmed is True
        assert archived is True

    def test_relationship_setter_rejects_old_vocabulary(
        self, client, authenticated_admin_user, db_cursor
    ):
        db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
        session_id, session_path = db_cursor.fetchone()
        db_cursor.execute(
            "SELECT person_id FROM session_person WHERE session_id = %s LIMIT 1", (session_id,)
        )
        person_id = db_cursor.fetchone()[0]

        with authenticated_admin_user:
            response = client.put(
                f"/api/sessions/{session_path}/people/{person_id}/relationship",
                json={"relationship": "regular"},  # deleted by 034
            )
        assert response.status_code == 400
