#!/usr/bin/env python3
"""
Phase 1 tail check (spec 024): corroborate/merge detection (§H30), attendance ops,
and bearer-token issuance round-trip.

Usage: venv/bin/python spike/test_phase1_tail.py [FLASK_PORT] [STREAM_PORT] [INSTANCE_ID]
"""
import sys, json, time, threading, queue, uuid
from _dbclean import baseline, cleanup
import requests
import psycopg2

FLASK = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
STREAM = f"http://localhost:{sys.argv[2] if len(sys.argv) > 2 else 8080}"
INSTANCE = int(sys.argv[3]) if len(sys.argv) > 3 else 1
EMAIL, PASSWORD = "ian@ceol.io", "password123"

s = requests.Session()
events = queue.Queue()
stop = threading.Event()


def sse_reader(cookies, last):
    url = f"{STREAM}/live/instances/{INSTANCE}/events?last_event_id={last}"
    with requests.get(url, cookies=cookies, stream=True, timeout=30) as r:
        assert r.status_code == 200
        ev, data = None, None
        for raw in r.iter_lines(decode_unicode=True):
            if stop.is_set():
                return
            if raw is None:
                continue
            line = raw.strip()
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
            elif line == "":
                if ev == "op" and data:
                    events.put(json.loads(data))
                ev, data = None, None


def wait_for(pred, what, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            e = events.get(timeout=0.2)
        except queue.Empty:
            continue
        if pred(e):
            return e
    raise AssertionError(f"timeout waiting for SSE: {what}")


def op(op_type, **payload):
    body = {"op_type": op_type, "op_id": str(uuid.uuid4()), **payload}
    return s.post(f"{FLASK}/api/live/instances/{INSTANCE}/ops", json=body).json()


def main():
    conn = psycopg2.connect(host="localhost", dbname="ceol_test", user="test_user", password="test_password")
    cur = conn.cursor()
    cur.execute("SELECT tune_id, name FROM tune WHERE redirect_to_tune_id IS NULL AND name IS NOT NULL ORDER BY tune_id LIMIT 1")
    tune_id, tune_name = cur.fetchone()
    cur.execute("SELECT person_id FROM person ORDER BY person_id LIMIT 1")
    person_id = cur.fetchone()[0]
    conn.close()

    assert s.post(f"{FLASK}/api/auth/login-password", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
    cookies = s.cookies.get_dict()
    hw = s.get(f"{FLASK}/api/live/instances/{INSTANCE}/bootstrap").json()["last_event_id"]
    threading.Thread(target=sse_reader, args=(cookies, hw), daemon=True).start()
    time.sleep(1.0)
    print(f"connected; high-water={hw}; tune_id={tune_id}; person_id={person_id}")

    # --- corroborate/merge (§H30): start a fresh set, add same linked tune twice ---
    op("set_break")  # close current set so the open set is empty
    r1 = op("add_tune", tune_id=tune_id)
    first_rid = r1["record"]["session_instance_tune_id"]
    wait_for(lambda x: x["op_type"] == "add_tune" and x["record"]["session_instance_tune_id"] == first_rid, "first add")

    r2 = op("add_tune", tune_id=tune_id)  # duplicate in the open set -> corroborate
    assert r2["op_type"] == "corroborate", f"expected corroborate, got {r2.get('op_type')}: {r2}"
    assert r2["record"]["session_instance_tune_id"] == first_rid, "must credit the earliest row, not a new one"
    assert r2["record"]["confidence"] == 100, "two corroborators -> verified (100)"
    wait_for(lambda x: x["op_type"] == "corroborate" and x["record"]["session_instance_tune_id"] == first_rid, "corroborate event")
    print(f"1. corroborate/merge: duplicate collapsed into record {first_rid}, confidence->100 ✓")

    # --- attendance ops ---
    r = op("attendance_add", person_id=person_id, attendance="yes")
    assert r["success"] and r["person"]["person_id"] == person_id, r
    wait_for(lambda x: x["op_type"] == "attendance_add" and x["person"]["person_id"] == person_id, "attendance_add")
    print(f"2. attendance_add (person {person_id}, action={r['action']}) ✓")

    r = op("attendance_remove", person_id=person_id)
    assert r["success"] and r.get("removed"), r
    wait_for(lambda x: x["op_type"] == "attendance_remove" and x["person"]["person_id"] == person_id, "attendance_remove")
    print("3. attendance_remove ✓")

    uniq = int(time.time())
    r = op("attendance_create_person", first_name="Test", last_name=f"Logger{uniq}", attendance="yes")
    assert r["success"] and r["created"] and r["person"]["person_id"], r
    wait_for(lambda x: x["op_type"] == "attendance_create_person" and x["person"]["person_id"] == r["person"]["person_id"], "create_person")
    print(f"4. attendance_create_person -> person {r['person']['person_id']} ✓")

    # --- bearer-token issuance + acceptance round-trip ---
    tok = s.post(f"{FLASK}/api/live/token").json()
    assert tok["success"] and tok["token_type"] == "Bearer" and tok["token"], tok
    bearer = requests.get(f"{STREAM}/live/instances/{INSTANCE}/events?last_event_id=999999999",
                          headers={"Authorization": f"Bearer {tok['token']}"}, stream=True, timeout=10)
    assert bearer.status_code == 200, f"minted bearer rejected: {bearer.status_code}"
    bearer.close()
    print("5. bearer-token issuance + streaming acceptance round-trip ✓")

    # --- name -> tune matching (Enter resolves text to a tune_id) ---
    op("set_break")  # fresh open set
    r = op("add_tune", name=tune_name)  # by text only, no tune_id
    assert r["record"]["tune_id"] == tune_id, f"typed name '{tune_name}' should link to tune {tune_id}, got {r['record']}"
    wait_for(lambda x: x["op_type"] == "add_tune" and x["record"]["tune_id"] == tune_id, "name-matched add")
    print(f"6. name->tune matching: '{tune_name}' linked to tune {tune_id} ✓")
    # ...and a second identical name in the same set corroborates by the resolved id
    r = op("add_tune", name=tune_name)
    assert r["op_type"] == "corroborate" and r["record"]["tune_id"] == tune_id, r
    print("7. matched-name duplicate corroborates by tune_id ✓")

    # --- raw-name fallback: identical unmatched text collapses too ---
    junk = f"Zzz Nontune {int(time.time())}"
    op("set_break")
    r1 = op("add_tune", name=junk)
    assert r1["record"]["tune_id"] is None, "junk should not match any tune"
    jrid = r1["record"]["session_instance_tune_id"]
    wait_for(lambda x: x["op_type"] == "add_tune" and x["record"]["session_instance_tune_id"] == jrid, "junk add")
    r2 = op("add_tune", name=junk.lower())  # different case -> still merges (normalized)
    assert r2["op_type"] == "corroborate" and r2["record"]["session_instance_tune_id"] == jrid, r2
    print("8. raw-name fallback: identical unmatched text collapses (case-insensitive) ✓")

    stop.set()
    print("\nPHASE 1 TAIL (corroborate + attendance + token + name-match): PASS ✅")


if __name__ == "__main__":
    _base = baseline()
    try:
        main()
    finally:
        cleanup(_base)
