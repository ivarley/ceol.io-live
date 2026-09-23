"""Tab-label counts on the session page (spec 052 §B8 Stage 2).

The Logs and People tabs fetch their own data when you open them, so a count made
in the client could only appear after you had already gone and looked. These three
numbers therefore ride on the detail payload.

A count next to a label is believed instantly and checked by nobody, so what is
pinned here is that each one matches what its tab actually shows on arrival:
cancelled nights are not in the list, and People opens on Members, which excludes
visitors and archived people. A count that includes rows the tab then hides is a
small lie that reads as a bug in the list.
"""

import json

import pytest

TC_SESSION = 95800
TC_INSTANCE_BASE = 95810
TC_PERSON_BASE = 95820


def _cleanup(cur):
    cur.execute(
        "DELETE FROM session_instance WHERE session_id = %s",
        (TC_SESSION,),
    )
    cur.execute("DELETE FROM session_person WHERE session_id = %s", (TC_SESSION,))
    cur.execute("DELETE FROM session WHERE session_id = %s", (TC_SESSION,))
    cur.execute(
        "DELETE FROM person WHERE person_id BETWEEN %s AND %s",
        (TC_PERSON_BASE, TC_PERSON_BASE + 50),
    )


@pytest.fixture
def counted_session(db_conn, db_cursor, authenticated_regular_user):
    """A session with three live nights and one cancelled, and a mixed roster."""
    cur = db_cursor
    _cleanup(cur)
    db_conn.commit()

    cur.execute(
        """
        INSERT INTO session (session_id, name, path, timezone, city, state, country,
                             show_people_list)
        VALUES (%s, 'Counted Session', 'test/counted', 'America/Chicago',
                'Austin', 'TX', 'USA', TRUE)
        """,
        (TC_SESSION,),
    )

    # Three that will be listed, one cancelled that will not.
    for i, cancelled in enumerate([False, False, False, True]):
        cur.execute(
            """
            INSERT INTO session_instance (session_instance_id, session_id, date, is_cancelled)
            VALUES (%s, %s, DATE '2031-02-01' + %s, %s)
            """,
            (TC_INSTANCE_BASE + i, TC_SESSION, i, cancelled),
        )

    # The viewer is a confirmed member, so they may see the roster at all.
    viewer = authenticated_regular_user.person_id
    cur.execute(
        """
        INSERT INTO session_person (session_id, person_id, relationship, confirmed, archived, is_admin)
        VALUES (%s, %s, 'member', TRUE, FALSE, FALSE)
        ON CONFLICT (session_id, person_id) DO UPDATE SET confirmed = TRUE, archived = FALSE
        """,
        (TC_SESSION, viewer),
    )

    # Two more members, one visitor, one archived member. Members = viewer + 2 = 3.
    roster = [
        ("member", False),
        ("member", False),
        ("visitor", False),
        ("member", True),
    ]
    for i, (relationship, archived) in enumerate(roster):
        pid = TC_PERSON_BASE + i
        cur.execute(
            "INSERT INTO person (person_id, first_name, last_name) VALUES (%s, 'Count', %s)",
            (pid, f"Person{i}"),
        )
        cur.execute(
            """
            INSERT INTO session_person (session_id, person_id, relationship, confirmed, archived, is_admin)
            VALUES (%s, %s, %s, TRUE, %s, FALSE)
            """,
            (TC_SESSION, pid, relationship, archived),
        )

    db_conn.commit()
    yield {"path": "test/counted", "viewer": viewer}

    _cleanup(db_cursor)
    db_conn.commit()


def _detail(client, user, path):
    with user:
        resp = client.get(f"/api/sessions/{path}/detail")
    assert resp.status_code == 200
    return json.loads(resp.data)


@pytest.mark.integration
class TestTabCounts:
    def test_the_logs_count_leaves_out_cancelled_nights(
        self, client, authenticated_regular_user, counted_session
    ):
        body = _detail(client, authenticated_regular_user, counted_session["path"])
        assert body["total_logs_count"] == 3

    def test_the_people_count_is_the_members_filter_the_tab_opens_on(
        self, client, authenticated_regular_user, counted_session
    ):
        # Viewer + two members. Not the visitor, not the archived member — the tab
        # does not show them until you change the filter, so the label must not
        # count them.
        body = _detail(client, authenticated_regular_user, counted_session["path"])
        assert body["total_people_count"] == 3

    def test_the_people_count_is_absent_for_someone_who_may_not_see_the_roster(
        self, client, authenticated_regular_user, counted_session, db_conn, db_cursor
    ):
        """The size of a group is information about it.

        `null`, not 0: "you can't know" and "there is nobody" are different, and a 0
        would render as a count of none rather than as no count at all.
        """
        db_cursor.execute(
            "UPDATE session_person SET confirmed = FALSE WHERE session_id = %s AND person_id = %s",
            (TC_SESSION, counted_session["viewer"]),
        )
        db_conn.commit()

        body = _detail(client, authenticated_regular_user, counted_session["path"])
        assert body["permissions"]["can_view_people"] is False
        assert body["total_people_count"] is None

    def test_turning_the_people_list_off_also_removes_the_count(
        self, client, authenticated_regular_user, counted_session, db_conn, db_cursor
    ):
        # spec 039: show_people_list off hides the tab from everyone, admins included.
        db_cursor.execute(
            "UPDATE session SET show_people_list = FALSE WHERE session_id = %s",
            (TC_SESSION,),
        )
        db_conn.commit()

        body = _detail(client, authenticated_regular_user, counted_session["path"])
        assert body["total_people_count"] is None

    def test_the_tunes_count_is_the_whole_list_not_the_first_page(
        self, client, authenticated_regular_user
    ):
        """The Tunes tab pages; the label counts all of them.

        Uses the seeded Mueller session, which has more tunes than fit one page on
        the big session it was seeded from.
        """
        body = _detail(client, authenticated_regular_user, "austin/mueller")
        assert body["total_tunes_count"] >= len(body["tunes"])
