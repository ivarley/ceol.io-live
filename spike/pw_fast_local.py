#!/usr/bin/env python3
"""
Playwright check for the local exact-match fast path (spec 024). A typed name that
matches the session's known repertoire EXACTLY logs instantly on Enter, with NO
network /match round-trip. Unknown text still falls through to the server matcher.
Run: venv/bin/python spike/pw_fast_local.py [FLASK_PORT] [INSTANCE_ID]
"""
import sys, time
import psycopg2
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5056}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def db():
    return psycopg2.connect(host="localhost", dbname="ceol_test", user="test_user", password="test_password")


def last_added(base):
    c = db()
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT session_instance_tune_id, tune_id, name FROM session_instance_tune "
            "WHERE session_instance_tune_id > %s AND record_type='tune' AND NOT deleted "
            "ORDER BY session_instance_tune_id DESC LIMIT 1",
            (base,),
        )
        return cur.fetchone()
    finally:
        c.close()


def rows(page):
    return page.eval_on_selector_all(".tune-row .name", "e => e.map(x => x.textContent.trim())")


def main():
    failures = []
    base = baseline()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
            pg.set_viewport_size({"width": 440, "height": 760})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)

            match_calls = {"n": 0, "armed": False}
            def on_req(req):
                if match_calls["armed"] and "/match" in req.url:
                    match_calls["n"] += 1
            pg.on("request", on_req)

            ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
            pg.goto(f"{F}/live/instances/{INST}")
            pg.wait_for_selector(".tune-row", timeout=8000)
            pg.wait_for_timeout(1200)  # let bootstrap (with vocabulary) settle

            # --- exact known tune: type + Enter immediately, assert NO /match call ---
            b1 = baseline()
            match_calls["armed"] = True
            pg.fill(".composer input", "Drowsy Maggie")
            pg.press(".composer input", "Enter")  # fired well within the 180ms debounce
            pg.wait_for_timeout(1500)
            match_calls["armed"] = False
            print(f"  /match calls during fast exact Enter: {match_calls['n']}")
            if match_calls["n"] != 0:
                failures.append(f"exact local match should not hit /match, saw {match_calls['n']} call(s)")
            rec = last_added(b1)
            print(f"  added row: {rec}")
            if not rec or rec[2] != "Drowsy Maggie":
                failures.append(f"expected 'Drowsy Maggie' row, got {rec}")
            elif rec[1] != 27:
                failures.append(f"row should be LINKED to tune_id 27, got tune_id={rec[1]}")

            # --- unknown text: should fall through to the server (/match called), unlinked ---
            b2 = baseline()
            match_calls["armed"] = True
            mark = f"Zzqx Nonexistent {int(time.time())}"
            pg.fill(".composer input", mark)
            pg.wait_for_timeout(400)  # allow the debounced type-ahead to run
            pg.press(".composer input", "Enter")
            pg.wait_for_timeout(1500)
            match_calls["armed"] = False
            print(f"  /match calls for unknown text: {match_calls['n']}")
            if match_calls["n"] == 0:
                failures.append("unknown text should fall through to the server /match path")
            rec2 = last_added(b2)
            print(f"  unknown row: {rec2}")
            if not rec2 or rec2[1] is not None:
                failures.append(f"unknown text should log UNLINKED (tune_id NULL), got {rec2}")

            if errs:
                print(f"  page errors: {errs}")
                failures.append(f"page errors: {errs}")
            b.close()
    finally:
        cleanup(base)

    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
