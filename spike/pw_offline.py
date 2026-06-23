#!/usr/bin/env python3
"""
Faithful Playwright driver for the live-logging offline flow.

Uses a PERSISTENT browser profile so the service worker, Cache Storage, and
IndexedDB persist across reloads exactly like a real browser (the ephemeral
default context hid the real SW-cache bugs). Reproduces the actual sequence:
load online -> go offline -> RELOAD -> the shell must still load (no ERR_FAILED)
and render the cached tunes; then offline ops; then reconnect.

Run: venv/bin/python spike/pw_offline.py [FLASK_PORT] [INSTANCE_ID]
Pass a 3rd arg "keep" to reuse the profile dir across runs.
"""
import sys, time, tempfile, os
from playwright.sync_api import sync_playwright

FLASK = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INSTANCE = int(sys.argv[2] if len(sys.argv) > 2 else 1)
EMAIL, PASSWORD = "ian@ceol.io", "password123"
PROFILE = os.path.join(tempfile.gettempdir(), "pw-ceol-profile")


def log(m):
    print(f"  {m}", flush=True)


def tune_rows(page):
    return page.eval_on_selector_all(".set li .name", "els => els.map(e => e.textContent.trim())")


def main():
    failures = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        errors = []
        events_reqs = []
        page.on("request", lambda r: events_reqs.append(r.url) if "/events" in r.url else None)
        EXPECTED = ("ERR_INTERNET_DISCONNECTED", "ERR_NETWORK", "Failed to load resource")
        page.on("console", lambda m: errors.append(m.text) if (m.type == "error" and not any(x in m.text for x in EXPECTED)) else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        # login (cookie on the context)
        r = ctx.request.post(f"{FLASK}/api/auth/login-password", data={"email": EMAIL, "password": PASSWORD})
        assert r.ok, f"login failed {r.status}"

        # --- online load: let the SW install, take control, and prime the shell cache ---
        page.goto(f"{FLASK}/live/instances/{INSTANCE}")
        page.wait_for_selector(".composer input", timeout=10000)
        page.wait_for_function("() => navigator.serviceWorker && navigator.serviceWorker.controller !== null", timeout=10000)
        page.wait_for_timeout(2000)  # prime cache-shell + write snapshot
        online_rows = tune_rows(page)
        sw_controls = page.evaluate("() => navigator.serviceWorker.controller !== null")
        log(f"online: {len(online_rows)} rows, SW controlling={sw_controls}, status={page.text_content('.status').strip()!r}")
        assert sw_controls, "service worker should control the page"
        assert len(online_rows) > 0

        # The shell MUST be cached for offline reload to work (this is the actual
        # invariant the ERR_FAILED bug violated when the cache was wiped).
        cached_urls = page.evaluate("""async () => {
          const out = []
          for (const n of await caches.keys()) {
            const c = await caches.open(n)
            for (const r of await c.keys()) out.push(r.url)
          }
          return out
        }""")
        nav_cached = any(f"/live/instances/{INSTANCE}" in u for u in cached_urls)
        log(f"shell cached: {nav_cached} ({len(cached_urls)} entries)")
        if not nav_cached:
            failures.append("page shell not cached -> offline reload would ERR_FAILED")

        # --- THE failing case: go offline, then RELOAD ---
        ctx.set_offline(True)
        page.wait_for_timeout(500)
        reload_ok, reload_err = True, ""
        try:
            page.reload(timeout=10000)
            page.wait_for_selector(".composer input", timeout=8000)
        except Exception as e:
            reload_ok, reload_err = False, str(e).splitlines()[0]
        log(f"offline reload: ok={reload_ok} {('('+reload_err+')') if reload_err else ''}")
        if not reload_ok:
            failures.append(f"offline reload failed: {reload_err}")
        else:
            page.wait_for_timeout(1500)
            rows = tune_rows(page)
            pill = page.text_content(".status").strip()
            log(f"offline reload rendered: {len(rows)} rows, pill={pill!r}")
            if len(rows) < len(online_rows):
                failures.append(f"offline reload showed {len(rows)} rows, expected >= {len(online_rows)}")
            if pill != "offline":
                failures.append(f"pill should be 'offline', got {pill!r}")

            # offline add (so the banner shows), then check banner agrees with pill
            page.fill(".composer input", f"PW Off {int(time.time())}")
            page.press(".composer input", "Enter")
            page.wait_for_timeout(400)
            banner = page.text_content(".offline-banner") if page.query_selector(".offline-banner") else ""
            log(f"offline banner={banner.strip()!r}")
            if "offline" not in banner:
                failures.append(f"banner should say 'offline' (agree with pill), got {banner.strip()!r}")
            # no SSE retry spam while offline
            ev_before = len(events_reqs)
            page.wait_for_timeout(5000)
            ev_during = len(events_reqs) - ev_before
            log(f"/events requests during 5s offline window: {ev_during}")
            if ev_during > 0:
                failures.append(f"{ev_during} SSE requests fired while offline (should be 0)")
            if page.query_selector(".set li:not(.pending):not(.removing) button.remove"):
                page.click(".set li:not(.pending):not(.removing) button.remove")
                page.wait_for_timeout(300)
                if len(page.query_selector_all(".set li.removing")) != 1:
                    failures.append("offline remove did not mark a row removing")
                else:
                    page.click(".set li.removing button.restore")
                    page.wait_for_timeout(300)
            sets_before = page.eval_on_selector_all(".set", "e => e.length")
            page.click("button.endset")
            page.wait_for_timeout(300)
            nm = f"PW AfterBreak {int(time.time())}"
            page.fill(".composer input", nm)
            page.press(".composer input", "Enter")
            page.wait_for_timeout(500)
            last_set = page.eval_on_selector_all(".set:last-child li .name", "e => e.map(x => x.textContent.trim())")
            if not (nm in last_set and len(last_set) == 1):
                failures.append(f"end-set offline didn't start a new set; last set={last_set}")

        # --- reconnect ---
        ctx.set_offline(False)
        page.wait_for_timeout(4000)
        pill = page.text_content(".status").strip()
        temps = page.eval_on_selector_all(".set li.pending", "e => e.length")
        log(f"reconnect: pill={pill!r}, temp_rows={temps}, banner={bool(page.query_selector('.offline-banner'))}")
        if pill != "live":
            failures.append(f"after reconnect pill should be 'live', got {pill!r}")
        if temps != 0:
            failures.append("temp rows remained after reconnect")

        if errors:
            failures.append(f"console/page errors: {errors[:6]}")
        ctx.close()

    print("\n" + ("PASS ✅" if not failures else "FAIL ❌\n  - " + "\n  - ".join(failures)))
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
