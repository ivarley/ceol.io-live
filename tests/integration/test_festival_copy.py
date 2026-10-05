"""POST /api/sessions/<path>/copy-year (spec 056 "Spawning a year")."""

import pytest

from places_helpers import committed, logged_in  # noqa: F401 (fixture)

pytestmark = pytest.mark.integration

PAYLOAD = {
    "year": "2027",
    "initiation_date": "2027-10-21",
    "termination_date": "2027-10-24",
}


@pytest.fixture
def source(committed):
    """probefest/2026: a festival year with a venue, a non-default setting, two
    admins (people 1 and 3), a plain member (2), an instance and a thesession link."""
    committed.place("probefest", "Probe Fest", kind="festival", parent=1)
    sid = committed.session(
        "probefest/2026",
        1,
        name="Probe Fest 2026",
        session_type="festival",
        initiation_date="2026-10-22",
        termination_date="2026-10-25",
        timezone="America/Chicago",
        location_name="Jim Bowie",
        location_street="1 Main St",
        comments="Bring a chair",
        live_cache_session_limit=150,
        track_set_starters=False,
        thesession_id=99991,
        recurrence='{"schedules": []}',
    )
    committed.member(sid, 1, is_admin=True)
    committed.member(sid, 3, is_admin=True)
    committed.member(sid, 2)
    committed.instance(sid, "2026-10-22")
    return sid


def _copy(client, path="probefest/2026", person_id=1, is_system_admin=False, **over):
    with logged_in(client, person_id=person_id, is_system_admin=is_system_admin):
        return client.post(f"/api/sessions/{path}/copy-year", json={**PAYLOAD, **over})


def _row(committed, path):
    rows = committed.query(
        """SELECT session_type, place_id, location_name, location_street, timezone, comments,
                  live_cache_session_limit, track_set_starters, thesession_id, recurrence,
                  initiation_date::text, termination_date::text, name, session_id
           FROM session WHERE path = %s""",
        (path,),
    )
    return rows[0] if rows else None


def test_copies_the_year(client, committed, source):
    resp = _copy(client)
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json() == {"success": True, "path": "probefest/2027"}
    row = _row(committed, "probefest/2027")
    assert row[:8] == (
        "festival",
        1,
        "Jim Bowie",
        "1 Main St",
        "America/Chicago",
        "Bring a chair",
        150,
        False,
    )
    # Not copied: the upstream link and the recurrence.
    assert row[8:10] == (None, None)
    assert row[10:13] == ("2027-10-21", "2027-10-24", "Probe Fest 2027")


def test_admins_carry_and_nobody_else(client, committed, source):
    _copy(client)
    new_id = _row(committed, "probefest/2027")[13]
    people = committed.query(
        "SELECT person_id, is_admin, confirmed, relationship FROM session_person "
        "WHERE session_id = %s ORDER BY person_id",
        (new_id,),
    )
    assert people == [(1, True, True, "member"), (3, True, True, "member")]
    assert (
        committed.query(
            "SELECT 1 FROM session_instance WHERE session_id = %s", (new_id,)
        )
        == []
    )


def test_the_copier_becomes_an_admin(client, committed, source):
    # A system admin who is not on the roster at all.
    resp = _copy(client, person_id=4, is_system_admin=True)
    assert resp.status_code == 201, resp.get_json()
    new_id = _row(committed, "probefest/2027")[13]
    admins = committed.query(
        "SELECT person_id FROM session_person WHERE session_id = %s AND is_admin ORDER BY 1",
        (new_id,),
    )
    assert admins == [(1,), (3,), (4,)]


def test_backfills_an_earlier_year(client, committed, source):
    resp = _copy(
        client, year="2025", initiation_date="2025-10-23", termination_date="2025-10-26"
    )
    assert resp.status_code == 201
    assert _row(committed, "probefest/2025")[12] == "Probe Fest 2025"


def test_a_name_from_the_form(client, committed, source):
    _copy(client, name="Probe Fest 2027: the tenth")
    assert _row(committed, "probefest/2027")[12] == "Probe Fest 2027: the tenth"


def test_year_exists(client, committed, source):
    resp = _copy(client, year="2026")
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "year_exists"


def test_a_plain_member_may_not(client, committed, source):
    resp = _copy(client, person_id=2)
    assert resp.status_code == 403
    assert _row(committed, "probefest/2027") is None


@pytest.mark.parametrize(
    "over",
    [
        {"initiation_date": ""},
        {"termination_date": None},
        {"initiation_date": "2027-10-24", "termination_date": "2027-10-21"},
        {"year": "27"},
    ],
)
def test_bad_dates_or_year(client, committed, source, over):
    assert _copy(client, **over).status_code == 400


def test_not_a_festival_year(client, committed):
    with logged_in(client):
        resp = client.post("/api/sessions/austin/mueller/copy-year", json=PAYLOAD)
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "not_festival"
