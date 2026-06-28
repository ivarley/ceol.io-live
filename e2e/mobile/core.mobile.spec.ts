import { test, expect } from "@playwright/test";
import { SESSIONS, STORAGE } from "../support/data";
import { openMenu } from "../support/nav";

/**
 * Mobile-viewport subset (Pixel 5 device profile — see playwright.config.ts).
 * The app is mobile-first, so the core journeys get a dedicated small-screen run.
 * Files must be named *.mobile.spec.ts to be picked up by the `mobile` project.
 */

test.use({ storageState: STORAGE.regular });

test("home: hamburger menu opens on mobile", async ({ page }) => {
  await page.goto("/");
  const menu = await openMenu(page);
  await expect(menu.getByRole("link", { name: /My Tunes/i })).toBeVisible();
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
