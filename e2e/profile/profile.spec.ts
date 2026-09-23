import { test, expect } from "@playwright/test";
import { STORAGE } from "../support/data";
import { expectNoServerError } from "../support/nav";

/** User profile (/me) and the add-session wizard. */

test.use({ storageState: STORAGE.regular });

test.describe("profile (/me)", () => {
  test("is one vertical list: details, then sections, then account", async ({ page }) => {
    // Spec 052 §B3. This page used to carry a six-tab strip AND a vertical account
    // list beneath it — two kinds of menu on one screen. The tabs became rows, so
    // everything below your details is the same shape of thing.
    await page.goto("/me");
    await expect(page.locator("h1")).toContainText(/Profile/i);
    await expect(page.locator("#profileTabs")).toHaveCount(0);

    await expect(page.locator("#profile-sections")).toBeVisible();
    await expect(page.locator("#profile-sections .section-row")).toHaveCount(5);
    await expect(page.locator("#account-section")).toBeVisible();
    await expectNoServerError(page);
  });

  test("opening Sessions drills in, and Back returns", async ({ page }) => {
    // Labelled "Sessions", not "My Sessions", since spec 034.
    await page.goto("/me");
    await page.locator("#sessions-tab").click();

    await expect(page.locator("#sessions")).toBeVisible();
    await expect(page).toHaveURL(/\?tab=sessions/);
    // The section has the screen to itself; the list it came from is gone.
    await expect(page.locator("#profile-sections")).toHaveCount(0);

    await page.locator("#section-back").click();
    await expect(page.locator("#profile-sections")).toBeVisible();
    await expect(page).not.toHaveURL(/\?tab=/);
    await expectNoServerError(page);
  });

  test("a ?tab= link still lands on its section", async ({ page }) => {
    // The URLs did not change when the tabs did, so anything already pointing at
    // one of these keeps working.
    await page.goto("/me?tab=tunes");
    await expect(page.locator("#tunes")).toBeVisible();
    await expect(page.locator("#section-back")).toBeVisible();
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
    // Path is NOT in this list: it is generated from name + city, so those are what
    // a person actually has to supply (SessionSheet.svelte).
    await expect(page.locator(".session-sheet-actions .field-error")).toContainText(
      /Name, City, State, Country/
    );
    await expect(page).toHaveURL(/\/add-session/);
    // Escape abandons the sheet and returns to the wizard.
    await page.keyboard.press("Escape");
    await expect(page.locator("#sessionDetailsForm")).not.toBeVisible();
    await expect(page.locator("#sessionUrlForm")).toBeVisible();
  });
});
