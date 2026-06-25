#!/usr/bin/env python3
"""
Playwright check: seam model (spec 021 §C) — Split on intra-set seams, a NEW set
created from the between-sets ("inter") seam, and Join on that inter seam. Plus the
contextual Done button. Self-contained: only touches rows it creates.
Run: venv/bin/python spike/pw_seams.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def nsets(pg):
    return pg.eval_on_selector_all(".set", "e => e.length")


def arm_after(pg, name):
    return pg.evaluate(
        "(name) => { const r=[...document.querySelectorAll('.tune-row')].find(x=>x.querySelector('.name').textContent.trim()===name);"
        " if(!r) return false; const s=r.nextElementSibling;"
        " if(s&&s.classList.contains('seam')&&!s.classList.contains('start-seam')&&!s.classList.contains('end-seam')){s.click();return true} return false }",
        name,
    )


def arm_inter_before(pg, name):
    # the between-sets seam immediately preceding the set whose first tune is `name`
    return pg.evaluate(
        "(name) => { for(const s of document.querySelectorAll('.set')){ const f=s.querySelector('.tune-row .name');"
        " if(f&&f.textContent.trim()===name){ const prev=s.previousElementSibling;"
        " if(prev&&prev.classList.contains('inter-seam')){prev.click();return true} } } return false }",
        name,
    )


def set_of(pg, name):
    # tunes (names) in the set that contains `name`
    return pg.evaluate(
        "(name) => { for(const s of document.querySelectorAll('.set')){ const ns=[...s.querySelectorAll('.tune-row .name')].map(x=>x.textContent.trim());"
        " if(ns.includes(name)) return ns } return null }",
        name,
    )


def add(pg, name):
    pg.fill(".composer input", name); pg.press(".composer input", "Enter"); pg.wait_for_timeout(900)


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 820})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1000)

        # three tunes appended into one open set at the end (all test-owned)
        t = int(time.time())
        a, c2, c3, nw = f"SeamA {t}", f"SeamB {t}", f"SeamC {t}", f"SeamN {t}"
        pg.eval_on_selector_all(".end-seam", "els => els[0].click()")
        for nm in (a, c2, c3):
            add(pg, nm)

        # 1. Done button: arming a mid seam swaps End set -> Done
        arm_after(pg, a); pg.wait_for_timeout(200)
        if not pg.query_selector(".done-btn") or pg.query_selector(".endset"):
            fail.append("mid-seam cursor should show Done (not End set)")
        print(f"1. Done={pg.query_selector('.done-btn') is not None}, EndSet={pg.query_selector('.endset') is not None}")

        # 2. Split after SeamB (intra-set) -> +1 set
        sb = nsets(pg)
        arm_after(pg, c2); pg.wait_for_timeout(200)
        split = pg.query_selector(".seam.active .seam-pill.split")
        print(f"2. split pill present={split is not None}")
        if not split:
            fail.append("intra-set active seam should show a Split pill")
        else:
            split.click(); pg.wait_for_timeout(1000)
            sa = nsets(pg)
            print(f"   split -> sets {sb} -> {sa}; now [{set_of(pg, a)}] [{set_of(pg, c3)}]")
            if sa != sb + 1: fail.append(f"split should add a set ({sb}->{sa})")

        # 3. New set from the inter (between-sets) seam, before SeamC's set -> +1 set,
        #    and the new tune is alone in its own set.
        sb = nsets(pg)
        if not arm_inter_before(pg, c3):
            fail.append("could not find the between-sets seam before SeamC")
        else:
            pg.wait_for_timeout(200)
            add(pg, nw); pg.wait_for_timeout(800)
            sa = nsets(pg)
            ns = set_of(pg, nw)
            print(f"3. new-set -> sets {sb} -> {sa}; new set = {ns}")
            if sa != sb + 1: fail.append(f"new-set should add a set ({sb}->{sa})")
            if ns != [nw]: fail.append(f"new tune should be alone in its set, got {ns}")

        # 4. Join from the inter seam before SeamC's set (removes that break) -> -1 set,
        #    merging the new tune's set into SeamC's.
        sb = nsets(pg)
        arm_inter_before(pg, c3); pg.wait_for_timeout(200)
        joinp = pg.query_selector(".seam.active .seam-pill.join")
        print(f"4. join pill present={joinp is not None}")
        if not joinp:
            fail.append("the between-sets active seam should show a Join pill")
        else:
            joinp.click(); pg.wait_for_timeout(1000)
            sa = nsets(pg)
            merged = set_of(pg, c3)
            print(f"   join -> sets {sb} -> {sa}; merged = {merged}")
            if sa != sb - 1: fail.append(f"join should remove a set ({sb}->{sa})")
            if not merged or nw not in merged or c3 not in merged:
                fail.append(f"join should merge the new tune with SeamC, got {merged}")

        if errs:
            fail.append(f"errors: {errs[:4]}")
        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    _base = baseline()
    try:
        main()
    finally:
        cleanup(_base)
