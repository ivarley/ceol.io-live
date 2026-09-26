import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";

/**
 * Mobile-viewport subset (Pixel 5 device profile — see playwright.config.ts).
 * The app is mobile-first, so the core journeys get a dedicated small-screen run.
 * Files must be named *.mobile.spec.ts to be picked up by the `mobile` project.
 */

test.use({ storageState: STORAGE.regular });

test("home: the tab bar is the phone navigation, and the hamburger is gone", async ({
  page,
}) => {
  // This test used to open the hamburger and look for "My Tunes" in it. Spec 052
  // §B8 Stage 5 replaced that menu with a four-tab bar below 768px, so the
  // assertion is now the replacement rather than the thing replaced. The menu
  // still exists and is still the navigation above 768px — see the desktop check
  // in this file's sibling specs — which is why it is hidden here, not deleted.
  await page.goto("/");
  const bar = page.locator("#tab-bar");
  await expect(bar).toBeVisible();
  await expect(bar.locator(".tab-bar-item")).toHaveCount(4);
  await expect(page.locator(".hamburger-menu")).toBeHidden();
});

test("the fixed header keeps its full height with the hamburger hidden", async ({
  page,
}) => {
  // It did not. The logo is position:absolute and contributes no height, so the bar's
  // height came entirely from the tallest thing in the utilities row — which was the
  // hamburger button. Hiding that for the tab bar collapsed the header to 10px: the
  // logo hung out of the bottom and the page scrolled through behind it.
  //
  // Nothing else would have caught it. Every sticky offset on the session page reads
  // --site-header-h, so they all kept believing 42px while the bar was 10.
  await page.goto("/");
  await expect(page.locator(".hamburger-menu")).toBeHidden();

  const box = await page.evaluate(() => {
    const css = getComputedStyle(document.documentElement).getPropertyValue(
      "--site-header-h",
    );
    const header = document
      .querySelector("header.header")!
      .getBoundingClientRect();
    const logo = document.querySelector(".site-logo")!.getBoundingClientRect();
    return {
      declared: parseFloat(css),
      height: header.height,
      headerBottom: header.bottom,
      logoBottom: logo.bottom,
      bodyPad: parseFloat(getComputedStyle(document.body).paddingTop),
    };
  });

  // The bar is as tall as the variable everything else offsets by.
  expect(box.height).toBeCloseTo(box.declared, 0);
  // The logo sits inside it rather than over the page behind.
  expect(box.logoBottom).toBeLessThanOrEqual(box.headerBottom + 0.5);
  // And the page starts below the bar, not 2px under it.
  expect(box.bodyPad).toBeCloseTo(box.declared, 0);
});

test("sessions directory is usable on mobile", async ({ page }) => {
  await page.goto("/sessions");
  // The list itself is the page. The heading is served (one response is right at
  // both sizes) but hidden here, because the tab bar already names this screen.
  await expect(page.locator("h1.page-title")).toBeHidden();
  await expect(
    page.locator("#sessions-list .session-row").first(),
  ).toBeVisible();
});

test("session detail renders on mobile", async ({ page }) => {
  await page.goto(`/sessions/${SESSIONS.mueller.path}`);
  await expect(page.locator("h1")).toContainText(SESSIONS.mueller.name);
  await expect(page.locator("#tunes-list")).toBeVisible();
});

test("my tunes renders on mobile", async ({ page }) => {
  await page.goto("/my-tunes");
  await expect(page.locator("h1.page-title")).toBeHidden();
  await expect(page.locator("#search-input")).toBeVisible();
});
