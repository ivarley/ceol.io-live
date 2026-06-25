#!/usr/bin/env python3
"""
Playwright: ambiguous-Enter gate (021-style matching, not in 024). Typing a fragment
that matches several tunes with no unique exact match must NOT auto-link; it enters a
local "red" state (no row logged). A 2nd Enter logs it as typed (unlinked). A unique
match links immediately; no-match logs unlinked immediately. Self-cleaning.
Run: venv/bin/python spike/pw_ambig.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def rows(pg):
    return pg.eval_on_selector_all(".tune-row .name", "e => e.map(x => x.textContent.trim())")


def last_set_names(pg):
    return pg.evaluate("()=>{const ss=document.querySelectorAll('.set');if(!ss.length)return[];return[...ss[ss.length-1].querySelectorAll('.tune-row .name')].map(x=>x.textContent.trim())}")


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 880})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1000)

        # fresh open set at the end so added rows are isolated
        pg.eval_on_selector_all(".end-seam", "els => els[els.length-1].click()")
        pg.eval_on_selector_all(".composer input", "els => els[0].focus()")
        if pg.query_selector(".composer .endset.hot"):
            pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)

        n0 = len(rows(pg))

        # --- A) ambiguous fragment -> GATE (no row, red state) ---
        pg.fill(".composer input", "Humours"); pg.wait_for_timeout(700)
        pg.press(".composer input", "Enter"); pg.wait_for_timeout(600)
        amb = pg.query_selector(".composer input.ambiguous") is not None
        hint = pg.query_selector(".ambig-hint") is not None
        added = len(rows(pg)) - n0
        print(f"A. after ambiguous Enter: red={amb}, hint={hint}, rows_added={added}")
        if not amb: fail.append("ambiguous Enter should put the input in the red state")
        if not hint: fail.append("ambiguous Enter should show the .ambig-hint")
        if added != 0: fail.append(f"ambiguous Enter must NOT log a row (added {added})")

        # --- B) 2nd Enter -> log as typed (unlinked) ---
        pg.press(".composer input", "Enter"); pg.wait_for_timeout(900)
        ls = last_set_names(pg)
        print(f"B. after 2nd Enter, last set tail={ls[-1:] if ls else ls}")
        if not ls or ls[-1] != "Humours":
            fail.append(f"2nd Enter should log 'Humours' as typed; last set tail={ls[-1:] if ls else ls}")
        # and it should be unlinked (dashed amber + badge)
        unl = pg.evaluate("()=>{const r=[...document.querySelectorAll('.tune-row')].find(x=>x.querySelector('.name').textContent.trim()==='Humours');return r?r.classList.contains('unlinked'):null}")
        print(f"   logged-as-typed row unlinked? {unl}")
        if unl is not True: fail.append("the logged-as-typed 'Humours' row should be .unlinked")

        # --- C) unique exact name -> links immediately, no gate ---
        pg.fill(".composer input", "Out On The Ocean"); pg.wait_for_timeout(700)
        pg.press(".composer input", "Enter"); pg.wait_for_timeout(900)
        amb2 = pg.query_selector(".composer input.ambiguous") is not None
        linked = pg.evaluate("()=>{const r=[...document.querySelectorAll('.tune-row')].find(x=>/out on the ocean/i.test(x.querySelector('.name').textContent));return r?!r.classList.contains('unlinked'):null}")
        print(f"C. unique-exact 'Out On The Ocean': gated={amb2}, linked(not-unlinked)={linked}")
        if amb2: fail.append("a unique exact match should NOT gate")
        if linked is not True: fail.append("a unique exact match should link (not unlinked)")

        # --- D) no match -> unlinked immediately, no gate ---
        raw = f"ZZQQ Nomatch {int(time.time())}"
        pg.fill(".composer input", raw); pg.wait_for_timeout(700)
        pg.press(".composer input", "Enter"); pg.wait_for_timeout(900)
        amb3 = pg.query_selector(".composer input.ambiguous") is not None
        present = raw in rows(pg)
        print(f"D. no-match {raw!r}: gated={amb3}, logged={present}")
        if amb3: fail.append("a no-match should NOT gate")
        if not present: fail.append("a no-match should log unlinked immediately")

        if errs: fail.append(f"errors: {errs[:3]}")
        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    base = baseline()
    try:
        main()
    finally:
        cleanup(base)
