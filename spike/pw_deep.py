#!/usr/bin/env python3
"""
Playwright check: deep catalog search (spec 021 §D) — modal, type filter, notation
(abcjs), badges, tap-to-log, log-as-is. Self-contained (cleans up added tunes).
Run: venv/bin/python spike/pw_deep.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def rows(pg):
    return pg.eval_on_selector_all(".tune-row .name", "e=>e.map(x=>x.textContent.trim())")


def open_deep(pg):
    # access is via the menu now (no bottom-bar button)
    pg.click(".hamburger-btn"); pg.wait_for_timeout(150)
    pg.eval_on_selector_all(".hamburger-item", "els=>{const a=els.find(x=>x.textContent.includes('Find a tune')); if(a)a.click()}")
    pg.wait_for_selector(".deep-modal", timeout=4000); pg.wait_for_timeout(300)


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

        # open deep search via the menu
        open_deep(pg)
        ntabs = pg.eval_on_selector_all(".deep-tab", "e=>e.length")
        chips_hidden = pg.query_selector(".deep-type-chip") is None  # chips live in the popout
        print(f"1. modal open, {ntabs} tabs; filter chips hidden initially={chips_hidden}")
        if ntabs < 3: fail.append("expected By name / By ABC / filter tabs")
        if not chips_hidden: fail.append("type chips should be behind the filter popout, not always shown")

        # ABC auto-default: short note-only input → ABC mode; a normal name → name mode
        tab_active = lambda label: pg.evaluate("(l)=>{const t=[...document.querySelectorAll('.deep-tab')].find(x=>x.textContent.trim()===l); return !!(t&&t.classList.contains('active'))}", label)
        pg.fill(".deep-field", "ged"); pg.wait_for_timeout(450)
        print(f"1b. 'ged' → ABC mode active={tab_active('By ABC')}")
        if not tab_active("By ABC"): fail.append("short note-only input should auto-select ABC mode")
        pg.fill(".deep-field", "silver"); pg.wait_for_timeout(450)
        print(f"1c. 'silver' → name mode active={tab_active('By name')}")
        if not tab_active("By name"): fail.append("a normal name should auto-select name mode")

        # search "silver"
        pg.fill(".deep-field", "silver"); pg.wait_for_timeout(700)
        cards = pg.eval_on_selector_all(".deep-card .deep-name", "e=>e.map(x=>x.textContent.trim())")
        print(f"2. results for 'silver': {cards[:5]} ({len(cards)})")
        if not cards: fail.append("deep search 'silver' should return results")
        if not any("Silver" in c for c in cards): fail.append(f"expected a Silver match; got {cards[:5]}")
        # notation shows as a server-rendered image (Silver Spear is cached); lazy
        # ones render on scroll, so give them a moment
        pg.wait_for_timeout(1500)
        imgs = pg.eval_on_selector_all(".deep-staff .incipit-img", "e=>e.length")
        print(f"   notation images shown: {imgs}")
        if imgs == 0: fail.append("expected at least one server-rendered notation image")

        # open the filter popout, click "Reels" -> results reels only + removable pill
        pg.click(".deep-filter-tab"); pg.wait_for_selector(".deep-filters .deep-type-chip", timeout=3000)
        pg.eval_on_selector_all(".deep-type-chip", "els=>{const r=els.find(x=>x.textContent.trim()==='Reels'); if(r)r.click()}")
        pg.wait_for_timeout(700)
        types = pg.eval_on_selector_all(".deep-card .deep-type", "e=>e.map(x=>x.textContent.trim())")
        pill = pg.query_selector(".deep-filters .filter-pill") is not None
        print(f"3. after Reels filter, types={set(types)}, pill={pill}")
        if types and any(t and t != 'Reel' for t in types): fail.append(f"Reels filter should show only reels; got {set(types)}")
        if not pill: fail.append("active filter should show a removable pill")
        pg.eval_on_selector_all(".deep-filters .filter-pill", "els=>els[0].click()"); pg.wait_for_timeout(500)

        # ABC search mode: search a note run, expect notation-matched results
        pg.eval_on_selector_all(".deep-tab", "els=>{const a=els.find(x=>x.textContent.trim()==='By ABC'); if(a)a.click()}")
        pg.wait_for_timeout(200); pg.fill(".deep-field", "GE"); pg.wait_for_timeout(800)
        abc_cards = pg.eval_on_selector_all(".deep-card .deep-name", "e=>e.length")
        print(f"3b. ABC-mode 'GE' results: {abc_cards}")
        if abc_cards == 0: fail.append("ABC-mode search should match tunes by notation")
        pg.eval_on_selector_all(".deep-tab", "els=>{const a=els.find(x=>x.textContent.trim()==='By name'); if(a)a.click()}")
        pg.wait_for_timeout(200); pg.fill(".deep-field", "silver"); pg.wait_for_timeout(700)

        # tap the first result -> logged at cursor, modal closes
        before = len(rows(pg))
        picked = pg.eval_on_selector(".deep-card .deep-name", "e=>e.textContent.trim()")
        pg.eval_on_selector_all(".deep-card", "els=>els[0].click()")
        pg.wait_for_timeout(1200)
        modal_gone = pg.query_selector(".deep-modal") is None
        now = rows(pg)
        print(f"4. tapped {picked!r}; modal closed={modal_gone}; rows {before}->{len(now)}")
        if not modal_gone: fail.append("modal should close after picking")
        if picked not in now: fail.append(f"picked tune {picked!r} should be logged; rows tail={now[-3:]}")

        # log-as-is: open again, type a nonsense name, log as-is
        open_deep(pg)
        raw = f"ZZ Deep {int(time.time())}"
        pg.fill(".deep-field", raw); pg.wait_for_timeout(600)
        pg.click(".deep-asis"); pg.wait_for_timeout(1200)
        now2 = rows(pg)
        print(f"5. log-as-is {raw!r} present={raw in now2}")
        if raw not in now2: fail.append(f"log-as-is should add {raw!r}; tail={now2[-3:]}")

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
