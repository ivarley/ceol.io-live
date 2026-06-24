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

        # 3. ⓘ -> drawer with real stats
        pg.eval_on_selector_all(".tune-row:not(.pending):not(.removing) .info-btn", "els => els[0].click()")
        pg.wait_for_selector(".drawer", timeout=4000)
        pg.wait_for_timeout(600)
        title = pg.text_content(".drawer-title")
        stats = pg.eval_on_selector_all(".d-statrow", "e => e.map(x => x.textContent.trim())")
        has_unlinked = pg.query_selector(".d-note") is not None
        print(f"3. drawer title={title!r}, stats={stats}, unlinked_note={has_unlinked}")
        if not pg.query_selector(".drawer"): fail.append("drawer did not open")
        if not stats and not has_unlinked: fail.append("drawer showed neither stats nor unlinked note")

        # 4. close drawer (Done button; the scrim's center is under the panel)
        pg.click(".drawer-done"); pg.wait_for_timeout(300)
        if pg.query_selector(".drawer"): fail.append("drawer did not close")
        print(f"4. drawer closed={pg.query_selector('.drawer') is None}")

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
