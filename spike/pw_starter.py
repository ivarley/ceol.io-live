#!/usr/bin/env python3
"""
Playwright check: "started by" attribution (spec 021 §19; attribute_set_starter).
Isolates a fresh set, attributes a starter from the attendance picker, verifies the
tray + set-card pill, then clears it. Self-contained. Locates the set by our tune
name (not DOM position) so it's robust to other sets.
Run: venv/bin/python spike/pw_starter.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)

_SET_EL = """(args) => {
  const [name, sel] = args;
  for (const s of document.querySelectorAll('.set')) {
    const ns = [...s.querySelectorAll('.tune-row .name')].map(x => x.textContent.trim());
    if (ns.includes(name)) return s.querySelector(sel);
  }
  return null;
}"""


def click_in_set(pg, name, sel):
    return pg.evaluate("(args)=>{ const el=(" + _SET_EL + ")(args); if(el){el.click(); return true} return false }", [name, sel])


def text_in_set(pg, name, sel):
    return pg.evaluate("(args)=>{ const el=(" + _SET_EL + ")(args); return el? el.textContent.trim():null }", [name, sel])


def ensure_picker(pg, name):
    """Make sure the set's tray AND starter picker are open (the tray closes after a pick)."""
    if text_in_set(pg, name, ".set-tray") is None:
        click_in_set(pg, name, ".set-label"); pg.wait_for_timeout(250)
    if text_in_set(pg, name, ".starter-picker") is None:
        click_in_set(pg, name, ".starter-value"); pg.wait_for_timeout(500)


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1000)

        # isolate a fresh set with one tune at the end
        pg.eval_on_selector_all(".end-seam", "els => els[els.length-1].click()"); pg.wait_for_timeout(200)
        if pg.query_selector(".composer .endset.hot"):
            pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)
        nm = f"Starter Probe {int(time.time())}"
        pg.fill(".composer input", nm); pg.press(".composer input", "Enter"); pg.wait_for_timeout(1200)

        # open the tray + picker (one click on the value)
        click_in_set(pg, nm, ".set-label"); pg.wait_for_timeout(250)
        # "Started by [Not set]" — the value itself opens the droplist
        nv = text_in_set(pg, nm, ".starter-value")
        print(f"0. starter value before = {nv!r} (expect 'Not set')")
        if nv != "Not set": fail.append(f"unset starter should read 'Not set', got {nv!r}")
        click_in_set(pg, nm, ".starter-value")
        pg.wait_for_selector(".starter-picker .starter-item", timeout=4000); pg.wait_for_timeout(800)
        items = pg.eval_on_selector_all(".starter-picker .starter-item", "e=>e.map(x=>x.textContent.trim())")
        print(f"1. picker open, items={items[:3]} … {len(items)} total")
        if not any("Aoife" in t for t in items): fail.append("picker should list attendees (Aoife)")
        if not any("Add a player" in t for t in items): fail.append("picker should have '+ Add a player' at the bottom")

        # pick Aoife — picking now CLOSES the tray and flashes the pill
        pg.fill(".starter-filter", "Aoife"); pg.wait_for_timeout(300)
        pg.eval_on_selector_all(".starter-picker .starter-item", "els=>{const a=els.find(x=>x.textContent.includes('Aoife')); if(a)a.click()}")
        pg.wait_for_timeout(1200)
        tray_closed = text_in_set(pg, nm, ".set-tray") is None
        pill = text_in_set(pg, nm, ".starter-pill")
        print(f"2. tray closed={tray_closed}, set-card pill={pill!r}")
        if not tray_closed: fail.append("tray should close immediately after choosing a starter")
        if not pill or "Aoife" not in pill: fail.append(f"set card should show starter pill with Aoife, got {pill!r}")

        # "Add a player" opens the attendance editor (§F) — reopen tray+picker first
        ensure_picker(pg, nm)
        pg.eval_on_selector_all(".starter-item.add-player", "els=>els[0] && els[0].click()")
        pg.wait_for_timeout(400)
        editor = pg.query_selector(".drawer .att-list") is not None
        print(f"3. Add-a-player opened attendance editor={editor}")
        if not editor: fail.append("Add a player should open the attendance editor")
        if pg.query_selector(".drawer-done"): pg.click(".drawer-done")  # close it
        pg.wait_for_timeout(300)

        # clear it — reopen tray+picker
        ensure_picker(pg, nm)
        pg.eval_on_selector_all(".starter-item.clear", "els=>els[0] && els[0].click()")
        pg.wait_for_timeout(1100)
        pill2 = text_in_set(pg, nm, ".starter-pill")
        print(f"4. after clear, pill={pill2!r}")
        if pill2: fail.append(f"starter pill should be gone after clear, got {pill2!r}")

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
