#!/usr/bin/env python3
"""
Offline tune-match cache (#5c). A tune searched while ONLINE is cached; later, while
OFFLINE, typing the same name still surfaces it so the tune can be LINKED (not logged
as raw/unlinked text). Without the cache, offline matchFor returns [] -> unlinked.

Flow: online search "Cooley" (warms cache) -> go OFFLINE -> type "Cooley" -> the cached
result appears in the dropdown -> tap it -> the new row is LINKED (no .unlinked).
Self-cleaning.

Run: venv/bin/python spike/pw_offline_match.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)
QUERY = "Cooley"


def last_set(pg):
    return pg.evaluate("()=>{const ss=document.querySelectorAll('.set');if(!ss.length)return[];const s=ss[ss.length-1];return[...s.querySelectorAll('.tune-row')].map(r=>({name:r.querySelector('.name').textContent.trim(),unlinked:r.classList.contains('unlinked')}))}")


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 880}); pg.set_default_timeout(10000)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1200)

        # WARM the cache online: type the query, let the debounced search + cache run
        pg.eval_on_selector_all(".composer input", "els => els[0].focus()")
        pg.fill(".composer input", QUERY); pg.wait_for_timeout(1200)
        online_results = pg.eval_on_selector_all(".results li .r-name", "e => e.map(x => x.textContent.trim())")
        print(f"0. online results for {QUERY!r}: {online_results[:4]}")
        if not online_results:
            print("FAIL ❌ no online results to cache"); b.close(); sys.exit(1)
        target = online_results[0]
        pg.fill(".composer input", ""); pg.wait_for_timeout(400)

        # fresh set at the end so the added row is isolated
        pg.eval_on_selector_all(".end-seam", "els => els[els.length-1].click()")
        pg.eval_on_selector_all(".composer input", "els => els[0].focus()")
        if pg.query_selector(".composer .endset.hot"):
            pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)

        # --- go OFFLINE ---
        ctx.set_offline(True); pg.wait_for_timeout(600)

        # type the SAME query offline: the cached result should appear
        pg.fill(".composer input", QUERY); pg.wait_for_timeout(900)
        offline_results = pg.eval_on_selector_all(".results li .r-name", "e => e.map(x => x.textContent.trim())")
        print(f"1. OFFLINE results for {QUERY!r} (from cache): {offline_results[:4]}")
        if not offline_results:
            fail.append("offline: cached results should appear in the dropdown (cache miss)")

        # tap the cached result -> should LINK (not unlinked)
        if offline_results:
            pg.eval_on_selector_all(".results li", "els => els[0] && els[0].click()")
            pg.wait_for_timeout(700)
            ls = last_set(pg)
            print(f"2. last set after offline add: {ls}")
            linkedRow = next((r for r in ls if target.split(',')[0].lower() in r['name'].lower()), None)
            if not linkedRow:
                fail.append(f"the offline-added tune {target!r} should be in the last set; got {ls}")
            elif linkedRow['unlinked']:
                fail.append("offline add via cache should be LINKED (not .unlinked)")

        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    base = baseline()
    try:
        main()
    finally:
        cleanup(base)
