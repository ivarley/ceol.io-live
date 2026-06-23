#!/usr/bin/env python3
"""
Phase 2 chunk 1 — presence (spec 024 §F). Two users each open an SSE stream; each
sees a live roster; arrival ordinals are distinct + stable; leaving updates others.

Run against an instance with NO browser windows attached (presence is real — open
browsers legitimately show up). Default instance 2.

Usage: venv/bin/python spike/test_phase2_presence.py [FLASK_PORT] [STREAM_PORT] [INSTANCE_ID]
"""
import sys, json, time, threading, queue
import requests

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
    ian = login("ian@ceol.io")
    sarah = login("sarah.oconnor@example.com")

    qi, qs = queue.Queue(), queue.Queue()
    threading.Thread(target=presence_reader, args=(ian, qi), daemon=True).start()
    time.sleep(0.8)
    r = latest(qi)
    assert r and len(r) == 1, f"ian alone should see roster of 1, got {r}"
    print(f"1. ian connects -> roster {[(p['name'], p['arrival_seq']) for p in r]} ✓")

    sarah_holder = {}
    threading.Thread(target=presence_reader, args=(sarah, qs, sarah_holder), daemon=True).start()
    time.sleep(1.0)

    ri = latest(qi)
    seqs = {p["person_id"]: p["arrival_seq"] for p in ri}
    assert len(ri) == 2, f"ian should now see 2 present, got {ri}"
    assert sorted(seqs.values()) == [0, 1], f"arrival ordinals should be distinct 0,1; got {seqs}"
    print(f"2. sarah joins -> ian sees both {[(p['name'], p['arrival_seq']) for p in ri]} ✓")

    rs = latest(qs)
    assert len(rs) == 2, f"sarah should also see 2, got {rs}"
    print("3. sarah sees the same 2-person roster ✓")

    # sarah leaves: force-close her response socket so the server's disconnect
    # watcher fires (a flag/session.close wouldn't — her reader is mid-iter_lines).
    sarah_holder["r"].close()
    sarah.close()
    r = latest(qi, timeout=8)
    assert r and len(r) == 1, f"after sarah leaves, ian should see 1, got {r}"
    print(f"4. sarah disconnects -> ian's roster shrinks to {[(p['name'], p['arrival_seq']) for p in r]} ✓")

    # ordinal stability: ian reconnecting keeps seq 0 (monotonic by first arrival)
    ian2 = login("ian@ceol.io")
    q2 = queue.Queue()
    threading.Thread(target=presence_reader, args=(ian2, q2), daemon=True).start()
    time.sleep(0.8)
    r = latest(q2)
    ian_seq = next((p["arrival_seq"] for p in r if p["person_id"] == 77128), None)
    assert ian_seq == 0, f"ian's arrival ordinal should stay 0, got {ian_seq} ({r})"
    print("5. ian's arrival ordinal stable across reconnect (still 0) ✓")

    # the reopen case the user hit: sarah rejoins -> ian (still connected) sees her return
    sarah2 = login("sarah.oconnor@example.com")
    sh2 = {}
    threading.Thread(target=presence_reader, args=(sarah2, queue.Queue(), sh2), daemon=True).start()
    time.sleep(1.0)
    r = latest(qi, timeout=6)
    names = sorted(p["name"] for p in (r or []))
    assert r and "Sarah" in names, f"after sarah reopens, ian should see her again, got {r}"
    print(f"6. sarah reopens -> ian sees her return {names} ✓")

    ian.close(); ian2.close(); sarah2.close()
    print("\nPHASE 2 PRESENCE: PASS ✅")


if __name__ == "__main__":
    main()
