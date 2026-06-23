#!/usr/bin/env python3
"""
Playwright check for insert-at-position / seams (spec 021 §B).
Place the cursor on a mid-list seam, add a tune, and verify it lands THERE
(not at the end) — and that the cursor advances for a burst.
Run: venv/bin/python spike/pw_insert.py [FLASK_PORT] [INSTANCE_ID]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def rows(page):
    return page.eval_on_selector_all(".tune-row .name", "e => e.map(x => x.textContent.trim())")


def main():
    failures = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 440, "height": 760})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000)
        pg.wait_for_timeout(1200)

        # default cursor = end (end-seam active)
        end_active = pg.eval_on_selector(".end-seam", "e => e.classList.contains('active')")
        print(f"  default cursor at end: {end_active}")
        if not end_active:
            failures.append("default cursor should be the end seam")

        # place cursor on the seam after the FIRST tune
        before_rows = rows(pg)
        first_name = before_rows[0]
        pg.eval_on_selector_all(".seam:not(.end-seam)", "els => els[0].click()")
        pg.wait_for_timeout(200)
        # add a uniquely-named tune there
        mark = f"INS {int(time.time())}"
        pg.fill(".composer input", mark)
        pg.press(".composer input", "Enter")
        pg.wait_for_timeout(1500)
        after_rows = rows(pg)
        idx = after_rows.index(mark) if mark in after_rows else -1
        print(f"  inserted {mark!r} at index {idx} (first tune was {first_name!r}); total {len(before_rows)}->{len(after_rows)}")
        if idx != 1:
            failures.append(f"insert should land at index 1 (after first tune), landed at {idx}")

        # burst: cursor should have advanced past the inserted tune -> next lands at index 2
        mark2 = f"INS2 {int(time.time())}"
        pg.fill(".composer input", mark2)
        pg.press(".composer input", "Enter")
        pg.wait_for_timeout(1500)
        seq = rows(pg)
        i1, i2 = seq.index(mark) if mark in seq else -9, seq.index(mark2) if mark2 in seq else -9
        print(f"  burst: {mark!r}@{i1}, {mark2!r}@{i2} (expect consecutive)")
        if i2 != i1 + 1:
            failures.append(f"burst insert should be consecutive ({i1},{i2})")

        if errs:
            failures.append(f"errors: {errs[:4]}")
        b.close()
    print("\n" + ("PASS ✅" if not failures else "FAIL ❌\n  - " + "\n  - ".join(failures)))
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    _base = baseline()
    try:
        main()
    finally:
        cleanup(_base)
