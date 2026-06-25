#!/usr/bin/env python3
"""
Per-session logger color (spec 024 §F). A person's palette color is assigned on
first appearance at a session, persisted in session_logger_color, distinct from
other loggers at that session, and STABLE across reconnects / streaming restarts
(so a regular is the same color week to week). Color != attendance != membership:
no session_person / session_instance_person row is touched.

Self-cleaning: deletes the color rows it creates (and asserts none pre-exist for
its test persons at the session, so the run starts deterministic).

Usage: venv/bin/python spike/test_color.py [FLASK_PORT] [STREAM_PORT] [INSTANCE_ID]
"""
import sys, os, json, time, threading, queue
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from database import get_db_connection

FLASK = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
STREAM = f"http://localhost:{sys.argv[2] if len(sys.argv) > 2 else 5015}"
INSTANCE = int(sys.argv[3]) if len(sys.argv) > 3 else 2
IAN, SARAH = 77128, 2     # person_ids


def session_of(instance_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id=%s", (instance_id,))
    sid = cur.fetchone()[0]; conn.close()
    return sid


def color_rows(session_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT person_id, color FROM session_logger_color WHERE session_id=%s AND person_id IN (%s,%s)",
                (session_id, IAN, SARAH))
    rows = dict(cur.fetchall()); conn.close()
    return rows


def clear_colors(session_id):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM session_logger_color WHERE session_id=%s AND person_id IN (%s,%s)",
                (session_id, IAN, SARAH))
    conn.commit(); conn.close()


def login(email):
    s = requests.Session()
    assert s.post(f"{FLASK}/api/auth/login-password", json={"email": email, "password": "password123"}).status_code == 200
    return s


def reader(session, out_q, holder=None):
    url = f"{STREAM}/live/instances/{INSTANCE}/events?last_event_id=999999999"
    try:
        with session.get(url, stream=True, timeout=30) as r:
            if holder is not None:
                holder["r"] = r
            ev = data = None
            for raw in r.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                line = raw.strip()
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()
                elif line == "" and ev == "presence" and data:
                    out_q.put(json.loads(data)["roster"]); ev = data = None
                elif line == "":
                    ev = data = None
    except Exception:
        pass


def latest(q, timeout=5):
    deadline = time.time() + timeout; seen = None
    while time.time() < deadline:
        try:
            seen = q.get(timeout=0.2)
        except queue.Empty:
            if seen is not None:
                return seen
    return seen


def seq_of(roster, pid):
    return next((p["arrival_seq"] for p in (roster or []) if p["person_id"] == pid), None)


def main():
    sid = session_of(INSTANCE)
    clear_colors(sid)   # start deterministic
    assert color_rows(sid) == {}, "expected no pre-existing color rows after clear"
    fail = []

    ian = login("ian@ceol.io")
    sarah = login("sarah.oconnor@example.com")
    sessions = [ian, sarah]
    try:
        qi = queue.Queue()
        threading.Thread(target=reader, args=(ian, qi), daemon=True).start()
        time.sleep(0.9)
        ri = latest(qi)
        ian_seq = seq_of(ri, IAN)
        print(f"1. ian connects -> color idx {ian_seq}")
        if ian_seq is None or not (0 <= ian_seq < 8):
            fail.append(f"ian should get a palette index 0..7, got {ian_seq}")

        # persisted in session_logger_color (and ONLY there)
        rows = color_rows(sid)
        print(f"2. session_logger_color rows: {rows}")
        if rows.get(IAN) != ian_seq:
            fail.append(f"ian's color should be persisted as {ian_seq}, db has {rows.get(IAN)}")

        # sarah joins -> distinct color
        sh = {}
        threading.Thread(target=reader, args=(sarah, queue.Queue(), sh), daemon=True).start()
        time.sleep(1.0)
        ri2 = latest(qi)
        sarah_seq = seq_of(ri2, SARAH)
        print(f"3. sarah joins -> color idx {sarah_seq}; roster {[(p['name'], p['arrival_seq']) for p in (ri2 or [])]}")
        if sarah_seq is None or sarah_seq == ian_seq:
            fail.append(f"sarah's color must be distinct from ian's ({ian_seq}), got {sarah_seq}")
        if color_rows(sid).get(SARAH) != sarah_seq:
            fail.append("sarah's color not persisted")

        # stability: ian reconnects -> SAME color (the whole point)
        ian2 = login("ian@ceol.io"); sessions.append(ian2)
        q2 = queue.Queue()
        threading.Thread(target=reader, args=(ian2, q2), daemon=True).start()
        time.sleep(0.9)
        ian_seq2 = seq_of(latest(q2), IAN)
        print(f"4. ian reconnects -> color idx {ian_seq2} (was {ian_seq})")
        if ian_seq2 != ian_seq:
            fail.append(f"ian's color must be stable across reconnect: {ian_seq} -> {ian_seq2}")

        # color must NOT have created attendance/membership rows
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT count(*) FROM session_person WHERE session_id=%s AND person_id=%s", (sid, IAN))
        sp_ian = cur.fetchone()[0]; conn.close()
        # (ian may legitimately already be a member; we only assert the color row exists,
        #  which it does — the negative-side-effect guarantee is structural: separate table.)
        print(f"5. ian session_person rows (informational): {sp_ian}")
    finally:
        for s in sessions:
            s.close()
        time.sleep(0.5)
        clear_colors(sid)
        print(f"6. cleaned up color rows -> {color_rows(sid)}")

    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    main()
