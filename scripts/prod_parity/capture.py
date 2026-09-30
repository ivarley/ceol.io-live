"""Read-only sample of production, signed out: the sessions list, each session's
nights, and the logs of 40 nights (the 8 biggest, and 32 at random). Paced, GETs only,
nothing written to the server; people fields are already stripped for signed-out reads.

    ./venv/bin/python scripts/prod_parity/capture.py /tmp/ceol-prod
    node scripts/prod_parity/web_summary.mjs /tmp/ceol-prod
    cd ios/CeolKit && CEOL_PROD_SAMPLES=/tmp/ceol-prod swift test --filter Production

(or `make prod-parity`). The Swift tests decode every file with the generated API types
and check each night orders and splits exactly as the web's logstate.js does."""
import json, os, random, sys, time
import requests

OUT = sys.argv[1]
BASE = "https://ceol.io"
H = {"X-Ceol-Client": "ios/0.0.0 (parity-check)", "Accept": "application/json"}
os.makedirs(OUT, exist_ok=True)
s = requests.Session()

def get(path):
    time.sleep(0.25)
    r = s.get(BASE + path, headers=H, timeout=20)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else None)

def save(name, body):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(body, f)

code, sessions = get("/api/sessions/with-today-status")
save("sessions.json", sessions)
nights = []
for sess in sessions["sessions"]:
    code, logs = get(f"/api/sessions/{sess['path']}/logs")
    if code != 200 or not logs:
        continue
    save(f"logs_{sess['path'].replace('/', '_')}.json", logs)
    for year, items in (logs.get("instances_by_year") or {}).items():
        for it in items:
            nights.append((sess["path"], it))
print("sessions", len(sessions["sessions"]), "nights", len(nights))
random.seed(7)
logged = [n for n in nights if (n[1].get("tune_count") or 0) > 0]
print("nights with tunes", len(logged))
# The biggest few, and a spread of the rest.
logged.sort(key=lambda n: -(n[1].get("tune_count") or 0))
sample = logged[:8] + random.sample(logged[8:], min(32, max(0, len(logged) - 8)))
got = 0
for path, it in sample:
    iid = it["session_instance_id"]
    code, b = get(f"/api/live/instances/{iid}/bootstrap")
    if code == 200 and b:
        save(f"night_{iid}.json", b)
        got += 1
    else:
        print("skip", iid, code)
print("nights saved", got)
