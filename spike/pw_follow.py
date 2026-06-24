#!/usr/bin/env python3
"""
Playwright check: live-logging cursor follow-the-end (§E). When my cursor is parked
right after the last tune of the open set and someone else appends a tune, my cursor
moves to the END so my next tune lands AFTER theirs (not between).
Run: venv/bin/python spike/pw_follow.py [PORT] [INST]
"""
import sys, os, time, json, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def set_names(pg, name):
    return pg.evaluate("""(name)=>{ for(const s of document.querySelectorAll('.set')){ const ns=[...s.querySelectorAll('.tune-row .name')].map(x=>x.textContent.trim()); if(ns.includes(name)) return ns } return null }""", name)


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        a = b.new_context(); pg = a.new_page(); pg.set_viewport_size({"width": 460, "height": 900})
        a.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".status-live", timeout=8000); pg.wait_for_timeout(800)

        # isolate a fresh open set with tune A at the very end
        pg.eval_on_selector_all(".end-seam", "els => els[els.length-1].click()"); pg.wait_for_timeout(200)
        if pg.query_selector(".composer .endset.hot"):
            pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)
        t = int(time.time())
        A, B, C = f"AAA {t}", f"BBB {t}", f"CCC {t}"
        pg.fill(".composer input", A); pg.press(".composer input", "Enter"); pg.wait_for_timeout(1200)

        # park my cursor right after A (the last tune): select it, "↓ After"
        pg.evaluate("""(name)=>{ const r=[...document.querySelectorAll('.tune-row')].find(x=>x.querySelector('.name').textContent.trim()===name); r && r.click() }""", A)
        pg.wait_for_timeout(200)
        pg.eval_on_selector_all(".row-actions button", "els=>{const e=els.find(b=>b.textContent.includes('After')); if(e)e.click()}")
        pg.wait_for_timeout(300)

        # sarah appends B at the end (separate context)
        sb = b.new_context(); sb.request.post(f"{F}/api/auth/login-password", data={"email": "sarah.oconnor@example.com", "password": "password123"})
        sb.request.post(f"{F}/api/live/instances/{INST}/ops", data=json.dumps({"op_type": "add_tune", "op_id": str(uuid.uuid4()), "name": B}), headers={"Content-Type": "application/json"})
        # wait for B to arrive via SSE
        pg.wait_for_function("(b)=>[...document.querySelectorAll('.tune-row .name')].some(e=>e.textContent.trim()===b)", arg=B, timeout=6000)
        pg.wait_for_timeout(400)
        print("after B arrives:", set_names(pg, A))

        # now I log C — with the fix it should land AFTER B (at the end)
        pg.fill(".composer input", C); pg.press(".composer input", "Enter"); pg.wait_for_timeout(1300)
        names = set_names(pg, A)
        print("final set order:", names)
        # expect A, B, C in order (C last)
        try:
            iA, iB, iC = names.index(A), names.index(B), names.index(C)
            if not (iA < iB < iC):
                fail.append(f"expected order A<B<C (C after B); got {names}")
        except (ValueError, AttributeError, TypeError):
            fail.append(f"missing tunes in set: {names}")
        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    _base = baseline()
    try:
        main()
    finally:
        cleanup(_base)
