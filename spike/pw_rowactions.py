#!/usr/bin/env python3
"""
Playwright check: tune-row selection + action bar (Before/After/Remove) and the
info drawer (spec 021 §E/§18). Run: venv/bin/python spike/pw_rowactions.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 780})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1000)

        # 1. tap a row -> selected + action bar
        pg.eval_on_selector_all(".tune-row:not(.pending):not(.removing)", "els => els[0].click()")
        pg.wait_for_timeout(200)
        selected = pg.query_selector(".tune-row.selected") is not None
        actions = pg.eval_on_selector_all(".row-actions button", "e => e.map(x => x.textContent.trim())")
        print(f"1. select -> selected={selected}, actions={actions}")
        if not selected: fail.append("row did not become selected")
        if not any("After" in a for a in actions): fail.append("no After action")
        if not any("Remove" in a for a in actions): fail.append("no Remove action")

        # 2. '↓ After' moves the cursor off the end
        end_active_before = pg.eval_on_selector(".end-seam", "e => e.classList.contains('active')")
        pg.eval_on_selector_all(".row-actions button", "els => els.find(b => b.textContent.includes('After')).click()")
        pg.wait_for_timeout(200)
        end_active_after = pg.eval_on_selector(".end-seam", "e => e.classList.contains('active')")
        seam_active = pg.query_selector(".seam.active:not(.end-seam)") is not None
        print(f"2. After -> end_active {end_active_before}->{end_active_after}, mid-seam active={seam_active}")
        if not seam_active: fail.append("After did not activate a mid seam (cursor)")

        # 3. ⓘ on a LINKED tune -> the legacy tune-detail modal (reused verbatim)
        opened = pg.evaluate("""()=>{ const r=[...document.querySelectorAll('.tune-row')].find(x=>x.querySelector('.name').textContent.trim().includes('Silver Spear'));
            if(!r) return false; const btn=r.querySelector('.info-btn'); if(!btn) return false; btn.click(); return true }""")
        if not opened: fail.append("could not find a linked 'Silver Spear' row to open")
        pg.wait_for_selector("#tune-detail-modal.show", timeout=4000)
        pg.wait_for_timeout(700)
        disp = pg.eval_on_selector("#tune-detail-modal", "e => getComputedStyle(e).display")
        content = pg.eval_on_selector("#tune-detail-content", "e => e.innerText")
        full_width = pg.eval_on_selector(".modal-dialog", "e => Math.round(e.getBoundingClientRect().width)")
        print(f"3. legacy modal display={disp}, width={full_width}, has stats={'Popularity' in content}, name={'Silver Spear' in content}")
        if disp == "none": fail.append("tune-detail modal did not open")
        if "Silver Spear" not in content: fail.append("modal should show the tune name")
        if "Popularity" not in content: fail.append("modal should show stats (legacy layout)")
        if full_width < 440: fail.append(f"modal should be full-width (got {full_width})")

        # 4. close (Escape)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
        closed = pg.eval_on_selector("#tune-detail-modal", "e => getComputedStyle(e).display") == "none"
        print(f"4. modal closed={closed}")
        if not closed: fail.append("modal did not close on Escape")

        if errs: fail.append(f"errors: {errs[:4]}")
        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    _base = baseline()
    try:
        main()
    finally:
        cleanup(_base)
