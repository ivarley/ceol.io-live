import { test, expect } from "@playwright/test";

/**
 * The signed-out phone IA (spec 052 §B17).
 *
 * A signed-out visitor used to get the hamburger and no tab bar, because /my-tunes
 * and /me both bounce to login and a four-tab bar would have been two tabs and two
 * rejections. They get three tabs that all work instead, and the hamburger is gone
 * from phones entirely.
 */

test.describe("signed out, on a phone", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("three tabs, all of which go somewhere", async ({ page }) => {
    await page.goto("/");
    const tabs = page.locator("#tab-bar .tab-bar-item");
    await expect(tabs).toHaveCount(3);
    await expect(tabs.nth(0)).toHaveAttribute("href", "/");
    await expect(tabs.nth(1)).toHaveAttribute("href", "/sessions");
    await expect(tabs.nth(2)).toHaveAttribute("href", "/about");

    // Every one of them lands on a real page rather than a login wall.
    for (const href of ["/", "/sessions", "/about"]) {
      const res = await page.goto(href);
      expect(res!.status(), `${href} should render for a visitor`).toBe(200);
      expect(page.url(), `${href} should not bounce to login`).not.toContain("/login");
    }
  });

  test("no hamburger anywhere on a phone", async ({ page }) => {
    for (const href of ["/", "/sessions", "/about", "/help"]) {
      await page.goto(href);
      const ham = page.locator(".hamburger-menu");
      if (await ham.count()) {
        await expect(ham, `hamburger still showing on ${href}`).not.toBeVisible();
      }
    }
  });

  test("About carries what the signed-out menu carried", async ({ page }) => {
    await page.goto("/about");
    await expect(page.locator("#about-login")).toHaveAttribute("href", "/login");
    await expect(page.locator("#about-help")).toHaveAttribute("href", "/help");
    // Share is a header control, so it does not need a row here.
    await expect(page.locator("#share-btn")).toBeVisible();
  });

  test("signed in, About offers the profile instead of the login page", async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: "e2e/.auth/admin.json" });
    const page = await ctx.newPage();
    await page.goto("/about");
    await expect(page.locator("#about-me")).toHaveAttribute("href", "/me");
    await expect(page.locator("#about-login")).toHaveCount(0);
    // and the signed-in bar is still four tabs
    await expect(page.locator("#tab-bar .tab-bar-item")).toHaveCount(4);
    await ctx.close();
  });
});

test.describe("tunes in common", () => {
  test.use({ storageState: "e2e/.auth/admin.json" });

  test("offers a named way back, and only to a session that exists", async ({ page }) => {
    // Was `javascript:history.back()`, which has nothing to go back to when the URL
    // came from a link — and the app is display:standalone, so an installed visitor
    // has no browser Back either.
    await page.goto("/me/and/2?from=austin/mueller");
    const back = page.locator("#ct-back");
    await expect(back).toHaveAttribute("href", "/sessions/austin/mueller");
    await expect(back).toContainText("Mueller Session");

    // Only a real session path yields a row: no origin, a bogus one, or an attempt
    // at traversal all render the page with no row rather than a broken link.
    for (const q of ["", "?from=nope/nope", "?from=../../etc", "?from=/etc/passwd"]) {
      const res = await page.goto(`/me/and/2${q}`);
      expect(res!.status()).toBe(200);
      await expect(page.locator("#ct-back")).toHaveCount(0);
    }
  });
});
