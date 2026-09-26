"""
Integration tests for the admin person merge (spec 040).

Service-level tests run inside one uncommitted transaction (db_conn
auto-rollback) against a fixture pair with every collision shape: overlapping
tunes/instruments/sessions/attendance/logger-colors, set-starter attributions,
recordings, referral pointers, and (per-test) login accounts. They pin the
field-merge doctrine: furthest-along status, summed heard_count, earliest
learned_date, concatenated notes, OR'd grant booleans, AND'd archived/is_auto,
member-beats-visitor, yes>maybe>no attendance, MIN arrival_seq, winner-stands
scalars — plus the profile fill-gaps rule and delete-loser-first email
inheritance.

HTTP tests only cover the auth gate (403 for non-system-admins); the endpoint
body is a thin two-phase wrapper over the same service functions.
"""

import pytest

from services.person_merge_service import (
    MergeValidationError,
    build_merge_preview,
    execute_merge,
)

pytestmark = pytest.mark.integration

# Throwaway fixture ids (96xx block), all rolled back.
L = 9601   # loser — merged away
W = 9602   # winner — survivor
X = 9603   # bystander person (referred_by pointer holder)
S_BOTH = 9601    # session both belong to
S_ONLY = 9602    # session only the loser belongs to
I_BOTH = 9601    # instance both attended
I_ONLY = 9602    # instance only the loser attended
T_BOTH = 9601    # tune both have in person_tune
T_ONLY = 9602    # tune only the loser has (with instrument overrides)
SIT = 9601       # logged tune row started by the loser
REC = 9601       # recording made by the loser
U_L = 9601       # loser's user account
U_W = 9602       # winner's user account
U_X = 9603       # bystander user account (referred by the loser)


def _build(cur):
    """The full collision scenario (no accounts; tests add those per-case)."""
    cur.execute(
        "INSERT INTO person (person_id, first_name, last_name, email, city) VALUES "
        "(%s, 'Loser', 'Dupe', 'dupe@x.test', 'Cork'), "
        "(%s, 'Winner', 'Real', NULL, NULL), "
        "(%s, 'By', 'Stander', NULL, NULL)",
        (L, W, X),
    )
    cur.execute(
        "INSERT INTO session (session_id, name, path) VALUES "
        "(%s, 'Merge040 Both', 'merge040-both'), (%s, 'Merge040 Only', 'merge040-only')",
        (S_BOTH, S_ONLY),
    )
    cur.execute(
        "INSERT INTO session_instance (session_instance_id, session_id, date) VALUES "
        "(%s, %s, '2026-07-01'), (%s, %s, '2026-07-02')",
        (I_BOTH, S_BOTH, I_ONLY, S_ONLY),
    )
    cur.execute("INSERT INTO tune (tune_id, name, tune_type) VALUES (%s, 'Both Reel', 'Reel'), (%s, 'Only Jig', 'Jig')", (T_BOTH, T_ONLY))

    # session_person: colliding row (winner unconfirmed visitor with reminder
    # off; loser confirmed archived member admin) + loser-only row.
    cur.execute(
        """INSERT INTO session_person (session_id, person_id, relationship, confirmed, archived,
                                       is_admin, gets_email_reminder, gets_email_followup) VALUES
           (%s, %s, 'visitor', FALSE, FALSE, FALSE, FALSE, FALSE),
           (%s, %s, 'member',  TRUE,  TRUE,  TRUE,  TRUE,  FALSE),
           (%s, %s, 'member',  TRUE,  FALSE, FALSE, FALSE, FALSE)""",
        (S_BOTH, W, S_BOTH, L, S_ONLY, L),
    )

    # attendance: colliding (winner maybe/no comment/seq 5; loser yes/comment/seq 2)
    # + loser-only.
    cur.execute(
        """INSERT INTO session_instance_person (session_instance_id, person_id, attendance, comment, arrival_seq) VALUES
           (%s, %s, 'maybe', NULL, 5),
           (%s, %s, 'yes', 'brought the flute', 2),
           (%s, %s, 'no', NULL, NULL)""",
        (I_BOTH, W, I_BOTH, L, I_ONLY, L),
    )

    # person_instrument: colliding Fiddle (winner auto, loser curated) + loser-only Banjo.
    cur.execute(
        "INSERT INTO person_instrument (person_id, instrument, is_auto) VALUES "
        "(%s, 'Fiddle', TRUE), (%s, 'Fiddle', FALSE), (%s, 'Banjo', TRUE)",
        (W, L, L),
    )

    # person_tune: colliding T_BOTH (winner behind but annotated; loser further
    # along with heard_count and notes) + loser-only T_ONLY.
    cur.execute(
        """INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count, learned_date, notes, name_alias) VALUES
           (%s, %s, 'want to learn', 3, NULL, 'winner note', 'Winner Alias'),
           (%s, %s, 'learned', 4, '2024-01-01', 'loser note', 'Loser Alias'),
           (%s, %s, 'learning', NULL, NULL, NULL, NULL)""",
        (W, T_BOTH, L, T_BOTH, L, T_ONLY),
    )
    # overrides: colliding (Whistle on T_BOTH), move-under-colliding-parent
    # (Concertina on T_BOTH), carried-by-cascade (Fiddle on T_ONLY).
    cur.execute(
        """INSERT INTO person_tune_instrument (person_id, tune_id, instrument, status) VALUES
           (%s, %s, 'Whistle', 'learned'),
           (%s, %s, 'Whistle', 'learning'),
           (%s, %s, 'Concertina', 'learning'),
           (%s, %s, 'Fiddle', 'learned')""",
        (L, T_BOTH, W, T_BOTH, L, T_BOTH, L, T_ONLY),
    )

    # logger colors: colliding on S_BOTH (winner keeps 1) + loser-only on S_ONLY.
    cur.execute(
        "INSERT INTO session_logger_color (session_id, person_id, color) VALUES "
        "(%s, %s, 1), (%s, %s, 2), (%s, %s, 3)",
        (S_BOTH, W, S_BOTH, L, S_ONLY, L),
    )

    # a set the loser started, and a recording they made
    cur.execute(
        "INSERT INTO session_instance_tune (session_instance_tune_id, session_instance_id, tune_id, "
        "order_position, record_type, started_by_person_id) VALUES (%s, %s, %s, 'a0', 'tune', %s)",
        (SIT, I_BOTH, T_BOTH, L),
    )
    cur.execute(
        "INSERT INTO recording (recording_id, session_instance_id, person_id, storage_key, duration_ms) "
        "VALUES (%s, %s, %s, 'recordings/test/merge040.m4a', 600000)",
        (REC, I_BOTH, L),
    )

    # a bystander user referred by the loser
    cur.execute(
        "INSERT INTO user_account (user_id, person_id, username, user_email, referred_by_person_id) "
        "VALUES (%s, %s, 'merge040-bystander', 'by@x.test', %s)",
        (U_X, X, L),
    )


def _add_account(cur, user_id, person_id, username):
    cur.execute(
        "INSERT INTO user_account (user_id, person_id, username, user_email) VALUES (%s, %s, %s, %s)",
        (user_id, person_id, username, f"{username}@x.test"),
    )


def _merge(conn, **kwargs):
    return execute_merge(conn, L, W, user_id=None, **kwargs)


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def test_self_merge_rejected(db_conn):
    with pytest.raises(MergeValidationError):
        execute_merge(db_conn, L, L, user_id=None)


def test_missing_person_rejected(db_conn):
    with pytest.raises(MergeValidationError) as e:
        execute_merge(db_conn, 99999901, 99999902, user_id=None)
    assert e.value.status == 404


# --------------------------------------------------------------------------- #
# clean moves
# --------------------------------------------------------------------------- #

def test_clean_moves_repoint_everything(db_cursor, db_conn):
    _build(db_cursor)
    result = _merge(db_conn)
    assert result["success"] is True
    assert result["moved"] == {
        "person_tune": 1,
        "person_instrument": 1,
        "person_tune_instrument": 2,  # carried Fiddle + moved Concertina
        "session_person": 1,
        "session_instance_person": 1,
        "session_logger_color": 1,
        "set_starter_attributions": 1,
        "recordings": 1,
        "referred_by_pointers": 1,
    }

    checks = [
        ("SELECT COUNT(*) FROM person_tune WHERE person_id = %s", 2),
        ("SELECT COUNT(*) FROM person_instrument WHERE person_id = %s", 2),
        ("SELECT COUNT(*) FROM person_tune_instrument WHERE person_id = %s", 3),
        ("SELECT COUNT(*) FROM session_person WHERE person_id = %s", 2),
        ("SELECT COUNT(*) FROM session_instance_person WHERE person_id = %s", 2),
        ("SELECT COUNT(*) FROM session_logger_color WHERE person_id = %s", 2),
        ("SELECT COUNT(*) FROM session_instance_tune WHERE started_by_person_id = %s", 1),
        ("SELECT COUNT(*) FROM recording WHERE person_id = %s", 1),
        ("SELECT COUNT(*) FROM user_account WHERE referred_by_person_id = %s", 1),
    ]
    for sql, expected in checks:
        db_cursor.execute(sql, (W,))
        assert db_cursor.fetchone()[0] == expected, sql
        # ...and nothing left pointing at the loser
        db_cursor.execute(sql, (L,))
        assert db_cursor.fetchone()[0] == 0, sql

    db_cursor.execute("SELECT COUNT(*) FROM person WHERE person_id = %s", (L,))
    assert db_cursor.fetchone()[0] == 0


# --------------------------------------------------------------------------- #
# field-merge doctrine
# --------------------------------------------------------------------------- #

def test_person_tune_field_merge(db_cursor, db_conn):
    _build(db_cursor)
    result = _merge(db_conn)
    assert result["field_merged"]["person_tune"] == 1
    db_cursor.execute(
        "SELECT learn_status, heard_count, learned_date, notes, name_alias "
        "FROM person_tune WHERE person_id = %s AND tune_id = %s",
        (W, T_BOTH),
    )
    learn_status, heard_count, learned_date, notes, name_alias = db_cursor.fetchone()
    assert learn_status == "learned"            # furthest along wins
    assert heard_count == 7                      # 3 + 4, hearings were split
    assert learned_date is not None              # loser's earliest non-null
    assert notes == "winner note\n\nloser note"  # both kept
    assert name_alias == "Winner Alias"          # scalar: winner's row stands


def test_person_tune_instrument_merge(db_cursor, db_conn):
    _build(db_cursor)
    _merge(db_conn)
    db_cursor.execute(
        "SELECT instrument, status FROM person_tune_instrument "
        "WHERE person_id = %s AND tune_id = %s ORDER BY instrument",
        (W, T_BOTH),
    )
    assert db_cursor.fetchall() == [
        ("Concertina", "learning"),  # moved under the colliding parent
        ("Whistle", "learned"),      # collided: furthest along wins
    ]


def test_person_instrument_curation_survives(db_cursor, db_conn):
    _build(db_cursor)
    _merge(db_conn)
    db_cursor.execute(
        "SELECT is_auto FROM person_instrument WHERE person_id = %s AND instrument = 'Fiddle'", (W,)
    )
    # AND, not OR: is_auto=False is deliberate curation
    assert db_cursor.fetchone()[0] is False


def test_session_person_merge(db_cursor, db_conn):
    _build(db_cursor)
    _merge(db_conn)
    db_cursor.execute(
        "SELECT relationship, confirmed, archived, is_admin, gets_email_reminder, gets_email_followup "
        "FROM session_person WHERE session_id = %s AND person_id = %s",
        (S_BOTH, W),
    )
    relationship, confirmed, archived, is_admin, reminder, followup = db_cursor.fetchone()
    assert relationship == "member"   # member beats visitor
    assert confirmed is True          # OR
    assert archived is False          # AND — either row alive means alive
    assert is_admin is True           # OR
    assert reminder is True           # OR
    assert followup is False


def test_attendance_merge(db_cursor, db_conn):
    _build(db_cursor)
    _merge(db_conn)
    db_cursor.execute(
        "SELECT attendance, comment, arrival_seq FROM session_instance_person "
        "WHERE session_instance_id = %s AND person_id = %s",
        (I_BOTH, W),
    )
    attendance, comment, arrival_seq = db_cursor.fetchone()
    assert attendance == "yes"                 # yes > maybe
    assert comment == "brought the flute"      # only one side had one
    assert arrival_seq == 2                    # MIN: earlier arrival


def test_logger_color_winner_stands(db_cursor, db_conn):
    _build(db_cursor)
    _merge(db_conn)
    db_cursor.execute(
        "SELECT session_id, color FROM session_logger_color WHERE person_id = %s ORDER BY session_id", (W,)
    )
    assert db_cursor.fetchall() == [(S_BOTH, 1), (S_ONLY, 3)]


# --------------------------------------------------------------------------- #
# profile fields
# --------------------------------------------------------------------------- #

def test_profile_fill_gaps_and_email_inheritance(db_cursor, db_conn):
    _build(db_cursor)
    result = _merge(db_conn)
    # email + city were NULL on the winner: filled from the loser — email
    # inheritance proves the loser row is deleted BEFORE the winner update
    # (the partial unique index would reject it otherwise).
    assert result["profile_fills"] == {"email": "dupe@x.test", "city": "Cork"}
    db_cursor.execute("SELECT email, city, first_name FROM person WHERE person_id = %s", (W,))
    assert db_cursor.fetchone() == ("dupe@x.test", "Cork", "Winner")


def test_winner_values_never_overwritten(db_cursor, db_conn):
    _build(db_cursor)
    db_cursor.execute("UPDATE person SET email = 'real@x.test' WHERE person_id = %s", (W,))
    result = _merge(db_conn)
    assert "email" not in result["profile_fills"]
    db_cursor.execute("SELECT email FROM person WHERE person_id = %s", (W,))
    assert db_cursor.fetchone()[0] == "real@x.test"


# --------------------------------------------------------------------------- #
# accounts
# --------------------------------------------------------------------------- #

def test_loser_only_account_repointed(db_cursor, db_conn):
    _build(db_cursor)
    _add_account(db_cursor, U_L, L, "merge040-loser")
    result = _merge(db_conn)
    assert result["deleted_user_id"] is None
    db_cursor.execute("SELECT person_id FROM user_account WHERE user_id = %s", (U_L,))
    assert db_cursor.fetchone()[0] == W


def test_both_accounts_requires_choice(db_cursor, db_conn):
    _build(db_cursor)
    _add_account(db_cursor, U_L, L, "merge040-loser")
    _add_account(db_cursor, U_W, W, "merge040-winner")
    with pytest.raises(MergeValidationError, match="surviving_user_id"):
        _merge(db_conn)
    with pytest.raises(MergeValidationError, match="must be one of"):
        _merge(db_conn, surviving_user_id=U_X)


def test_both_accounts_losers_account_survives(db_cursor, db_conn):
    """The admin picks the LOSING person's account: the winner's own account is
    deleted and the survivor is re-linked, with the deleted user's corroborations
    repointed (conflict rows dropped) and email records reattributed."""
    _build(db_cursor)
    _add_account(db_cursor, U_L, L, "merge040-loser")
    _add_account(db_cursor, U_W, W, "merge040-winner")

    # U_W (about to be deleted) owns user-keyed rows; a second logged tune lets
    # us exercise both the conflict-drop and the clean repoint.
    db_cursor.execute(
        "INSERT INTO session_instance_tune (session_instance_tune_id, session_instance_id, tune_id, "
        "order_position, record_type) VALUES (%s, %s, %s, 'a1', 'tune')",
        (SIT + 1, I_BOTH, T_BOTH),
    )
    db_cursor.execute(
        "INSERT INTO corroboration (record_id, user_id) VALUES (%s, %s), (%s, %s), (%s, %s)",
        (SIT, U_L, SIT, U_W, SIT + 1, U_W),  # SIT: both users -> U_W's row drops
    )
    db_cursor.execute(
        "INSERT INTO email_message (email_message_id, subject, body_markdown, sent_by_user_id) "
        "VALUES (%s, 's', 'b', %s)",
        (9601, U_W),
    )
    db_cursor.execute(
        "INSERT INTO email_message_recipient (email_message_id, user_id, email, status) "
        "VALUES (%s, %s, 'a@x.test', 'sent'), (%s, %s, 'b@x.test', 'sent')",
        (9601, U_L, 9601, U_W),  # both recipients -> U_W's row drops
    )

    result = _merge(db_conn, surviving_user_id=U_L)
    assert result["deleted_user_id"] == U_W

    db_cursor.execute("SELECT person_id FROM user_account WHERE user_id = %s", (U_L,))
    assert db_cursor.fetchone()[0] == W
    db_cursor.execute("SELECT COUNT(*) FROM user_account WHERE user_id = %s", (U_W,))
    assert db_cursor.fetchone()[0] == 0

    db_cursor.execute("SELECT record_id, user_id FROM corroboration WHERE record_id IN (%s, %s) ORDER BY record_id", (SIT, SIT + 1))
    assert db_cursor.fetchall() == [(SIT, U_L), (SIT + 1, U_L)]
    db_cursor.execute("SELECT sent_by_user_id FROM email_message WHERE email_message_id = 9601")
    assert db_cursor.fetchone()[0] == U_L
    db_cursor.execute("SELECT user_id FROM email_message_recipient WHERE email_message_id = 9601")
    assert db_cursor.fetchall() == [(U_L,)]


def test_both_accounts_winners_account_survives(db_cursor, db_conn):
    _build(db_cursor)
    _add_account(db_cursor, U_L, L, "merge040-loser")
    _add_account(db_cursor, U_W, W, "merge040-winner")
    result = _merge(db_conn, surviving_user_id=U_W)
    assert result["deleted_user_id"] == U_L
    db_cursor.execute("SELECT user_id, person_id FROM user_account WHERE person_id = %s", (W,))
    assert db_cursor.fetchall() == [(U_W, W)]


# --------------------------------------------------------------------------- #
# history
# --------------------------------------------------------------------------- #

def test_history_rows_written(db_cursor, db_conn):
    _build(db_cursor)
    _add_account(db_cursor, U_L, L, "merge040-loser")
    _merge(db_conn)

    # the loser's final state is snapshotted as a DELETE
    db_cursor.execute(
        "SELECT first_name, email FROM person_history WHERE person_id = %s AND operation = 'DELETE'", (L,)
    )
    assert db_cursor.fetchone() == ("Loser", "dupe@x.test")
    # the winner's pre-fill state as an UPDATE
    db_cursor.execute(
        "SELECT email FROM person_history WHERE person_id = %s AND operation = 'UPDATE'", (W,)
    )
    assert db_cursor.fetchone() == (None,)
    # colliding person_tune: winner UPDATE + loser DELETE snapshots
    db_cursor.execute(
        "SELECT person_id, operation, learn_status FROM person_tune_history "
        "WHERE tune_id = %s ORDER BY person_id",
        (T_BOTH,),
    )
    assert (L, "DELETE", "learned") in db_cursor.fetchall()
    db_cursor.execute(
        "SELECT COUNT(*) FROM person_tune_history WHERE person_id = %s AND tune_id = %s AND operation = 'UPDATE'",
        (W, T_BOTH),
    )
    assert db_cursor.fetchone()[0] == 1
    # the loser-only tune's move is snapshotted under the OLD person_id
    db_cursor.execute(
        "SELECT COUNT(*) FROM person_tune_history WHERE person_id = %s AND tune_id = %s AND operation = 'UPDATE'",
        (L, T_ONLY),
    )
    assert db_cursor.fetchone()[0] == 1
    # repointed account snapshotted with its old person_id
    db_cursor.execute(
        "SELECT person_id FROM user_account_history WHERE user_id = %s AND operation = 'UPDATE'", (U_L,)
    )
    assert db_cursor.fetchone()[0] == L


# --------------------------------------------------------------------------- #
# preview
# --------------------------------------------------------------------------- #

def test_preview_reports_without_mutating(db_cursor, db_conn):
    _build(db_cursor)
    preview = build_merge_preview(db_conn, L, W)
    assert preview["preview"] is True
    assert preview["accounts"] == {"situation": "none", "needs_choice": False}
    assert preview["moves"]["person_tune"] == 1
    assert preview["moves"]["set_starter_attributions"] == 1

    pt = preview["collisions"]["person_tune"]
    assert len(pt) == 1 and pt[0]["tune_name"] == "Both Reel"
    assert pt[0]["result"]["learn_status"] == "learned"
    assert pt[0]["result"]["heard_count"] == 7
    assert {o["instrument"] for o in pt[0]["instrument_overrides"]} == {"Whistle", "Concertina"}

    sp = preview["collisions"]["session_person"]
    assert len(sp) == 1 and sp[0]["result"]["relationship"] == "member"
    assert len(preview["collisions"]["session_instance_person"]) == 1
    assert len(preview["collisions"]["session_logger_color"]) == 1

    assert preview["profile"]["fills"] == {"email": "dupe@x.test", "city": "Cork"}

    # nothing changed
    db_cursor.execute("SELECT COUNT(*) FROM person WHERE person_id IN (%s, %s)", (L, W))
    assert db_cursor.fetchone()[0] == 2
    db_cursor.execute("SELECT COUNT(*) FROM person_tune WHERE person_id = %s", (L,))
    assert db_cursor.fetchone()[0] == 2


def test_preview_flags_account_choice_and_discards(db_cursor, db_conn):
    _build(db_cursor)
    _add_account(db_cursor, U_L, L, "merge040-loser")
    _add_account(db_cursor, U_W, W, "merge040-winner")
    db_cursor.execute("UPDATE person SET email = 'real@x.test' WHERE person_id = %s", (W,))
    preview = build_merge_preview(db_conn, L, W)
    assert preview["accounts"]["situation"] == "both"
    assert preview["accounts"]["needs_choice"] is True
    assert preview["profile"]["discards"] == {"email": "dupe@x.test"}
    assert any("Both people have login accounts" in w for w in preview["warnings"])
    assert any("Discarding email" in w for w in preview["warnings"])


# --------------------------------------------------------------------------- #
# HTTP auth gate
# --------------------------------------------------------------------------- #

def test_endpoint_requires_system_admin(client, authenticated_regular_user):
    with authenticated_regular_user:
        resp = client.post(
            "/api/admin/people/merge",
            json={"loser_person_id": 1, "winner_person_id": 2},
        )
        assert resp.status_code == 403
