#!/usr/bin/env python3
"""
Phase 0 walking-skeleton end-to-end check (spec 024 §K).

Drives the REAL pipeline over HTTP against locally-running services:
  login -> open SSE (a 'second client') -> POST add_tune (referee) ->
  assert the committed tune arrives over SSE within ~1s.

Proves: Svelte-equivalent POST -> referee (one txn: session_instance_tune +
session_event + pg_notify) -> streaming service LISTEN -> SSE fan-out -> client.

Usage: venv/bin/python spike/test_phase0_e2e.py [FLASK_PORT] [STREAM_PORT] [INSTANCE_ID]
"""
import sys, json, time, threading, queue, uuid
from _dbclean import baseline, cleanup
import requests

FLASK = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
STREAM = f"http://localhost:{sys.argv[2] if len(sys.argv) > 2 else 8080}"
INSTANCE = int(sys.argv[3]) if len(sys.argv) > 3 else 1
EMAIL, PASSWORD = "ian@ceol.io", "password123"


def sse_reader(cookies, last_event_id, out_q, stop):
    url = f"{STREAM}/live/instances/{INSTANCE}/events?last_event_id={last_event_id}"
    with requests.get(url, headers={"Accept": "text/event-stream"}, cookies=cookies,
                      stream=True, timeout=30) as r:
        assert r.status_code == 200, f"SSE status {r.status_code}"
        event, data = None, None
        for raw in r.iter_lines(decode_unicode=True):
            if stop.is_set():
                return
            if raw is None:
                continue
            line = raw.strip()
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
            elif line == "":  # dispatch on blank line
                if event and data:
                    out_q.put((event, data))
                event, data = None, None


def main():
    s = requests.Session()

    r = s.post(f"{FLASK}/api/auth/login-password", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:200]}"
    cookies = s.cookies.get_dict()
    print("1. logged in, cookie keys:", list(cookies))

    r = s.get(f"{FLASK}/api/live/instances/{INSTANCE}/bootstrap")
    assert r.status_code == 200 and r.json().get("success"), f"bootstrap failed: {r.text[:200]}"
    boot = r.json()
    hw = boot["last_event_id"]
    print(f"2. bootstrap OK: {len(boot['records'])} records, high-water event_id={hw}")

    # Open the SSE stream as a connected 'second client', from the high-water mark.
    out_q, stop = queue.Queue(), threading.Event()
    t = threading.Thread(target=sse_reader, args=(cookies, hw, out_q, stop), daemon=True)
    t.start()
    time.sleep(1.0)  # let the stream connect + go live
    print("3. SSE client connected")

    # Unauthenticated SSE must be rejected.
    anon = requests.get(f"{STREAM}/live/instances/{INSTANCE}/events", stream=True)
    assert anon.status_code == 401, f"expected 401 for anon SSE, got {anon.status_code}"
    anon.close()
    print("4. anonymous SSE correctly rejected (401)")

    tune_name = f"Phase0 Skeleton Reel {int(time.time())}"
    t0 = time.time()
    r = s.post(f"{FLASK}/api/live/instances/{INSTANCE}/ops",
               json={"op_type": "add_tune", "op_id": str(uuid.uuid4()), "name": tune_name})
    assert r.status_code == 200 and r.json().get("success"), f"add_tune failed: {r.text[:200]}"
    posted = r.json()
    print(f"5. POST add_tune -> event_id={posted['event_id']}, record_id={posted['record']['session_instance_tune_id']}")

    # Assert it arrives over SSE.
    deadline = time.time() + 5
    got = None
    while time.time() < deadline:
        try:
            event, data = out_q.get(timeout=0.2)
        except queue.Empty:
            continue
        payload = json.loads(data)
        if event == "op" and payload.get("op_type") == "add_tune" and payload.get("record", {}).get("name") == tune_name:
            got = payload
            break
    latency = (time.time() - t0) * 1000
    stop.set()

    assert got, "FAIL: add_tune event did not arrive over SSE"
    assert got["record"]["session_instance_tune_id"] == posted["record"]["session_instance_tune_id"]
    print(f"6. SSE delivered the add_tune to the client in {latency:.0f}ms ✓")
    print("\nPHASE 0 WALKING SKELETON: PASS ✅")


if __name__ == "__main__":
    _base = baseline()
    try:
        main()
    finally:
        cleanup(_base)
