import { test, expect } from "@playwright/test";
import { NOTATION, SESSIONS } from "../support/data";

/**
 * Logged-out smoke tests: every public page returns 200 and renders its shell.
 * No authentication — these run as an anonymous visitor.
 */

test.describe("public pages load", () => {
  const pages: Array<{ name: string; url: string; expect: RegExp }> = [
    { name: "home", url: "/", expect: /session/i },
    { name: "sessions list", url: "/sessions", expect: /session/i },
    { name: "session detail", url: `/sessions/${SESSIONS.mueller.path}`, expect: /Mueller/i },
    { name: "login", url: "/login", expect: /log in|login/i },
    { name: "register", url: "/register", expect: /register|sign up|create/i },
    { name: "help", url: "/help", expect: /help/i },
    { name: "help sessions", url: "/help/sessions", expect: /session/i },
    { name: "help my-tunes", url: "/help/my-tunes", expect: /tune/i },
    { name: "share", url: "/share", expect: /./ },
  ];

  for (const p of pages) {
    test(`${p.name} renders`, async ({ page }) => {
      const res = await page.goto(p.url);
      expect(res?.status(), `${p.url} status`).toBeLessThan(400);
      await expect(page.locator("body")).toContainText(p.expect);
      // No server-rendered error page.
      await expect(page.locator("body")).not.toContainText(/Internal Server Error|Traceback/i);
    });
  }
});

/**
 * Notation search on a PUBLIC page. The session Tunes tab filters a list the page already
 * holds, and notation matching for it is a server round trip — so POST /api/tunes/abc-filter
 * is @public_api on purpose. If it ever gains an auth decorator, the filter silently stops
 * matching notes for logged-out visitors, which is exactly the kind of failure nobody
 * reports. This pins it.
 */
test.describe("notation search (logged out)", () => {
  test("a session's Tunes tab narrows by notation for an anonymous visitor", async ({ page }) => {
    await page.goto(`/sessions/${SESSIONS.mueller.path}/tunes`);
    const search = page.locator("#tune-search");
    await expect(search).toBeVisible();

    await search.fill(NOTATION.phrase);
    const rows = page.locator(".tune-name");
    await expect(rows).toHaveCount(1, { timeout: 8000 });
    await expect(rows.first()).toContainText(NOTATION.tune.name);
  });

  test("the notation filter endpoint answers an anonymous caller", async ({ request }) => {
    const res = await request.post("/api/tunes/abc-filter", {
      data: { q: NOTATION.phrase, tune_ids: [NOTATION.tune.id, 27, 55] },
    });
    expect(res.status()).toBe(200);
    expect((await res.json()).tune_ids).toEqual([NOTATION.tune.id]);
  });
});

test.describe("auth gating", () => {
  test("protected page redirects anonymous user to login", async ({ page }) => {
    await page.goto("/my-tunes");
    await expect(page).toHaveURL(/\/login\?next=%2Fmy-tunes/);
  });

  test("admin area redirects anonymous user away", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).not.toHaveURL(/\/admin$/);
  });
});
