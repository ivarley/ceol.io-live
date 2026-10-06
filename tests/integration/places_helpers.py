"""Shared fixtures for the spec 055 tests. The endpoints commit on their own
connections, so these tests commit their setup too and undo it afterwards."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from auth import User
from database import get_db_connection

PROBE = "Place Probe"


@contextmanager
def logged_in(client, person_id=1, is_system_admin=True):
    user = User(
        user_id=1,
        person_id=person_id,
        username="admin",
        email="t@example.com",
        first_name="T",
        last_name="U",
        is_active=True,
        is_system_admin=is_system_admin,
        timezone="UTC",
        email_verified=True,
    )
    with patch("auth.User.get_by_id", return_value=user):
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.user_id)
            sess["_fresh"] = True
            sess["is_system_admin"] = is_system_admin
            sess["admin_session_ids"] = []
        yield user
        with client.session_transaction() as sess:
            sess.clear()


class Committed:
    """Writes that other connections can see, removed at teardown."""

    def __init__(self):
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()
        # The ids that existed before the test, not a max: another test may leave a
        # row with a high explicit id, and new rows would then slip under a max.
        self.cur.execute("SELECT place_id FROM place")
        self.places_before = [r[0] for r in self.cur.fetchall()]
        self.cur.execute("SELECT session_id FROM session")
        self.sessions_before = [r[0] for r in self.cur.fetchall()]
        self.cur.execute("SELECT from_path FROM path_redirect")
        self.redirects = {r[0] for r in self.cur.fetchall()}

    def place(
        self,
        slug,
        name,
        kind="place",
        parent=None,
        area="Texas",
        country="United States",
    ):
        if kind == "festival":
            area = country = None
        self.cur.execute(
            """INSERT INTO place (slug, name, kind, parent_place_id, area, country)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING place_id""",
            (slug, name, kind, parent, area, country),
        )
        place_id = self.cur.fetchone()[0]
        self.conn.commit()
        return place_id

    def session(self, path, place_id, name=None, session_type="regular", **columns):
        """A session row; `columns` sets any others (initiation_date, timezone, …)."""
        fields = {
            "name": name or f"{PROBE} {path}",
            "path": path,
            "place_id": place_id,
            "session_type": session_type,
            "city": "x",
            "timezone": "UTC",
            **columns,
        }
        cols = ", ".join(fields)
        marks = ", ".join(["%s"] * len(fields))
        self.cur.execute(
            f"INSERT INTO session ({cols}) VALUES ({marks}) RETURNING session_id",
            tuple(fields.values()),
        )
        session_id = self.cur.fetchone()[0]
        self.conn.commit()
        return session_id

    def member(self, session_id, person_id, is_admin=False):
        self.cur.execute(
            """INSERT INTO session_person (session_id, person_id, relationship, confirmed, is_admin)
               VALUES (%s, %s, 'member', TRUE, %s)""",
            (session_id, person_id, is_admin),
        )
        self.conn.commit()

    def logged_tune(self, instance_id, tune_id):
        self.cur.execute(
            """INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position)
               VALUES (%s, %s, 'a0')""",
            (instance_id, tune_id),
        )
        self.conn.commit()

    def instance(self, session_id, date):
        self.cur.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, %s) RETURNING session_instance_id",
            (session_id, date),
        )
        instance_id = self.cur.fetchone()[0]
        self.conn.commit()
        return instance_id

    def redirect(self, from_path, to_path):
        self.cur.execute(
            "INSERT INTO path_redirect (from_path, to_path) VALUES (%s, %s)",
            (from_path, to_path),
        )
        self.conn.commit()

    def query(self, sql, args=()):
        self.cur.execute(sql, args)
        rows = self.cur.fetchall()
        self.conn.commit()
        return rows

    def cleanup(self):
        cur = self.cur
        self.conn.rollback()
        cur.execute(
            "SELECT session_id FROM session WHERE NOT (session_id = ANY(%s))",
            (self.sessions_before,),
        )
        new_sessions = [r[0] for r in cur.fetchall()]
        if new_sessions:
            cur.execute(
                "DELETE FROM session_instance_tune WHERE session_instance_id IN "
                "(SELECT session_instance_id FROM session_instance WHERE session_id = ANY(%s))",
                (new_sessions,),
            )
            for table in (
                "session_instance",
                "session_person",
                "session_person_history",
                "session_history",
            ):
                cur.execute(
                    f"DELETE FROM {table} WHERE session_id = ANY(%s)", (new_sessions,)
                )
            cur.execute(
                "DELETE FROM session WHERE session_id = ANY(%s)", (new_sessions,)
            )
        cur.execute(
            "SELECT place_id FROM place WHERE NOT (place_id = ANY(%s))",
            (self.places_before,),
        )
        new_places = [r[0] for r in cur.fetchall()]
        if new_places:
            cur.execute(
                "UPDATE session SET place_id = NULL WHERE place_id = ANY(%s)",
                (new_places,),
            )
            cur.execute(
                "UPDATE place SET parent_place_id = NULL WHERE place_id = ANY(%s)",
                (new_places,),
            )
            cur.execute("DELETE FROM place WHERE place_id = ANY(%s)", (new_places,))
        cur.execute("SELECT from_path FROM path_redirect")
        for (from_path,) in cur.fetchall():
            if from_path not in self.redirects:
                cur.execute(
                    "DELETE FROM path_redirect WHERE from_path = %s", (from_path,)
                )
        self.conn.commit()
        cur.close()
        self.conn.close()


@pytest.fixture
def committed():
    c = Committed()
    yield c
    c.cleanup()
