#!/usr/bin/env python3
"""
Offline confirm + attribute (set-starter) ops (spec 024 §G, #5a). These were
online-only (graceful notice); now they queue offline like add/remove/change:
optimistic apply -> queued while offline -> flush + persist on reconnect.

Flow: add a tune online (real id, isolated set) -> seed confidence=50 so Confirm
shows -> go OFFLINE -> Confirm (queues) + set a starter (queues) -> go ONLINE ->
both flush -> verify DB has confidence=100 and started_by set. Self-cleaning.

Run: venv/bin/python spike/pw_offline_ops.py [PORT] [INST]
"""
import sys, os, time
from _dbclean import baseline, cleanup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from database import get_db_connection
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def db_one(sql, args=(), tries=6):
    # statement_timeout + retry: a direct UPDATE on a just-added row can briefly wait on
    # the live op's insert lock (single-threaded dev Flask under load). Fail fast + retry
    # instead of hanging the whole test.
    last = None
    for _ in range(tries):
        c = None
        try:
            c = get_db_connection(); cur = c.cursor()
            cur.execute("SET statement_timeout = 3000")
            cur.execute(sql, args)
            row = cur.fetchone() if cur.description else None
            c.commit(); c.close()
            return row
        except Exception as e:
            last = e
            try:
                if c: c.close()
            except Exception:
                pass
            time.sleep(1)
    raise last


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(); pg = ctx.new_page(); pg.set_viewport_size({"width": 460, "height": 880})
        pg.set_default_timeout(10000)  # fail fast instead of the 30s default
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1200)

        # add an isolated tune in a fresh set at the end (real, linked)
        pg.eval_on_selector_all(".end-seam", "els => els[els.length-1].click()")
        pg.eval_on_selector_all(".composer input", "els => els[0].focus()")
        if pg.query_selector(".composer .endset.hot"):
            pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)
        pg.fill(".composer input", "Silver Spear"); pg.wait_for_timeout(700)
        pg.eval_on_selector_all(".results li", "els => els[0] && els[0].click()"); pg.wait_for_timeout(2500)

        rid = db_one(
            "SELECT MAX(session_instance_tune_id) FROM session_instance_tune WHERE session_instance_id=%s AND record_type='tune' AND deleted=FALSE",
            (INST,))[0]
        print(f"0. added record_id={rid}")
        # seed low confidence so the Confirm button appears, then reload to pick it up
        db_one("UPDATE session_instance_tune SET confidence=50 WHERE session_instance_tune_id=%s", (rid,))
        print("0a. seeded confidence; reloading", flush=True)
        pg.reload(); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1200)
        print("0b. reloaded", flush=True)

        # --- go OFFLINE ---
        ctx.set_offline(True); pg.wait_for_timeout(500)
        print("0c. offline", flush=True)

        # select our row (last set) and Confirm it offline
        pg.evaluate("()=>{const ss=document.querySelectorAll('.set');const r=ss[ss.length-1].querySelector('.tune-row');r&&r.click()}")
        pg.wait_for_timeout(200)
        had_confirm = pg.evaluate("()=>{const b=[...document.querySelectorAll('.row-actions button')].find(x=>/confirm/i.test(x.textContent));if(b){b.click();return true}return false}")
        pg.wait_for_timeout(500)
        print(f"1. offline confirm clicked: button_present={had_confirm}")
        if not had_confirm:
            fail.append("Confirm button should be present for the low-confidence row")
        pill = pg.text_content(".status").strip() if pg.query_selector(".status") else ""
        print(f"   pill after offline confirm = {pill!r}")

        # set a starter on the set offline (tray pill -> starter value -> first attendee)
        pg.evaluate("()=>{const ss=document.querySelectorAll('.set');const pillEl=ss[ss.length-1].querySelector('.set-label');pillEl&&pillEl.click()}")
        pg.wait_for_timeout(300)
        pg.eval_on_selector_all(".starter-value", "els => els[els.length-1] && els[els.length-1].click()")
        pg.wait_for_timeout(300)
        picked = pg.evaluate("()=>{const it=[...document.querySelectorAll('.starter-item')].find(x=>!x.classList.contains('clear')&&!x.classList.contains('add-player'));if(it){it.click();return it.textContent.trim()}return null}")
        pg.wait_for_timeout(500)
        print(f"2. offline starter picked: {picked!r}")

        # --- back ONLINE -> flush ---
        ctx.set_offline(False); pg.wait_for_timeout(500)
        pg.evaluate("()=>window.dispatchEvent(new Event('online'))")
        pg.wait_for_timeout(2500)

        conf = db_one("SELECT confidence FROM session_instance_tune WHERE session_instance_tune_id=%s", (rid,))[0]
        starter = db_one("SELECT started_by_person_id FROM session_instance_tune WHERE session_instance_tune_id=%s", (rid,))[0]
        print(f"3. after reconnect: confidence={conf}, started_by_person_id={starter}")
        if conf != 100:
            fail.append(f"offline confirm should persist confidence=100 on flush, got {conf}")
        if picked and starter is None:
            fail.append("offline set-starter should persist started_by_person_id on flush")

        if errs:
            fail.append(f"errors: {errs[:4]}")
        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    base = baseline()
    try:
        main()
    finally:
        cleanup(base)
