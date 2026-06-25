#!/usr/bin/env python3
"""
Offline mid-set insert id remap (#5b). A chained offline insert where the 2nd insert
is anchored to a tune that itself was added offline (a still-temp record): its op
carries after_record_id="temp-...". On flush the temp anchor must be remapped to the
real id, or the server 500s ("invalid input syntax for integer temp-...") and the row
is dropped. Verifies all three tunes survive, in order, with no temp-id error.

Run: venv/bin/python spike/pw_offline_insert.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def last_set(pg):
    return pg.evaluate("()=>{const ss=document.querySelectorAll('.set');if(!ss.length)return[];return[...ss[ss.length-1].querySelectorAll('.tune-row .name')].map(x=>x.textContent.trim())}")


def add(pg, q):
    pg.fill(".composer input", q); pg.wait_for_timeout(700)
    # tap a REAL result (has .r-name, not the empty/deeper rows); else Enter to log as typed
    picked = pg.eval_on_selector_all(
        ".results li",
        "els => { const r=els.find(e=>e.querySelector('.r-name') && !e.classList.contains('result-deeper') && !e.classList.contains('result-empty')); if(r){r.click(); return true} return false }",
    )
    if not picked:
        pg.press(".composer input", "Enter")
    pg.wait_for_timeout(700)


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 880})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1200)

        # fresh set + tune A (online, real id)
        pg.eval_on_selector_all(".end-seam", "els => els[els.length-1].click()")
        pg.eval_on_selector_all(".composer input", "els => els[0].focus()")
        if pg.query_selector(".composer .endset.hot"):
            pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)
        add(pg, "Silver Spear")
        ls = last_set(pg)
        a = ls[-1] if ls else None
        print(f"0. online tune A = {a!r}; last set = {ls}")

        # cursor after A (mid-list insertion point), then go OFFLINE
        pg.evaluate("()=>{const ss=document.querySelectorAll('.set');const r=ss[ss.length-1].querySelector('.tune-row');r&&r.click()}")
        pg.wait_for_timeout(150)
        pg.eval_on_selector_all(".row-actions button", "els => { const e=els.find(x=>/after/i.test(x.textContent)); e && e.click() }")
        pg.wait_for_timeout(200)
        ctx.set_offline(True); pg.wait_for_timeout(400)

        # B anchored to real A; C anchored to TEMP B
        add(pg, "Banshee")
        add(pg, "Cooley")
        offline_set = last_set(pg)
        print(f"1. offline last set (optimistic) = {offline_set}")

        # back ONLINE -> flush
        ctx.set_offline(False); pg.wait_for_timeout(400)
        pg.evaluate("()=>window.dispatchEvent(new Event('online'))")
        pg.wait_for_timeout(3000)

        final = last_set(pg)
        print(f"2. after flush, last set = {final}")
        if len(final) != 3:
            fail.append(f"expected 3 tunes in the set after flush, got {len(final)}: {final}")
        # order: A first, and all three present (C must survive the temp-anchor remap)
        if final and final[0] != a:
            fail.append(f"first tune should still be {a!r}, got {final[0]!r}")
        temp_errs = [e for e in errs if "temp-" in e or "invalid input syntax" in e]
        if temp_errs:
            fail.append(f"temp-id error on flush (remap failed): {temp_errs[:2]}")
        if errs:
            print(f"   console/page errors: {errs[:4]}")

        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    base = baseline()
    try:
        main()
    finally:
        cleanup(base)
