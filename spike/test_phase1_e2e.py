#!/usr/bin/env python3
"""
Phase 1 end-to-end check (spec 024 §C/§E): full op vocabulary, op_id idempotency,
and rejection, each verified to flow over SSE.

Usage: venv/bin/python spike/test_phase1_e2e.py [FLASK_PORT] [STREAM_PORT] [INSTANCE_ID]
"""
import sys, json, time, threading, queue, uuid
from _dbclean import baseline, cleanup
import requests

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


def op(op_type, op_id=None, **payload):
    body = {"op_type": op_type, "op_id": op_id or str(uuid.uuid4()), **payload}
    r = s.post(f"{FLASK}/api/live/instances/{INSTANCE}/ops", json=body)
    assert r.status_code in (200, 400, 404), f"{op_type} -> {r.status_code}: {r.text[:200]}"
    return r.json(), body["op_id"]


def main():
    assert s.post(f"{FLASK}/api/auth/login-password", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
    cookies = s.cookies.get_dict()
    hw = s.get(f"{FLASK}/api/live/instances/{INSTANCE}/bootstrap").json()["last_event_id"]
    threading.Thread(target=sse_reader, args=(cookies, hw), daemon=True).start()
    time.sleep(1.0)
    print(f"connected; high-water={hw}")

    tag = int(time.time())

    # add_tune
    res, _ = op("add_tune", name=f"Maid Behind the Bar {tag}")
    rid = res["record"]["session_instance_tune_id"]
    e = wait_for(lambda x: x["op_type"] == "add_tune" and x["record"]["session_instance_tune_id"] == rid, "add_tune")
    add_event_id = e["event_id"]
    print(f"1. add_tune -> record {rid}, event {add_event_id} ✓")

    # idempotency: resend the SAME op_id -> dedup, same event, no new SSE
    dup_op_id = str(uuid.uuid4())
    r1, _ = op("add_tune", op_id=dup_op_id, name=f"Dup Reel {tag}")
    dup_rid, dup_eid = r1["record"]["session_instance_tune_id"], r1["event_id"]
    wait_for(lambda x: x["event_id"] == dup_eid, "first dup event")
    r2, _ = op("add_tune", op_id=dup_op_id, name=f"Dup Reel {tag}")
    assert r2.get("duplicate") and r2["event_id"] == dup_eid, f"expected dedup, got {r2}"
    # ensure no second event with a new id for that name arrives
    time.sleep(0.5)
    extra = [x for x in list(events.queue) if x.get("record", {}).get("name") == f"Dup Reel {tag}"]
    assert not extra, "duplicate op produced a second SSE event"
    print(f"2. op_id idempotency: resend deduped to event {dup_eid}, no new record ✓")

    # change_tune (rename)
    newname = f"The Maid Behind the Bar {tag}"
    op("change_tune", record_id=rid, name=newname)
    wait_for(lambda x: x["op_type"] == "change_tune" and x["record"]["name"] == newname, "change_tune")
    print("3. change_tune (rename) ✓")

    # set_confidence: add a low-confidence (audio-like) tune, then confirm to 100
    res, _ = op("add_tune", name=f"Audio Guess {tag}", source="audio", confidence=55)
    arid = res["record"]["session_instance_tune_id"]
    assert res["record"]["confidence"] == 55
    op("set_confidence", record_id=arid, confidence=100)
    wait_for(lambda x: x["op_type"] == "set_confidence" and x["record"]["session_instance_tune_id"] == arid and x["record"]["confidence"] == 100, "set_confidence")
    print("4. set_confidence (55 -> 100, corroboration recorded) ✓")

    # set_break (insert)
    res, _ = op("set_break", action="insert", after_record_id=rid)
    brid = res["record"]["session_instance_tune_id"]
    e = wait_for(lambda x: x["op_type"] == "set_break" and x.get("record", {}).get("session_instance_tune_id") == brid, "set_break")
    assert e["record"]["record_type"] == "break"
    print(f"5. set_break (insert break {brid}) ✓")

    # remove_tune (soft tombstone)
    op("remove_tune", record_id=rid)
    wait_for(lambda x: x["op_type"] == "remove_tune" and x["record"]["session_instance_tune_id"] == rid and x["record"]["deleted"], "remove_tune")
    print("6. remove_tune (tombstone) ✓")

    # rejection: edit a removed record -> rejected target_deleted, no SSE event
    before = s.get(f"{FLASK}/api/live/instances/{INSTANCE}/bootstrap").json()["last_event_id"]
    r, _ = op("change_tune", record_id=rid, name="zombie")
    assert r.get("rejected") and r["reason"] == "target_deleted", f"expected rejection, got {r}"
    time.sleep(0.4)
    after = s.get(f"{FLASK}/api/live/instances/{INSTANCE}/bootstrap").json()["last_event_id"]
    assert before == after, "rejected op must not append an event"
    print("7. removal-beats-edit: change on tombstoned row rejected, no event ✓")

    stop.set()
    print("\nPHASE 1 OP VOCABULARY + IDEMPOTENCY + REJECTION: PASS ✅")


if __name__ == "__main__":
    _base = baseline()
    try:
        main()
    finally:
        cleanup(_base)
