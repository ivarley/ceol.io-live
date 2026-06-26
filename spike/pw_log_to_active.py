#!/usr/bin/env python3
"""
Playwright check for "Log to current session" from a tune-detail page elsewhere in
the app (spec 024). When the user has an active session (the header green dot), the
shared tune-detail modal offers a button that navigates to the live editor with
?tune=<id>; the editor appends that tune to the end of the session instance.
Run: venv/bin/python spike/pw_log_to_active.py [FLASK_PORT] [INSTANCE_ID]
"""
import sys, time
import psycopg2
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)
TUNE_ID = 2  # "Bucks Of Oranmore, The"


def db():
    return psycopg2.connect(host="localhost", dbname="ceol_test", user="test_user", password="test_password")


def set_active(instance_id):
    c = db()
    try:
        cur = c.cursor()
        cur.execute("UPDATE person SET at_active_session_instance_id = %s WHERE person_id = (SELECT person_id FROM user_account WHERE username='ian')", (instance_id,))
        c.commit()
    finally:
        c.close()


def rows(page):
    return page.eval_on_selector_all(".tune-row .name", "e => e.map(x => x.textContent.trim())")


def main():
    failures = []
    base = baseline()
    set_active(INST)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
            pg.set_viewport_size({"width": 440, "height": 760})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
            ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})

            # A tune-detail page elsewhere in the app: open the shared modal (global lookup,
            # exactly like the app-wide "Find a tune") on a page that loads base.html + modal.
            pg.goto(f"{F}/admin/tunes")
            pg.wait_for_timeout(500)
            has_active = pg.evaluate("!!window.activeSession")
            print(f"  window.activeSession present: {has_active}")
            if not has_active:
                failures.append("window.activeSession not exposed by base.html")

            pg.evaluate(
                """([tid]) => TuneDetailModal.show({
                    context: 'session_instance', tuneId: tid,
                    apiEndpoint: '/api/tunes/' + tid + '/detail',
                    additionalData: { isUserLoggedIn: true, global: true, tuneName: 'Tune' }
                })""",
                [TUNE_ID],
            )
            pg.wait_for_selector(".active-session-log-btn", timeout=5000)
            label = pg.eval_on_selector(".active-session-log-btn", "e => e.textContent.trim()")
            print(f"  log button label: {label!r}")
            if "Mueller" not in label:
                failures.append(f"button should name the active session, got {label!r}")

            # Click it -> should navigate to the live editor with ?tune=<id> (then the app
            # strips the param after capturing it).
            pg.click(".active-session-log-btn")
            pg.wait_for_url("**/live/instances/**", timeout=8000)
            print(f"  navigated to: {pg.url}")
            if f"/live/instances/{INST}" not in pg.url:
                failures.append(f"should navigate to live editor for instance {INST}, got {pg.url}")

            pg.wait_for_selector(".tune-row", timeout=8000)
            pg.wait_for_timeout(2000)
            after = rows(pg)
            print(f"  last 3 rows after append: {after[-3:]}")
            # The appended tune should be the LAST row.
            if not after or "Bucks Of Oranmore" not in (after[-1] or ""):
                failures.append(f"appended tune should be last row, got last={after[-1] if after else None!r}")

            # The ?tune= param must be stripped so a reload doesn't re-add it.
            if "tune=" in pg.url:
                failures.append(f"?tune= should be stripped from URL after append, got {pg.url}")

            # Reload: the tune should NOT be added a second time.
            n_before = len([r for r in after if "Bucks Of Oranmore" in (r or "")])
            pg.reload()
            pg.wait_for_selector(".tune-row", timeout=8000)
            pg.wait_for_timeout(1500)
            n_after = len([r for r in rows(pg) if "Bucks Of Oranmore" in (r or "")])
            print(f"  'Bucks' count before/after reload: {n_before}/{n_after}")
            if n_after != n_before:
                failures.append(f"reload re-added the tune ({n_before} -> {n_after})")

            if errs:
                print(f"  page errors: {errs}")
                failures.append(f"page errors: {errs}")

            b.close()
    finally:
        cleanup(base)
        set_active(None)

    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
