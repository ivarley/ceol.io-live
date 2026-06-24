#!/usr/bin/env python3
"""
Playwright check: attendance editor (spec 024 §F) — header list + Manage drawer,
search/check-in, check-out, create-person. Cleans up the attendance + person rows
it creates (the standard _dbclean only covers tunes).
Run: venv/bin/python spike/pw_attendance.py [PORT] [INST]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from database import get_db_connection
from _dbclean import baseline as sit_baseline, cleanup as sit_cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def people_baseline():
    c = get_db_connection(); cur = c.cursor()
    cur.execute("SELECT COALESCE(MAX(person_id),0) FROM person"); p = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(MAX(session_instance_person_id),0) FROM session_instance_person"); s = cur.fetchone()[0]
    c.close(); return p, s


def people_cleanup(bp, bs):
    c = get_db_connection(); cur = c.cursor()
    cur.execute("DELETE FROM session_instance_person WHERE session_instance_person_id > %s", (bs,))
    cur.execute("DELETE FROM person_instrument WHERE person_id > %s", (bp,))
    cur.execute("DELETE FROM person WHERE person_id > %s", (bp,))
    c.commit(); c.close()


def att_list(pg):
    return pg.eval_on_selector_all(".att-list .att-name", "e=>e.map(x=>x.textContent.trim())")


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1200)

        # open via the header: expand, then Manage
        pg.click(".topbar-row"); pg.wait_for_timeout(300)
        if not pg.query_selector(".header-attend"): fail.append("expanded header should show an attendance line")
        pg.click(".ha-manage"); pg.wait_for_selector(".drawer .att-list", timeout=4000); pg.wait_for_timeout(400)
        before = att_list(pg)
        print(f"1. editor open, checked-in={len(before)}")

        # search + check in a non-attending person — tap the whole result row (no Add button)
        pg.fill(".att-search", "an"); pg.wait_for_timeout(600)
        # an already-attending result must be disabled (dimmed, not pickable)
        bad = pg.eval_on_selector_all(".att-result", "els=>els.some(e=>e.querySelector('.att-in') && !e.disabled)")
        if bad: fail.append("already-attending results should be disabled (not pickable)")
        added = pg.evaluate("""()=>{ const btn=[...document.querySelectorAll('.att-result')].find(x=>!x.disabled);
            if(!btn) return null; const n=btn.querySelector('.att-name').textContent.trim(); btn.click(); return n }""")
        pg.wait_for_timeout(1100)
        print(f"2. tapped-to-add {added!r}; list now {len(att_list(pg))}")
        if not added: fail.append("search should surface a tappable non-attending person")
        elif added not in att_list(pg): fail.append(f"{added!r} should appear in checked-in list after tap")

        # create a new person
        ts = int(time.time())
        fn, ln = "Zzatt", f"Tester{ts}"
        pg.click(".att-create-toggle"); pg.wait_for_selector(".att-create input", timeout=3000)
        inputs = pg.query_selector_all(".att-create input")
        inputs[0].fill(fn); inputs[1].fill(ln)
        pg.click(".att-create .att-add"); pg.wait_for_timeout(1200)
        created_name = f"{fn} {ln[0]}"
        print(f"3. created {created_name!r}; list now {att_list(pg)[-3:]}")
        if not any(created_name in n for n in att_list(pg)): fail.append(f"created person {created_name!r} should be checked in; list={att_list(pg)}")

        # check out the existing person we added (restore prior state); created person
        # is removed by DB cleanup
        if added:
            ok = pg.evaluate("""(name)=>{ const li=[...document.querySelectorAll('.att-list li')].find(x=>x.querySelector('.att-name').textContent.trim()===name);
                if(!li) return false; li.querySelector('.att-x').click(); return true }""", added)
            pg.wait_for_timeout(1100)
            print(f"4. checked out {added!r}; present={added in att_list(pg)}")
            if added in att_list(pg): fail.append(f"{added!r} should be gone after check-out")

        if errs: fail.append(f"errors: {errs[:4]}")
        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    sb = sit_baseline(); bp, bs = people_baseline()
    try:
        main()
    finally:
        people_cleanup(bp, bs); sit_cleanup(sb)
