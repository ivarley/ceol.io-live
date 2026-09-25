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

  test("four tabs, all of which go somewhere", async ({ page }) => {
    await page.goto("/");
    const tabs = page.locator("#tab-bar .tab-bar-item");
    await expect(tabs).toHaveCount(4);
    await expect(tabs.nth(0)).toHaveAttribute("href", "/");
    await expect(tabs.nth(1)).toHaveAttribute("href", "/sessions");
    // The tradition's tunes, not yours: /my-tunes needs an account, /tunes does not.
    await expect(tabs.nth(2)).toHaveAttribute("href", "/tunes");
    await expect(tabs.nth(3)).toHaveAttribute("href", "/about");

    // Every one of them lands on a real page rather than a login wall.
    for (const href of ["/", "/sessions", "/tunes", "/about"]) {
      const res = await page.goto(href);
      expect(res!.status(), `${href} should render for a visitor`).toBe(200);
      expect(page.url(), `${href} should not bounce to login`).not.toContain("/login");
    }
  });

  test("no hamburger anywhere on a phone", async ({ page }) => {
    for (const href of ["/", "/sessions", "/tunes", "/about", "/help"]) {
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

test.describe("the public tunes list", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("lists the most common tunes, most-bookmarked first", async ({ page }) => {
    await page.goto("/tunes");
    const rows = page.locator(".pt-row");
    await expect(rows).toHaveCount(100);

    // Ordered by tunebook count, descending — that is the whole claim of the page.
    const counts = await page.evaluate(() =>
      [...document.querySelectorAll(".pt-row .pt-books")].map((e) =>
        Number((e.textContent || "0").replace(/,/g, ""))
      )
    );
    expect(counts.length).toBeGreaterThan(1);
    const sorted = [...counts].sort((a, b) => b - a);
    expect(counts).toEqual(sorted);
  });

  test("search reaches past the hundred", async ({ page }) => {
    await page.goto("/tunes");
    const onTop = await page.evaluate(() =>
      [...document.querySelectorAll(".pt-name")].map((e) => e.textContent!.trim())
    );

    await page.locator("#pt-search").fill("banish");
    // Poll on the RESULT, not the row count: the list still holds the hundred while
    // the request is in flight, so "more than zero rows" is true before the search
    // has landed and reads the old first row.
    await expect
      .poll(() => page.locator(".pt-name").first().textContent())
      .toMatch(/banish/i);
    const found = (await page.locator(".pt-name").first().textContent())!.trim();
    // ...and it really is beyond the list you were shown.
    expect(onTop).not.toContain(found);

    // Clearing restores the top hundred.
    await page.locator("#pt-search").fill("");
    await expect.poll(() => page.locator(".pt-row").count()).toBe(100);
  });

  test("offers nothing that needs an account", async ({ page }) => {
    await page.goto("/tunes");
    // The tune drawer opens for a visitor — its feed is public — but with no way to
    // add anything to a tunebook they do not have.
    await page.locator(".pt-row").first().click();
    await expect
      .poll(() => page.evaluate(() => /Drowsy Maggie/.test(document.body.innerText)))
      .toBe(true);
    expect(
      await page.evaluate(() => /add to my tunes|add to tunebook/i.test(document.body.innerText))
    ).toBe(false);
  });

  test("the public endpoint carries no personal data, and is not the private one", async ({ request }) => {
    // /api/tunes/popular already existed, is login-gated, and joins person_tune to say
    // which tunes are in YOUR tunebook. This is a different question for a different
    // audience, so it is a different endpoint.
    const pub = await request.get("/api/tunes/top?limit=5");
    expect(pub.status()).toBe(200);
    const body = await pub.json();
    expect(body.success).toBe(true);
    expect(body.tunes.length).toBe(5);
    for (const t of body.tunes) {
      expect(Object.keys(t).sort()).toEqual(["name", "tune_id", "tune_type", "tunebook_count"]);
    }
    expect((await request.get("/api/tunes/popular")).status()).toBe(401);
  });
});
