#!/usr/bin/env python3
"""Playwright check: editable session notes in the expanded header (§F, edit_notes op).
Saves a note, reloads to confirm persistence, restores the original.
Run: venv/bin/python spike/pw_notes.py [PORT] [INST]"""
import sys, time
from playwright.sync_api import sync_playwright
F=f"http://localhost:{sys.argv[1] if len(sys.argv)>1 else 5055}"
INST=int(sys.argv[2] if len(sys.argv)>2 else 1)

def get_notes_via_api(ctx):
    r=ctx.request.get(f"{F}/api/live/instances/{INST}/bootstrap"); return r.json().get("notes")

def main():
    fail=[]
    with sync_playwright() as p:
        b=p.chromium.launch(); ctx=b.new_context(); pg=ctx.new_page(); pg.set_viewport_size({"width":460,"height":900})
        ctx.request.post(f"{F}/api/auth/login-password", data={"email":"ian@ceol.io","password":"password123"})
        original = get_notes_via_api(ctx)
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row",timeout=8000); pg.wait_for_timeout(800)
        # expand header -> edit notes
        pg.click(".topbar-row"); pg.wait_for_selector(".hn-area",timeout=3000)
        # Save hidden until dirty
        if pg.query_selector(".hn-save"): fail.append("Save should be hidden until the note is edited")
        note=f"PW note {int(time.time())}"
        pg.fill(".hn-area", note); pg.wait_for_timeout(200)
        if not pg.query_selector(".hn-save"): fail.append("Save should appear once the note changes")
        pg.click(".hn-save"); pg.wait_for_timeout(1000)
        saved = get_notes_via_api(ctx)
        print(f"1. saved note -> server notes={saved!r}")
        if saved != note: fail.append(f"server should persist the note; got {saved!r}")
        # save button gone after save (clean)
        if pg.query_selector(".hn-save"): fail.append("Save should disappear after saving (no longer dirty)")
        # reload -> note shows in the textarea
        pg.reload(); pg.wait_for_selector(".tune-row",timeout=8000); pg.wait_for_timeout(800)
        pg.click(".topbar-row"); pg.wait_for_selector(".hn-area",timeout=3000)
        shown = pg.input_value(".hn-area")
        print(f"2. after reload, textarea={shown!r}")
        if shown != note: fail.append(f"note should persist across reload; got {shown!r}")
        # restore original
        pg.fill(".hn-area", original or ""); pg.wait_for_timeout(150); pg.click(".hn-save"); pg.wait_for_timeout(800)
        print(f"3. restored original notes={get_notes_via_api(ctx)!r}")
        b.close()
    print("\n"+("PASS ✅" if not fail else "FAIL ❌\n  - "+"\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)

if __name__=="__main__": main()
