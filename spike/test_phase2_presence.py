#!/usr/bin/env python3
"""
Phase 2 chunk 1 — presence (spec 024 §F). Two users each open an SSE stream; each
sees a live roster; arrival ordinals are distinct + stable; leaving updates others.

Run against an instance with NO browser windows attached (presence is real — open
browsers legitimately show up). Default instance 2.

NOTE: arrival_seq in the roster is now the PERSISTED per-session color index
(session_logger_color), not an in-memory ordinal. It's still 0/1 here because this
test clears its persons' color rows first (deterministic) and ian connects before
sarah, so least-used assignment hands out 0 then 1. See spike/test_color.py for the
color-specific assertions. This test cleans up its color rows in a finally.

Usage: venv/bin/python spike/test_phase2_presence.py [FLASK_PORT] [STREAM_PORT] [INSTANCE_ID]
"""
import sys, os, json, time, threading, queue
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from database import get_db_connection

_TEST_PERSONS = (77128, 2)  # ian, sarah


def _clear_colors():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute(
        "DELETE FROM session_logger_color WHERE session_id = "
        "(SELECT session_id FROM session_instance WHERE session_instance_id = %s) "
        "AND person_id IN %s",
        (INSTANCE, _TEST_PERSONS),
    )
    conn.commit(); conn.close()

FLASK = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
STREAM = f"http://localhost:{sys.argv[2] if len(sys.argv) > 2 else 8080}"
INSTANCE = int(sys.argv[3]) if len(sys.argv) > 3 else 2


def login(email):
    s = requests.Session()
    assert s.post(f"{FLASK}/api/auth/login-password", json={"email": email, "password": "password123"}).status_code == 200
    return s


def presence_reader(session, out_q, holder=None):
    url = f"{STREAM}/live/instances/{INSTANCE}/events?last_event_id=999999999"
    try:
        with session.get(url, stream=True, timeout=30) as r:
            if holder is not None:
                holder["r"] = r  # let the main thread force-close this socket
            ev, data = None, None
            for raw in r.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                line = raw.strip()
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()
                elif line == "":
                    if ev == "presence" and data:
                        out_q.put(json.loads(data)["roster"])
                    ev, data = None, None
    except Exception:
        pass  # session.close() from main thread interrupts the stream -> we exit


def latest(q, timeout=5):
    deadline = time.time() + timeout
    seen = None
    while time.time() < deadline:
        try:
            seen = q.get(timeout=0.2)
        except queue.Empty:
            if seen is not None:
                return seen
    return seen


def main():
    _clear_colors()  # deterministic 0/1 assignment regardless of prior runs
    ian = login("ian@ceol.io")
    sarah = login("sarah.oconnor@example.com")

    # Count PRESENT people only — disconnected people now linger as away=True for up to
    # AWAY_TTL (§F), and a prior run's away entries may still be in the roster.
    def present(r):
        return [p for p in (r or []) if not p.get("away")]

    qi, qs = queue.Queue(), queue.Queue()
    threading.Thread(target=presence_reader, args=(ian, qi), daemon=True).start()
    time.sleep(0.8)
    r = latest(qi)
    assert len(present(r)) == 1, f"ian alone should be the only one PRESENT, got {r}"
    print(f"1. ian connects -> present {[p['name'] for p in present(r)]} ✓")

    sarah_holder = {}
    threading.Thread(target=presence_reader, args=(sarah, qs, sarah_holder), daemon=True).start()
    time.sleep(1.0)

    ri = latest(qi)
    pri = present(ri)
    seqs = {p["person_id"]: p["arrival_seq"] for p in pri}
    assert len(pri) == 2, f"ian should now see 2 PRESENT, got {ri}"
    # Color ordinals must be DISTINCT (the invariant). Exact values are no longer 0,1:
    # they're persisted per-session palette indices (session_logger_color), so if other
    # people at this session already hold colors the new joiners get the next free ones.
    assert len(set(seqs.values())) == 2, f"arrival ordinals should be distinct; got {seqs}"
    print(f"2. sarah joins -> ian sees both present {[(p['name'], p['arrival_seq']) for p in pri]} ✓")

    rs = latest(qs)
    assert len(present(rs)) == 2, f"sarah should also see 2 present, got {rs}"
    print("3. sarah sees the same 2 present ✓")

    # sarah leaves: force-close her response socket so the server's disconnect
    # watcher fires (a flag/session.close wouldn't — her reader is mid-iter_lines).
    # Per the away-state (§F), a disconnected person LINGERS as away (devices=0, away=True)
    # for up to AWAY_TTL rather than vanishing — so ian still sees 2 entries, but only 1
    # present (away=False) and sarah marked away.
    sarah_holder["r"].close()
    sarah.close()
    r = latest(qi, timeout=8)
    present = [p for p in (r or []) if not p.get("away")]
    sarah_entry = next((p for p in (r or []) if p["person_id"] == 2), None)
    assert len(present) == 1, f"after sarah leaves, ian should see 1 PRESENT, got {[ (p['name'], p.get('away')) for p in (r or []) ]}"
    assert sarah_entry and sarah_entry.get("away") is True, f"sarah should linger as away=True, got {sarah_entry}"
    print(f"4. sarah disconnects -> she lingers as away; present={[p['name'] for p in present]} ✓")

    # ordinal stability: ian reconnecting keeps the SAME persisted color index
    ian_seq0 = seqs[77128]
    ian2 = login("ian@ceol.io")
    q2 = queue.Queue()
    threading.Thread(target=presence_reader, args=(ian2, q2), daemon=True).start()
    time.sleep(0.8)
    r = latest(q2)
    ian_seq = next((p["arrival_seq"] for p in r if p["person_id"] == 77128), None)
    assert ian_seq == ian_seq0, f"ian's color index should stay {ian_seq0}, got {ian_seq} ({r})"
    print(f"5. ian's color index stable across reconnect (still {ian_seq}) ✓")

    # the reopen case the user hit: sarah rejoins -> ian (still connected) sees her return
    sarah2 = login("sarah.oconnor@example.com")
    sh2 = {}
    threading.Thread(target=presence_reader, args=(sarah2, queue.Queue(), sh2), daemon=True).start()
    time.sleep(1.0)
    r = latest(qi, timeout=6)
    sarah_back = next((p for p in (r or []) if p["person_id"] == 2), None)
    assert sarah_back and not sarah_back.get("away"), f"after sarah reopens, ian should see her PRESENT again, got {r}"
    print(f"6. sarah reopens -> ian sees her present again ✓")

    ian.close(); ian2.close(); sarah2.close()
    print("\nPHASE 2 PRESENCE: PASS ✅")


if __name__ == "__main__":
    try:
        main()
    finally:
        _clear_colors()
