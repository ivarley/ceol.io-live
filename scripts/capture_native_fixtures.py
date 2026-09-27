"""Capture real API responses for the iOS package's decoding tests (spec 052 §D).

For every GET the contract test checks (tests/contract/test_native_surface.py
CHECKED_GETS) whose 200 response has a named schema, call it against the seeded
local database as the native app would (X-Ceol-Client + a Bearer token from the
native login), and write the body to

    ios/CeolKit/Tests/CeolAPITests/Fixtures/<SchemaName>.json

CeolAPITests decodes each file into the generated Components.Schemas.<SchemaName>.
The contract test proves the server matches the spec; this proves the Swift the spec
generates can read what the server actually sends. Re-run after a change to the
spec or to a payload (`make ios-fixtures`); the files are committed.

One night of a seeded session is marked active for the capture, so the
active_instances arrays hold an item rather than validating vacuously.
"""

import json
import logging
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests", "contract"))

OUT = os.path.join(ROOT, "ios", "CeolKit", "Tests", "CeolAPITests", "Fixtures")
HEADERS = {"X-Ceol-Client": "ios/0.0.0 (fixture-capture)"}


def main():
    logging.disable(logging.CRITICAL)
    from app import app
    from database import get_db_connection
    from test_native_surface import CHECKED_GETS, SPEC_PATH

    with open(SPEC_PATH) as f:
        spec = yaml.safe_load(f)

    client = app.test_client()
    r = client.post(
        "/api/auth/login-password",
        json={"email": "ian@ceol.io", "password": "password123"},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.get_json()
    headers = {**HEADERS, "Authorization": f"Bearer {r.get_json()['token']}"}

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT si.session_instance_id, si.is_active
        FROM session_instance si JOIN session s ON s.session_id = si.session_id
        WHERE s.path = 'austin/mueller' ORDER BY si.date DESC LIMIT 1
        """
    )
    siid, was_active = cur.fetchone()
    cur.execute("UPDATE session_instance SET is_active = TRUE WHERE session_instance_id = %s", (siid,))
    conn.commit()
    try:
        os.makedirs(OUT, exist_ok=True)
        written = []
        for template, url in CHECKED_GETS:
            ref = (
                spec["paths"][template]["get"]
                .get("responses", {})
                .get("200", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
                .get("$ref")
            )
            if not ref:
                continue
            name = ref.rsplit("/", 1)[-1]
            resp = client.get(url, headers=headers)
            assert resp.status_code == 200, (url, resp.get_json())
            with open(os.path.join(OUT, f"{name}.json"), "w") as f:
                json.dump(resp.get_json(), f, indent=2, sort_keys=True, ensure_ascii=False)
                f.write("\n")
            written.append(name)
    finally:
        cur.execute("UPDATE session_instance SET is_active = %s WHERE session_instance_id = %s", (was_active, siid))
        conn.commit()
        conn.close()

    print(f"Wrote {len(written)} fixtures to {os.path.relpath(OUT, ROOT)}: {', '.join(sorted(written))}")


if __name__ == "__main__":
    main()
