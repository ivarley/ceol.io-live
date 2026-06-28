import { test, expect } from "@playwright/test";
import { SESSIONS } from "../support/data";

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
