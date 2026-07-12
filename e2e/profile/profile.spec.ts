import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/** User profile (/me) and the add-session wizard. */

test.use({ storageState: STORAGE.regular });

test.describe("profile (/me)", () => {
  test("renders the profile with tabbed sections", async ({ page }) => {
    await page.goto("/me");
    await expect(page.locator("h1")).toContainText(/Profile/i);
    await expect(page.locator("#profileTabs")).toBeVisible();
    await expectNoServerError(page);
  });

  test("switching to the My Sessions tab works", async ({ page }) => {
    await page.goto("/me");
    // Desktop renders the sections as ARIA tabs (mobile uses a <select>).
    await page.getByRole("tab", { name: /My Sessions/i }).click();
    await expect(page.locator("#sessions")).toBeVisible();
    await expectNoServerError(page);
  });

  test("switching to the Tunes tab works", async ({ page }) => {
    await page.goto("/me");
    await page.getByRole("tab", { name: /^Tunes$/i }).click();
    await expect(page.locator("#tunes")).toBeVisible();
  });

  test("entering edit mode reveals the save control", async ({ page }) => {
    await page.goto("/me");
    await page.getByRole("button", { name: /^Edit$/ }).first().click();
    await expect(page.getByRole("button", { name: /^Save$/ }).first()).toBeVisible();
  });
});

test.describe("add a session", () => {
  test("renders the URL-import wizard", async ({ page }) => {
    await page.goto("/add-session");
    await expect(page.locator("h1")).toContainText(/Add A New Session/i);
    await expect(page.locator("#sessionUrlForm")).toBeVisible();
    await expect(page.locator("#sessionUrl")).toBeVisible();
  });

  test("submitting an empty URL does not crash the page", async ({ page }) => {
    await page.goto("/add-session");
    await page.getByRole("button", { name: /^Next$/ }).click();
    await expectNoServerError(page);
    await expect(page).toHaveURL(/\/add-session/);
  });

  test("the empty-session flow opens the review sheet and validates required fields", async ({ page }) => {
    await page.goto("/add-session");
    await page.getByRole("link", { name: /just add it here/i }).click();
    await expect(page.locator("#sessionDetailsForm")).toBeVisible();
    await expect(page.locator("#sessionName")).toHaveValue("");
    // Saving the empty form surfaces validation instead of creating a row.
    await page.locator("#saveSessionBtn").click();
    await expect(page.locator(".session-sheet-actions .field-error")).toContainText(
      /Name, Path, City, State, Country/
    );
    await expect(page).toHaveURL(/\/add-session/);
    // Escape abandons the sheet and returns to the wizard.
    await page.keyboard.press("Escape");
    await expect(page.locator("#sessionDetailsForm")).not.toBeVisible();
    await expect(page.locator("#sessionUrlForm")).toBeVisible();
  });
});
