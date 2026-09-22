import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";

/**
 * Mobile-viewport subset (Pixel 5 device profile — see playwright.config.ts).
 * The app is mobile-first, so the core journeys get a dedicated small-screen run.
 * Files must be named *.mobile.spec.ts to be picked up by the `mobile` project.
 */

test.use({ storageState: STORAGE.regular });

test("home: the tab bar is the phone navigation, and the hamburger is gone", async ({ page }) => {
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

test("sessions directory is usable on mobile", async ({ page }) => {
  await page.goto("/sessions");
  await expect(page.locator("h1")).toContainText(/Sessions/i);
  await expect(page.locator("#sessions-tbody tr").first()).toBeVisible();
});

test("session detail renders on mobile", async ({ page }) => {
  await page.goto(`/sessions/${SESSIONS.mueller.path}`);
  await expect(page.locator("h1")).toContainText(SESSIONS.mueller.name);
  await expect(page.locator("#tunes-list")).toBeVisible();
});

test("my tunes renders on mobile", async ({ page }) => {
  await page.goto("/my-tunes");
  await expect(page.locator("h1")).toContainText(/My Tunes/i);
  await expect(page.locator("#search-input")).toBeVisible();
});
