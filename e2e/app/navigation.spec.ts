import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";
import { openMenu, expectNoServerError } from "../support/nav";

/** Primary navigation: the hamburger menu and find-a-tune. */

test.describe("authenticated navigation", () => {
  test.use({ storageState: STORAGE.regular });

  test("the menu mirrors the tab bar, then what /me's Account section holds", async ({
    page,
  }) => {
    // The tab bar is the phone's navigation and this is the desktop form of it. Both
    // are in the DOM on every page — CSS decides which one you see — so the two can be
    // compared without resizing, which is the point: they are one IA rendered twice.
    await page.goto("/");
    const tabs = await page
      .locator(".tab-bar-item .tab-bar-label")
      .allInnerTexts()
      .then((t) => t.map((s) => s.trim()));
    expect(tabs).toEqual(["Home", "Sessions", "Tunes", "Me"]);

    const menu = await openMenu(page);
    const items = await menu
      .locator(".hamburger-item")
      .allInnerTexts()
      .then((t) => t.map((s) => s.trim()));

    // Home is the logo beside the menu button, so it is the one tab with no row here.
    expect(items.slice(0, 3)).toEqual(tabs.slice(1));
    // ...then the Account section from /me. No Admin: this is the regular user.
    expect(items.slice(3)).toEqual(["Share", "Help", "Log Out"]);
  });

  test("the menu says whose account you are in", async ({ page }) => {
    // /me ends on this line, and the menu is otherwise the only place in the app that
    // never names the account you are signed into.
    await page.goto("/");
    const menu = await openMenu(page);
    await expect(menu.locator(".hamburger-who")).toHaveText(
      /^Signed in as \S+/,
    );
  });

  test("menu navigates to your tunes", async ({ page }) => {
    await page.goto("/");
    const menu = await openMenu(page);
    // "Tunes", as the tab bar calls it — it was "My Tunes" when the menu was its own
    // vocabulary.
    await menu.getByRole("link", { name: /^Tunes$/i }).click();
    await expect(page).toHaveURL(/\/my-tunes/);
    // The page has no heading (spec 052 §B1); its search box is the landmark.
    await expect(page.locator("#search-input")).toBeVisible();
  });

  test("regular user does NOT see the Admin link", async ({ page }) => {
    await page.goto("/");
    const menu = await openMenu(page);
    await expect(menu.getByRole("link", { name: /^Admin$/ })).toHaveCount(0);
  });
});

test.describe("admin navigation", () => {
  test.use({ storageState: STORAGE.admin });

  test("admin user sees the Admin link", async ({ page }) => {
    await page.goto("/");
    const menu = await openMenu(page);
    await expect(menu.getByRole("link", { name: /^Admin$/ })).toBeVisible();
  });
});

test.describe("authenticated home dashboard", () => {
  test.use({ storageState: STORAGE.regular });

  test("home renders the dashboard shell without errors", async ({ page }) => {
    await page.goto("/");
    await expectNoServerError(page);
    await expect(page.locator("button.hamburger-btn")).toBeVisible();
  });
});

test.describe("desktop pages say which one you are on", () => {
  // Both halves, together, because they are one rule. A phone names the current
  // screen in the tab bar along the bottom, so a heading repeating that word cost a
  // line at the top of the smallest screen — which is why these came out. Above
  // 768px there is no tab bar and nothing else says where you are.
  test.use({ storageState: STORAGE.regular });

  const PAGES: [string, string][] = [
    ["/sessions", "Sessions"],
    ["/my-tunes", "Tunes"],
  ];

  test("the title is there on a desktop viewport", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    for (const [url, title] of PAGES) {
      await page.goto(url);
      const h = page.locator(".page-title");
      await expect(h, `${url} should be titled`).toBeVisible();
      await expect(h).toHaveText(title);
    }
  });

  test("...and not on a phone, where the tab bar already says it", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const [url, title] of PAGES) {
      await page.goto(url);
      // Served either way and hidden by CSS, so one response is right at both sizes.
      await expect(page.locator(".page-title")).toHaveCount(1);
      await expect(page.locator(".page-title")).toBeHidden();
      // The tab bar is carrying the name instead.
      await expect(
        page.locator(`.tab-bar-item.active .tab-bar-label`),
      ).toHaveText(title);
    }
  });

  test("it matches the home page's greeting, which is the same thing one page over", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });

    const shape = (sel: string) =>
      page.evaluate((s) => {
        const e = document.querySelector(s)!;
        const cs = getComputedStyle(e);
        const b = e.getBoundingClientRect();
        return {
          x: Math.round(b.x),
          y: Math.round(b.y),
          font: cs.fontFamily.split(",")[0].replace(/["']/g, ""),
          weight: cs.fontWeight,
          size: cs.fontSize,
        };
      }, sel);

    await page.goto("/");
    const greeting = await shape(".home-greeting");

    await page.goto("/sessions");
    const title = await shape(".page-title");

    // Same position on the page, not just the same type: the greeting sits below an
    // inline 1.2rem margin on #home-root, and the heading has to clear the same gap
    // or the two pages start one line apart.
    expect(title).toEqual(greeting);
  });
});
