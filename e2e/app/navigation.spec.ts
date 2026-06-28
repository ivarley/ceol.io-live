import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";
import { openMenu, expectNoServerError } from "../support/nav";

/** Primary navigation: the hamburger menu, dark-mode toggle, and find-a-tune. */

test.describe("authenticated navigation", () => {
  test.use({ storageState: STORAGE.regular });

  test("hamburger menu exposes the expected destinations", async ({ page }) => {
    await page.goto("/");
    const menu = await openMenu(page);

    for (const label of [/My Tunes/i, /My Sessions/i, /Add A Session/i, /Help/i, /Log Out/i]) {
      await expect(menu.getByRole("link", { name: label })).toBeVisible();
    }
  });

  test("menu navigates to My Tunes", async ({ page }) => {
    await page.goto("/");
    const menu = await openMenu(page);
    await menu.getByRole("link", { name: /^My Tunes$/i }).click();
    await expect(page).toHaveURL(/\/my-tunes/);
    await expect(page.locator("h1")).toContainText(/My Tunes/i);
  });

  test("regular user does NOT see the Admin link", async ({ page }) => {
    await page.goto("/");
    const menu = await openMenu(page);
    await expect(menu.getByRole("link", { name: /^Admin$/ })).toHaveCount(0);
  });

  test("dark mode toggle flips the theme and persists", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    const before = await html.getAttribute("data-theme");

    const menu = await openMenu(page);
    await menu.getByText(/Dark Mode|Light Mode/i).click();

    await expect
      .poll(async () => html.getAttribute("data-theme"))
      .not.toBe(before);

    // Survives a reload (persisted to storage).
    const afterToggle = await html.getAttribute("data-theme");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", afterToggle!);
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
