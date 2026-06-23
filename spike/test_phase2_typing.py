#!/usr/bin/env python3
"""
Phase 2 chunk 2 — typing indicators (spec 024 §F). A typing signal POSTed to the
streaming service broadcasts to other clients, clears on commit, and times out.

Run against a browserless instance. Usage: ... [FLASK_PORT] [STREAM_PORT] [INSTANCE_ID]
"""
import sys, json, time, threading, queue
import requests

FLASK = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
STREAM = f"http://localhost:{sys.argv[2] if len(sys.argv) > 2 else 8080}"
INSTANCE = int(sys.argv[3]) if len(sys.argv) > 3 else 4


def login(email):
    s = requests.Session()
    assert s.post(f"{FLASK}/api/auth/login-password", json={"email": email, "password": "password123"}).status_code == 200
    return s


def reader(session, out_q, holder):
    url = f"{STREAM}/live/instances/{INSTANCE}/events?last_event_id=999999999"
    try:
        with session.get(url, stream=True, timeout=30) as r:
            holder["r"] = r
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
                    if ev == "typing" and data:
                        out_q.put(json.loads(data)["typing"])
                    ev, data = None, None
    except Exception:
        pass


def latest_typing(q, timeout=4):
    deadline = time.time() + timeout
    seen = None
    while time.time() < deadline:
        try:
            seen = q.get(timeout=0.2)
        except queue.Empty:
            if seen is not None:
                return seen
    return seen


def wait_names(q, want_names, timeout=12):
    """Wait until a typing snapshot with exactly want_names (set) arrives."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            snap = q.get(timeout=0.3)
        except queue.Empty:
            continue
        if {t["name"] for t in snap} == set(want_names):
            return snap
    return None


def main():
    ian = login("ian@ceol.io")
    sarah = login("sarah.oconnor@example.com")

    qi, hi = queue.Queue(), {}
    threading.Thread(target=reader, args=(ian, qi, hi), daemon=True).start()
    time.sleep(0.8)
    # drain any initial empty typing snapshot
    latest_typing(qi, timeout=1)

    # sarah starts typing -> ian sees her
    sarah.post(f"{STREAM}/live/instances/{INSTANCE}/typing", json={"typing": True, "anchor": None})
    snap = wait_names(qi, {"Sarah"}, timeout=5)
    assert snap, "ian should see Sarah typing"
    print(f"1. sarah types -> ian sees typing: {[t['name'] for t in snap]} ✓")

    # sarah clears (clear-on-commit / blur) -> ian sees empty
    sarah.post(f"{STREAM}/live/instances/{INSTANCE}/typing", json={"typing": False})
    snap = wait_names(qi, set(), timeout=5)
    assert snap is not None, "ian should see Sarah's typing cleared"
    print("2. sarah clears -> ian sees typing empty ✓")

    # inactivity timeout: sarah types and goes silent; service expires it (~10s TTL)
    sarah.post(f"{STREAM}/live/instances/{INSTANCE}/typing", json={"typing": True})
    assert wait_names(qi, {"Sarah"}, timeout=5), "ian should see Sarah typing again"
    t0 = time.time()
    snap = wait_names(qi, set(), timeout=15)  # wait for server-side expiry
    assert snap is not None, "typing should auto-expire after inactivity"
    print(f"3. inactivity timeout -> auto-expired after ~{time.time() - t0:.0f}s ✓")

    hi["r"].close()
    print("\nPHASE 2 TYPING: PASS ✅")


if __name__ == "__main__":
    main()
