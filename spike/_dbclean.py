"""
Test cleanup helper: remove session_instance_tune rows a test created, so test
runs don't pollute the session. Capture baseline() before the test; cleanup(base)
after (delete every row with a higher id — tunes AND breaks the test added).
corroboration rows cascade (ON DELETE CASCADE); session_event feed rows are left
(harmless delivery log).
"""
import psycopg2


def _conn():
    return psycopg2.connect(host="localhost", dbname="ceol_test", user="test_user", password="test_password")


def baseline():
    c = _conn()
    try:
        cur = c.cursor()
        cur.execute("SELECT COALESCE(MAX(session_instance_tune_id), 0) FROM session_instance_tune")
        return cur.fetchone()[0]
    finally:
        c.close()


def cleanup(base):
    if base is None:
        return
    c = _conn()
    try:
        cur = c.cursor()
        cur.execute("DELETE FROM session_instance_tune WHERE session_instance_tune_id > %s", (base,))
        c.commit()
    finally:
        c.close()
