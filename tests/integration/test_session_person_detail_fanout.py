"""GET /api/sessions/<path>/people/<person_id> — one row per attended night.

The regression this pins: `attended_instances` used to be aggregated by joining
`session_instance_person` into the same query as `person_instrument`. That is a
cartesian product — every attended night came back once PER INSTRUMENT. A
fiddle-and-mandolin player with 13 nights got 26 entries, every date twice.

It hid well. The sibling `array_agg(DISTINCT pi.instrument)` collapsed the same
fan-out on its own side, so the instruments looked right and only attendance was
wrong; and a player with exactly one instrument saw nothing amiss at all. What
finally surfaced it was the UI, where the list is keyed and a duplicate key is a
hard render error rather than a cosmetic one — clicking such a person threw
`each_key_duplicate` and the detail sheet came up broken.

So the assertions below are deliberately about COUNTS, not about whether the
endpoint answers: the bug never changed the status code.
"""

import json
import uuid

import pytest


def _mk_person(cur, instruments):
    unique = uuid.uuid4().hex[:8]
    cur.execute(
        """
        INSERT INTO person (first_name, last_name, email)
        VALUES ('Fanout', %s, %s) RETURNING person_id
        """,
        (f"Test{unique}", f"fanout-{unique}@example.com"),
    )
    person_id = cur.fetchone()[0]
    for inst in instruments:
        cur.execute(
            "INSERT INTO person_instrument (person_id, instrument) VALUES (%s, %s)",
            (person_id, inst),
        )
    return person_id


def _attend(cur, session_id, person_id, dates):
    """Mark the person present at one instance per date, creating the instances."""
    instance_ids = []
    for d in dates:
        cur.execute(
            """
            INSERT INTO session_instance (session_id, date, is_cancelled)
            VALUES (%s, %s, FALSE) RETURNING session_instance_id
            """,
            (session_id, d),
        )
        instance_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO session_instance_person (session_instance_id, person_id, attendance)
            VALUES (%s, %s, 'yes')
            """,
            (instance_id, person_id),
        )
        instance_ids.append(instance_id)
    return instance_ids


@pytest.mark.integration
class TestAttendedInstancesAreNotMultipliedByInstruments:
    def _session(self, cur):
        cur.execute("SELECT session_id, path FROM session ORDER BY session_id LIMIT 1")
        return cur.fetchone()

    def _make(self, db_conn, db_cursor, instruments, dates, viewer_person_id):
        session_id, session_path = self._session(db_cursor)
        person_id = _mk_person(db_cursor, instruments)
        instance_ids = _attend(db_cursor, session_id, person_id, dates)
        # The person must belong to the session to be visible on its People tab,
        # and the VIEWER must be confirmed there to see it at all (spec 034).
        cur = db_cursor
        cur.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed, archived, is_admin)
            VALUES (%s, %s, 'member', TRUE, FALSE, FALSE)
            ON CONFLICT (session_id, person_id) DO UPDATE SET confirmed = TRUE
            """,
            (session_id, person_id),
        )
        cur.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed, archived, is_admin)
            VALUES (%s, %s, 'member', TRUE, FALSE, FALSE)
            ON CONFLICT (session_id, person_id) DO UPDATE SET confirmed = TRUE
            """,
            (session_id, viewer_person_id),
        )
        db_conn.commit()
        return session_path, person_id, instance_ids

    def test_two_instruments_do_not_double_the_nights(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        dates = ["2031-03-04", "2031-03-11", "2031-03-18"]
        session_path, person_id, instance_ids = self._make(
            db_conn, db_cursor, ["fiddle", "mandolin"], dates,
            authenticated_regular_user.person_id,
        )

        with authenticated_regular_user:
            resp = client.get(f"/api/sessions/{session_path}/people/{person_id}")

        assert resp.status_code == 200
        person = json.loads(resp.data)["person"]

        attended = person["attended_instances"]
        assert len(attended) == len(dates), (
            f"expected one entry per night, got {len(attended)} for {len(dates)} nights "
            f"and 2 instruments — the instrument join is fanning out again"
        )
        got_ids = sorted(a["session_instance_id"] for a in attended)
        assert got_ids == sorted(instance_ids)
        # and the instruments are still right (they were never the visible symptom)
        assert sorted(person["instruments"]) == ["fiddle", "mandolin"]

    def test_five_instruments_do_not_quintuple_them_either(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        # The multiplier was the instrument COUNT, so one extra instrument would
        # have looked like a near-miss. Five makes the failure unmistakable.
        dates = ["2031-04-01", "2031-04-08"]
        session_path, person_id, _ = self._make(
            db_conn, db_cursor, ["fiddle", "flute", "banjo", "guitar", "bodhran"], dates,
            authenticated_regular_user.person_id,
        )

        with authenticated_regular_user:
            resp = client.get(f"/api/sessions/{session_path}/people/{person_id}")

        attended = json.loads(resp.data)["person"]["attended_instances"]
        assert len(attended) == 2

    def test_a_person_with_no_instruments_still_reports_their_nights(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        # The other edge of the same join: with no instrument rows a LEFT JOIN
        # keeps one NULL row, and it must not swallow the attendance.
        dates = ["2031-05-06", "2031-05-13", "2031-05-20"]
        session_path, person_id, _ = self._make(
            db_conn, db_cursor, [], dates, authenticated_regular_user.person_id,
        )

        with authenticated_regular_user:
            resp = client.get(f"/api/sessions/{session_path}/people/{person_id}")

        person = json.loads(resp.data)["person"]
        assert len(person["attended_instances"]) == 3
        assert list(person["instruments"]) == []

    def test_two_instances_on_one_date_are_two_entries(
        self, client, authenticated_regular_user, db_conn, db_cursor
    ):
        """A festival runs a session twice in a day (spec 047), so a date is not a
        unique key. Both nights must come back, with distinct instance ids — which
        is why the UI keys this list on the id rather than the date."""
        session_path, person_id, instance_ids = self._make(
            db_conn, db_cursor, ["fiddle"], ["2031-06-07", "2031-06-07"],
            authenticated_regular_user.person_id,
        )

        with authenticated_regular_user:
            resp = client.get(f"/api/sessions/{session_path}/people/{person_id}")

        attended = json.loads(resp.data)["person"]["attended_instances"]
        assert len(attended) == 2
        assert len({a["session_instance_id"] for a in attended}) == 2
        assert {a["date"] for a in attended} == {"2031-06-07"}
