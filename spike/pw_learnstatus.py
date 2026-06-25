#!/usr/bin/env python3
"""
Playwright check: learn-status droplist AUTO-SAVES on change (spec 006) from the
live-screen tune-detail drawer — no Save click. Restores the original status so
the run leaves the DB unchanged.
Run: venv/bin/python spike/pw_learnstatus.py [PORT] [INST]
"""
import sys, os
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from database import get_db_connection

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)
TUNE_ID = 517           # "Pigeon On The Gate, The" — on ian's list, in instance 1
TUNE_NAME = "Pigeon On The Gate"
PERSON_ID = 77128       # ian


def db_status():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT learn_status FROM person_tune WHERE person_id=%s AND tune_id=%s", (PERSON_ID, TUNE_ID))
    row = cur.fetchone(); conn.close()
    return row[0] if row else None


def set_status(val):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("UPDATE person_tune SET learn_status=%s WHERE person_id=%s AND tune_id=%s", (val, PERSON_ID, TUNE_ID))
    conn.commit(); conn.close()


def main():
    original = db_status()
    print(f"0. original db learn_status = {original!r}")
    target = "learned" if original != "learned" else "learning"
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 860})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1000)

        # select the Pigeon row and open its Info drawer
        ok = pg.evaluate(
            "(name)=>{ const r=[...document.querySelectorAll('.tune-row')].find(x=>x.querySelector('.name').textContent.trim().toLowerCase().includes(name.toLowerCase())); if(!r) return false; r.click(); return true }",
            TUNE_NAME,
        )
        if not ok:
            print("FAIL ❌ could not find the test tune row"); b.close(); sys.exit(1)
        pg.wait_for_timeout(200)
        pg.eval_on_selector_all(".row-actions button", "els => { const e=els.find(b=>b.textContent.includes('Info')); if(e) e.click() }")
        pg.wait_for_selector("#tune-detail-modal #tunebook-status-select", timeout=6000)
        print("1. drawer open, status droplist present")

        # change the droplist WITHOUT touching any Save button
        before = pg.eval_on_selector("#tunebook-status-select", "e => e.value")
        pg.select_option("#tunebook-status-select", target)
        # wait for the auto-save round-trip: select re-enabled + section recolored
        pg.wait_for_function(
            "t => { const s=document.getElementById('tunebook-status-select'); const sec=document.querySelector('.tunebook-status-section'); return s && !s.disabled && sec && sec.className.includes('tunebook-status-'+t.replace(/ /g,'-')) }",
            arg=target, timeout=5000,
        )
        print(f"2. changed {before!r} -> {target!r}; section recolored")

        # the Save button must NOT be the thing that persisted it — verify DB updated already
        pg.wait_for_timeout(400)
        after_db = db_status()
        print(f"3. db learn_status after change = {after_db!r}")
        if after_db != target:
            fail.append(f"auto-save did not persist: db is {after_db!r}, expected {target!r}")

        # Save button should be disabled (status change shouldn't leave the form dirty)
        save_dirty = pg.evaluate(
            "()=>{ const b=[...document.querySelectorAll('#tune-detail-modal button')].find(x=>x.textContent.trim().toLowerCase().startsWith('save')); return b ? !b.disabled : null }"
        )
        print(f"4. Save button dirty(enabled)? {save_dirty}")
        if save_dirty is True:
            fail.append("Save button is enabled after auto-save — status change should not leave the form dirty")

        if errs:
            fail.append(f"errors: {errs[:4]}")
        b.close()

    # restore
    set_status(original)
    print(f"5. restored db learn_status -> {db_status()!r}")
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    main()
