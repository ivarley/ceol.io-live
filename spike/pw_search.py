#!/usr/bin/env python3
"""
Playwright check for the type-ahead search + tap-to-add UI (spec 021 §D).
Run: venv/bin/python spike/pw_search.py [FLASK_PORT] [INSTANCE_ID]
"""
import sys, time
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

FLASK = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INSTANCE = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def log(m):
    print(f"  {m}", flush=True)


def rows(page):
    return page.eval_on_selector_all(".tune-row .name", "e => e.map(x => x.textContent.trim())")


def main():
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text else None)

        ctx.request.post(f"{FLASK}/api/auth/login-password", data={"email": "ian@ceol.io", "password": "password123"})
        page.goto(f"{FLASK}/live/instances/{INSTANCE}")
        page.wait_for_selector(".composer input", timeout=10000)
        page.wait_for_timeout(1000)

        # type a query -> results sheet appears
        page.fill(".composer input", "Cool")
        try:
            page.wait_for_selector(".results li", timeout=4000)
        except Exception:
            failures.append("no search results appeared for 'Cool'")
        res = page.eval_on_selector_all(".results li .r-name", "e => e.map(x => x.textContent.trim())")
        log(f"results for 'Cool': {res[:5]}")
        if not res:
            failures.append("results list empty")

        before = len(rows(page))
        if res:
            first = res[0]
            page.click(".results li:first-child")
            page.wait_for_timeout(1200)
            after_rows = rows(page)
            log(f"after pick {first!r}: rows {before} -> {len(after_rows)}; input={page.input_value('.composer input')!r}; results_open={bool(page.query_selector('.results li'))}")
            # The picked tune is present afterward (added, or merged if already there
            # via corroboration — either is correct).
            if first not in after_rows:
                failures.append(f"picked tune {first!r} not present after pick")
            if page.input_value(".composer input") != "":
                failures.append("input should clear after pick (stay-hot)")
            if page.query_selector(".results li"):
                failures.append("results sheet should close after pick")

        # Enter picks the TOP match for a partial (not the raw text)
        page.fill(".composer input", "Cool")
        page.wait_for_selector(".results li", timeout=4000)
        top = page.eval_on_selector(".results li:first-child .r-name", "e => e.textContent.trim()")
        page.press(".composer input", "Enter")
        page.wait_for_timeout(1200)
        added = rows(page)
        log(f"Enter on 'Cool' -> top match {top!r} added={top in added}, raw 'Cool' present={'Cool' in added}")
        if top not in added:
            failures.append(f"Enter should add the top match {top!r}")
        if "Cool" in added:
            failures.append("Enter added raw 'Cool' instead of the matched tune")

        # Debounce-race: type a prefix, let its results load, then type the rest and
        # hit Enter BEFORE the new search fires. Must commit a match for the full text,
        # not the stale prefix's top result.
        page.fill(".composer input", "Cool")
        page.wait_for_selector(".results li", timeout=4000)  # prefix results loaded
        stale_top = page.eval_on_selector(".results li:first-child .r-name", "e => e.textContent.trim()")
        page.focus(".composer input")
        page.type(".composer input", "ey", delay=10)  # -> "Cooley" (no debounce wait)
        page.press(".composer input", "Enter")  # fire before the 180ms debounce
        page.wait_for_timeout(1500)
        added = rows(page)
        # whatever it added must actually match "Cooley" (contain it), not some stale prefix hit
        matched = [r for r in added if "cooley" in r.lower()]
        log(f"race: stale_top={stale_top!r}; added a Cooley match={bool(matched)}")
        if not matched:
            failures.append(f"debounce race: committed a non-matching tune (stale_top was {stale_top!r})")

        # Stuck-dropdown race: type fast, hit Enter, then wait PAST the debounce —
        # the pending search must not repopulate the dropdown after commit.
        page.focus(".composer input")
        page.type(".composer input", "Castle", delay=10)
        page.press(".composer input", "Enter")
        page.wait_for_timeout(900)  # well past the 180ms debounce
        if page.query_selector(".results li"):
            failures.append("dropdown reappeared after commit (pending search not cancelled)")
        if page.input_value(".composer input") != "":
            failures.append("input not cleared after fast Enter")
        log(f"post-fast-Enter: results_open={bool(page.query_selector('.results li'))}, input={page.input_value('.composer input')!r}")

        # ABC fallback: a short note-only query with no NAME matches falls back to a
        # notation search (results flagged "♪ notation"). 'GED' matches no names.
        page.fill(".composer input", "GED")
        page.wait_for_timeout(1000)
        abc_badges = page.eval_on_selector_all(".results .r-abc", "e => e.length")
        names = [n for n in page.eval_on_selector_all(".results li .r-name", "e => e.map(x => x.textContent.trim())") if "Search" not in n]
        log(f"ABC fallback 'GED': {len(names)} results, ♪ badges={abc_badges}")
        if not names or abc_badges == 0:
            failures.append("ABC-pattern query with no name match should fall back to notation results")
        page.fill(".composer input", "")

        # No quick matches -> the dropdown still shows "No tunes match" + a deeper-search
        # option (which opens the deep modal carrying the query).
        page.fill(".composer input", "zzxqwvk")
        page.wait_for_timeout(900)
        empty = page.text_content(".result-empty") if page.query_selector(".result-empty") else None
        deeper = page.query_selector(".result-deeper") is not None
        log(f"no-match: empty msg={empty!r}, deeper option={deeper}")
        if not empty or "No tunes match" not in empty:
            failures.append("no-match should show a 'No tunes match your search' message")
        if not deeper:
            failures.append("no-match should still offer the deeper-search option")
        else:
            page.eval_on_selector_all(".result-deeper", "els => els[0].click()")
            page.wait_for_selector(".deep-modal", timeout=4000)
            if page.eval_on_selector(".deep-field", "e => e.value") != "zzxqwvk":
                failures.append("deeper search should open carrying the typed query")
            page.press(".deep-field", "Escape"); page.wait_for_timeout(200)
        page.fill(".composer input", "")  # clear so the next step is clean

        # Enter with no match -> adds raw (server still attempts exact match)
        raw = f"PW NoMatch {int(time.time())}"
        page.fill(".composer input", raw)
        page.press(".composer input", "Enter")
        page.wait_for_timeout(1000)
        if raw not in rows(page):
            failures.append("Enter with no match should add the raw text")

        if errs:
            failures.append(f"console/page errors: {errs[:5]}")
        browser.close()

    print("\n" + ("PASS ✅" if not failures else "FAIL ❌\n  - " + "\n  - ".join(failures)))
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    _base = baseline()
    try:
        main()
    finally:
        cleanup(_base)
