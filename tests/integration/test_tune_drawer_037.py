"""Spec 037 — the restructured tune drawer.

Pins the three things 037 changed on the backend, all of which are about WHO may say
WHAT about a tune:

  * person_tune.key — "I play this in ..."
  * the Session tab's permission split — the session's own alias/setting/key is the
    session making a canonical statement about its repertoire (ADMINS), while a specific
    instance is a record of what happened in a room the member was in (ANY MEMBER)
  * Remove From Session is only ever available for a tune with NO plays here

The first of those closes a live hole: before 037, update_session_tune_details was merely
@api_login_required, so any logged-in user could rewrite the alias, setting and key of any
tune at any session they had never attended.
"""
import json

import pytest


@pytest.fixture
def session_fixture(db_cursor, db_conn):
    """A session with one tune in its repertoire that has never been played, plus a
    second tune that HAS been played at an instance. Returns the ids/paths."""
    db_cursor.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
    session_id, path = db_cursor.fetchone()

    db_cursor.execute("SELECT tune_id FROM tune ORDER BY tune_id LIMIT 2")
    unplayed_tune, played_tune = (r[0] for r in db_cursor.fetchall())

    # A tune enrolled in the repertoire but never actually played here.
    db_cursor.execute(
        """DELETE FROM session_instance_tune sit
           USING session_instance si
           WHERE sit.session_instance_id = si.session_instance_id
             AND si.session_id = %s AND sit.tune_id = %s""",
        (session_id, unplayed_tune),
    )
    db_cursor.execute(
        """INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)
           ON CONFLICT (session_id, tune_id) DO NOTHING""",
        (session_id, unplayed_tune),
    )

    # A tune that HAS been played here, at a known instance.
    db_cursor.execute(
        "SELECT session_instance_id FROM session_instance WHERE session_id = %s ORDER BY date DESC LIMIT 1",
        (session_id,),
    )
    instance_id = db_cursor.fetchone()[0]
    db_cursor.execute(
        """INSERT INTO session_tune (session_id, tune_id) VALUES (%s, %s)
           ON CONFLICT (session_id, tune_id) DO NOTHING""",
        (session_id, played_tune),
    )
    db_cursor.execute(
        """INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type)
           VALUES (%s, %s, '1', 'tune')
           RETURNING session_instance_tune_id""",
        (instance_id, played_tune),
    )
    db_conn.commit()

    return {
        "session_id": session_id,
        "path": path,
        "instance_id": instance_id,
        "unplayed_tune": unplayed_tune,
        "played_tune": played_tune,
    }


def _set_membership(db_cursor, db_conn, session_id, person_id, is_admin):
    db_cursor.execute(
        """INSERT INTO session_person (session_id, person_id, is_admin)
           VALUES (%s, %s, %s)
           ON CONFLICT (session_id, person_id) DO UPDATE SET is_admin = EXCLUDED.is_admin""",
        (session_id, person_id, is_admin),
    )
    db_conn.commit()


class TestPersonalKey:
    """person_tune.key — a label, not a fact about what got played."""

    def test_put_round_trips_the_key(self, client, authenticated_user, db_cursor, db_conn):
        with authenticated_user as user:
            db_cursor.execute("SELECT tune_id FROM tune ORDER BY tune_id LIMIT 1")
            tune_id = db_cursor.fetchone()[0]
            db_cursor.execute(
                """INSERT INTO person_tune (person_id, tune_id, learn_status)
                   VALUES (%s, %s, 'learning')
                   ON CONFLICT (person_id, tune_id) DO UPDATE SET learn_status = 'learning'
                   RETURNING person_tune_id""",
                (user.person_id, tune_id),
            )
            ptid = db_cursor.fetchone()[0]
            db_conn.commit()

            resp = client.put(
                f"/api/my-tunes/{ptid}",
                data=json.dumps({"key": "Edorian"}),
                content_type="application/json",
            )
            assert resp.status_code == 200, resp.data
            assert json.loads(resp.data)["person_tune"]["key"] == "Edorian"

            detail = json.loads(client.get(f"/api/tunes/{tune_id}/detail").data)
            assert detail["session_tune"]["person_tune_status"]["key"] == "Edorian"

            # Empty string clears it back to "no preference — whatever the setting says".
            client.put(f"/api/my-tunes/{ptid}", data=json.dumps({"key": ""}), content_type="application/json")
            db_cursor.execute("SELECT key FROM person_tune WHERE person_tune_id = %s", (ptid,))
            assert db_cursor.fetchone()[0] is None


class TestSessionLayerIsAdminOnly:
    """The hole 037 closes."""

    def test_a_non_member_cannot_rewrite_what_a_session_plays(
        self, client, authenticated_user, session_fixture, db_cursor, db_conn
    ):
        f = session_fixture
        with authenticated_user as user:
            db_cursor.execute(
                "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
                (f["session_id"], user.person_id),
            )
            db_conn.commit()

            resp = client.put(
                f"/api/sessions/{f['path']}/tunes/{f['played_tune']}",
                data=json.dumps({"alias": "Hostile Rename"}),
                content_type="application/json",
            )
            assert resp.status_code == 403

            db_cursor.execute(
                "SELECT alias FROM session_tune WHERE session_id = %s AND tune_id = %s",
                (f["session_id"], f["played_tune"]),
            )
            assert db_cursor.fetchone()[0] != "Hostile Rename"

    def test_a_plain_member_cannot_either(
        self, client, authenticated_user, session_fixture, db_cursor, db_conn
    ):
        f = session_fixture
        with authenticated_user as user:
            _set_membership(db_cursor, db_conn, f["session_id"], user.person_id, is_admin=False)
            resp = client.put(
                f"/api/sessions/{f['path']}/tunes/{f['played_tune']}",
                data=json.dumps({"alias": "Members Rename"}),
                content_type="application/json",
            )
            assert resp.status_code == 403

    def test_a_session_admin_can(self, client, authenticated_user, session_fixture, db_cursor, db_conn):
        f = session_fixture
        with authenticated_user as user:
            _set_membership(db_cursor, db_conn, f["session_id"], user.person_id, is_admin=True)
            resp = client.put(
                f"/api/sessions/{f['path']}/tunes/{f['played_tune']}",
                data=json.dumps({"alias": "The House Name", "key": "Ador"}),
                content_type="application/json",
            )
            assert resp.status_code == 200, resp.data
            db_cursor.execute(
                "SELECT alias, key FROM session_tune WHERE session_id = %s AND tune_id = %s",
                (f["session_id"], f["played_tune"]),
            )
            assert db_cursor.fetchone() == ("The House Name", "Ador")

    def test_saving_in_general_enrolls_a_tune_that_has_no_session_tune_row(
        self, client, authenticated_user, session_fixture, db_cursor, db_conn
    ):
        """A human saying "we play this in Ador here" is the strongest possible evidence
        the tune belongs in the repertoire. Asking would be a silly question."""
        f = session_fixture
        with authenticated_user as user:
            _set_membership(db_cursor, db_conn, f["session_id"], user.person_id, is_admin=True)
            db_cursor.execute(
                "DELETE FROM session_tune WHERE session_id = %s AND tune_id = %s",
                (f["session_id"], f["played_tune"]),
            )
            db_conn.commit()

            resp = client.put(
                f"/api/sessions/{f['path']}/tunes/{f['played_tune']}",
                data=json.dumps({"key": "Ador"}),
                content_type="application/json",
            )
            assert resp.status_code == 200, resp.data
            db_cursor.execute(
                "SELECT key FROM session_tune WHERE session_id = %s AND tune_id = %s",
                (f["session_id"], f["played_tune"]),
            )
            assert db_cursor.fetchone()[0] == "Ador"


class TestInstanceLayerIsOpenToMembers:
    """The deliberate LOOSENING: a member was in the room, so they may say what got
    played. Before 037 a non-admin member could only set setting_override."""

    def test_a_plain_member_may_now_set_the_name_and_key(
        self, client, authenticated_user, session_fixture, db_cursor, db_conn
    ):
        f = session_fixture
        with authenticated_user as user:
            _set_membership(db_cursor, db_conn, f["session_id"], user.person_id, is_admin=False)
            resp = client.put(
                f"/api/sessions/{f['path']}/{f['instance_id']}/tunes/{f['played_tune']}",
                data=json.dumps({"name": "The Fast One", "key_override": "Gmajor"}),
                content_type="application/json",
            )
            assert resp.status_code == 200, resp.data
            db_cursor.execute(
                """SELECT name, key_override FROM session_instance_tune
                   WHERE session_instance_id = %s AND tune_id = %s""",
                (f["instance_id"], f["played_tune"]),
            )
            assert db_cursor.fetchone() == ("The Fast One", "Gmajor")

    def test_a_non_member_still_cannot(
        self, client, authenticated_user, session_fixture, db_cursor, db_conn
    ):
        f = session_fixture
        with authenticated_user as user:
            db_cursor.execute(
                "DELETE FROM session_person WHERE session_id = %s AND person_id = %s",
                (f["session_id"], user.person_id),
            )
            db_conn.commit()
            resp = client.put(
                f"/api/sessions/{f['path']}/{f['instance_id']}/tunes/{f['played_tune']}",
                data=json.dumps({"name": "Nope"}),
                content_type="application/json",
            )
            assert resp.status_code == 403


class TestRemoveFromSessionRequiresNoPlays:
    """Every tune played at an instance belongs to the session's repertoire. This
    endpoint used to break that invariant: it deleted the session_tune row and left the
    plays orphaned."""

    def test_refuses_when_the_tune_has_plays_here(
        self, client, admin_user, session_fixture, db_cursor
    ):
        f = session_fixture
        with admin_user:
            resp = client.delete(f"/api/sessions/{f['path']}/tunes/{f['played_tune']}")
            assert resp.status_code == 409
            assert "played at this session" in json.loads(resp.data)["message"]

            db_cursor.execute(
                "SELECT 1 FROM session_tune WHERE session_id = %s AND tune_id = %s",
                (f["session_id"], f["played_tune"]),
            )
            assert db_cursor.fetchone(), "the repertoire row survives a refused delete"

    def test_allows_un_enrolling_a_tune_that_was_never_played(
        self, client, admin_user, session_fixture, db_cursor
    ):
        f = session_fixture
        with admin_user:
            resp = client.delete(f"/api/sessions/{f['path']}/tunes/{f['unplayed_tune']}")
            assert resp.status_code == 200, resp.data
            db_cursor.execute(
                "SELECT 1 FROM session_tune WHERE session_id = %s AND tune_id = %s",
                (f["session_id"], f["unplayed_tune"]),
            )
            assert db_cursor.fetchone() is None


class TestHistoryAttendedFilter:
    """"While I was there" is a FILTER, not a scope (spec 037).

    It ANDs on top of whatever else is selected, which is why "nights at Mueller I was
    actually there for" is expressible at all — it wasn't when `attended` was one of a set
    of mutually-exclusive scopes and you had to choose between "this session" and "the
    ones I attended".
    """

    def _attend(self, db_cursor, db_conn, instance_id, person_id):
        db_cursor.execute(
            """INSERT INTO session_instance_person (session_instance_id, person_id, attendance)
               VALUES (%s, %s, 'yes')
               ON CONFLICT (session_instance_id, person_id)
               DO UPDATE SET attendance = 'yes'""",
            (instance_id, person_id),
        )
        db_conn.commit()

    def test_it_composes_with_a_session_filter(
        self, client, authenticated_user, session_fixture, db_cursor, db_conn
    ):
        f = session_fixture
        with authenticated_user as user:
            # A second instance at the same session where the tune was also played, but
            # which the viewer did NOT attend.
            db_cursor.execute(
                """SELECT session_instance_id FROM session_instance
                   WHERE session_id = %s AND session_instance_id <> %s LIMIT 1""",
                (f["session_id"], f["instance_id"]),
            )
            other_instance = db_cursor.fetchone()[0]
            db_cursor.execute(
                """INSERT INTO session_instance_tune
                   (session_instance_id, tune_id, order_position, record_type)
                   VALUES (%s, %s, 'z', 'tune')""",
                (other_instance, f["played_tune"]),
            )
            db_conn.commit()
            self._attend(db_cursor, db_conn, f["instance_id"], user.person_id)

            base = f"/api/tunes/{f['played_tune']}/history?session_path={f['path']}"

            unfiltered = {p["session_instance_id"] for p in json.loads(client.get(base).data)["play_instances"]}
            assert {f["instance_id"], other_instance} <= unfiltered

            # ...and with the filter on, only the night I was actually at. Note this is a
            # session filter AND an attended filter at once — the combination that the old
            # mutually-exclusive scopes could not express.
            filtered = {p["session_instance_id"] for p in json.loads(client.get(base + "&attended=1").data)["play_instances"]}
            assert filtered == {f["instance_id"]}
            assert other_instance not in filtered

    def test_every_row_says_whether_i_was_there(
        self, client, authenticated_user, session_fixture, db_cursor, db_conn
    ):
        """The point of marking rather than only filtering: you can see at a glance which
        of a tune's plays you were present for, without hiding the ones you weren't."""
        f = session_fixture
        with authenticated_user as user:
            self._attend(db_cursor, db_conn, f["instance_id"], user.person_id)
            rows = json.loads(
                client.get(f"/api/tunes/{f['played_tune']}/history?session_path={f['path']}").data
            )["play_instances"]
            attended = {p["session_instance_id"]: p["attended"] for p in rows}
            assert attended[f["instance_id"]] is True

    def test_anonymous_viewers_get_no_flag_and_cannot_filter(self, client, session_fixture):
        f = session_fixture
        rows = json.loads(
            client.get(f"/api/tunes/{f['played_tune']}/history?session_path={f['path']}").data
        )["play_instances"]
        assert all(p["attended"] is False for p in rows)
        assert client.get(f"/api/tunes/{f['played_tune']}/history?attended=1").status_code == 401

    def test_the_old_scope_attended_still_works(self, client, authenticated_user, session_fixture):
        """?scope=attended predates the filter and is still honoured — it means the filter
        with no other person restriction."""
        f = session_fixture
        with authenticated_user:
            resp = client.get(f"/api/tunes/{f['played_tune']}/history?scope=attended")
            assert resp.status_code == 200
            assert json.loads(resp.data)["success"]


class TestSessionScopePayload:
    """What the Session tab renders from."""

    def test_carries_the_droplist_instances_and_the_permission_flags(
        self, client, authenticated_user, session_fixture, db_cursor, db_conn
    ):
        f = session_fixture
        with authenticated_user as user:
            _set_membership(db_cursor, db_conn, f["session_id"], user.person_id, is_admin=False)
            data = json.loads(
                client.get(f"/api/tunes/{f['played_tune']}/detail?session={f['path']}").data
            )
            scope = data["session_tune"]["session_scope"]

            assert scope["session_name"]
            # A member may edit a night, but not what the session plays in general.
            assert scope["can_edit_instance"] is True
            assert scope["can_edit_session"] is False
            # It has plays, so un-enrolling isn't on offer at all.
            assert scope["can_remove_from_session"] is False

            # The droplist is populated with the instances this tune was PLAYED at —
            # the only ones session_instance_tune can hold overrides for — each carrying
            # the "Set N, tune M" coordinates of every time it came round that night.
            ids = [i["session_instance_id"] for i in scope["played_instances"]]
            assert f["instance_id"] in ids
            for inst in scope["played_instances"]:
                assert set(inst) == {
                    "session_instance_id",
                    "date",
                    "start_time",
                    "location_override",
                    "positions",
                }
                assert inst["positions"], "an instance is only listed because it has plays"
                for p in inst["positions"]:
                    assert set(p) == {"session_instance_tune_id", "set_number", "position_in_set"}
                    assert p["set_number"] >= 1 and p["position_in_set"] >= 1

    def test_set_and_tune_numbers_skip_breaks_and_count_a_tune_played_twice(
        self, client, admin_user, session_fixture, db_cursor, db_conn
    ):
        """The "Set 3, tune 2" coordinates. Breaks number the SETS and must never take a
        tune number themselves (spec 023), and a tune played twice in one night gets two
        entries — which is exactly the case the instance-override key can't distinguish
        (see the wrinkle at the foot of spec 037)."""
        f = session_fixture
        tune_id = f["played_tune"]

        # Build a clean night: tune | break | X | tune  ->  Set 1 tune 1, then Set 2 tune 2.
        db_cursor.execute(
            "DELETE FROM session_instance_tune WHERE session_instance_id = %s", (f["instance_id"],)
        )
        db_cursor.execute("SELECT tune_id FROM tune WHERE tune_id <> %s LIMIT 1", (tune_id,))
        other = db_cursor.fetchone()[0]
        for pos, tid, rec in [
            ("a", tune_id, "tune"),
            ("b", None, "break"),
            ("c", other, "tune"),
            ("d", tune_id, "tune"),
        ]:
            db_cursor.execute(
                """INSERT INTO session_instance_tune
                   (session_instance_id, tune_id, order_position, record_type)
                   VALUES (%s, %s, %s, %s)""",
                (f["instance_id"], tid, pos, rec),
            )
        db_conn.commit()

        with admin_user:
            data = json.loads(client.get(f"/api/tunes/{tune_id}/detail?session={f['path']}").data)
            inst = next(
                i
                for i in data["session_tune"]["session_scope"]["played_instances"]
                if i["session_instance_id"] == f["instance_id"]
            )

        coords = [(p["set_number"], p["position_in_set"]) for p in inst["positions"]]
        # Set 1: the tune (the break does NOT take tune number 2).
        # Set 2: the other tune is tune 1, ours is tune 2.
        assert coords == [(1, 1), (2, 2)]

    def test_a_soft_deleted_play_does_not_count(
        self, client, admin_user, session_fixture, db_cursor, db_conn
    ):
        """`deleted` was filtered nowhere before this: a soft-deleted play still inflated
        "played here N times" AND blocked un-enrolling the tune."""
        f = session_fixture
        db_cursor.execute(
            "UPDATE session_instance_tune SET deleted = TRUE WHERE tune_id = %s", (f["played_tune"],)
        )
        db_conn.commit()

        with admin_user:
            data = json.loads(
                client.get(f"/api/tunes/{f['played_tune']}/detail?session={f['path']}").data
            )
            st = data["session_tune"]
            assert st["times_played"] == 0
            assert st["session_scope"]["played_instances"] == []
            # ...and with no *real* plays left, un-enrolling becomes possible again.
            assert st["session_scope"]["can_remove_from_session"] is True
            assert client.delete(f"/api/sessions/{f['path']}/tunes/{f['played_tune']}").status_code == 200

    def test_an_unplayed_tune_offers_removal_to_an_admin_and_lists_no_instances(
        self, client, admin_user, session_fixture
    ):
        f = session_fixture
        with admin_user:
            data = json.loads(
                client.get(f"/api/tunes/{f['unplayed_tune']}/detail?session={f['path']}").data
            )
            scope = data["session_tune"]["session_scope"]
            assert scope["can_edit_session"] is True
            assert scope["can_remove_from_session"] is True
            assert scope["played_instances"] == []
