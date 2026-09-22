"""The home payload's Today fields (spec 052 §B8 Stage 4).

Home's Today card is the subset of `upcoming_sessions` dated today, so everything
it shows has to travel on those rows: where the session is, whether it is live, how
many people are in the room, and how many tunes are on the log.

Two of those are counts over one-to-many relations, computed in the same query. That
is the shape that has already gone wrong once here: `attended_instances` used to be
aggregated alongside `person_instrument`, so every attended night came back once per
instrument the player owned. The counts below are scalar subqueries for that reason,
and the tests that matter most are the ones that would catch them multiplying each
other rather than the ones that check a field exists.
"""

import json

import pytest

HT_SESSION = 95700
HT_SESSION_B = 95701
HT_INSTANCE = 95702
HT_INSTANCE_B = 95703
HT_TUNE_BASE = 95710


def _cleanup(cur):
    """Remove everything this file creates, in dependency order."""
    cur.execute(
        "UPDATE person SET at_active_session_instance_id = NULL "
        "WHERE at_active_session_instance_id IN (%s, %s)",
        (HT_INSTANCE, HT_INSTANCE_B),
    )
    cur.execute(
        "DELETE FROM session_instance_tune WHERE session_instance_id IN (%s, %s)",
        (HT_INSTANCE, HT_INSTANCE_B),
    )
    cur.execute(
        "DELETE FROM session_instance WHERE session_instance_id IN (%s, %s)",
        (HT_INSTANCE, HT_INSTANCE_B),
    )
    cur.execute(
        "DELETE FROM session_person WHERE session_id IN (%s, %s)",
        (HT_SESSION, HT_SESSION_B),
    )
    cur.execute(
        "DELETE FROM session WHERE session_id IN (%s, %s)", (HT_SESSION, HT_SESSION_B)
    )


@pytest.fixture
def tonight(db_conn, db_cursor, authenticated_regular_user):
    """One live session on today's date, with a part-written log and people present.

    Dated with CURRENT_DATE rather than a literal, because "today" is the whole
    condition for the card existing and a fixed date stops being today tomorrow.
    """
    person_id = authenticated_regular_user.person_id
    cur = db_cursor

    # Build from a known-empty state and tear back down to one. These rows carry
    # explicit ids so the tests can name them, which means a leftover from the
    # previous test is a primary-key collision rather than a fresh row.
    _cleanup(cur)
    db_conn.commit()

    cur.execute(
        """
        INSERT INTO session (session_id, name, path, timezone, location_name, city, state, country)
        VALUES (%s, 'Home Today Session', 'test/home-today', 'America/Chicago',
                'The Test Bar', 'Austin', 'TX', 'USA')
        ON CONFLICT (session_id) DO NOTHING
        """,
        (HT_SESSION,),
    )
    cur.execute(
        """
        INSERT INTO session_person (session_id, person_id, relationship, confirmed, is_admin)
        VALUES (%s, %s, 'member', TRUE, FALSE)
        ON CONFLICT (session_id, person_id) DO UPDATE SET relationship = 'member'
        """,
        (HT_SESSION, person_id),
    )
    cur.execute(
        """
        INSERT INTO session_instance (session_instance_id, session_id, date, start_time, end_time,
                                      is_active, is_cancelled)
        VALUES (%s, %s, CURRENT_DATE, '19:00', '22:00', TRUE, FALSE)
        """,
        (HT_INSTANCE, HT_SESSION),
    )

    # Four tunes and one break. The break must not be counted: it is a set boundary
    # (spec 023), not something anybody played.
    for i, order in enumerate(["V", "W", "X", "Y"]):
        cur.execute(
            "INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, %s, 'Reel') "
            "ON CONFLICT (tune_id) DO NOTHING",
            (HT_TUNE_BASE + i, f"Home Today Tune {i}"),
        )
        cur.execute(
            """
            INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type)
            VALUES (%s, %s, %s, 'tune')
            """,
            (HT_INSTANCE, HT_TUNE_BASE + i, order),
        )
    cur.execute(
        """
        INSERT INTO session_instance_tune (session_instance_id, tune_id, order_position, record_type)
        VALUES (%s, NULL, 'Z', 'break')
        """,
        (HT_INSTANCE,),
    )

    db_conn.commit()
    yield {"session_id": HT_SESSION, "instance_id": HT_INSTANCE, "person_id": person_id}

    _cleanup(db_cursor)
    db_conn.commit()


def _home(client, user):
    with user:
        resp = client.get("/api/home")
    assert resp.status_code == 200
    return json.loads(resp.data)


def _row(body, instance_id):
    rows = [
        s for s in body["upcoming_sessions"] if s["session_instance_id"] == instance_id
    ]
    assert (
        len(rows) == 1
    ), f"expected exactly one row for instance {instance_id}, got {len(rows)}"
    return rows[0]


@pytest.mark.integration
class TestTodayFields:
    def test_the_card_has_everything_it_needs_without_a_second_request(
        self, client, authenticated_regular_user, tonight
    ):
        body = _home(client, authenticated_regular_user)
        row = _row(body, tonight["instance_id"])

        assert row["is_active"] is True
        assert row["location_name"] == "The Test Bar"
        assert row["end_time"] == "22:00:00"
        assert row["date"] == body["today"]

    def test_the_tally_counts_tunes_and_not_the_set_breaks(
        self, client, authenticated_regular_user, tonight
    ):
        body = _home(client, authenticated_regular_user)
        assert _row(body, tonight["instance_id"])["tunes_logged"] == 4

    def test_a_deleted_tune_leaves_the_tally(
        self, client, authenticated_regular_user, tonight, db_conn, db_cursor
    ):
        db_cursor.execute(
            "UPDATE session_instance_tune SET deleted = TRUE "
            "WHERE session_instance_id = %s AND tune_id = %s",
            (tonight["instance_id"], HT_TUNE_BASE),
        )
        db_conn.commit()

        body = _home(client, authenticated_regular_user)
        assert _row(body, tonight["instance_id"])["tunes_logged"] == 3

    def test_people_here_counts_the_room_and_nobody_else(
        self, client, authenticated_regular_user, tonight, db_conn, db_cursor
    ):
        body = _home(client, authenticated_regular_user)
        assert _row(body, tonight["instance_id"])["people_here"] == 0

        db_cursor.execute(
            """
            UPDATE person SET at_active_session_instance_id = %s
            WHERE person_id IN (SELECT person_id FROM person ORDER BY person_id LIMIT 2)
            """,
            (tonight["instance_id"],),
        )
        arrived = db_cursor.rowcount
        db_conn.commit()

        body = _home(client, authenticated_regular_user)
        assert _row(body, tonight["instance_id"])["people_here"] == arrived == 2

    def test_the_two_counts_do_not_multiply_each_other(
        self, client, authenticated_regular_user, tonight, db_conn, db_cursor
    ):
        """The regression this file exists for.

        Four logged tunes and three people in the room. Joined rather than
        subqueried, the answer would be 12 and 12 — and both numbers would look
        plausible on the card, which is how the last one survived for months.
        """
        # Put three DISTINCT people in the room. Naming ids literally alongside the
        # viewer's own would silently be two when the viewer happens to be one of
        # them, so the expected number comes from the update itself.
        db_cursor.execute(
            """
            UPDATE person SET at_active_session_instance_id = %s
            WHERE person_id IN (
                SELECT person_id FROM person ORDER BY person_id LIMIT 3
            )
            """,
            (tonight["instance_id"],),
        )
        in_the_room = db_cursor.rowcount
        db_conn.commit()
        assert in_the_room == 3

        row = _row(_home(client, authenticated_regular_user), tonight["instance_id"])
        assert row["tunes_logged"] == 4, "the head count multiplied the log"
        assert row["people_here"] == 3, "the log multiplied the head count"

    def test_the_viewers_name_travels_with_the_payload(
        self, client, authenticated_regular_user, tonight
    ):
        # The greeting used to read current_user in Jinja. The page is a Svelte
        # bundle now, and a native Home screen should not need /api/me to say hello.
        body = _home(client, authenticated_regular_user)
        assert body["viewer"]["person_id"] == authenticated_regular_user.person_id
        assert body["viewer"]["first_name"]


@pytest.mark.integration
class TestTwoSessionsOnOneDay:
    """A festival, or simply two sessions you belong to on the same evening.

    This is why Today is a strip rather than a card: the client picks every row
    whose date is today, so the payload has to return both rather than one.
    """

    def test_both_nights_come_back_as_separate_rows(
        self, client, authenticated_regular_user, tonight, db_conn, db_cursor
    ):
        db_cursor.execute(
            """
            INSERT INTO session (session_id, name, path, timezone, location_name, city, state, country)
            VALUES (%s, 'Home Today Session B', 'test/home-today-b', 'America/Chicago',
                    'The Other Bar', 'Austin', 'TX', 'USA')
            ON CONFLICT (session_id) DO NOTHING
            """,
            (HT_SESSION_B,),
        )
        db_cursor.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed, is_admin)
            VALUES (%s, %s, 'member', TRUE, FALSE)
            ON CONFLICT (session_id, person_id) DO UPDATE SET relationship = 'member'
            """,
            (HT_SESSION_B, tonight["person_id"]),
        )
        db_cursor.execute(
            """
            INSERT INTO session_instance (session_instance_id, session_id, date, start_time, end_time,
                                          is_active, is_cancelled)
            VALUES (%s, %s, CURRENT_DATE, '20:00', '23:00', FALSE, FALSE)
            """,
            (HT_INSTANCE_B, HT_SESSION_B),
        )
        db_conn.commit()

        body = _home(client, authenticated_regular_user)
        today_rows = [
            s for s in body["upcoming_sessions"] if s["date"] == body["today"]
        ]
        ids = {s["session_instance_id"] for s in today_rows}

        assert HT_INSTANCE in ids
        assert HT_INSTANCE_B in ids
        # The second one has its own log (empty) and its own liveness.
        second = _row(body, HT_INSTANCE_B)
        assert second["is_active"] is False
        assert second["tunes_logged"] == 0
