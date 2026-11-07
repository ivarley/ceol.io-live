"""The admin person page's Sessions tab (spec 052 §B1): the payload's `sessions`
list carries each session's town as a `place` object (spec 055, replacing the flat
city/state/country), the two role axes raw, and the roster flags the tab marks."""

from places_helpers import committed  # noqa: F401 (fixture)

PERSON = 2  # sarah_fiddle, seeded


def _sessions_for(person_id, session_ids):
    from database import get_db_connection
    from serializers import build_person_details_payload

    conn = get_db_connection()
    try:
        payload = build_person_details_payload(
            conn, person_id, is_user_profile=False, is_system_admin=True
        )
    finally:
        conn.close()
    return {
        s["session_id"]: s
        for s in payload["sessions"]
        if s["session_id"] in session_ids
    }


def test_the_persons_sessions_carry_place_role_and_roster_flags(committed):
    town = committed.place("probe-town", "Probe Town")
    in_town = committed.session(
        "probe-town/weekly", town, name="Probe Weekly", location_name="The Snug"
    )
    nowhere = committed.session("probe-nowhere/x", None, name="Probe Nowhere")
    # An admin who only visits, not yet vouched for; and an archived member.
    committed.query(
        """INSERT INTO session_person (session_id, person_id, relationship, confirmed, is_admin)
           VALUES (%s, %s, 'visitor', FALSE, TRUE) RETURNING session_id""",
        (in_town, PERSON),
    )
    committed.query(
        """INSERT INTO session_person (session_id, person_id, relationship, confirmed, is_admin, archived)
           VALUES (%s, %s, 'member', TRUE, FALSE, TRUE) RETURNING session_id""",
        (nowhere, PERSON),
    )

    rows = _sessions_for(PERSON, {in_town, nowhere})
    assert set(rows) == {in_town, nowhere}

    visited = rows[in_town]
    assert visited["session_name"] == "Probe Weekly"
    assert visited["session_path"] == "probe-town/weekly"
    assert visited["place"] == {"slug": "probe-town", "name": "Probe Town"}
    assert visited["location"] == "Probe Town"
    assert visited["location_name"] == "The Snug"
    # Admin outranks the relationship in the badge; the relationship ships raw.
    assert visited["role"] == "Admin"
    assert visited["is_admin"] is True
    assert visited["relationship"] == "visitor"
    assert visited["confirmed"] is False
    assert visited["archived"] is False

    member = rows[nowhere]
    assert member["place"] is None
    assert member["location"] == ""
    assert member["role"] == "Member"
    assert member["relationship"] == "member"
    assert member["archived"] is True
