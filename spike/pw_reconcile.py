#!/usr/bin/env python3
"""
Reconnect reconciliation review (#4, spec 024 §G). An offline-originated op the server
REJECTS on flush (e.g. you edited a tune someone else removed) must surface in a review
modal — not vanish as a transient toast.

Flow: online add tune X -> go OFFLINE -> edit X (rename, queued) -> tombstone X in the
DB (simulating another logger removing it) -> go ONLINE -> flush -> change_tune is
rejected (target_deleted) -> the .reconcile modal appears listing the dropped edit.
Self-cleaning.

Run: venv/bin/python spike/pw_reconcile.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from database import get_db_connection

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def db_exec(sql, args=(), tries=6):
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
    from playwright.sync_api import sync_playwright
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 880}); pg.set_default_timeout(10000)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1200)

        # add tune X (online, real id) in a fresh set
        pg.eval_on_selector_all(".end-seam", "els => els[els.length-1].click()")
        pg.eval_on_selector_all(".composer input", "els => els[0].focus()")
        if pg.query_selector(".composer .endset.hot"):
            pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)
        pg.fill(".composer input", "Silver Spear"); pg.wait_for_timeout(800)
        pg.eval_on_selector_all(".results li", "els => { const r=els.find(e=>e.querySelector('.r-name') && !e.classList.contains('result-deeper')); r && r.click() }")
        pg.wait_for_timeout(2500)
        rid = db_exec("SELECT MAX(session_instance_tune_id) FROM session_instance_tune WHERE session_instance_id=%s AND record_type='tune' AND deleted=FALSE", (INST,))[0]
        print(f"0. added X = record {rid}", flush=True)

        # OFFLINE -> edit X (rename) -> queued
        ctx.set_offline(True); pg.wait_for_timeout(500)
        pg.evaluate("()=>{const ss=document.querySelectorAll('.set');const r=ss[ss.length-1].querySelector('.tune-row');r&&r.click()}")
        pg.wait_for_timeout(150)
        pg.eval_on_selector_all(".row-actions button", "els => { const e=els.find(x=>/edit/i.test(x.textContent)); e && e.click() }")
        pg.wait_for_timeout(200)
        pg.fill(".composer input", "ZZ Renamed Offline"); pg.press(".composer input", "Enter"); pg.wait_for_timeout(500)
        print("1. offline edit queued", flush=True)

        # someone else removes X while we're offline (tombstone in DB)
        db_exec("UPDATE session_instance_tune SET deleted=TRUE WHERE session_instance_tune_id=%s", (rid,))
        print("2. X tombstoned server-side", flush=True)

        # ONLINE -> flush -> change_tune rejected -> reconcile modal
        ctx.set_offline(False); pg.wait_for_timeout(400)
        pg.evaluate("()=>window.dispatchEvent(new Event('online'))")
        pg.wait_for_timeout(3000)

        has_modal = pg.query_selector(".reconcile") is not None
        body = pg.text_content(".reconcile") if has_modal else ""
        print(f"3. reconcile modal shown={has_modal}; body~={(body or '').strip()[:120]!r}", flush=True)
        if not has_modal:
            fail.append("reconcile modal should appear when an offline op is rejected on flush")
        elif "Edit" not in body:
            fail.append(f"reconcile modal should describe the dropped Edit; got {body!r}")

        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    base = baseline()
    try:
        main()
    finally:
        cleanup(base)
