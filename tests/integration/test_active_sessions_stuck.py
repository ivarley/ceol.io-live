"""The active-sessions job turns off every night it turned on.

It scans a few days around today for nights that should be on, and once only saw
those days. A night moved out of them while on (set_date to last week) or cancelled
while on was never seen again and stayed "on now" for good.
"""
import datetime

import pytest


@pytest.fixture
def stuck_instances(db_cursor, db_conn):
    """Two nights left on: one dated a month ago, one cancelled today. Committed, since
    the job uses its own connection, and deleted afterwards."""
    db_cursor.execute("SELECT session_id FROM session ORDER BY session_id LIMIT 1")
    session_id = db_cursor.fetchone()[0]
    today = datetime.date.today()
    ids = []
    for date, cancelled in ((today - datetime.timedelta(days=30), False), (today, True)):
        db_cursor.execute(
            """
            INSERT INTO session_instance (session_id, date, start_time, end_time, is_active, is_cancelled)
            VALUES (%s, %s, '00:00', '23:59', TRUE, %s) RETURNING session_instance_id
            """,
            (session_id, date, cancelled),
        )
        ids.append(db_cursor.fetchone()[0])
    db_conn.commit()
    yield ids
    db_cursor.execute("DELETE FROM session_instance WHERE session_instance_id = ANY(%s)", (ids,))
    db_conn.commit()


def test_job_turns_off_nights_outside_its_window(stuck_instances, db_cursor, db_conn):
    from active_session_manager import update_active_sessions

    stats = update_active_sessions()

    deactivated = {d["instance_id"] for d in stats["deactivated"]}
    assert set(stuck_instances) <= deactivated
    db_conn.commit()  # a fresh snapshot, to see the job's writes
    db_cursor.execute(
        "SELECT session_instance_id, is_active FROM session_instance WHERE session_instance_id = ANY(%s)",
        (stuck_instances,),
    )
    assert all(not active for _, active in db_cursor.fetchall())
