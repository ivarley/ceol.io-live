#!/usr/bin/env python3
"""
Row-color policy + away presence (§F refinements):
  - a row is tinted only when logged by SOMEONE ELSE (my own rows stay plain),
  - when a peer disconnects they linger as a DIMMED (away) avatar and their rows stay
    colored (until the 1h server-side away-TTL, not waited on here).

Two browser contexts: sarah logs a linked tune, ian (watching) verifies it's colored
while his own added tune is not; then sarah disconnects and ian sees her go away
(dimmed) with her row still colored. Self-cleaning.

Run: venv/bin/python spike/pw_away.py [PORT] [INST]
"""
import sys
from _dbclean import baseline, cleanup
from playwright.sync_api import sync_playwright

F = f"http://localhost:{sys.argv[1] if len(sys.argv) > 1 else 5055}"
INST = int(sys.argv[2] if len(sys.argv) > 2 else 1)


def login_page(b, email):
    ctx = b.new_context(); pg = ctx.new_page(); pg.set_viewport_size({"width": 460, "height": 880})
    pg.set_default_timeout(10000)
    ctx.request.post(f"{F}/api/auth/login-password", data={"email": email, "password": "password123"})
    pg.goto(f"{F}/live/instances/{INST}"); pg.wait_for_selector(".tune-row", timeout=8000); pg.wait_for_timeout(1200)
    return ctx, pg


def add_linked(pg, q):
    pg.eval_on_selector_all(".end-seam", "els => els[els.length-1].click()")
    pg.eval_on_selector_all(".composer input", "els => els[0].focus()")
    if pg.query_selector(".composer .endset.hot"):
        pg.click(".composer .endset.hot"); pg.wait_for_timeout(700)
    pg.fill(".composer input", q); pg.wait_for_timeout(900)
    pg.eval_on_selector_all(".results li", "els => { const r=els.find(e=>e.querySelector('.r-name') && !e.classList.contains('result-deeper')); r && r.click() }")
    pg.wait_for_timeout(1500)
    return pg.evaluate("()=>{const ss=document.querySelectorAll('.set');const s=ss[ss.length-1];const r=[...s.querySelectorAll('.tune-row')].pop();return r?r.querySelector('.name').textContent.trim():null}")


def last_row(pg):
    # the most-recently-appended tune row (adds go to a fresh set at the end)
    return pg.evaluate("()=>{const rows=document.querySelectorAll('.tune-row');const r=rows[rows.length-1];return r?{name:r.querySelector('.name').textContent.trim(),hasby:r.classList.contains('has-by')}:null}")


def avatars(pg):
    return pg.evaluate("()=>[...document.querySelectorAll('.topbar-presence .avatar')].map(a=>({title:a.getAttribute('title'),away:a.classList.contains('away')}))")


def main():
    fail = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ian_ctx, ian = login_page(b, "ian@ceol.io")
        sarah_ctx, sarah = login_page(b, "sarah.oconnor@example.com")
        ian.wait_for_timeout(800)
        av = avatars(ian)
        print(f"0. ian sees avatars: {av}")
        if len(av) < 2:
            fail.append(f"ian should see 2 present avatars (ian+sarah), got {av}")

        # sarah logs a linked tune -> in ian's view the newest row is sarah's, colored
        t_name = add_linked(sarah, "Silver Spear")
        print(f"1. sarah logged {t_name!r}")
        ian.wait_for_timeout(1500)
        lr = last_row(ian)
        print(f"2. ian's newest row (sarah's): {lr}")
        if not lr or lr["name"] != t_name or lr["hasby"] is not True:
            fail.append(f"a peer's (sarah's) row should be colored in ian's view; got {lr}")

        # sarah disconnects -> ian sees her as AWAY (dimmed); her row stays colored
        sarah_ctx.close()
        ian.wait_for_timeout(2500)
        av2 = avatars(ian)
        print(f"3. after sarah disconnects, ian avatars: {av2}")
        if not any(a["away"] for a in av2):
            fail.append(f"sarah should remain as a dimmed AWAY avatar after disconnect, got {av2}")
        lr2 = last_row(ian)
        print(f"4. sarah's row while away: {lr2}")
        if not lr2 or lr2["hasby"] is not True:
            fail.append(f"an away peer's row should stay colored; got {lr2}")

        # ian logs his OWN linked tune -> newest row is his -> NOT colored
        u_name = add_linked(ian, "Banshee")
        ian.wait_for_timeout(800)
        lr3 = last_row(ian)
        print(f"5. ian's OWN newest row: {lr3}")
        if not lr3 or lr3["name"] != u_name or lr3["hasby"] is not False:
            fail.append(f"my own row should NOT be colored; got {lr3}")

        b.close()
    print("\n" + ("PASS ✅" if not fail else "FAIL ❌\n  - " + "\n  - ".join(fail)))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    base = baseline()
    try:
        main()
    finally:
        cleanup(base)
