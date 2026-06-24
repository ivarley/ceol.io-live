#!/usr/bin/env python3
"""Playwright check: 'already logged' merge nudge (§D16). Log a tune twice into the
open set -> the 2nd merges + shows a nudge -> 'Keep both' re-adds a distinct row.
Run: venv/bin/python spike/pw_merge.py [PORT] [INST]"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright
F=f"http://localhost:{sys.argv[1] if len(sys.argv)>1 else 5055}"
INST=int(sys.argv[2] if len(sys.argv)>2 else 1)
def count(pg, name):
    return pg.eval_on_selector_all(".tune-row .name", "(e,n)=>e.filter(x=>x.textContent.trim()===n).length", name)
def main():
    fail=[]
    with sync_playwright() as p:
        b=p.chromium.launch(); ctx=b.new_context(); pg=ctx.new_page(); pg.set_viewport_size({"width":460,"height":900})
        ctx.request.post(f"{F}/api/auth/login-password", data={"email":"ian@ceol.io","password":"password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row",timeout=8000); pg.wait_for_timeout(1000)
        # fresh open set, log a unique raw tune
        pg.eval_on_selector_all(".end-seam","els=>els[els.length-1].click()"); pg.wait_for_timeout(200)
        if pg.query_selector(".composer .endset.hot"): pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)
        nm=f"MergeProbe {int(time.time())}"
        pg.fill(".composer input", nm); pg.press(".composer input","Enter"); pg.wait_for_timeout(1100)
        c1=count(pg, nm)
        # log the SAME tune again into the open set -> should merge + nudge
        pg.fill(".composer input", nm); pg.press(".composer input","Enter"); pg.wait_for_timeout(1300)
        nudge=pg.query_selector(".merge-nudge") is not None
        c2=count(pg, nm)
        print(f"1. after dup: nudge shown={nudge}, count {c1}->{c2} (expect 1, merged)")
        if not nudge: fail.append("duplicate append should show the merge nudge")
        if c2!=1: fail.append(f"duplicate should merge (count should stay 1, got {c2})")
        # Keep both -> distinct second row
        if nudge:
            pg.click(".merge-nudge .mn-keep"); pg.wait_for_timeout(1300)
            c3=count(pg, nm)
            print(f"2. after Keep both: count -> {c3} (expect 2)")
            if c3!=2: fail.append(f"Keep both should add a distinct row (expected 2, got {c3})")
            if pg.query_selector(".merge-nudge"): fail.append("nudge should dismiss after Keep both")
        b.close()
    print("\n"+("PASS ✅" if not fail else "FAIL ❌\n  - "+"\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)
if __name__=="__main__":
    base=baseline()
    try: main()
    finally: cleanup(base)
