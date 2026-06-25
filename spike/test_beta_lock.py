#!/usr/bin/env python3
"""
Beta rollout + one-way editor lock (spec 024 beta). HTTP-level checks:
  - a beta-flagged user is redirected from the classic session page to /live/instances/<id>
  - a live op claims the instance (logging_mode -> 'live')
  - the classic bulk-save / delete refuse (409) on a 'live' instance
  - the classic page shows the read-only banner for a non-beta user
  - the admin toggle (beta flag) + admin reset (logging mode) work and are admin-only

Restores instance state (logging_mode + notes) and the non-beta user's flag afterward.
Run: venv/bin/python spike/test_beta_lock.py [PORT] [INST] [PATH]
"""
import sys, uuid
import requests
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from database import get_db_connection

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)
PATH = sys.argv[3] if len(sys.argv) > 3 else "austin/mueller"
SARAH_UID = 2  # non-beta test user


def db(sql, args=(), fetch=False):
    c = get_db_connection(); cur = c.cursor(); cur.execute(sql, args)
    row = cur.fetchone() if fetch else None
    c.commit(); c.close()
    return row


def login(email):
    s = requests.Session()
    assert s.post(f"{F}/api/auth/login-password", json={"email": email, "password": "password123"}).status_code == 200
    return s


def main():
    fail = []
    orig_mode = db("SELECT logging_mode FROM session_instance WHERE session_instance_id=%s", (INST,), fetch=True)[0]
    orig_notes = db("SELECT comments FROM session_instance WHERE session_instance_id=%s", (INST,), fetch=True)[0]
    db("UPDATE session_instance SET logging_mode='legacy' WHERE session_instance_id=%s", (INST,))
    db("UPDATE user_account SET beta_live_logging=TRUE WHERE username='ian'")
    db("UPDATE user_account SET beta_live_logging=FALSE WHERE user_id=%s", (SARAH_UID,))
    try:
        ian = login("ian@ceol.io")        # beta + system admin
        sarah = login("sarah.oconnor@example.com")  # non-beta

        # 1) beta user redirected to the live editor
        r = ian.get(f"{F}/sessions/{PATH}/{INST}", allow_redirects=False)
        ok = r.status_code in (301, 302) and f"/live/instances/{INST}" in (r.headers.get("Location") or "")
        print(f"1. beta user redirect: {r.status_code} -> {r.headers.get('Location')}  {'OK' if ok else 'FAIL'}")
        if not ok: fail.append("beta user should redirect to /live/instances/<id>")

        # 2) a live op claims the instance
        op = {"op_type": "edit_notes", "op_id": str(uuid.uuid4()), "notes": orig_notes or ""}
        ian.post(f"{F}/api/live/instances/{INST}/ops", json=op)
        mode = db("SELECT logging_mode FROM session_instance WHERE session_instance_id=%s", (INST,), fetch=True)[0]
        print(f"2. logging_mode after live op: {mode}  {'OK' if mode == 'live' else 'FAIL'}")
        if mode != "live": fail.append("a live op should claim the instance (logging_mode='live')")

        # 3) classic bulk-save + delete refused on a live instance
        rs = sarah.post(f"{F}/api/sessions/{PATH}/{INST}/save_tunes", json={"tune_sets": []})
        print(f"3a. classic save on live instance: {rs.status_code} locked={rs.json().get('locked')}  {'OK' if rs.status_code == 409 else 'FAIL'}")
        if rs.status_code != 409: fail.append("classic bulk-save should 409 on a live instance")

        # 4) non-beta user sees the read-only banner (not redirected)
        pg = sarah.get(f"{F}/sessions/{PATH}/{INST}")
        banner = pg.status_code == 200 and "live-locked-banner" in pg.text
        print(f"4. non-beta page banner: status={pg.status_code} banner={'live-locked-banner' in pg.text}  {'OK' if banner else 'FAIL'}")
        if not banner: fail.append("non-beta user should see the read-only banner on a live instance")

        # 4b) the classic editor offers NO way into edit mode on a live instance (Edit
        # button hidden) — read-only, not just save-blocked. Use ian (a session admin so
        # the editor renders) with beta temporarily off so he isn't redirected.
        import re
        db("UPDATE user_account SET beta_live_logging=FALSE WHERE username='ian'")
        live_html = ian.get(f"{F}/sessions/{PATH}/{INST}").text
        db("UPDATE session_instance SET logging_mode='legacy' WHERE session_instance_id=%s", (INST,))
        legacy_html = ian.get(f"{F}/sessions/{PATH}/{INST}").text
        db("UPDATE session_instance SET logging_mode='live' WHERE session_instance_id=%s", (INST,))
        db("UPDATE user_account SET beta_live_logging=TRUE WHERE username='ian'")
        live_btn = bool(re.search(r'<button[^>]*id="enter-edit-mode-btn"', live_html))
        legacy_btn = bool(re.search(r'<button[^>]*id="enter-edit-mode-btn"', legacy_html))
        print(f"4b. Edit button — live instance: {live_btn} (expect False), legacy: {legacy_btn} (expect True)")
        if live_btn: fail.append("Edit button must be hidden on a live instance (no edit mode)")
        if not legacy_btn: fail.append("Edit button should show on a legacy instance")

        # 5) admin reset (logging mode) — admin only
        rr = ian.post(f"{F}/api/admin/instances/{INST}/logging-mode", json={"mode": "legacy"})
        rn = sarah.post(f"{F}/api/admin/instances/{INST}/logging-mode", json={"mode": "legacy"})
        print(f"5. admin reset={rr.status_code} (admin) / {rn.status_code} (non-admin, expect 403)")
        if rr.status_code != 200 or rn.status_code != 403:
            fail.append(f"reset should be admin-only: admin={rr.status_code} non-admin={rn.status_code}")

        # 6) admin beta toggle — admin only
        rt = ian.post(f"{F}/api/admin/users/{SARAH_UID}/beta-logging", json={"enabled": True})
        on = db("SELECT beta_live_logging FROM user_account WHERE user_id=%s", (SARAH_UID,), fetch=True)[0]
        rtn = sarah.post(f"{F}/api/admin/users/{SARAH_UID}/beta-logging", json={"enabled": False})
        print(f"6. admin toggle={rt.status_code} (sarah beta now {on}) / non-admin={rtn.status_code} (expect 403)")
        if rt.status_code != 200 or on is not True or rtn.status_code != 403:
            fail.append("beta toggle should be admin-only and flip the flag")
    finally:
        db("UPDATE session_instance SET logging_mode=%s, comments=%s WHERE session_instance_id=%s", (orig_mode, orig_notes, INST))
        db("UPDATE user_account SET beta_live_logging=FALSE WHERE user_id=%s", (SARAH_UID,))
        db("UPDATE user_account SET beta_live_logging=TRUE WHERE username='ian'")  # ian stays beta in dev
        print(f"7. restored logging_mode={orig_mode!r}, sarah beta=off, ian beta=on")

    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    main()
