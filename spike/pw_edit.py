#!/usr/bin/env python3
"""
Playwright check: Edit/relink a tune (spec 021 §E, change_tune) + the per-set
tune-type label pill. Self-contained — only touches rows it creates.
Run: venv/bin/python spike/pw_edit.py [PORT] [INST]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def pick(pg, query):
    """Type a query, wait for results that match it, click the top one. Returns its name."""
    pg.fill(".composer input", "")
    pg.wait_for_timeout(250)
    pg.fill(".composer input", query)
    # wait until the top result actually reflects this query (not a stale prior search)
    needle = query.split()[0].lower()
    pg.wait_for_function(
        "needle => { const e=document.querySelector('.results li .r-name'); return e && e.textContent.toLowerCase().includes(needle) }",
        arg=needle, timeout=4000,
    )
    top = pg.eval_on_selector(".results li .r-name", "e => e.textContent.trim()")
    pg.eval_on_selector_all(".results li", "els => els[0].click()")
    pg.wait_for_timeout(900)
    return top


def row_names(pg):
    return pg.eval_on_selector_all(".tune-row .name", "e => e.map(x => x.textContent.trim())")


def label_of_set_with(pg, name):
    return pg.evaluate(
        "(name)=>{ for(const s of document.querySelectorAll('.set')){ const ns=[...s.querySelectorAll('.tune-row .name')].map(x=>x.textContent.trim());"
        " if(ns.includes(name)){ const l=s.querySelector('.set-label'); return l? l.textContent.trim() : null } } return '__noset__' }",
        name,
    )


def select_row(pg, name):
    return pg.evaluate(
        "(name)=>{ const r=[...document.querySelectorAll('.tune-row')].find(x=>x.querySelector('.name').textContent.trim()===name);"
        " if(!r) return false; r.click(); return true }",
        name,
    )


def last_set_names(pg):
    # names in the final set card (where our isolated test tune lives)
    return pg.evaluate(
        "()=>{ const ss=document.querySelectorAll('.set'); if(!ss.length) return [];"
        " return [...ss[ss.length-1].querySelectorAll('.tune-row .name')].map(x=>x.textContent.trim()) }"
    )


def edit_last_set_tune(pg):
    # select the (isolated) tune in the LAST set and click its Edit action — never
    # touch a pre-existing same-named row earlier in the list.
    pg.evaluate("()=>{ const ss=document.querySelectorAll('.set'); const r=ss[ss.length-1].querySelector('.tune-row'); r && r.click() }")
    pg.wait_for_timeout(150)
    pg.eval_on_selector_all(".row-actions button", "els => { const e=els.find(b=>b.textContent.includes('Edit')); if(e) e.click() }")
    pg.wait_for_timeout(200)


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
        pg.set_viewport_size({"width": 460, "height": 860})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)
        ctx.request.post(f"{F}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1000)

        # fresh set at the end, with one catalog tune picked from search (so it has a type)
        pg.eval_on_selector_all(".end-seam", "els => els[els.length - 1].click()")
        pg.eval_on_selector_all(".composer input", "els => els[0].focus()")
        # end-set first so our tune is isolated in its own set (clean label assertion) —
        # but only if the end is OPEN; a closed end already starts a new set.
        if pg.query_selector(".composer .endset.hot"):
            pg.click(".composer .endset.hot"); pg.wait_for_timeout(800)
        n1 = pick(pg, "Silver Spear")
        print(f"1. added linked tune: {n1!r}; last set={last_set_names(pg)}")
        if last_set_names(pg) != [n1]:
            fail.append(f"picked tune {n1!r} should be alone in the last set, got {last_set_names(pg)}")

        # set-label pill reflects the tune's type
        lbl = label_of_set_with(pg, n1)
        print(f"2. set-label for its set = {lbl!r}")
        if not lbl:
            fail.append(f"set containing a typed tune should show a type pill (got {lbl!r})")

        # Edit -> banner + Save button
        edit_last_set_tune(pg)
        banner = pg.query_selector(".edit-banner") is not None
        save = pg.evaluate("()=>{ const b=[...document.querySelectorAll('.composer button')].find(x=>x.textContent.trim()==='Save'); return !!b }")
        print(f"3. edit banner={banner}, Save button={save}")
        if not banner: fail.append("Edit should show the editing banner")
        if not save: fail.append("composer primary button should read 'Save' while editing")

        # relink to a different tune via search
        n2 = pick(pg, "Cooley")
        print(f"4. relinked to {n2!r}; last set={last_set_names(pg)}")
        if last_set_names(pg) != [n2]:
            fail.append(f"relink should change the isolated set to [{n2!r}], got {last_set_names(pg)}")

        # Edit again -> rename to raw text (no match) -> unlinked rename
        edit_last_set_tune(pg)
        raw = f"ZZ Custom {int(time.time())}"
        pg.fill(".composer input", raw); pg.press(".composer input", "Enter"); pg.wait_for_timeout(1000)
        print(f"5. renamed to raw text; last set={last_set_names(pg)}")
        if last_set_names(pg) != [raw]:
            fail.append(f"raw rename should show [{raw!r}] in the last set, got {last_set_names(pg)}")

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
